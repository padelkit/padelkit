# ruff: noqa: E501
"""3D CAD Scene-Graph & Optical Projection SVG Schematic Engine for PadelKit Docs.

Uses a true 3D scene-graph renderer (`Scene3D`, `Face3D`, `Segment3D`) backed by
`padelkit.camera.Camera` (`K`, `R|t`, `CameraDistortion`), depth-sorted painter's
algorithm, automatic 3D-to-viewport bounding-box fitting, and SVG `<clipPath>`
isolation to generate publication-grade technical schematics.

Outputs deterministic `-light.svg` and `-dark.svg` pairs into `docs/images/schematics/`.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np

from padelkit.camera import (
    Camera,
    CameraDistortion,
    CameraExtrinsics,
    CameraIntrinsics,
)
from padelkit.court import CoordinateSystem, Court, CourtLandmark
from padelkit.physics import (
    BallPhysicsEngine,
    BallProperties,
    BallState,
    SurfaceMaterials,
)
from padelkit.scoring import MatchConfiguration, Player, ServingEngine, Team, TeamId


@dataclass(frozen=True)
class ThemePalette:
    """Color tokens for light and dark SVG schematic themes."""

    mode: Literal["light", "dark"]
    bg_canvas: str
    bg_panel: str
    border: str
    grid_line: str
    court_floor: str
    court_line_fg: str
    court_line_bg: str
    glass_fill: str
    glass_stroke: str
    fence_fill: str
    fence_stroke: str
    pillar_stroke: str
    text_primary: str
    text_muted: str
    badge_bg: str
    accent_primary: str
    accent_secondary: str
    accent_tertiary: str
    accent_danger: str


LIGHT_PALETTE = ThemePalette(
    mode="light",
    bg_canvas="#f8fafc",
    bg_panel="#ffffff",
    border="#cbd5e1",
    grid_line="#e2e8f0",
    court_floor="#e2e8f0",
    court_line_fg="#0f172a",
    court_line_bg="#64748b",
    glass_fill="#bae6fd",
    glass_stroke="#0284c7",
    fence_fill="#f1f5f9",
    fence_stroke="#64748b",
    pillar_stroke="#334155",
    text_primary="#09090b",
    text_muted="#475569",
    badge_bg="#ffffff",
    accent_primary="#059669",
    accent_secondary="#0284c7",
    accent_tertiary="#d97706",
    accent_danger="#e11d48",
)

DARK_PALETTE = ThemePalette(
    mode="dark",
    bg_canvas="#090d16",
    bg_panel="#0f172a",
    border="#1e293b",
    grid_line="#1e293b",
    court_floor="#111c2d",
    court_line_fg="#f8fafc",
    court_line_bg="#64748b",
    glass_fill="#0ea5e9",
    glass_stroke="#38bdf8",
    fence_fill="#1e293b",
    fence_stroke="#94a3b8",
    pillar_stroke="#cbd5e1",
    text_primary="#f4f4f5",
    text_muted="#94a3b8",
    badge_bg="#090d16",
    accent_primary="#34d399",
    accent_secondary="#38bdf8",
    accent_tertiary="#fbbf24",
    accent_danger="#fb7185",
)

FONT_SANS = "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif"
FONT_MONO = "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace"


def _fmt(val: float) -> str:
    """Format a float to 1 decimal place while rejecting NaN or infinite values."""
    fval = float(val)
    if not math.isfinite(fval):
        raise ValueError(f"Non-finite coordinate in SVG schematic: {val}")
    if abs(fval) < 1e-4:
        fval = 0.0
    if abs(fval - round(fval)) < 1e-3:
        return f"{int(round(fval))}"
    return f"{fval:.1f}"


class SvgCanvas:
    """Declarative XML builder for clean, deterministic SVG technical diagrams."""

    def __init__(
        self,
        width: int,
        height: int,
        title: str,
        desc: str,
        palette: ThemePalette,
    ) -> None:
        self.width = width
        self.height = height
        self.palette = palette
        self.root = ET.Element(
            "svg",
            {
                "xmlns": "http://www.w3.org/2000/svg",
                "viewBox": f"0 0 {width} {height}",
                "width": "100%",
                "height": "auto",
                "role": "img",
            },
        )
        title_el = ET.SubElement(self.root, "title")
        title_el.text = title
        desc_el = ET.SubElement(self.root, "desc")
        desc_el.text = desc
        self.defs = ET.SubElement(self.root, "defs")
        self._target: ET.Element = self.root
        self._register_markers()
        self.rect(
            0,
            0,
            width,
            height,
            fill=palette.bg_canvas,
            stroke=palette.border,
            stroke_width=1.5,
            rx=14,
        )

    def _register_markers(self) -> None:
        colors = {
            "fg": self.palette.court_line_fg,
            "muted": self.palette.text_muted,
            "primary": self.palette.accent_primary,
            "secondary": self.palette.accent_secondary,
            "tertiary": self.palette.accent_tertiary,
            "danger": self.palette.accent_danger,
        }
        for key, color in colors.items():
            marker = ET.SubElement(
                self.defs,
                "marker",
                {
                    "id": f"arrow-{key}",
                    "viewBox": "0 0 10 10",
                    "refX": "8",
                    "refY": "5",
                    "markerWidth": "5.5",
                    "markerHeight": "5.5",
                    "orient": "auto-start-reverse",
                },
            )
            ET.SubElement(
                marker,
                "path",
                {"d": "M 0 1.5 L 9 5 L 0 8.5 z", "fill": color},
            )

    def clip_group(
        self,
        clip_id: str,
        x: float,
        y: float,
        w: float,
        h: float,
        rx: float = 0.0,
    ) -> ET.Element:
        """Create a `<clipPath>` in `<defs>` and return a `<g clip-path="url(#...)">`."""
        cp = ET.SubElement(self.defs, "clipPath", {"id": clip_id})
        attrs = {"x": _fmt(x), "y": _fmt(y), "width": _fmt(w), "height": _fmt(h)}
        if rx > 0:
            attrs["rx"] = _fmt(rx)
        ET.SubElement(cp, "rect", attrs)
        return ET.SubElement(self.root, "g", {"clip-path": f"url(#{clip_id})"})

    def radial_gradient(
        self,
        grad_id: str,
        stops: Sequence[tuple[str, str]],
        *,
        cx: str = "35%",
        cy: str = "35%",
        r: str = "65%",
    ) -> None:
        """Register a `<radialGradient>` in `<defs>`."""
        rg = ET.SubElement(
            self.defs,
            "radialGradient",
            {"id": grad_id, "cx": cx, "cy": cy, "r": r},
        )
        for offset_pct, stop_color in stops:
            ET.SubElement(
                rg,
                "stop",
                {"offset": offset_pct, "stop-color": stop_color},
            )

    def set_target(self, target: ET.Element | None = None) -> None:
        """Set the active parent XML element (`None` resets to root `<svg>`)."""
        self._target = target if target is not None else self.root

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill: str = "none",
        stroke: str = "none",
        stroke_width: float = 1.0,
        rx: float = 0.0,
        opacity: float = 1.0,
        dash: str | None = None,
    ) -> ET.Element:
        attrs = {
            "x": _fmt(x),
            "y": _fmt(y),
            "width": _fmt(w),
            "height": _fmt(h),
            "fill": fill,
            "stroke": stroke,
            "stroke-width": _fmt(stroke_width),
        }
        if rx > 0:
            attrs["rx"] = _fmt(rx)
        if opacity < 1.0:
            attrs["opacity"] = _fmt(opacity)
        if dash:
            attrs["stroke-dasharray"] = dash
        return ET.SubElement(self._target, "rect", attrs)

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        stroke: str,
        stroke_width: float = 1.5,
        dash: str | None = None,
        opacity: float = 1.0,
        marker_start: str | None = None,
        marker_end: str | None = None,
    ) -> ET.Element:
        attrs = {
            "x1": _fmt(x1),
            "y1": _fmt(y1),
            "x2": _fmt(x2),
            "y2": _fmt(y2),
            "stroke": stroke,
            "stroke-width": _fmt(stroke_width),
            "stroke-linecap": "round",
        }
        if dash:
            attrs["stroke-dasharray"] = dash
        if opacity < 1.0:
            attrs["opacity"] = _fmt(opacity)
        if marker_start:
            attrs["marker-start"] = f"url(#{marker_start})"
        if marker_end:
            attrs["marker-end"] = f"url(#{marker_end})"
        return ET.SubElement(self._target, "line", attrs)

    def polyline(
        self,
        points: Sequence[tuple[float, float]] | np.ndarray,
        *,
        stroke: str,
        stroke_width: float = 1.5,
        fill: str = "none",
        dash: str | None = None,
        opacity: float = 1.0,
        marker_end: str | None = None,
    ) -> ET.Element:
        pts_str = " ".join(f"{_fmt(p[0])},{_fmt(p[1])}" for p in points)
        attrs = {
            "points": pts_str,
            "fill": fill,
            "stroke": stroke,
            "stroke-width": _fmt(stroke_width),
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
        }
        if dash:
            attrs["stroke-dasharray"] = dash
        if opacity < 1.0:
            attrs["opacity"] = _fmt(opacity)
        if marker_end:
            attrs["marker-end"] = f"url(#{marker_end})"
        return ET.SubElement(self._target, "polyline", attrs)

    def polygon(
        self,
        points: Sequence[tuple[float, float]] | np.ndarray,
        *,
        fill: str = "none",
        stroke: str = "none",
        stroke_width: float = 1.0,
        fill_opacity: float = 1.0,
        stroke_opacity: float = 1.0,
        dash: str | None = None,
    ) -> ET.Element:
        pts_str = " ".join(f"{_fmt(p[0])},{_fmt(p[1])}" for p in points)
        attrs = {
            "points": pts_str,
            "fill": fill,
            "stroke": stroke,
            "stroke-width": _fmt(stroke_width),
            "stroke-linejoin": "round",
        }
        if fill_opacity < 1.0:
            attrs["fill-opacity"] = _fmt(fill_opacity)
        if stroke_opacity < 1.0:
            attrs["stroke-opacity"] = _fmt(stroke_opacity)
        if dash:
            attrs["stroke-dasharray"] = dash
        return ET.SubElement(self._target, "polygon", attrs)

    def circle(
        self,
        cx: float,
        cy: float,
        r: float,
        *,
        fill: str,
        stroke: str = "none",
        stroke_width: float = 1.5,
        opacity: float = 1.0,
    ) -> ET.Element:
        attrs = {
            "cx": _fmt(cx),
            "cy": _fmt(cy),
            "r": _fmt(r),
            "fill": fill,
            "stroke": stroke,
            "stroke-width": _fmt(stroke_width),
        }
        if opacity < 1.0:
            attrs["opacity"] = _fmt(opacity)
        return ET.SubElement(self._target, "circle", attrs)

    def path(
        self,
        d: str,
        *,
        stroke: str,
        stroke_width: float = 1.5,
        fill: str = "none",
        dash: str | None = None,
        opacity: float = 1.0,
        marker_end: str | None = None,
    ) -> ET.Element:
        attrs = {
            "d": d,
            "fill": fill,
            "stroke": stroke,
            "stroke-width": _fmt(stroke_width),
            "stroke-linecap": "round",
            "stroke-linejoin": "round",
        }
        if dash:
            attrs["stroke-dasharray"] = dash
        if opacity < 1.0:
            attrs["opacity"] = _fmt(opacity)
        if marker_end:
            attrs["marker-end"] = f"url(#{marker_end})"
        return ET.SubElement(self._target, "path", attrs)

    def text(
        self,
        x: float,
        y: float,
        content: str,
        *,
        fill: str | None = None,
        size: float = 12.0,
        weight: str = "500",
        mono: bool = False,
        anchor: Literal["start", "middle", "end"] = "middle",
        baseline: str = "middle",
    ) -> ET.Element:
        attrs = {
            "x": _fmt(x),
            "y": _fmt(y),
            "fill": fill or self.palette.text_primary,
            "font-family": FONT_MONO if mono else FONT_SANS,
            "font-size": _fmt(size),
            "font-weight": weight,
            "text-anchor": anchor,
            "dominant-baseline": baseline,
        }
        el = ET.SubElement(self._target, "text", attrs)
        el.text = content
        return el

    def header(self, title: str, subtitle: str) -> None:
        self.text(
            28,
            27,
            title,
            fill=self.palette.text_primary,
            size=15,
            weight="700",
            anchor="start",
        )
        self.text(
            28,
            47,
            subtitle,
            fill=self.palette.text_muted,
            size=11.0,
            weight="400",
            mono=True,
            anchor="start",
        )

    def dimension_arrow(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        label: str,
        *,
        marker_key: str = "tertiary",
        color: str | None = None,
        label_offset: tuple[float, float] = (0.0, 0.0),
        bidirectional: bool = True,
    ) -> None:
        stroke_color = color or self.palette.accent_tertiary
        self.line(
            x1,
            y1,
            x2,
            y2,
            stroke=stroke_color,
            stroke_width=1.5,
            marker_start=f"arrow-{marker_key}" if bidirectional else None,
            marker_end=f"arrow-{marker_key}",
        )
        mx = 0.5 * (x1 + x2) + label_offset[0]
        my = 0.5 * (y1 + y2) + label_offset[1]
        tw = max(len(label) * 6.5 + 10.0, 32.0)
        self.rect(
            mx - tw / 2,
            my - 9,
            tw,
            18,
            fill=self.palette.bg_panel,
            stroke=stroke_color,
            stroke_width=1.0,
            rx=4,
        )
        self.text(
            mx,
            my + 0.5,
            label,
            fill=stroke_color,
            size=10.0,
            weight="700",
            mono=True,
        )

    def callout_badge(
        self,
        x: float,
        y: float,
        badge_text: str,
        *,
        color: str,
        label: str | None = None,
        offset: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        bx = x + offset[0]
        by = y + offset[1]
        if abs(offset[0]) > 2.0 or abs(offset[1]) > 2.0:
            self.line(
                x,
                y,
                bx,
                by,
                stroke=color,
                stroke_width=1.1,
                dash="2 2",
                opacity=0.85,
            )
            self.circle(x, y, 3.2, fill=color, stroke=self.palette.bg_panel)
        bw = max(len(badge_text) * 6.4 + 10.0, 19.0)
        self.rect(
            bx - bw / 2,
            by - 9.0,
            bw,
            18.0,
            fill=self.palette.badge_bg,
            stroke=color,
            stroke_width=1.4,
            rx=9.0,
        )
        self.text(
            bx,
            by + 0.5,
            badge_text,
            fill=color,
            size=9.8,
            weight="700",
            mono=True,
        )
        if label:
            anchor: Literal["start", "end"] = "start" if offset[0] >= 0 else "end"
            lx = bx + (bw / 2 + 5 if offset[0] >= 0 else -bw / 2 - 5)
            self.text(
                lx,
                by + 0.5,
                label,
                fill=self.palette.text_primary,
                size=9.8,
                weight="600",
                mono=True,
                anchor=anchor,
            )

    def to_xml_string(self) -> str:
        ET.indent(self.root, space="  ")
        xml_bytes = ET.tostring(self.root, encoding="unicode")
        return xml_bytes + "\n"


# --------------------------------------------------------------------------- #
# True 3D CAD Scene-Graph & Depth-Sorted Optical Renderer
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Face3D:
    """3D planar polygon with material styling for depth-sorted Painter's rendering."""

    vertices: np.ndarray  # (N, 3)
    fill: str
    fill_opacity: float = 0.20
    stroke: str = "none"
    stroke_width: float = 1.0
    stroke_opacity: float = 1.0
    dash: str | None = None
    layer_bias: float = 0.0  # Positive bias pushes further back in Painter's sort


@dataclass(frozen=True)
class Segment3D:
    """3D line/polyline segment with material styling and depth-sort support."""

    points: np.ndarray  # (N, 3)
    stroke: str
    stroke_width: float = 1.4
    opacity: float = 1.0
    dash: str | None = None
    subdivide: int = 1
    layer_bias: float = 0.0


@dataclass
class Scene3D:
    """3D CAD scene graph holding faces and line segments for projective rendering."""

    faces: list[Face3D] = field(default_factory=list)
    segments: list[Segment3D] = field(default_factory=list)

    def add_face(
        self,
        vertices: Sequence[Sequence[float]] | np.ndarray,
        *,
        fill: str,
        fill_opacity: float = 0.20,
        stroke: str = "none",
        stroke_width: float = 1.0,
        stroke_opacity: float = 1.0,
        dash: str | None = None,
        layer_bias: float = 0.0,
    ) -> None:
        self.faces.append(
            Face3D(
                vertices=np.asarray(vertices, dtype=np.float64),
                fill=fill,
                fill_opacity=fill_opacity,
                stroke=stroke,
                stroke_width=stroke_width,
                stroke_opacity=stroke_opacity,
                dash=dash,
                layer_bias=layer_bias,
            )
        )

    def add_segment(
        self,
        p1: Sequence[float],
        p2: Sequence[float],
        *,
        stroke: str,
        stroke_width: float = 1.4,
        opacity: float = 1.0,
        dash: str | None = None,
        subdivide: int = 1,
        layer_bias: float = 0.0,
    ) -> None:
        self.segments.append(
            Segment3D(
                points=np.asarray([p1, p2], dtype=np.float64),
                stroke=stroke,
                stroke_width=stroke_width,
                opacity=opacity,
                dash=dash,
                subdivide=subdivide,
                layer_bias=layer_bias,
            )
        )

    def all_vertices(self) -> np.ndarray:
        """Return all 3D vertices across faces and segments for auto-fitting."""
        chunks: list[np.ndarray] = [f.vertices for f in self.faces]
        chunks.extend(s.points for s in self.segments)
        return np.vstack(chunks) if chunks else np.zeros((0, 3), dtype=np.float64)


class ViewportProjector3D:
    """Projects 3D world coordinates through `padelkit.camera.Camera` and auto-fits to a 2D SVG rectangle."""

    def __init__(
        self,
        camera: Camera,
        fit_points_3d: np.ndarray,
        rect_x: float,
        rect_y: float,
        rect_w: float,
        rect_h: float,
        padding_px: float = 36.0,
        shift_uv: tuple[float, float] = (0.0, 0.0),
    ) -> None:
        self.camera = camera
        uv, _ = camera.project_points(np.asarray(fit_points_3d, dtype=np.float64))
        u_min, v_min = float(np.min(uv[:, 0])), float(np.min(uv[:, 1]))
        u_max, v_max = float(np.max(uv[:, 0])), float(np.max(uv[:, 1]))
        span_u = max(u_max - u_min, 1e-6)
        span_v = max(v_max - v_min, 1e-6)

        avail_w = max(rect_w - 2.0 * padding_px, 10.0)
        avail_h = max(rect_h - 2.0 * padding_px, 10.0)
        self.scale = min(avail_w / span_u, avail_h / span_v)
        self.u_center = 0.5 * (u_min + u_max)
        self.v_center = 0.5 * (v_min + v_max)
        self.cx = rect_x + 0.5 * rect_w + shift_uv[0]
        self.cy = rect_y + 0.5 * rect_h + shift_uv[1]

    def project_point(self, xyz: Sequence[float] | np.ndarray) -> tuple[float, float]:
        uv, _ = self.camera.project_points(np.asarray([xyz], dtype=np.float64))
        u = self.cx + (float(uv[0, 0]) - self.u_center) * self.scale
        v = self.cy + (float(uv[0, 1]) - self.v_center) * self.scale
        return u, v

    def project_points(self, pts_3d: np.ndarray) -> np.ndarray:
        uv, _ = self.camera.project_points(np.asarray(pts_3d, dtype=np.float64))
        out = np.empty_like(uv)
        out[:, 0] = self.cx + (uv[:, 0] - self.u_center) * self.scale
        out[:, 1] = self.cy + (uv[:, 1] - self.v_center) * self.scale
        return out

    def camera_depth(self, pts_3d: np.ndarray) -> float:
        """Compute mean Z_cam depth in OpenCV camera coordinates for Painter's sorting."""
        r_mat = self.camera.extrinsics.R
        t_vec = self.camera.extrinsics.t
        pts_cam = (r_mat @ pts_3d.T).T + t_vec
        return float(np.mean(pts_cam[:, 2]))

    def render_scene(self, svg: SvgCanvas, scene: Scene3D) -> None:
        """Render all 3D faces and segments sorted back-to-front by camera depth."""
        draw_ables: list[tuple[float, Literal["face", "seg"], Face3D | Segment3D]] = []
        for f in scene.faces:
            z_depth = self.camera_depth(f.vertices) + f.layer_bias
            draw_ables.append((z_depth, "face", f))
        for s in scene.segments:
            z_depth = self.camera_depth(s.points) + s.layer_bias
            draw_ables.append((z_depth, "seg", s))

        # Painter's algorithm: largest Z_cam (furthest from camera) drawn first
        draw_ables.sort(key=lambda item: item[0], reverse=True)

        for _, kind, obj in draw_ables:
            if kind == "face":
                assert isinstance(obj, Face3D)
                uv = self.project_points(obj.vertices)
                svg.polygon(
                    uv,
                    fill=obj.fill,
                    fill_opacity=obj.fill_opacity,
                    stroke=obj.stroke,
                    stroke_width=obj.stroke_width,
                    stroke_opacity=obj.stroke_opacity,
                    dash=obj.dash,
                )
            else:
                assert isinstance(obj, Segment3D)
                if obj.subdivide <= 1 and obj.points.shape[0] == 2:
                    u1, v1 = self.project_point(obj.points[0])
                    u2, v2 = self.project_point(obj.points[1])
                    svg.line(
                        u1,
                        v1,
                        u2,
                        v2,
                        stroke=obj.stroke,
                        stroke_width=obj.stroke_width,
                        opacity=obj.opacity,
                        dash=obj.dash,
                    )
                else:
                    uv = self.project_points(obj.points)
                    svg.polyline(
                        uv,
                        stroke=obj.stroke,
                        stroke_width=obj.stroke_width,
                        opacity=obj.opacity,
                        dash=obj.dash,
                    )


def build_fip_court_3d_scene(
    palette: ThemePalette,
    *,
    include_walls: bool = True,
    include_panel_divisions: bool = True,
) -> Scene3D:
    """Build the authentic 3D FIP court CAD model matching `src/padelkit/viz/template.py`.

    Includes:
    - Floor surface (`20m x 10m`), baselines, sidelines, service lines (`Y = ±7m`), and center service line.
    - Back walls (`Y = ±10m`): 5 modules of `2m` width (`X = -5, -3, -1, 1, 3, 5`), tempered glass (`Z = 0..3m`) + metallic mesh (`Z = 3..4m`).
    - Side walls (`X = ±5m`): stepped corner module (`|Y| in [8, 10]`, `3m` glass + `1m` mesh = `4m`), second module (`|Y| in [6, 8]`, `2m` glass + `1m` mesh = `3m`), metallic mesh panels (`|Y| in [1, 6]`, `Z = 0..3m`), and central `2m` doorway opening (`Y in [-1, 1]`).
    - 3D Net (`Y = 0`): net posts (`Z = 0..0.92m`), catenary top tape (`0.92m` at posts sagging to `0.88m` at center), center vertical strap, and vertical net mesh lines.
    """
    scene = Scene3D()

    # 1. Court floor base (bias +100 so floor always renders underneath court lines and walls)
    scene.add_face(
        [(-5.0, -10.0, 0.0), (5.0, -10.0, 0.0), (5.0, 10.0, 0.0), (-5.0, 10.0, 0.0)],
        fill=palette.court_floor,
        fill_opacity=1.0,
        stroke=palette.court_line_fg,
        stroke_width=1.8,
        layer_bias=100.0,
    )

    # Floor court markings (bias +50 keeps markings strictly above floor & below 3D walls/net)
    for p1, p2 in [
        ((-5.0, -7.0, 0.0), (5.0, -7.0, 0.0)),
        ((-5.0, 7.0, 0.0), (5.0, 7.0, 0.0)),
        ((0.0, -7.0, 0.0), (0.0, 7.0, 0.0)),
        ((-5.0, 0.0, 0.0), (5.0, 0.0, 0.0)),
    ]:
        scene.add_segment(
            p1,
            p2,
            stroke=palette.court_line_fg,
            stroke_width=1.4,
            opacity=0.90,
            layer_bias=50.0,
        )

    # 2. 3D Net at Y = 0 (posts 0.92m, center 0.88m catenary)
    xs_net = np.linspace(-5.0, 5.0, 11)
    top_net = [(float(x), 0.0, 0.88 + 0.04 * ((float(x) / 5.0) ** 2)) for x in xs_net]
    net_poly = [(-5.0, 0.0, 0.0), (5.0, 0.0, 0.0), *reversed(top_net)]
    scene.add_face(
        net_poly,
        fill=palette.accent_secondary,
        fill_opacity=0.16,
        stroke=palette.accent_secondary,
        stroke_width=1.5,
    )
    # Net top white tape and center strap
    scene.segments.append(
        Segment3D(
            points=np.asarray(top_net, dtype=np.float64),
            stroke=palette.court_line_fg,
            stroke_width=2.0,
        )
    )
    scene.add_segment(
        (0.0, 0.0, 0.0),
        (0.0, 0.0, 0.88),
        stroke=palette.court_line_fg,
        stroke_width=1.6,
    )
    for x_post in (-5.0, 5.0):
        scene.add_segment(
            (x_post, 0.0, 0.0),
            (x_post, 0.0, 0.92),
            stroke=palette.pillar_stroke,
            stroke_width=2.2,
        )
    if include_panel_divisions:
        for x_m in (-4.0, -3.0, -2.0, -1.0, 1.0, 2.0, 3.0, 4.0):
            z_top = 0.88 + 0.04 * ((x_m / 5.0) ** 2)
            scene.add_segment(
                (x_m, 0.0, 0.0),
                (x_m, 0.0, z_top),
                stroke=palette.accent_secondary,
                stroke_width=0.7,
                opacity=0.45,
            )

    if not include_walls:
        return scene

    # 3. Back Walls at Y = -10.0m and Y = +10.0m (5 panels of 2.0m width: 3.0m glass + 1.0m metallic mesh)
    for y_back in (-10.0, 10.0):
        # Tempered Glass Band (Z = 0..3m)
        scene.add_face(
            [
                (-5.0, y_back, 0.0),
                (5.0, y_back, 0.0),
                (5.0, y_back, 3.0),
                (-5.0, y_back, 3.0),
            ],
            fill=palette.glass_fill,
            fill_opacity=0.14,
            stroke=palette.glass_stroke,
            stroke_width=1.4,
        )
        # Upper Metallic Mesh Band (Z = 3..4m)
        scene.add_face(
            [
                (-5.0, y_back, 3.0),
                (5.0, y_back, 3.0),
                (5.0, y_back, 4.0),
                (-5.0, y_back, 4.0),
            ],
            fill=palette.fence_fill,
            fill_opacity=0.12,
            stroke=palette.fence_stroke,
            stroke_width=1.2,
            dash="4 3",
        )
        if include_panel_divisions:
            for x_div in (-3.0, -1.0, 1.0, 3.0):
                scene.add_segment(
                    (x_div, y_back, 0.0),
                    (x_div, y_back, 3.0),
                    stroke=palette.glass_stroke,
                    stroke_width=0.9,
                    opacity=0.65,
                )
                scene.add_segment(
                    (x_div, y_back, 3.0),
                    (x_div, y_back, 4.0),
                    stroke=palette.fence_stroke,
                    stroke_width=0.9,
                    opacity=0.65,
                    dash="3 3",
                )

    # 4. Stepped Side Walls at X = -5.0m and X = +5.0m (matching `template.py` sideSegments)
    for x_side in (-5.0, 5.0):
        for y_sign in (-1.0, 1.0):
            y10 = 10.0 * y_sign
            y8 = 8.0 * y_sign
            y6 = 6.0 * y_sign
            y1 = 1.0 * y_sign  # Doorway opening in [-1.0, +1.0]

            # Corner 2m segment (|Y| in [8, 10]): 3m glass + 1m mesh (total 4m)
            scene.add_face(
                [
                    (x_side, y10, 0.0),
                    (x_side, y8, 0.0),
                    (x_side, y8, 3.0),
                    (x_side, y10, 3.0),
                ],
                fill=palette.glass_fill,
                fill_opacity=0.13,
                stroke=palette.glass_stroke,
                stroke_width=1.3,
            )
            scene.add_face(
                [
                    (x_side, y10, 3.0),
                    (x_side, y8, 3.0),
                    (x_side, y8, 4.0),
                    (x_side, y10, 4.0),
                ],
                fill=palette.fence_fill,
                fill_opacity=0.10,
                stroke=palette.fence_stroke,
                stroke_width=1.1,
                dash="4 3",
            )

            # Second 2m segment (|Y| in [6, 8]): 2m glass + 1m mesh (total 3m)
            scene.add_face(
                [
                    (x_side, y8, 0.0),
                    (x_side, y6, 0.0),
                    (x_side, y6, 2.0),
                    (x_side, y8, 2.0),
                ],
                fill=palette.glass_fill,
                fill_opacity=0.13,
                stroke=palette.glass_stroke,
                stroke_width=1.3,
            )
            scene.add_face(
                [
                    (x_side, y8, 2.0),
                    (x_side, y6, 2.0),
                    (x_side, y6, 3.0),
                    (x_side, y8, 3.0),
                ],
                fill=palette.fence_fill,
                fill_opacity=0.10,
                stroke=palette.fence_stroke,
                stroke_width=1.1,
                dash="4 3",
            )

            # Metallic fence section (|Y| in [1, 6], Z = 0..3m, doorway at [-1, 1])
            scene.add_face(
                [
                    (x_side, y6, 0.0),
                    (x_side, y1, 0.0),
                    (x_side, y1, 3.0),
                    (x_side, y6, 3.0),
                ],
                fill=palette.fence_fill,
                fill_opacity=0.08,
                stroke=palette.fence_stroke,
                stroke_width=1.1,
                dash="4 3",
            )
            if include_panel_divisions:
                for y_div in (4.0 * y_sign, 2.0 * y_sign):
                    scene.add_segment(
                        (x_side, y_div, 0.0),
                        (x_side, y_div, 3.0),
                        stroke=palette.fence_stroke,
                        stroke_width=0.85,
                        opacity=0.55,
                        dash="3 3",
                    )

    return scene


# --------------------------------------------------------------------------- #
# 3D-to-2D Clipping & Polyline Simplification Utilities
# --------------------------------------------------------------------------- #


def clip_segment_near_plane(
    p1_cam: np.ndarray,
    p2_cam: np.ndarray,
    z_near: float = 0.10,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Clip a 3D line segment in camera coordinates against Z_cam >= z_near."""
    z1, z2 = float(p1_cam[2]), float(p2_cam[2])
    if z1 < z_near and z2 < z_near:
        return None
    if z1 >= z_near and z2 >= z_near:
        return p1_cam, p2_cam
    t = (z_near - z1) / (z2 - z1)
    p_clip = p1_cam + t * (p2_cam - p1_cam)
    if z1 < z_near:
        return p_clip, p2_cam
    return p1_cam, p_clip


def project_polyline_3d(
    camera: Camera,
    points_3d: np.ndarray | Sequence[Sequence[float]],
    subdivide: int = 1,
    z_near: float = 0.10,
) -> np.ndarray:
    """Subdivide, near-plane clip, and project a 3D polyline into 2D image pixels."""
    pts = np.asarray(points_3d, dtype=np.float64)
    if pts.shape[0] < 2:
        uv, _ = camera.project_points(pts)
        return uv

    sampled: list[np.ndarray] = []
    for i in range(pts.shape[0] - 1):
        p_a, p_b = pts[i], pts[i + 1]
        ts = np.linspace(0.0, 1.0, max(subdivide, 1) + 1)
        if i > 0:
            ts = ts[1:]
        for t in ts:
            sampled.append(p_a + t * (p_b - p_a))
    dense_world = np.vstack(sampled)

    r_mat = camera.extrinsics.R
    t_vec = camera.extrinsics.t
    dense_cam = (r_mat @ dense_world.T).T + t_vec

    valid_world: list[np.ndarray] = []
    r_inv = r_mat.T
    for i in range(dense_cam.shape[0] - 1):
        clipped = clip_segment_near_plane(dense_cam[i], dense_cam[i + 1], z_near=z_near)
        if clipped is not None:
            c1, c2 = clipped
            if not valid_world:
                valid_world.append(r_inv @ (c1 - t_vec))
            valid_world.append(r_inv @ (c2 - t_vec))
    if not valid_world:
        return np.zeros((0, 2), dtype=np.float64)

    uv, _ = camera.project_points(np.vstack(valid_world))
    return uv


def rdp_simplify_2d(points_2d: np.ndarray, epsilon: float = 0.50) -> np.ndarray:
    """Simplify a 2D polyline via the Ramer-Douglas-Peucker algorithm."""
    pts = np.asarray(points_2d, dtype=np.float64)
    if pts.shape[0] <= 2:
        return pts

    start, end = pts[0], pts[-1]
    seg = end - start
    seg_len = float(np.hypot(seg[0], seg[1]))

    if seg_len < 1e-9:
        dists = np.hypot(pts[:, 0] - start[0], pts[:, 1] - start[1])
    else:
        cross = np.abs(
            seg[0] * (start[1] - pts[:, 1]) - (start[0] - pts[:, 0]) * seg[1]
        )
        dists = cross / seg_len

    max_idx = int(np.argmax(dists))
    max_dist = float(dists[max_idx])

    if max_dist > epsilon:
        left = rdp_simplify_2d(pts[: max_idx + 1], epsilon=epsilon)
        right = rdp_simplify_2d(pts[max_idx:], epsilon=epsilon)
        return np.vstack([left[:-1], right])
    return np.vstack([start, end])


def simplify_trajectory_preserve_cusps(
    positions_2d: np.ndarray,
    bounce_indices: Sequence[int],
    epsilon: float = 0.35,
) -> np.ndarray:
    """Simplify a 2D trajectory while preserving exact sharp vertices at bounces and apexes."""
    pts = np.asarray(positions_2d, dtype=np.float64)
    n_pts = pts.shape[0]
    if n_pts <= 2:
        return pts

    cuts = sorted({0, n_pts - 1, *(idx for idx in bounce_indices if 0 <= idx < n_pts)})
    segments: list[np.ndarray] = []
    for i in range(len(cuts) - 1):
        i_start, i_end = cuts[i], cuts[i + 1]
        sub = rdp_simplify_2d(pts[i_start : i_end + 1], epsilon=epsilon)
        if segments:
            sub = sub[1:]
        segments.append(sub)
    return np.vstack(segments)


# --------------------------------------------------------------------------- #
# 10 Diagram Generators
# --------------------------------------------------------------------------- #


def render_court_landmarks_3d(palette: ThemePalette) -> str:
    """1. Full 3D CAD court schematic with all 17 standardized FIP CourtLandmarks."""
    svg = SvgCanvas(
        960,
        540,
        "PadelKit 17 Standardized 3D Court Landmarks",
        "3D CAD view of the 17 CourtLandmark positions: 1-13 on floor (Z=0m) and 14-17 on back walls (Z=4.0m).",
        palette,
    )
    svg.header(
        "17 Standardized 3D Court Landmarks (CourtLandmark)",
        "Floor landmarks 1–13 (Z = 0.0 m)  |  Back-wall top corners 14–17 (Z = 4.0 m)  |  CoordinateSystem.CENTERED",
    )
    svg.line(646, 68, 646, 512, stroke=palette.border, stroke_width=1.0)

    court = Court.fip_standard()
    pts_3d = court.landmarks_3d(CoordinateSystem.CENTERED)

    # Use a low-distortion telephoto axonometric camera (FOV = 18 deg at 54m)
    cam = Camera(
        intrinsics=CameraIntrinsics.from_fov(
            width_px=1200, height_px=900, horizontal_fov_deg=18.0
        ),
        extrinsics=CameraExtrinsics.from_look_at(
            position=(-34.0, -34.0, 24.0),
            target=(0.0, 0.0, 1.4),
        ),
    )

    scene = build_fip_court_3d_scene(
        palette, include_walls=True, include_panel_divisions=True
    )
    projector = ViewportProjector3D(
        cam,
        scene.all_vertices(),
        rect_x=24.0,
        rect_y=64.0,
        rect_w=615.0,
        rect_h=430.0,
        padding_px=42.0,
        shift_uv=(0.0, -8.0),
    )

    clip_g = svg.clip_group("clip-court-3d", 24, 64, 615, 452, rx=10)
    svg.set_target(clip_g)
    projector.render_scene(svg, scene)

    # Vertical dashed elevation guides for the 4 wall-top landmarks (14-17)
    for corner_xy in [(-5.0, -10.0), (5.0, -10.0), (-5.0, 10.0), (5.0, 10.0)]:
        u_lo, v_lo = projector.project_point((corner_xy[0], corner_xy[1], 0.0))
        u_hi, v_hi = projector.project_point((corner_xy[0], corner_xy[1], 4.0))
        svg.line(
            u_lo,
            v_lo,
            u_hi,
            v_hi,
            stroke=palette.accent_secondary,
            stroke_width=1.6,
            dash="3 3",
        )

    # World origin triad at net center (0, 0, 0)
    o_u, o_v = projector.project_point((0.0, 0.0, 0.0))
    x_u, x_v = projector.project_point((1.8, 0.0, 0.0))
    y_u, y_v = projector.project_point((0.0, 2.2, 0.0))
    z_u, z_v = projector.project_point((0.0, 0.0, 1.8))
    svg.line(
        o_u,
        o_v,
        x_u,
        x_v,
        stroke=palette.accent_danger,
        stroke_width=2.0,
        marker_end="arrow-danger",
    )
    svg.text(
        x_u + 11,
        x_v + 4,
        "+X",
        fill=palette.accent_danger,
        size=9.5,
        weight="700",
        mono=True,
    )
    svg.line(
        o_u,
        o_v,
        y_u,
        y_v,
        stroke=palette.accent_primary,
        stroke_width=2.0,
        marker_end="arrow-primary",
    )
    svg.text(
        y_u + 12,
        y_v - 4,
        "+Y",
        fill=palette.accent_primary,
        size=9.5,
        weight="700",
        mono=True,
    )
    svg.line(
        o_u,
        o_v,
        z_u,
        z_v,
        stroke=palette.accent_tertiary,
        stroke_width=2.0,
        marker_end="arrow-tertiary",
    )
    svg.text(
        z_u,
        z_v - 11,
        "+Z",
        fill=palette.accent_tertiary,
        size=9.5,
        weight="700",
        mono=True,
    )

    # Draw numbered badges 1..17 with clean non-overlapping offsets
    offsets: dict[int, tuple[float, float]] = {
        1: (22, 14),
        2: (22, 8),
        3: (-24, 10),
        4: (18, 12),
        5: (24, 6),
        6: (-24, 4),
        7: (22, 10),
        8: (24, 2),
        9: (-24, -4),
        10: (18, -10),
        11: (24, -4),
        12: (-24, -6),
        13: (22, 10),
        14: (-26, -8),
        15: (22, -14),
        16: (-22, -14),
        17: (22, -14),
    }

    members = list(CourtLandmark)
    for idx, landmark in enumerate(members, start=1):
        xyz = pts_3d[landmark.value]
        u, v = projector.project_point(xyz)
        is_wall = idx >= 14
        color = palette.accent_secondary if is_wall else palette.accent_primary
        dx, dy = offsets[idx]
        svg.callout_badge(u, v, str(idx), color=color, offset=(dx, dy))

    # Borderless material legend at bottom-left of 3D view
    svg.rect(38, 476, 360, 28, fill=palette.bg_canvas, opacity=0.88, rx=6)
    svg.rect(
        48, 485, 10, 10, fill=palette.glass_fill, stroke=palette.glass_stroke, rx=2
    )
    svg.text(
        64,
        490,
        "Tempered Glass (3m / 2m)",
        fill=palette.text_muted,
        size=9.5,
        mono=True,
        anchor="start",
    )
    svg.rect(
        218,
        485,
        10,
        10,
        fill=palette.fence_fill,
        stroke=palette.fence_stroke,
        dash="2 2",
        rx=2,
    )
    svg.text(
        234,
        490,
        "Metallic Mesh (4m / 3m)",
        fill=palette.text_muted,
        size=9.5,
        mono=True,
        anchor="start",
    )

    svg.set_target(None)

    # Right panel table of 17 landmarks
    svg.text(
        666,
        85,
        "IDX",
        fill=palette.text_muted,
        size=9.0,
        weight="700",
        mono=True,
        anchor="start",
    )
    svg.text(
        696,
        85,
        "COURT LANDMARK ENUM",
        fill=palette.text_muted,
        size=9.0,
        weight="700",
        mono=True,
        anchor="start",
    )
    svg.text(
        926,
        85,
        "(X, Y, Z)",
        fill=palette.text_muted,
        size=9.0,
        weight="700",
        mono=True,
        anchor="end",
    )
    svg.line(666, 97, 926, 97, stroke=palette.border, stroke_width=1.0)
    for idx, landmark in enumerate(members, start=1):
        xyz = pts_3d[landmark.value]
        is_wall = idx >= 14
        color = palette.accent_secondary if is_wall else palette.accent_primary
        row_y = 97 + idx * 23.7
        svg.callout_badge(678, row_y, str(idx), color=color)
        svg.text(
            696,
            row_y + 0.5,
            landmark.value,
            fill=palette.text_primary,
            size=9.5,
            weight="600",
            mono=True,
            anchor="start",
        )
        coord_str = f"({xyz[0]:4.0f},{xyz[1]:5.0f},{xyz[2]:3.0f})"
        svg.text(
            926,
            row_y + 0.5,
            coord_str,
            fill=palette.text_muted,
            size=9.0,
            mono=True,
            anchor="end",
        )

    return svg.to_xml_string()


def render_court_dimensions(palette: ThemePalette) -> str:
    """2. 2D FIP plan blueprint + Side-wall glass/mesh elevation + Net catenary profile."""
    svg = SvgCanvas(
        960,
        520,
        "PadelKit Official FIP CourtDimensions Blueprint",
        "2D top-down dimension schematic, side/back wall glass-and-mesh elevation, and net profile for CourtDimensions.",
        palette,
    )
    svg.header(
        "Official FIP CourtDimensions Blueprint (Meters)",
        "length = 20.0m  |  width = 10.0m  |  service_line_distance_from_back = 3.0m  |  net = 0.88m / 0.92m",
    )

    court = Court.fip_standard()
    dims = court.dimensions

    # Left zone: Horizontal 2D Court Plan (Length along X, Width along Y)
    svg.line(582, 68, 582, 496, stroke=palette.border, stroke_width=1.0)
    svg.text(
        42,
        88,
        "A. TOP-DOWN FLOOR PLAN (20.0m × 10.0m)",
        fill=palette.text_primary,
        size=11.5,
        weight="700",
        mono=True,
        anchor="start",
    )

    cx0, cy0 = 48.0, 148.0
    scale = 19.2  # 20m -> 384px, 10m -> 192px
    cw = dims.length * scale
    ch = dims.width * scale
    svc_px = dims.service_line_distance_from_back * scale

    svg.rect(
        cx0,
        cy0,
        cw,
        ch,
        fill=palette.court_floor,
        stroke=palette.court_line_fg,
        stroke_width=2.2,
    )
    # 2m panel tick marks along perimeter
    for m_step in range(2, 20, 2):
        tx = cx0 + m_step * scale
        svg.line(tx, cy0 - 4, tx, cy0 + 4, stroke=palette.text_muted, stroke_width=1.0)
        svg.line(
            tx,
            cy0 + ch - 4,
            tx,
            cy0 + ch + 4,
            stroke=palette.text_muted,
            stroke_width=1.0,
        )

    # Service lines & center service line
    svg.line(
        cx0 + svc_px,
        cy0,
        cx0 + svc_px,
        cy0 + ch,
        stroke=palette.court_line_fg,
        stroke_width=1.6,
    )
    svg.line(
        cx0 + cw - svc_px,
        cy0,
        cx0 + cw - svc_px,
        cy0 + ch,
        stroke=palette.court_line_fg,
        stroke_width=1.6,
    )
    svg.line(
        cx0 + svc_px,
        cy0 + ch / 2,
        cx0 + cw - svc_px,
        cy0 + ch / 2,
        stroke=palette.court_line_fg,
        stroke_width=1.6,
    )
    # Net at center
    svg.line(
        cx0 + cw / 2,
        cy0 - 8,
        cx0 + cw / 2,
        cy0 + ch + 8,
        stroke=palette.accent_secondary,
        stroke_width=2.6,
        dash="5 3",
    )
    svg.text(
        cx0 + cw / 2,
        cy0 + ch + 18,
        "NET",
        fill=palette.accent_secondary,
        size=8.5,
        weight="700",
        mono=True,
    )

    # Extension guides and clean non-overlapping dimension arrows
    svg.line(cx0, cy0, cx0, cy0 - 34, stroke=palette.border, dash="2 2")
    svg.line(cx0 + cw, cy0, cx0 + cw, cy0 - 34, stroke=palette.border, dash="2 2")
    svg.dimension_arrow(
        cx0,
        cy0 - 24,
        cx0 + cw,
        cy0 - 24,
        f"length = {dims.length:.1f} m",
        marker_key="primary",
        color=palette.accent_primary,
    )

    svg.line(cx0 + cw, cy0, cx0 + cw + 60, cy0, stroke=palette.border, dash="2 2")
    svg.line(
        cx0 + cw,
        cy0 + ch,
        cx0 + cw + 60,
        cy0 + ch,
        stroke=palette.border,
        dash="2 2",
    )
    svg.dimension_arrow(
        cx0 + cw + 52,
        cy0,
        cx0 + cw + 52,
        cy0 + ch,
        f"width = {dims.width:.1f} m",
        marker_key="secondary",
        color=palette.accent_secondary,
    )

    # Bottom sub-dimensions with extension lines so arrows are clearly visible
    y_dim1 = cy0 + ch + 36
    y_dim2 = cy0 + ch + 76
    svg.line(cx0, cy0 + ch, cx0, y_dim1 + 8, stroke=palette.border, dash="2 2")
    svg.line(
        cx0 + svc_px,
        cy0 + ch,
        cx0 + svc_px,
        y_dim2 + 8,
        stroke=palette.border,
        dash="2 2",
    )
    svg.line(
        cx0 + cw / 2,
        cy0 + ch,
        cx0 + cw / 2,
        y_dim2 + 8,
        stroke=palette.border,
        dash="2 2",
    )

    svg.line(
        cx0 + 4,
        y_dim1,
        cx0 + svc_px - 4,
        y_dim1,
        stroke=palette.accent_tertiary,
        stroke_width=1.6,
        marker_start="arrow-tertiary",
        marker_end="arrow-tertiary",
    )
    svg.text(
        cx0 + svc_px + 10,
        y_dim1,
        f"service_line_distance_from_back = {dims.service_line_distance_from_back:.1f} m",
        fill=palette.accent_tertiary,
        size=9.5,
        weight="600",
        mono=True,
        anchor="start",
    )

    svg.dimension_arrow(
        cx0 + svc_px,
        y_dim2,
        cx0 + cw / 2,
        y_dim2,
        "7.0 m",
        marker_key="muted",
        color=palette.text_muted,
    )
    svg.text(
        cx0 + 0.5 * (svc_px + cw / 2),
        y_dim2 + 18,
        "service box depth (net to service line)",
        fill=palette.text_muted,
        size=8.8,
        mono=True,
    )

    # Right zone top: Side Wall Profile (V1 3.0m vs V2 4.0m with Glass vs Mesh modules)
    svg.text(
        608,
        86,
        "B. SIDE WALL ELEVATION (GLASS vs MESH)",
        fill=palette.text_primary,
        size=11.2,
        weight="700",
        mono=True,
        anchor="start",
    )

    ex0, ey_floor = 618.0, 232.0
    escale_x = 11.8  # 20m -> 236px
    escale_z = 22.0  # 4m -> 88px
    w_len = 20.0 * escale_x
    h_4m = dims.back_wall_height * escale_z
    h_3m = dims.side_wall_height * escale_z
    h_2m = 2.0 * escale_z
    step_2m = 2.0 * escale_x

    # Header annotation positioned cleanly above the 4.0m roofline
    svg.text(
        ex0 + w_len / 2,
        ey_floor - h_4m - 22,
        "side_wall = 3.0m  |  end step = 4.0m",
        fill=palette.text_primary,
        size=9.2,
        weight="600",
        mono=True,
    )

    # Left height ticks (0m, 2m, 3m, 4m)
    for h_m in (0, 2, 3, 4):
        ty = ey_floor - h_m * escale_z
        svg.line(ex0 - 4, ty, ex0, ty, stroke=palette.border, stroke_width=1.0)
        svg.text(
            ex0 - 6,
            ty + 0.5,
            f"{h_m}m",
            fill=palette.text_muted,
            size=7.8,
            mono=True,
            anchor="end",
        )

    # Full 3m / 4m metallic mesh background envelope
    v1_poly = [
        (ex0, ey_floor),
        (ex0, ey_floor - h_4m),
        (ex0 + step_2m, ey_floor - h_4m),
        (ex0 + step_2m, ey_floor - h_3m),
        (ex0 + w_len - step_2m, ey_floor - h_3m),
        (ex0 + w_len - step_2m, ey_floor - h_4m),
        (ex0 + w_len, ey_floor - h_4m),
        (ex0 + w_len, ey_floor),
    ]
    svg.polygon(
        v1_poly,
        fill=palette.fence_fill,
        fill_opacity=0.65,
        stroke=palette.fence_stroke,
        stroke_width=1.5,
        dash="4 3",
    )

    # Stepped Tempered Glass panels at both ends (3m glass in 0..2m, 2m glass in 2..4m)
    for x_start, x_dir in [(ex0, 1.0), (ex0 + w_len, -1.0)]:
        glass_poly = [
            (x_start, ey_floor),
            (x_start, ey_floor - h_3m),
            (x_start + x_dir * step_2m, ey_floor - h_3m),
            (x_start + x_dir * step_2m, ey_floor - h_2m),
            (x_start + x_dir * 2.0 * step_2m, ey_floor - h_2m),
            (x_start + x_dir * 2.0 * step_2m, ey_floor),
        ]
        svg.polygon(
            glass_poly,
            fill=palette.glass_fill,
            fill_opacity=0.45,
            stroke=palette.glass_stroke,
            stroke_width=1.8,
        )

    # 2m vertical panel division lines
    for m_i in range(1, 10):
        px_div = ex0 + m_i * step_2m
        top_h = h_4m if m_i in (1, 9) else h_3m
        svg.line(
            px_div,
            ey_floor,
            px_div,
            ey_floor - top_h,
            stroke=palette.border,
            stroke_width=0.9,
        )

    # Central 2.0m entry doorway cutout (X in [9m, 11m])
    door_x = ex0 + 9.0 * escale_x
    svg.rect(
        door_x,
        ey_floor - h_2m,
        step_2m,
        h_2m,
        fill=palette.bg_panel,
        stroke=palette.text_muted,
        stroke_width=1.0,
        dash="2 2",
    )
    svg.text(
        door_x + step_2m / 2,
        ey_floor - h_2m / 2,
        "2m",
        fill=palette.text_muted,
        size=7.5,
        mono=True,
    )

    svg.line(
        ex0 - 6,
        ey_floor,
        ex0 + w_len + 6,
        ey_floor,
        stroke=palette.court_line_fg,
        stroke_width=2.0,
    )

    # Staggered vertical 3.0m and 4.0m dimension arrows on right
    svg.line(
        ex0 + w_len,
        ey_floor - h_3m,
        ex0 + w_len + 28,
        ey_floor - h_3m,
        stroke=palette.border,
        dash="2 2",
    )
    svg.line(
        ex0 + w_len,
        ey_floor - h_4m,
        ex0 + w_len + 60,
        ey_floor - h_4m,
        stroke=palette.border,
        dash="2 2",
    )
    svg.dimension_arrow(
        ex0 + w_len + 20,
        ey_floor - h_3m,
        ex0 + w_len + 20,
        ey_floor,
        "3.0m",
        marker_key="secondary",
        color=palette.accent_secondary,
        label_offset=(0, 8),
    )
    svg.dimension_arrow(
        ex0 + w_len + 54,
        ey_floor - h_4m,
        ex0 + w_len + 54,
        ey_floor,
        "4.0m",
        marker_key="primary",
        color=palette.accent_primary,
        label_offset=(0, -14),
    )

    # Swatch legend below floor line
    svg.rect(
        618,
        251,
        10,
        10,
        fill=palette.glass_fill,
        stroke=palette.glass_stroke,
        rx=2,
    )
    svg.text(
        634,
        256,
        "Tempered Glass (3m / 2m)",
        fill=palette.text_muted,
        size=8.8,
        mono=True,
        anchor="start",
    )
    svg.rect(
        774,
        251,
        10,
        10,
        fill=palette.fence_fill,
        stroke=palette.fence_stroke,
        dash="2 2",
        rx=2,
    )
    svg.text(
        790,
        256,
        "Metallic Mesh (4m / 3m)",
        fill=palette.text_muted,
        size=8.8,
        mono=True,
        anchor="start",
    )

    # Right zone bottom: Net Height Profile (0.92m posts vs 0.88m center sag)
    svg.line(596, 284, 936, 284, stroke=palette.border, stroke_width=1.0)
    svg.text(
        608,
        312,
        "C. NET CATENARY PROFILE (WIDTH = 10.0m)",
        fill=palette.text_primary,
        size=11.2,
        weight="700",
        mono=True,
        anchor="start",
    )

    nx0, ny_floor = 638.0, 444.0
    nw = 244.0
    post_h = 84.0
    center_h = 66.0  # Exaggerated sag for visual clarity of 0.88m vs 0.92m

    net_d = (
        f"M {_fmt(nx0)} {_fmt(ny_floor - post_h)} "
        f"Q {_fmt(nx0 + nw / 2)} {_fmt(ny_floor - center_h + 14)} "
        f"{_fmt(nx0 + nw)} {_fmt(ny_floor - post_h)} "
        f"L {_fmt(nx0 + nw)} {_fmt(ny_floor)} "
        f"L {_fmt(nx0)} {_fmt(ny_floor)} Z"
    )
    svg.path(
        net_d,
        stroke=palette.accent_secondary,
        stroke_width=2.0,
        fill=palette.glass_fill,
        opacity=0.35,
    )
    # Subtle vertical net mesh ribs clipped under the quadratic top cord
    for k_net in range(1, 10):
        frac = k_net / 10.0
        xm = nx0 + frac * nw
        top_sag = (
            (1.0 - frac) ** 2 * post_h
            + 2 * (1.0 - frac) * frac * (center_h - 14.0)
            + frac**2 * post_h
        )
        svg.line(
            xm,
            ny_floor,
            xm,
            ny_floor - top_sag,
            stroke=palette.accent_secondary,
            stroke_width=0.7,
            opacity=0.35,
        )
    # Center strap & posts
    svg.line(
        nx0 + nw / 2,
        ny_floor,
        nx0 + nw / 2,
        ny_floor - center_h + 7,
        stroke=palette.court_line_fg,
        stroke_width=2.0,
    )
    svg.line(
        nx0,
        ny_floor,
        nx0,
        ny_floor - post_h,
        stroke=palette.pillar_stroke,
        stroke_width=3.0,
    )
    svg.line(
        nx0 + nw,
        ny_floor,
        nx0 + nw,
        ny_floor - post_h,
        stroke=palette.pillar_stroke,
        stroke_width=3.0,
    )
    svg.line(
        nx0 - 12,
        ny_floor,
        nx0 + nw + 12,
        ny_floor,
        stroke=palette.court_line_fg,
        stroke_width=2.0,
    )
    svg.callout_badge(
        nx0,
        ny_floor - post_h,
        f"posts: {dims.net_height_posts:.2f}m",
        color=palette.accent_secondary,
        offset=(42, -16),
    )
    svg.callout_badge(
        nx0 + nw / 2,
        ny_floor - center_h + 7,
        f"center: {dims.net_height_center:.2f}m",
        color=palette.accent_tertiary,
        offset=(36, -24),
    )
    svg.dimension_arrow(
        nx0,
        ny_floor + 24,
        nx0 + nw,
        ny_floor + 24,
        f"width = {dims.width:.1f} m",
        marker_key="muted",
        color=palette.text_muted,
    )

    return svg.to_xml_string()


def render_court_coordinate_systems(palette: ThemePalette) -> str:
    """3. Side-by-side comparison of CoordinateSystem.CENTERED vs CORNER_BASED."""
    svg = SvgCanvas(
        960,
        440,
        "PadelKit CoordinateSystem: CENTERED vs CORNER_BASED",
        "Side-by-side comparison of CoordinateSystem.CENTERED (origin at net center) and CORNER_BASED (origin at floor_near_left).",
        palette,
    )
    svg.header(
        "Coordinate System Comparison (CoordinateSystem)",
        "CENTERED: Origin (0, 0, 0) at net center  |  CORNER_BASED: Origin (0, 0, 0) at floor_near_left (+5m X, +10m Y shift)",
    )

    court = Court.fip_standard()
    systems = [
        (
            CoordinateSystem.CENTERED,
            24.0,
            "1. CoordinateSystem.CENTERED (Default)",
            "Origin (0.0, 0.0) at center of net",
        ),
        (
            CoordinateSystem.CORNER_BASED,
            492.0,
            "2. CoordinateSystem.CORNER_BASED",
            "Origin (0.0, 0.0) at floor_near_left",
        ),
    ]

    svg.line(480, 68, 480, 412, stroke=palette.border, stroke_width=1.0)
    for sys_enum, px, title, subtitle in systems:
        svg.text(
            px + 20,
            88,
            title,
            fill=palette.text_primary,
            size=12.0,
            weight="700",
            mono=True,
            anchor="start",
        )
        svg.text(
            px + 20,
            106,
            subtitle,
            fill=palette.text_muted,
            size=10.5,
            mono=True,
            anchor="start",
        )

        pts = court.landmarks_2d(coordinate_system=sys_enum)
        cx_mid = px + 224.0
        cy_mid = 258.0
        sx, sy = 13.4, 9.8  # 10m -> 134px, 20m -> 196px

        def to_uv(
            world_xy: tuple[float, float],
            _sys: CoordinateSystem = sys_enum,
            _cx: float = cx_mid,
            _cy: float = cy_mid,
        ) -> tuple[float, float]:
            wx, wy = world_xy
            if _sys is CoordinateSystem.CORNER_BASED:
                wx -= 5.0
                wy -= 10.0
            return _cx + wx * sx, _cy - wy * sy

        p_nl = to_uv(pts["floor_near_left"])
        p_fr = to_uv(pts["floor_far_right"])
        svg.rect(
            p_nl[0],
            p_fr[1],
            p_fr[0] - p_nl[0],
            p_nl[1] - p_fr[1],
            fill=palette.court_floor,
            stroke=palette.court_line_fg,
            stroke_width=2.0,
        )

        for k_a, k_b, col, dash in [
            ("service_near_left", "service_near_right", palette.court_line_fg, None),
            ("service_far_left", "service_far_right", palette.court_line_fg, None),
            ("service_near_center", "service_far_center", palette.court_line_fg, None),
            ("net_left", "net_right", palette.accent_secondary, "4 3"),
        ]:
            u1, v1 = to_uv(pts[k_a])
            u2, v2 = to_uv(pts[k_b])
            svg.line(u1, v1, u2, v2, stroke=col, stroke_width=1.6, dash=dash)

        net_l_uv = to_uv(pts["net_left"])
        svg.text(
            net_l_uv[0] - 18,
            net_l_uv[1],
            "NET",
            fill=palette.accent_secondary,
            size=8.5,
            weight="700",
            mono=True,
        )

        origin_key = (
            "center" if sys_enum is CoordinateSystem.CENTERED else "floor_near_left"
        )
        ox, oy = to_uv(pts[origin_key])
        svg.line(
            ox,
            oy,
            ox + 44,
            oy,
            stroke=palette.accent_danger,
            stroke_width=2.4,
            marker_end="arrow-danger",
        )
        svg.text(
            ox + 26,
            oy + 13,
            "+X",
            fill=palette.accent_danger,
            size=10.5,
            weight="700",
            mono=True,
        )
        svg.line(
            ox,
            oy,
            ox,
            oy - 44,
            stroke=palette.accent_primary,
            stroke_width=2.4,
            marker_end="arrow-primary",
        )
        svg.text(
            ox - 16,
            oy - 28,
            "+Y",
            fill=palette.accent_primary,
            size=10.5,
            weight="700",
            mono=True,
        )
        svg.circle(ox, oy, 4.5, fill=palette.accent_danger, stroke=palette.bg_canvas)

        for key, off in [
            ("floor_near_left", (-54, 22)),
            ("floor_near_right", (54, 22)),
            ("center", (102, 0)),
            ("floor_far_left", (-54, -20)),
            ("floor_far_right", (54, -20)),
        ]:
            wx, wy = pts[key]
            u, v = to_uv((wx, wy))
            svg.callout_badge(
                u,
                v,
                f"({wx:.0f}, {wy:.0f})",
                color=(
                    palette.accent_danger
                    if key == origin_key
                    else palette.accent_secondary
                ),
                offset=off,
            )

        range_text = (
            "X ∈ [-5.0, +5.0] m   |   Y ∈ [-10.0, +10.0] m"
            if sys_enum is CoordinateSystem.CENTERED
            else "X ∈ [0.0, +10.0] m   |   Y ∈ [0.0, +20.0] m"
        )
        svg.text(
            px + 222.0,
            401.0,
            range_text,
            fill=palette.text_muted,
            size=9.5,
            weight="600",
            mono=True,
        )

    return svg.to_xml_string()


def render_camera_frustum_3d(palette: ThemePalette) -> str:
    """4. Full 3D court with camera presets, viewing frustum pyramid, and coordinate frames."""
    svg = SvgCanvas(
        960,
        500,
        "PadelKit 3D Camera Frustum & Coordinate Frames",
        "3D CAD schematic of Camera.broadcast_near() frustum pyramid and World/Camera/Sensor coordinate frames.",
        palette,
    )
    svg.header(
        "Projective Camera Frustum & Coordinate Systems (padelkit.camera)",
        "1. World (X, Y, Z)  ->  2. OpenCV Camera (+X right, +Y down, +Z forward)  ->  3. Sensor Pixels (u, v)",
    )
    svg.line(612, 68, 612, 476, stroke=palette.border, stroke_width=1.0)

    court = Court.fip_standard()
    bcast_cam = Camera.broadcast_near(court=court)
    frustum = bcast_cam.frustum_corners_world(near_m=2.2, far_m=13.0)
    cam_pos = np.asarray(bcast_cam.extrinsics.position, dtype=np.float64)
    cam_r = np.asarray(bcast_cam.extrinsics.right, dtype=np.float64)
    cam_d = np.asarray(bcast_cam.extrinsics.down, dtype=np.float64)
    cam_f = np.asarray(bcast_cam.extrinsics.forward, dtype=np.float64)

    observer = Camera(
        intrinsics=CameraIntrinsics.from_fov(
            width_px=1200, height_px=850, horizontal_fov_deg=20.0
        ),
        extrinsics=CameraExtrinsics.from_look_at(
            position=(-34.0, -34.0, 26.0),
            target=(0.0, -1.5, 2.0),
        ),
    )

    scene = build_fip_court_3d_scene(
        palette, include_walls=True, include_panel_divisions=False
    )
    preset_pts = np.asarray(
        [
            cam_pos,
            cam_pos - 0.9 * cam_f,
            (0.0, 0.0, 10.5),
            (-4.8, -9.8, 3.6),
            (5.8, 0.0, 2.4),
        ],
        dtype=np.float64,
    )
    fit_pts = np.vstack(
        [scene.all_vertices(), frustum["near"], frustum["far"], preset_pts]
    )

    projector = ViewportProjector3D(
        observer,
        fit_pts,
        rect_x=24.0,
        rect_y=64.0,
        rect_w=580.0,
        rect_h=412.0,
        padding_px=44.0,
        shift_uv=(6.0, 0.0),
    )

    clip_g = svg.clip_group("clip-frustum-3d", 24, 64, 580, 412, rx=10)
    svg.set_target(clip_g)

    projector.render_scene(svg, scene)

    # Frustum pyramid from Camera.frustum_corners_world()
    c_uv = projector.project_point(cam_pos)
    near_uvs = [projector.project_point(p) for p in frustum["near"]]
    far_uvs = [projector.project_point(p) for p in frustum["far"]]

    for f_uv in far_uvs:
        svg.line(
            c_uv[0],
            c_uv[1],
            f_uv[0],
            f_uv[1],
            stroke=palette.accent_secondary,
            stroke_width=1.2,
            dash="4 3",
            opacity=0.80,
        )
    svg.polygon(
        far_uvs,
        fill=palette.accent_secondary,
        fill_opacity=0.09,
        stroke=palette.accent_secondary,
        stroke_width=1.4,
        dash="5 3",
    )
    svg.polygon(
        near_uvs,
        fill=palette.accent_secondary,
        fill_opacity=0.28,
        stroke=palette.accent_secondary,
        stroke_width=2.0,
    )

    # 3D wireframe camera body + lens hood aligned with extrinsics (right, down, forward)
    hw, hh, blen, llen = 0.42, 0.28, 0.85, 0.45
    front_ring = [
        cam_pos - hw * cam_r - hh * cam_d,
        cam_pos + hw * cam_r - hh * cam_d,
        cam_pos + hw * cam_r + hh * cam_d,
        cam_pos - hw * cam_r + hh * cam_d,
    ]
    back_ring = [pt - blen * cam_f for pt in front_ring]
    hood_ring = [
        cam_pos + llen * cam_f - 0.56 * cam_r - 0.40 * cam_d,
        cam_pos + llen * cam_f + 0.56 * cam_r - 0.40 * cam_d,
        cam_pos + llen * cam_f + 0.56 * cam_r + 0.40 * cam_d,
        cam_pos + llen * cam_f - 0.56 * cam_r + 0.40 * cam_d,
    ]
    front_uv = [projector.project_point(p) for p in front_ring]
    back_uv = [projector.project_point(p) for p in back_ring]
    hood_uv = [projector.project_point(p) for p in hood_ring]
    svg.polygon(
        back_uv,
        fill=palette.bg_canvas,
        fill_opacity=0.85,
        stroke=palette.accent_secondary,
        stroke_width=1.4,
    )
    for k in range(4):
        svg.line(
            back_uv[k][0],
            back_uv[k][1],
            front_uv[k][0],
            front_uv[k][1],
            stroke=palette.accent_secondary,
            stroke_width=1.4,
        )
        svg.line(
            front_uv[k][0],
            front_uv[k][1],
            hood_uv[k][0],
            hood_uv[k][1],
            stroke=palette.accent_secondary,
            stroke_width=1.4,
        )
    svg.polygon(
        hood_uv,
        fill=palette.accent_secondary,
        fill_opacity=0.22,
        stroke=palette.accent_secondary,
        stroke_width=1.6,
    )

    # Local OpenCV Camera Axes (+Xc right, +Yc down, +Zc forward)
    xc_uv = projector.project_point(cam_pos + 1.8 * cam_r)
    yc_uv = projector.project_point(cam_pos + 1.8 * cam_d)
    svg.line(
        c_uv[0],
        c_uv[1],
        xc_uv[0],
        xc_uv[1],
        stroke=palette.accent_danger,
        stroke_width=1.8,
        marker_end="arrow-danger",
    )
    svg.text(
        xc_uv[0] + 10,
        xc_uv[1] + 2,
        "+Xc",
        fill=palette.accent_danger,
        size=8.5,
        weight="700",
        mono=True,
    )
    svg.line(
        c_uv[0],
        c_uv[1],
        yc_uv[0],
        yc_uv[1],
        stroke=palette.accent_tertiary,
        stroke_width=1.8,
        marker_end="arrow-tertiary",
    )
    svg.text(
        yc_uv[0] - 12,
        yc_uv[1] + 6,
        "+Yc",
        fill=palette.accent_tertiary,
        size=8.5,
        weight="700",
        mono=True,
    )

    # Optical axis ray (+Zc) from broadcast_near camera to court center
    center_uv = projector.project_point((0.0, 0.0, 0.0))
    svg.line(
        c_uv[0],
        c_uv[1],
        center_uv[0],
        center_uv[1],
        stroke=palette.accent_tertiary,
        stroke_width=2.0,
        marker_end="arrow-tertiary",
    )
    svg.callout_badge(
        c_uv[0],
        c_uv[1],
        "broadcast_near",
        color=palette.accent_secondary,
        offset=(56, 22),
    )
    svg.callout_badge(
        center_uv[0],
        center_uv[1],
        "World (0,0,0)",
        color=palette.accent_primary,
        offset=(-64, 24),
    )

    # Other camera presets markers
    for label, pos_xyz, off in [
        ("overhead_zenith", (0.0, 0.0, 10.5), (66, -6)),
        ("corner_near_left", (-4.8, -9.8, 3.6), (58, 36)),
        ("side_net_right", (5.8, 0.0, 2.4), (62, 6)),
    ]:
        pu, pv = projector.project_point(pos_xyz)
        svg.callout_badge(pu, pv, label, color=palette.accent_tertiary, offset=off)

    svg.set_target(None)

    # Right panel: Coordinate frame transformation pipeline
    frames = [
        (
            "1. World Frame (Meters)",
            "(X, Y, Z) at Court Net Center",
            "+X: Right  |  +Y: Far  |  +Z: Up",
            None,
            palette.accent_primary,
            86.0,
            84.0,
        ),
        (
            "2. Camera Frame (OpenCV vs OpenGL)",
            "Extrinsics: R (3×3),  t = -R @ C",
            "OpenCV: +X right, +Y down, +Z fwd",
            "OpenGL: +X right, +Y up,   -Z fwd",
            palette.accent_secondary,
            202.0,
            106.0,
        ),
        (
            "3. Image Sensor Plane (Pixels)",
            "Intrinsics Matrix K (fx, fy, cx, cy)",
            "u = fx*(Xc/Zc)+cx, v = fy*(Yc/Zc)+cy",
            "Models: NONE | BROWN_CONRADY | FISHEYE",
            palette.accent_tertiary,
            340.0,
            106.0,
        ),
    ]
    for f_title, f_sub, f_line3, f_line4, f_col, fy, fh in frames:
        svg.rect(
            636,
            fy,
            282,
            fh,
            fill=palette.bg_panel,
            stroke=f_col,
            stroke_width=1.5,
            rx=8,
        )
        svg.text(
            650,
            fy + 20,
            f_title,
            fill=f_col,
            size=11.0,
            weight="700",
            anchor="start",
        )
        svg.text(
            650,
            fy + 41,
            f_sub,
            fill=palette.text_primary,
            size=9.6,
            mono=True,
            anchor="start",
        )
        svg.text(
            650,
            fy + 61,
            f_line3,
            fill=palette.text_muted,
            size=9.2,
            mono=True,
            anchor="start",
        )
        if f_line4:
            svg.text(
                650,
                fy + 81,
                f_line4,
                fill=palette.text_muted,
                size=9.0,
                mono=True,
                anchor="start",
            )

    # Inter-card transform arrows
    for y_top, y_bot, label_txt, col, mk in [
        (170.0, 202.0, "[R | t]", palette.accent_secondary, "secondary"),
        (308.0, 340.0, "K, dist", palette.accent_tertiary, "tertiary"),
    ]:
        svg.line(
            777,
            y_top + 2,
            777,
            y_bot - 3,
            stroke=col,
            stroke_width=1.6,
            marker_end=f"arrow-{mk}",
        )
        svg.rect(
            786,
            0.5 * (y_top + y_bot) - 8,
            56,
            16,
            fill=palette.bg_canvas,
            stroke=col,
            stroke_width=0.9,
            rx=4,
        )
        svg.text(
            814,
            0.5 * (y_top + y_bot) + 0.5,
            label_txt,
            fill=col,
            size=8.8,
            weight="700",
            mono=True,
        )

    return svg.to_xml_string()


def render_camera_sensor_projection(palette: ThemePalette) -> str:
    """5. 1920x1080 sensor view showing full 3D court projection and all 17 landmarks."""
    svg = SvgCanvas(
        900,
        500,
        "PadelKit 1080p Sensor Landmark Projection & Intrinsics",
        "2D sensor projection of the 3D FIP court and 17 CourtLandmark points onto a 1920x1080 sensor frame.",
        palette,
    )
    svg.header(
        "Sensor Plane Projection & CameraIntrinsics (1920 × 1080 px)",
        "landmarks_px = cam.project_court_landmarks()  |  Resolution = 1920×1080  |  Principal Point (cx=960, cy=540)",
    )

    sx0, sy0 = 58.0, 82.0
    sw, sh = 624.0, 351.0  # Exact 16:9 scaled from 1920x1080
    scale = sw / 1920.0

    svg.rect(
        sx0,
        sy0,
        sw,
        sh,
        fill=palette.bg_panel,
        stroke=palette.accent_secondary,
        stroke_width=2.0,
        rx=6,
    )

    # Sensor pixel grid
    for gx in range(1, 6):
        x_line = sx0 + gx * (sw / 6)
        svg.line(
            x_line, sy0, x_line, sy0 + sh, stroke=palette.grid_line, stroke_width=1.0
        )
    for gy in range(1, 4):
        y_line = sy0 + gy * (sh / 4)
        svg.line(
            sx0, y_line, sx0 + sw, y_line, stroke=palette.grid_line, stroke_width=1.0
        )

    court = Court.fip_standard()
    # Elevated wide broadcast camera so all 17 landmarks fall cleanly inside the 1920x1080 sensor with generous margins
    cam = Camera(
        intrinsics=CameraIntrinsics.from_fov(
            width_px=1920, height_px=1080, horizontal_fov_deg=60.0
        ),
        extrinsics=CameraExtrinsics.from_look_at(
            position=(0.0, -24.5, 11.4),
            target=(0.0, -0.5, 0.7),
        ),
    )
    proj_pts = cam.project_court_landmarks(court=court)

    def world_to_svg(pts_3d: np.ndarray) -> np.ndarray:
        uv, _ = cam.project_points(np.asarray(pts_3d, dtype=np.float64))
        out = np.empty_like(uv)
        out[:, 0] = sx0 + uv[:, 0] * scale
        out[:, 1] = sy0 + uv[:, 1] * scale
        return out

    # Clip all rendered 3D court geometry strictly inside the 1920x1080 sensor frame
    sensor_clip = svg.clip_group("clip-sensor-1080p", sx0, sy0, sw, sh, rx=6)
    svg.set_target(sensor_clip)

    scene = build_fip_court_3d_scene(
        palette, include_walls=True, include_panel_divisions=True
    )
    # Render 3D scene sorted by camera depth directly into sensor pixel space
    r_mat = cam.extrinsics.R
    t_vec = cam.extrinsics.t
    draw_ables: list[tuple[float, Literal["face", "seg"], Face3D | Segment3D]] = []
    for f in scene.faces:
        z_d = float(np.mean(((r_mat @ f.vertices.T).T + t_vec)[:, 2])) + f.layer_bias
        draw_ables.append((z_d, "face", f))
    for s in scene.segments:
        z_d = float(np.mean(((r_mat @ s.points.T).T + t_vec)[:, 2])) + s.layer_bias
        draw_ables.append((z_d, "seg", s))
    draw_ables.sort(key=lambda item: item[0], reverse=True)

    for _, kind, obj in draw_ables:
        if kind == "face":
            assert isinstance(obj, Face3D)
            svg.polygon(
                world_to_svg(obj.vertices),
                fill=obj.fill,
                fill_opacity=obj.fill_opacity,
                stroke=obj.stroke,
                stroke_width=obj.stroke_width,
                stroke_opacity=obj.stroke_opacity,
                dash=obj.dash,
            )
        else:
            assert isinstance(obj, Segment3D)
            uv_s = world_to_svg(obj.points)
            svg.polyline(
                uv_s,
                stroke=obj.stroke,
                stroke_width=obj.stroke_width,
                opacity=obj.opacity,
                dash=obj.dash,
            )

    # Top-right sensor HUD tag
    svg.text(
        sx0 + sw - 12,
        sy0 + 18,
        "1920 × 1080 px (16:9)",
        fill=palette.text_muted,
        size=9.2,
        weight="600",
        mono=True,
        anchor="end",
    )

    # Principal point crosshair (cx, cy)
    cx_px = sx0 + 960.0 * scale
    cy_px = sy0 + 540.0 * scale
    svg.line(
        cx_px - 12,
        cy_px,
        cx_px + 12,
        cy_px,
        stroke=palette.accent_danger,
        stroke_width=1.6,
    )
    svg.line(
        cx_px,
        cy_px - 12,
        cx_px,
        cy_px + 12,
        stroke=palette.accent_danger,
        stroke_width=1.6,
    )
    svg.callout_badge(
        cx_px,
        cy_px,
        "(cx, cy)",
        color=palette.accent_danger,
        offset=(58, -16),
    )

    # Draw all 17 projected landmarks inside the sensor
    badge_offsets: dict[int, tuple[float, float]] = {
        1: (-24, -12),
        2: (24, -12),
        3: (-24, 4),
        4: (0, 16),
        5: (24, 4),
        6: (-24, 0),
        7: (-24, 16),
        8: (24, 0),
        9: (-28, 8),
        10: (0, -16),
        11: (28, 8),
        12: (-28, -12),
        13: (28, -12),
        14: (-22, -12),
        15: (22, -12),
        16: (-20, -12),
        17: (20, -12),
    }
    for idx, lm in enumerate(CourtLandmark, start=1):
        u_px, v_px = proj_pts[lm.value]
        u_s = sx0 + u_px * scale
        v_s = sy0 + v_px * scale
        col = palette.accent_secondary if idx >= 14 else palette.accent_primary
        svg.callout_badge(u_s, v_s, str(idx), color=col, offset=badge_offsets[idx])

    svg.set_target(None)

    # Pixel axes (0,0) top-left outside clip group
    svg.line(
        sx0,
        sy0,
        sx0 + 60,
        sy0,
        stroke=palette.accent_tertiary,
        stroke_width=2.2,
        marker_end="arrow-tertiary",
    )
    svg.text(
        sx0 + 68,
        sy0 - 11,
        "+u (width_px = 1920)",
        fill=palette.accent_tertiary,
        size=9.5,
        weight="700",
        mono=True,
        anchor="start",
    )
    svg.line(
        sx0,
        sy0,
        sx0,
        sy0 + 60,
        stroke=palette.accent_tertiary,
        stroke_width=2.2,
        marker_end="arrow-tertiary",
    )
    svg.text(
        sx0 - 8,
        sy0 + 58,
        "+v",
        fill=palette.accent_tertiary,
        size=9.5,
        weight="700",
        mono=True,
        anchor="end",
    )
    svg.text(
        sx0 - 8,
        sy0 + 72,
        "1080",
        fill=palette.accent_tertiary,
        size=8.5,
        mono=True,
        anchor="end",
    )
    svg.circle(sx0, sy0, 4.0, fill=palette.accent_tertiary, stroke=palette.bg_canvas)
    svg.text(
        sx0 - 8,
        sy0 - 10,
        "(0,0)",
        fill=palette.accent_tertiary,
        size=8.5,
        weight="700",
        mono=True,
        anchor="end",
    )

    # Right callout column: Calibration matrix K & unprojection (borderless, separated by hairline rule)
    svg.line(696, 82, 696, 433, stroke=palette.border, stroke_width=1.0)
    svg.text(
        789,
        108,
        "Intrinsic Matrix K",
        fill=palette.text_primary,
        size=11.5,
        weight="700",
    )
    svg.polyline(
        [(738, 123), (731, 123), (731, 181), (738, 181)],
        stroke=palette.accent_secondary,
        stroke_width=1.6,
    )
    svg.polyline(
        [(840, 123), (847, 123), (847, 181), (840, 181)],
        stroke=palette.accent_secondary,
        stroke_width=1.6,
    )
    k_symbolic = [
        "fx   0   cx",
        " 0  fy   cy",
        " 0   0    1",
    ]
    for i, sym_txt in enumerate(k_symbolic):
        svg.text(
            789,
            133 + i * 19,
            sym_txt,
            fill=palette.accent_secondary,
            size=10.2,
            weight="600",
            mono=True,
        )
    svg.line(714, 194, 864, 194, stroke=palette.border, stroke_width=1.0)
    k_values = [
        (f"fx   = {cam.intrinsics.fx:6.1f} px", palette.text_primary),
        (f"fy   = {cam.intrinsics.fy:6.1f} px", palette.text_primary),
        (f"cx   = {cam.intrinsics.cx:6.1f} px", palette.text_primary),
        (f"cy   = {cam.intrinsics.cy:6.1f} px", palette.text_primary),
        (f"HFOV =   {cam.intrinsics.fov_horizontal_deg:.1f}°", palette.text_muted),
        (f"VFOV =   {cam.intrinsics.fov_vertical_deg:.1f}°", palette.text_muted),
    ]
    for i, (val_txt, col) in enumerate(k_values):
        svg.text(
            716,
            214 + i * 21,
            val_txt,
            fill=col,
            size=9.5,
            mono=True,
            anchor="start",
        )
    svg.line(714, 344, 864, 344, stroke=palette.border, stroke_width=1.0)
    svg.text(
        716,
        365,
        "proj_pts['center']:",
        fill=palette.accent_primary,
        size=9.2,
        weight="600",
        mono=True,
        anchor="start",
    )
    svg.text(
        716,
        387,
        f"({proj_pts['center'][0]:.0f}, {proj_pts['center'][1]:.1f}) px",
        fill=palette.text_primary,
        size=9.8,
        weight="700",
        mono=True,
        anchor="start",
    )

    return svg.to_xml_string()


def render_camera_distortion_grid(palette: ThemePalette) -> str:
    """6. 3-panel comparison of NONE, BROWN_CONRADY, and FISHEYE lens distortion."""
    svg = SvgCanvas(
        960,
        360,
        "PadelKit Optical Lens Distortion Models (CameraDistortion)",
        "Comparison of Pinhole (NONE), Brown-Conrady radial/tangential, and Kannala-Brandt Fisheye projections with 48-point polyline subdivision.",
        palette,
    )
    svg.header(
        "Optical Lens Distortion Models (CameraDistortion)",
        "Full 3D court enclosure & grid lines (N = 48 samples/segment) warped via Camera.project_points()",
    )

    models = [
        (
            "1. DistortionModel.NONE",
            "Ideal Rectilinear Pinhole",
            CameraDistortion.none(),
            palette.accent_primary,
            24.0,
        ),
        (
            "2. BROWN_CONRADY",
            "k1=-0.24, k2=0.06 (Barrel)",
            CameraDistortion.brown_conrady(k1=-0.24, k2=0.06, p1=0.001, p2=-0.001),
            palette.accent_secondary,
            336.0,
        ),
        (
            "3. FISHEYE (Kannala-Brandt)",
            "Equidistant Wide Action Lens",
            CameraDistortion.fisheye(k1=-0.10, k2=0.02, k3=-0.003, k4=0.0005),
            palette.accent_tertiary,
            648.0,
        ),
    ]

    intr = CameraIntrinsics.from_fov(
        width_px=260, height_px=190, horizontal_fov_deg=80.0
    )
    extr = CameraExtrinsics.from_look_at(
        position=(0.0, -16.8, 8.2),
        target=(0.0, 0.0, 0.6),
    )

    # Complete connected 3D court wireframe (floor, service lines, net, and full 3D walls with vertical posts)
    court_segments: list[
        tuple[tuple[float, float, float], tuple[float, float, float], bool]
    ] = [
        # Floor & service lines (is_wall=False)
        ((-5.0, -10.0, 0.0), (5.0, -10.0, 0.0), False),
        ((5.0, -10.0, 0.0), (5.0, 10.0, 0.0), False),
        ((5.0, 10.0, 0.0), (-5.0, 10.0, 0.0), False),
        ((-5.0, 10.0, 0.0), (-5.0, -10.0, 0.0), False),
        ((-5.0, -7.0, 0.0), (5.0, -7.0, 0.0), False),
        ((-5.0, 7.0, 0.0), (5.0, 7.0, 0.0), False),
        ((0.0, -7.0, 0.0), (0.0, 7.0, 0.0), False),
        # Net at Y = 0
        ((-5.0, 0.0, 0.0), (5.0, 0.0, 0.0), False),
        ((-5.0, 0.0, 0.92), (5.0, 0.0, 0.92), True),
        ((-5.0, 0.0, 0.0), (-5.0, 0.0, 0.92), True),
        ((5.0, 0.0, 0.0), (5.0, 0.0, 0.92), True),
        # Back & Side 3D Walls (connected vertical posts + horizontal glass/mesh beams)
        ((-5.0, -10.0, 0.0), (-5.0, -10.0, 4.0), True),
        ((5.0, -10.0, 0.0), (5.0, -10.0, 4.0), True),
        ((-5.0, 10.0, 0.0), (-5.0, 10.0, 4.0), True),
        ((5.0, 10.0, 0.0), (5.0, 10.0, 4.0), True),
        ((-5.0, -10.0, 4.0), (5.0, -10.0, 4.0), True),
        ((-5.0, 10.0, 4.0), (5.0, 10.0, 4.0), True),
        ((-5.0, 10.0, 3.0), (5.0, 10.0, 3.0), True),
        # Stepped side walls (left X=-5 and right X=+5)
        ((-5.0, -10.0, 3.0), (-5.0, 10.0, 3.0), True),
        ((5.0, -10.0, 3.0), (5.0, 10.0, 3.0), True),
        ((-5.0, -10.0, 4.0), (-5.0, -8.0, 4.0), True),
        ((-5.0, -8.0, 4.0), (-5.0, -8.0, 0.0), True),
        ((5.0, -10.0, 4.0), (5.0, -8.0, 4.0), True),
        ((5.0, -8.0, 4.0), (5.0, -8.0, 0.0), True),
        ((-5.0, 10.0, 4.0), (-5.0, 8.0, 4.0), True),
        ((-5.0, 8.0, 4.0), (-5.0, 8.0, 0.0), True),
        ((5.0, 10.0, 4.0), (5.0, 8.0, 4.0), True),
        ((5.0, 8.0, 4.0), (5.0, 8.0, 0.0), True),
    ]

    for idx_m, (title, subtitle, dist_model, accent, px) in enumerate(models):
        svg.rect(
            px,
            64,
            288,
            274,
            fill=palette.bg_panel,
            stroke=palette.border,
            rx=10,
        )
        svg.line(px + 14, 65, px + 96, 65, stroke=accent, stroke_width=2.6)
        svg.text(
            px + 16,
            88,
            title,
            fill=accent,
            size=11.5,
            weight="700",
            mono=True,
            anchor="start",
        )
        svg.text(
            px + 16,
            106,
            subtitle,
            fill=palette.text_muted,
            size=10.0,
            mono=True,
            anchor="start",
        )
        svg.line(px + 1, 118, px + 287, 118, stroke=palette.border, stroke_width=1.0)

        vp_x, vp_y = px + 14.0, 122.0
        clip_vp = svg.clip_group(
            f"clip-dist-{idx_m}", px + 4.0, 120.0, 280.0, 212.0, rx=8
        )
        svg.set_target(clip_vp)

        # Background sensor distortion grid via CameraDistortion.distort_normalized()
        for norm_c in np.linspace(-0.75, 0.75, 7):
            h_pts = np.column_stack([np.linspace(-1.05, 1.05, 40), np.full(40, norm_c)])
            v_pts = np.column_stack([np.full(40, norm_c), np.linspace(-0.75, 0.75, 40)])
            for grid_pts in (h_pts, v_pts):
                warped = dist_model.distort_normalized(grid_pts)
                uv = np.column_stack(
                    [
                        vp_x + 130.0 + warped[:, 0] * 105.0,
                        vp_y + 95.0 + warped[:, 1] * 105.0,
                    ]
                )
                svg.polyline(
                    rdp_simplify_2d(uv, epsilon=0.45),
                    stroke=palette.grid_line,
                    stroke_width=1.0,
                )

        cam = Camera(intrinsics=intr, extrinsics=extr, distortion=dist_model)
        for seg_a, seg_b, is_wall in court_segments:
            uv = project_polyline_3d(cam, [seg_a, seg_b], subdivide=36)
            if uv.shape[0] >= 2:
                uv[:, 0] += vp_x
                uv[:, 1] += vp_y
                svg.polyline(
                    rdp_simplify_2d(uv, epsilon=0.40),
                    stroke=accent if not is_wall else palette.fence_stroke,
                    stroke_width=1.8 if not is_wall else 1.1,
                    opacity=1.0 if not is_wall else 0.70,
                )

        # Principal point crosshair at optical center
        oc_x, oc_y = vp_x + 130.0, vp_y + 95.0
        svg.line(
            oc_x - 5,
            oc_y,
            oc_x + 5,
            oc_y,
            stroke=palette.accent_danger,
            stroke_width=1.2,
            opacity=0.75,
        )
        svg.line(
            oc_x,
            oc_y - 5,
            oc_x,
            oc_y + 5,
            stroke=palette.accent_danger,
            stroke_width=1.2,
            opacity=0.75,
        )

        svg.set_target(None)

    return svg.to_xml_string()


def render_physics_forces_9d(palette: ThemePalette) -> str:
    """7. 9D aerodynamic free-body diagram showing gravity, drag, and Spindt Magnus lift."""
    svg = SvgCanvas(
        900,
        420,
        "PadelKit 9D Ball Aerodynamics Free-Body Forces",
        "Free-body diagram of a spinning padel ball showing linear velocity, angular velocity spin vector, quadratic drag, gravity, and Spindt Magnus lift.",
        palette,
    )
    svg.header(
        "9D Ball State & Aerodynamic Forces (padelkit.physics)",
        "State = [x, y, z, vx, vy, vz, wx, wy, wz]  |  F_total = m*g + F_drag(Cd) + F_magnus(Cl_Spindt)",
    )
    svg.line(548, 68, 548, 392, stroke=palette.border, stroke_width=1.0)

    bx, by = 264.0, 228.0
    r_ball = 46.0

    # Ball radial gradient for 3D spherical contrast in both light & dark themes
    grad_id = f"ball-grad-{palette.mode}"
    stops = (
        [("0%", "#ecfccb"), ("55%", "#84cc16"), ("100%", "#365314")]
        if palette.mode == "dark"
        else [("0%", "#fef9c3"), ("55%", "#a3e635"), ("100%", "#4d7c0f")]
    )
    svg.radial_gradient(grad_id, stops)

    # Asymmetric curved streamlines showing Magnus pressure differential for counter-clockwise Backspin:
    # Tighter curved streamlines above (-ΔP low pressure) and wider spaced below (+ΔP high pressure)
    upper_streams = [
        f"M 440 {_fmt(by - 48)} C 350 {_fmt(by - 58)}, 285 {_fmt(by - 88)}, 72 {_fmt(by - 44)}",
        f"M 440 {_fmt(by - 76)} C 355 {_fmt(by - 84)}, 290 {_fmt(by - 110)}, 72 {_fmt(by - 70)}",
    ]
    lower_streams = [
        f"M 440 {_fmt(by + 44)} C 345 {_fmt(by + 58)}, 280 {_fmt(by + 74)}, 72 {_fmt(by + 68)}",
        f"M 440 {_fmt(by + 76)} C 345 {_fmt(by + 88)}, 280 {_fmt(by + 102)}, 72 {_fmt(by + 96)}",
    ]
    for st_d in upper_streams + lower_streams:
        svg.path(
            st_d,
            stroke=palette.text_muted,
            stroke_width=1.15,
            dash="5 4",
            opacity=0.48,
            marker_end="arrow-muted",
        )
    svg.text(
        118,
        by - 98,
        "-ΔP (Low Pressure)",
        fill=palette.accent_secondary,
        size=8.8,
        weight="600",
        mono=True,
    )
    svg.text(
        118,
        by + 116,
        "+ΔP (High Pressure)",
        fill=palette.text_muted,
        size=8.8,
        weight="600",
        mono=True,
    )

    # Spinning padel ball body & curved seam
    svg.circle(
        bx,
        by,
        r_ball,
        fill=f"url(#{grad_id})",
        stroke=palette.accent_tertiary,
        stroke_width=2.2,
    )
    seam_d = (
        f"M {_fmt(bx - 30)} {_fmt(by - 34)} "
        f"Q {_fmt(bx + 16)} {_fmt(by)} {_fmt(bx - 30)} {_fmt(by + 34)}"
    )
    svg.path(
        seam_d,
        stroke=palette.court_line_fg,
        stroke_width=1.8,
        dash="4 3",
        opacity=0.75,
    )

    # Counter-clockwise backspin arc (+ω_x out of page) in clean top-right sector
    spin_arc = (
        f"M {_fmt(bx + 54)} {_fmt(by - 26)} "
        f"A 60 60 0 0 0 {_fmt(bx + 9)} {_fmt(by - 59)}"
    )
    svg.path(
        spin_arc,
        stroke=palette.accent_tertiary,
        stroke_width=2.2,
        marker_end="arrow-tertiary",
    )
    svg.callout_badge(
        bx + 36,
        by - 48,
        "ω (Backspin)",
        color=palette.accent_tertiary,
        offset=(46, -24),
    )

    # Force & Velocity vectors from ball center
    svg.line(
        bx,
        by,
        bx + 150,
        by - 32,
        stroke=palette.accent_primary,
        stroke_width=2.8,
        marker_end="arrow-primary",
    )
    svg.callout_badge(
        bx + 150,
        by - 32,
        "v (Velocity)",
        color=palette.accent_primary,
        offset=(18, -20),
    )

    svg.line(
        bx,
        by,
        bx - 135,
        by + 29,
        stroke=palette.accent_danger,
        stroke_width=2.6,
        marker_end="arrow-danger",
    )
    svg.callout_badge(
        bx - 135,
        by + 29,
        "F_drag (-v̂)",
        color=palette.accent_danger,
        offset=(0, 22),
    )

    svg.line(
        bx,
        by,
        bx,
        by + 114,
        stroke=palette.court_line_fg,
        stroke_width=2.4,
        marker_end="arrow-fg",
    )
    svg.callout_badge(
        bx,
        by + 114,
        "F_g = m·g (-Z)",
        color=palette.court_line_fg,
        offset=(66, 0),
    )

    svg.line(
        bx,
        by,
        bx - 26,
        by - 120,
        stroke=palette.accent_secondary,
        stroke_width=2.8,
        marker_end="arrow-secondary",
    )
    svg.callout_badge(
        bx - 26,
        by - 120,
        "F_magnus ∝ ω × v",
        color=palette.accent_secondary,
        offset=(-56, -12),
    )
    svg.circle(bx, by, 4.0, fill=palette.court_line_fg, stroke=palette.bg_canvas)

    sample = BallState.from_shot(
        position=(0.0, -6.0, 1.2),
        velocity=(0.0, 20.0, 4.2),
        topspin_rpm=-1800.0,
        sidespin_rpm=0.0,
    )
    wx, wy, wz = sample.angular_velocity
    lines = [
        ("1. Quadratic Felt Drag", palette.accent_danger),
        ("Cd = 0.50 + 0.15 · fuzz_factor", palette.text_muted),
        ("F_drag = -½ ρ A Cd |v| v", palette.text_primary),
        ("2. Spindt Non-Linear Magnus Lift", palette.accent_secondary),
        ("Spin Ratio S = (R · |ω|) / |v|", palette.text_muted),
        ("Cl = 1 / (2.32 + 0.4 / (S + 0.1))", palette.text_primary),
        ("F_magnus = ½ ρ A Cl |v|² (ω̂ × v̂)", palette.text_primary),
        ("3. Sample Backspin BallState", palette.accent_primary),
        (
            f"Speed: {sample.speed_kmh:.1f} km/h | Spin: -1800 RPM",
            palette.text_muted,
        ),
        (
            f"ω = ({wx:+.0f}, {wy + 0.0:.0f}, {wz + 0.0:.0f}) rad/s",
            palette.text_muted,
        ),
    ]
    for i, (txt, col) in enumerate(lines):
        svg.text(
            578,
            94 + i * 29.0,
            txt,
            fill=col,
            size=10.0,
            weight="700" if txt[:2].endswith(".") else "500",
            mono=True,
            anchor="start",
        )

    return svg.to_xml_string()


def render_physics_trajectories(palette: ThemePalette) -> str:
    """8. RK4-simulated side-view trajectory comparison with floor & back-glass rebounds."""
    svg = SvgCanvas(
        960,
        440,
        "PadelKit RK4 Simulated Spin Trajectories (Y-Z Elevation)",
        "Side-elevation comparison of Topspin Smash, Flat Drive, and Backspin Bandeja simulated via BallPhysicsEngine.simulate().",
        palette,
    )
    svg.header(
        "RK4 Spin Trajectory Comparison (BallPhysicsEngine.simulate)",
        "Side Elevation (Y ∈ [-10m, +10m], Z ∈ [0m, 4.0m])  |  dt = 0.002s  |  Floor & Back-Glass Rebounds",
    )

    engine = BallPhysicsEngine()

    shots = [
        (
            "Topspin Smash (+2400 RPM)",
            BallState.from_shot(
                position=(0.0, -3.2, 2.70),
                velocity=(0.0, 21.5, -2.5),
                topspin_rpm=2400.0,
            ),
            1.15,
            palette.accent_danger,
            "High Rebound",
            (0, -18),
        ),
        (
            "Flat Drive (0 RPM)",
            BallState.from_shot(
                position=(0.0, -8.5, 1.15),
                velocity=(0.0, 21.2, 2.9),
                topspin_rpm=0.0,
            ),
            1.48,
            palette.accent_secondary,
            "Mid Rebound",
            (-48, 0),
        ),
        (
            "Backspin Bandeja (-2000 RPM)",
            BallState.from_shot(
                position=(0.0, -4.0, 2.15),
                velocity=(0.0, 14.2, -0.8),
                topspin_rpm=-2000.0,
            ),
            1.45,
            palette.accent_primary,
            "Low Skid",
            (-20, 13),
        ),
    ]

    x0, y_floor = 466.0, 366.0
    sx, sz = 39.0, 56.0

    def yz_to_uv(y_m: float, z_m: float) -> tuple[float, float]:
        return x0 + y_m * sx, y_floor - z_m * sz

    x_left, _ = yz_to_uv(-10.0, 0.0)
    x_right, _ = yz_to_uv(10.0, 0.0)

    # Reference elevation grid
    for z_grid in (1.0, 2.0, 3.0, 4.0):
        _, gv = yz_to_uv(0.0, z_grid)
        svg.line(
            x_left,
            gv,
            x_right,
            gv,
            stroke=palette.grid_line,
            stroke_width=1.0,
            dash="4 4",
        )
        svg.text(
            x_left - 12,
            gv,
            f"{z_grid:.0f}m",
            fill=palette.text_muted,
            size=9.5,
            mono=True,
            anchor="end",
        )

    # Court floor, service lines, net, and translucent 3m glass + 1m mesh back walls
    svg.line(
        x_left,
        y_floor,
        x_right,
        y_floor,
        stroke=palette.court_line_fg,
        stroke_width=2.4,
    )
    for x_wall, slab_x in [(x_left, x_left - 8.0), (x_right, x_right)]:
        svg.rect(
            slab_x,
            y_floor - 3.0 * sz,
            8.0,
            3.0 * sz,
            fill=palette.glass_fill,
            stroke=palette.glass_stroke,
            stroke_width=1.2,
            opacity=0.35,
        )
        svg.line(
            x_wall,
            y_floor,
            x_wall,
            y_floor - 3.0 * sz,
            stroke=palette.glass_stroke,
            stroke_width=3.2,
        )
        svg.line(
            x_wall,
            y_floor - 3.0 * sz,
            x_wall,
            y_floor - 4.0 * sz,
            stroke=palette.fence_stroke,
            stroke_width=2.5,
            dash="4 3",
        )
    svg.line(
        x0,
        y_floor,
        x0,
        y_floor - 0.88 * sz,
        stroke=palette.accent_tertiary,
        stroke_width=3.2,
    )

    for y_tick, lbl, anc, dx in [
        (-10.0, "Y = -10m (Near)", "start", -8.0),
        (-7.0, "-7m", "middle", 0.0),
        (0.0, "Y = 0m (Net 0.88m)", "middle", 0.0),
        (7.0, "+7m", "middle", 0.0),
        (10.0, "Y = +10m (Far)", "end", 8.0),
    ]:
        tu, _ = yz_to_uv(y_tick, 0.0)
        svg.text(
            tu + dx,
            y_floor + 20,
            lbl,
            fill=palette.text_muted,
            size=9.5,
            mono=True,
            anchor=anc,
        )

    for idx, (label, init_state, dur, color, tail_lbl, tail_off) in enumerate(shots):
        traj = engine.simulate(init_state, duration=dur, dt=0.002)
        pos = traj.positions
        uv_raw = np.column_stack([x0 + pos[:, 1] * sx, y_floor - pos[:, 2] * sz])

        bounce_idxs: list[int] = []
        for b in traj.bounces:
            b_idx = int(np.argmin(np.abs(traj.timestamps - b.timestamp)))
            bounce_idxs.append(b_idx)

        uv_clean = simplify_trajectory_preserve_cusps(uv_raw, bounce_idxs, epsilon=0.35)
        svg.polyline(
            uv_clean,
            stroke=color,
            stroke_width=2.4,
            marker_end=(
                "arrow-danger"
                if color == palette.accent_danger
                else (
                    "arrow-secondary"
                    if color == palette.accent_secondary
                    else "arrow-primary"
                )
            ),
        )

        svg.circle(
            uv_raw[0, 0], uv_raw[0, 1], 4.5, fill=color, stroke=palette.bg_canvas
        )
        for b in traj.bounces:
            bu, bv = yz_to_uv(b.position[1], b.position[2])
            svg.circle(
                bu, bv, 5.0, fill=palette.bg_canvas, stroke=color, stroke_width=2.2
            )

        if tail_lbl == "Low Skid":
            bu_last, bv_last = yz_to_uv(
                traj.bounces[-1].position[1], traj.bounces[-1].position[2]
            )
            svg.line(
                x_right + 8,
                bv_last,
                x_right + 17,
                bv_last,
                stroke=color,
                stroke_width=1.2,
                dash="2 2",
            )
            svg.text(
                x_right + 20,
                bv_last,
                tail_lbl,
                fill=color,
                size=8.8,
                weight="700",
                mono=True,
                anchor="start",
            )
        else:
            tx_end, ty_end = uv_clean[-1]
            svg.text(
                tx_end + tail_off[0],
                ty_end + tail_off[1],
                tail_lbl,
                fill=color,
                size=8.8,
                weight="700",
                mono=True,
            )

        lx = 92.0 + idx * 278.0
        svg.line(lx, 92, lx + 28, 92, stroke=color, stroke_width=2.8)
        svg.text(
            lx + 36,
            92,
            label,
            fill=color,
            size=10.2,
            weight="700",
            mono=True,
            anchor="start",
        )

    return svg.to_xml_string()


def render_physics_rebound_regimes(palette: ThemePalette) -> str:
    """9. 3-panel schematic of Coulomb SLIDING, ROLLING, and DAMPED contact regimes."""
    svg = SvgCanvas(
        960,
        380,
        "PadelKit Impulse Contact Rebound Regimes (ContactRegime)",
        "Comparison of ContactRegime.SLIDING on glass, ContactRegime.ROLLING on sandy turf, and ContactRegime.DAMPED on net/fence.",
        palette,
    )
    svg.header(
        "Impulse Contact Dynamics: Sliding vs. Rolling vs. Damped (ContactRegime)",
        "Analytical Coulomb friction threshold μ_crit determines tangential slip vs. surface grip during impact",
    )

    surf = SurfaceMaterials.fip_standard()
    alpha = BallProperties.fip_standard().inertia_ratio

    panels = [
        (
            "1. ContactRegime.SLIDING",
            f"Tempered Glass (μ={surf.glass_friction:.2f}, e={surf.glass_cor:.2f})",
            "Partial slip impulse; retains spin across contact",
            "J_t = -μ · |J_n| · v̂_slip",
            "|J_t| = μ·|J_n| < |J_roll|  (slip ≠ 0)",
            palette.accent_secondary,
            24.0,
            "sliding",
        ),
        (
            "2. ContactRegime.ROLLING",
            f"Sandy Turf Floor (μ={surf.floor_friction:.2f}, e={surf.floor_cor:.2f})",
            "Full surface grip; backspin reverses into forward roll",
            "v_t' + ω' × (-R·n̂) = 0  (Grip Lock)",
            f"α = I/(mR²) ≈ {alpha:.2f}  |  |J_t| ≤ μ·|J_n|",
            palette.accent_primary,
            336.0,
            "rolling",
        ),
        (
            "3. ContactRegime.DAMPED",
            f"Net & Fence Mesh (e_net={surf.net_damping:.2f}, e_fence={surf.fence_cor:.2f})",
            "Viscoelastic mesh absorbs normal impact velocity",
            "v_n' = -net_damping · v_n",
            "v_t' = 0.70·v_t  (Deadened drop)",
            palette.accent_danger,
            648.0,
            "damped",
        ),
    ]

    for title, sub, desc, formula1, formula2, col, px, mode in panels:
        svg.rect(
            px,
            64,
            288,
            292,
            fill=palette.bg_panel,
            stroke=palette.border,
            rx=10,
        )
        svg.line(px + 14, 65, px + 96, 65, stroke=col, stroke_width=2.6)
        svg.text(
            px + 16,
            86,
            title,
            fill=col,
            size=11.5,
            weight="700",
            mono=True,
            anchor="start",
        )
        svg.text(
            px + 16,
            105,
            sub,
            fill=palette.text_primary,
            size=9.5,
            weight="600",
            mono=True,
            anchor="start",
        )
        svg.text(
            px + 16,
            122,
            desc,
            fill=palette.text_muted,
            size=9.2,
            anchor="start",
        )

        if mode in ("sliding", "rolling"):
            surf_y = 252.0
            hx = px + 144.0
            if mode == "sliding":
                # Tempered glass slab with translucent sky tint & specular shine lines
                svg.rect(
                    px + 20,
                    surf_y,
                    248,
                    16,
                    fill=palette.glass_fill,
                    stroke=palette.glass_stroke,
                    stroke_width=1.8,
                    opacity=0.45,
                    rx=3,
                )
                for sx_off in (36, 56, 240):
                    svg.line(
                        px + sx_off,
                        surf_y + 13,
                        px + sx_off + 12,
                        surf_y + 3,
                        stroke=palette.glass_stroke,
                        stroke_width=1.2,
                        opacity=0.65,
                    )
                in_p = (hx - 74, 174)
                out_p = (hx + 82, 186)
            else:
                # Sandy turf floor speckled with aggregate dots
                svg.rect(
                    px + 20,
                    surf_y,
                    248,
                    16,
                    fill=palette.court_floor,
                    stroke=palette.court_line_fg,
                    stroke_width=1.6,
                    rx=3,
                )
                for dx in (*range(32, 138, 18), *range(244, 258, 12)):
                    svg.circle(
                        px + dx,
                        surf_y + 5 + (dx % 3) * 3,
                        1.1,
                        fill=palette.text_muted,
                        opacity=0.55,
                    )
                in_p = (hx - 74, 166)
                out_p = (hx + 66, 206)

            # Normal vector n-hat
            svg.line(
                hx,
                surf_y,
                hx,
                surf_y - 74,
                stroke=palette.text_muted,
                stroke_width=1.3,
                dash="3 3",
                marker_end="arrow-muted",
            )
            svg.text(
                hx + 11,
                surf_y - 68,
                "n̂",
                fill=palette.text_muted,
                size=10.0,
                mono=True,
            )
            # Incident & exit velocities
            svg.line(
                in_p[0],
                in_p[1],
                hx - 8,
                surf_y - 10,
                stroke=palette.text_muted,
                stroke_width=2.0,
                marker_end="arrow-muted",
            )
            svg.text(
                in_p[0] + 6,
                in_p[1] - 11,
                "v_in",
                fill=palette.text_muted,
                size=9.5,
                mono=True,
            )
            svg.line(
                hx + 8,
                surf_y - 10,
                out_p[0],
                out_p[1],
                stroke=col,
                stroke_width=2.4,
                marker_end=(
                    "arrow-secondary" if mode == "sliding" else "arrow-primary"
                ),
            )
            svg.text(
                out_p[0] - 8,
                out_p[1] - 12,
                "v_out",
                fill=col,
                size=10.0,
                weight="700",
                mono=True,
            )
            # Ball & regime-specific tangential cue
            svg.circle(
                hx,
                surf_y - 12,
                11.0,
                fill=palette.bg_canvas,
                stroke=col,
                stroke_width=2.2,
            )
            if mode == "sliding":
                # Tangential slip arrow along interface
                svg.line(
                    hx - 24,
                    surf_y + 8,
                    hx + 28,
                    surf_y + 8,
                    stroke=palette.accent_secondary,
                    stroke_width=1.8,
                    marker_end="arrow-secondary",
                )
                svg.text(
                    hx + 54,
                    surf_y + 8,
                    "slip > 0",
                    fill=palette.accent_secondary,
                    size=8.5,
                    weight="700",
                    mono=True,
                )
            else:
                # Forward-rolling grip spin arc over exit path
                roll_arc = (
                    f"M {_fmt(hx - 14)} {_fmt(surf_y - 24)} "
                    f"A 16 16 0 0 1 {_fmt(hx + 16)} {_fmt(surf_y - 22)}"
                )
                svg.path(
                    roll_arc,
                    stroke=palette.accent_primary,
                    stroke_width=1.8,
                    marker_end="arrow-primary",
                )
                svg.text(
                    hx + 54,
                    surf_y + 8,
                    "v_grip = 0",
                    fill=palette.accent_primary,
                    size=8.5,
                    weight="700",
                    mono=True,
                )
        else:
            # Panel 3: Vertical bowed mesh net + deadened vertical drop
            floor_y = 262.0
            net_x = px + 194.0
            svg.line(
                px + 24,
                floor_y,
                px + 264,
                floor_y,
                stroke=palette.court_line_fg,
                stroke_width=1.8,
            )
            # Tensioned vertical mesh cord visibly bowing rightward on impact
            svg.path(
                f"M {_fmt(net_x)} 148 Q {_fmt(net_x + 20)} 202 {_fmt(net_x)} {_fmt(floor_y)}",
                stroke=palette.accent_danger,
                stroke_width=2.6,
                dash="4 2",
            )
            svg.circle(net_x, 148, 3.5, fill=palette.pillar_stroke)
            svg.text(
                net_x + 18,
                156,
                "Net Mesh",
                fill=palette.text_muted,
                size=8.8,
                mono=True,
                anchor="start",
            )
            # Incident ball vector hitting net
            hx_net = net_x + 2.0
            hy_net = 200.0
            svg.line(
                px + 56,
                172,
                hx_net - 12,
                hy_net - 3,
                stroke=palette.text_muted,
                stroke_width=2.2,
                marker_end="arrow-muted",
            )
            svg.text(
                px + 72,
                160,
                "v_in",
                fill=palette.text_muted,
                size=9.5,
                mono=True,
            )
            # Deadened rebound dropping steep & slow
            svg.line(
                hx_net - 10,
                hy_net + 10,
                hx_net - 36,
                floor_y - 10,
                stroke=palette.accent_danger,
                stroke_width=2.4,
                marker_end="arrow-danger",
            )
            svg.text(
                hx_net - 58,
                floor_y - 14,
                "v_out",
                fill=palette.accent_danger,
                size=10.0,
                weight="700",
                mono=True,
            )
            svg.circle(
                hx_net - 6,
                hy_net,
                11.0,
                fill=palette.bg_canvas,
                stroke=col,
                stroke_width=2.2,
            )

        svg.line(
            px + 14,
            284,
            px + 274,
            284,
            stroke=palette.border,
            stroke_width=1.0,
        )
        svg.text(
            px + 144,
            306,
            formula1,
            fill=col,
            size=9.6,
            weight="700",
            mono=True,
        )
        svg.text(
            px + 144,
            326,
            formula2,
            fill=palette.text_muted,
            size=8.6,
            mono=True,
        )

    return svg.to_xml_string()


def render_serving_rotations(palette: ThemePalette) -> str:
    """10. Deuce/Ad service boxes, diagonal serve trajectories, and 4-game rotation cycle."""
    svg = SvgCanvas(
        960,
        440,
        "PadelKit Serving Geometry & 4-Game Rotation Cycle (ServingEngine)",
        "2D court serving quadrants (Deuce right vs Ad left) and 4-game server rotation computed by ServingEngine.",
        palette,
    )
    svg.header(
        "Serving Geometry & 4-Game Rotation State Machine (ServingEngine)",
        "Even points (0, 2, 4...): court_side = 'right' (Deuce)  |  Odd points (1, 3, 5...): court_side = 'left' (Ad)",
    )
    svg.line(572, 68, 572, 412, stroke=palette.border, stroke_width=1.0)

    cx0, cy0 = 64.0, 134.0
    scale = 22.0  # 20m -> 440px, 10m -> 220px
    cw, ch = 20.0 * scale, 10.0 * scale
    svc = 3.0 * scale

    svg.text(
        cx0 + cw * 0.25,
        112,
        "SERVING HALF",
        fill=palette.text_muted,
        size=9.5,
        weight="700",
        mono=True,
    )
    svg.text(
        cx0 + cw * 0.50,
        112,
        "NET (0.88m)",
        fill=palette.accent_tertiary,
        size=9.5,
        weight="700",
        mono=True,
    )
    svg.text(
        cx0 + cw * 0.75,
        112,
        "RECEIVING HALF",
        fill=palette.text_muted,
        size=9.5,
        weight="700",
        mono=True,
    )

    svg.rect(
        cx0,
        cy0,
        cw,
        ch,
        fill=palette.court_floor,
        stroke=palette.court_line_fg,
        stroke_width=2.0,
    )
    svg.rect(
        cx0 + cw / 2,
        cy0,
        cw / 2 - svc,
        ch / 2,
        fill=palette.accent_primary,
        opacity=0.18,
    )
    svg.rect(
        cx0 + cw / 2,
        cy0 + ch / 2,
        cw / 2 - svc,
        ch / 2,
        fill=palette.accent_secondary,
        opacity=0.18,
    )

    svg.line(
        cx0 + svc,
        cy0,
        cx0 + svc,
        cy0 + ch,
        stroke=palette.court_line_fg,
        stroke_width=1.6,
    )
    svg.line(
        cx0 + cw - svc,
        cy0,
        cx0 + cw - svc,
        cy0 + ch,
        stroke=palette.court_line_fg,
        stroke_width=1.6,
    )
    svg.line(
        cx0 + svc,
        cy0 + ch / 2,
        cx0 + cw - svc,
        cy0 + ch / 2,
        stroke=palette.court_line_fg,
        stroke_width=1.6,
    )
    svg.line(
        cx0 + cw / 2,
        cy0 - 6,
        cx0 + cw / 2,
        cy0 + ch + 6,
        stroke=palette.accent_tertiary,
        stroke_width=2.4,
        dash="4 3",
    )

    # Box quadrant labels inside receiving boxes
    svg.text(
        cx0 + cw * 0.67,
        cy0 + 18,
        "Deuce Box (0, 2, 4)",
        fill=palette.accent_primary,
        size=8.8,
        weight="700",
        mono=True,
    )
    svg.text(
        cx0 + cw * 0.67,
        cy0 + ch - 18,
        "Ad Box (1, 3, 5)",
        fill=palette.accent_secondary,
        size=8.8,
        weight="700",
        mono=True,
    )

    # Diagonal serves: server stance dot -> bounce target ring inside diagonal service box
    s_deuce = (cx0 + 44, cy0 + ch * 0.78)
    b_deuce = (cx0 + cw * 0.68, cy0 + ch * 0.28)
    svg.line(
        s_deuce[0],
        s_deuce[1],
        b_deuce[0] - 6,
        b_deuce[1] + 2,
        stroke=palette.accent_primary,
        stroke_width=2.2,
        marker_end="arrow-primary",
    )
    svg.circle(
        b_deuce[0],
        b_deuce[1],
        5.5,
        fill=palette.bg_canvas,
        stroke=palette.accent_primary,
        stroke_width=2.0,
    )
    svg.callout_badge(
        s_deuce[0],
        s_deuce[1],
        "S (right)",
        color=palette.accent_primary,
        offset=(12, 22),
    )
    svg.callout_badge(
        cx0 + cw * 0.88,
        cy0 + ch * 0.24,
        "R (right)",
        color=palette.accent_primary,
    )

    s_ad = (cx0 + 44, cy0 + ch * 0.22)
    b_ad = (cx0 + cw * 0.68, cy0 + ch * 0.72)
    svg.line(
        s_ad[0],
        s_ad[1],
        b_ad[0] - 6,
        b_ad[1] - 2,
        stroke=palette.accent_secondary,
        stroke_width=2.2,
        dash="5 3",
        marker_end="arrow-secondary",
    )
    svg.circle(
        b_ad[0],
        b_ad[1],
        5.5,
        fill=palette.bg_canvas,
        stroke=palette.accent_secondary,
        stroke_width=2.0,
    )
    svg.callout_badge(
        s_ad[0],
        s_ad[1],
        "S (left)",
        color=palette.accent_secondary,
        offset=(12, -22),
    )
    svg.callout_badge(
        cx0 + cw * 0.88,
        cy0 + ch * 0.76,
        "R (left)",
        color=palette.accent_secondary,
    )

    svg.text(
        cx0 + cw / 2,
        384,
        "First bounce must land inside diagonally opposite service box",
        fill=palette.text_muted,
        size=9.2,
        mono=True,
    )

    team_a = Team(
        id=TeamId.A,
        name="Team A",
        player1=Player("A1 (Right)", side="right"),
        player2=Player("A2 (Left)", side="left"),
    )
    team_b = Team(
        id=TeamId.B,
        name="Team B",
        player1=Player("B1 (Right)", side="right"),
        player2=Player("B2 (Left)", side="left"),
    )
    teams = {TeamId.A: team_a, TeamId.B: team_b}
    cfg = MatchConfiguration(starting_server_team=TeamId.A)
    s_engine = ServingEngine(cfg)

    svg.text(
        598,
        88,
        "4-Game ServingEngine Rotation Cycle",
        fill=palette.text_primary,
        size=12.0,
        weight="700",
        anchor="start",
    )

    for g_idx in range(4):
        st_even = s_engine.calculate_serving_state(
            teams=teams,
            points_played=0,
            total_games=g_idx,
            current_set=1,
            games_a=(g_idx + 1) // 2,
            games_b=g_idx // 2,
            in_tiebreak=False,
            in_super_tiebreak=False,
            tiebreak_starter=None,
        )
        assert (
            st_even is not None
            and st_even.player is not None
            and st_even.receiver is not None
        )
        ry = 108.0 + g_idx * 72.0
        col = (
            palette.accent_primary
            if st_even.team == TeamId.A
            else palette.accent_secondary
        )
        svg.rect(
            598,
            ry,
            290,
            52,
            fill=palette.bg_panel,
            stroke=col,
            stroke_width=1.4,
            rx=8,
        )
        svg.text(
            610,
            ry + 18,
            f"Game {g_idx + 1} (games={g_idx}) -> Team {st_even.team.value}",
            fill=col,
            size=10.2,
            weight="700",
            mono=True,
            anchor="start",
        )
        svg.text(
            610,
            ry + 37,
            f"Srv: {st_even.player.name} | Recv: {st_even.receiver.name}",
            fill=palette.text_muted,
            size=9.0,
            mono=True,
            anchor="start",
        )
        if g_idx < 3:
            svg.line(
                743,
                ry + 53,
                743,
                ry + 69,
                stroke=palette.text_muted,
                stroke_width=1.5,
                marker_end="arrow-muted",
            )

    # Cyclic return loop from Game 4 back to Game 1
    svg.polyline(
        [(888, 350), (912, 350), (912, 134), (892, 134)],
        stroke=palette.accent_primary,
        stroke_width=1.6,
        dash="4 3",
        marker_end="arrow-primary",
    )
    svg.text(
        743,
        398,
        "Repeats modulo 4 every 4 games",
        fill=palette.accent_primary,
        size=9.0,
        weight="600",
        mono=True,
    )

    return svg.to_xml_string()


# --------------------------------------------------------------------------- #
# Registry & CLI Entrypoint
# --------------------------------------------------------------------------- #

SCHEMATIC_GENERATORS: dict[str, Callable[[ThemePalette], str]] = {
    "court-landmarks-3d": render_court_landmarks_3d,
    "court-dimensions": render_court_dimensions,
    "court-coordinate-systems": render_court_coordinate_systems,
    "camera-frustum-3d": render_camera_frustum_3d,
    "camera-sensor-projection": render_camera_sensor_projection,
    "camera-distortion-grid": render_camera_distortion_grid,
    "physics-forces-9d": render_physics_forces_9d,
    "physics-trajectories": render_physics_trajectories,
    "physics-rebound-regimes": render_physics_rebound_regimes,
    "serving-rotations": render_serving_rotations,
}

MAX_SVG_BYTES = 45_000


def build_all_schematics_in_memory() -> dict[str, str]:
    """Generate all 20 themed schematic SVG strings (`{name}-{light|dark}.svg`)."""
    outputs: dict[str, str] = {}
    for name, fn in SCHEMATIC_GENERATORS.items():
        for palette in (LIGHT_PALETTE, DARK_PALETTE):
            filename = f"{name}-{palette.mode}.svg"
            xml_str = fn(palette)
            ET.fromstring(xml_str)
            encoded = xml_str.encode("utf-8")
            if len(encoded) > MAX_SVG_BYTES:
                raise ValueError(
                    f"{filename} exceeds {MAX_SVG_BYTES} bytes ({len(encoded)} bytes)"
                )
            outputs[filename] = xml_str
    return outputs


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate deterministic theme-aware SVG schematics for PadelKit docs."
    )
    default_out = (
        Path(__file__).resolve().parent.parent / "docs" / "images" / "schematics"
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=default_out,
        help="Target directory for generated SVG schematics.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify that existing SVG files on disk match generated output without writing.",
    )
    args = parser.parse_args(argv)

    out_dir: Path = args.out_dir
    generated = build_all_schematics_in_memory()

    if args.check:
        mismatches: list[str] = []
        for filename, expected_xml in generated.items():
            file_path = out_dir / filename
            if not file_path.exists():
                mismatches.append(f"Missing file: {file_path}")
                continue
            actual_bytes = file_path.read_bytes()
            expected_bytes = expected_xml.encode("utf-8")
            if (
                hashlib.sha256(actual_bytes).hexdigest()
                != hashlib.sha256(expected_bytes).hexdigest()
            ):
                mismatches.append(f"Out-of-date schematic: {file_path}")
        if mismatches:
            for msg in mismatches:
                print(msg, file=sys.stderr)
            return 1
        print(f"Verified {len(generated)} SVG schematics in {out_dir} (100% in sync).")
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    for filename, xml_str in generated.items():
        (out_dir / filename).write_text(xml_str, encoding="utf-8")

    fallback_path = out_dir.parent / "court-landmarks-3d.svg"
    fallback_path.write_text(generated["court-landmarks-3d-dark.svg"], encoding="utf-8")
    print(f"Generated {len(generated)} SVG schematics in {out_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
