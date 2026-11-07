# ruff: noqa: E501
"""Zero-dependency SVG technical schematic generator for PadelKit documentation.

Computes 2D orthographic and 3D perspective/axonometric vector schematics directly
from PadelKit's domain classes (`Court`, `Camera`, `CameraDistortion`,
`BallPhysicsEngine`, and `ServingEngine`) using only Python's standard library
and NumPy. Outputs deterministic `-light.svg` and `-dark.svg` pairs into
`docs/images/schematics/`.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import sys
import xml.etree.ElementTree as ET
from collections.abc import Callable, Sequence
from dataclasses import dataclass
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
from padelkit.physics import BallPhysicsEngine, BallState
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
    fence_stroke: str
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
    court_floor="#f1f5f9",
    court_line_fg="#0f172a",
    court_line_bg="#94a3b8",
    glass_fill="#e0f2fe",
    glass_stroke="#0284c7",
    fence_stroke="#64748b",
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
    court_line_bg="#475569",
    glass_fill="#0c4a6e",
    glass_stroke="#38bdf8",
    fence_stroke="#64748b",
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
    """Format a float to 2 decimal places while rejecting NaN or infinite values."""
    fval = float(val)
    if not math.isfinite(fval):
        raise ValueError(f"Non-finite coordinate in SVG schematic: {val}")
    if abs(fval) < 1e-4:
        fval = 0.0
    return f"{fval:.2f}"


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
                    "markerWidth": "6",
                    "markerHeight": "6",
                    "orient": "auto-start-reverse",
                },
            )
            ET.SubElement(
                marker,
                "path",
                {"d": "M 0 1.5 L 9 5 L 0 8.5 z", "fill": color},
            )

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
        return ET.SubElement(self.root, "rect", attrs)

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
        return ET.SubElement(self.root, "line", attrs)

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
        return ET.SubElement(self.root, "polyline", attrs)

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
        return ET.SubElement(self.root, "polygon", attrs)

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
        return ET.SubElement(self.root, "circle", attrs)

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
        return ET.SubElement(self.root, "path", attrs)

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
        el = ET.SubElement(self.root, "text", attrs)
        el.text = content
        return el

    def header(self, title: str, subtitle: str) -> None:
        self.text(
            28,
            28,
            title,
            fill=self.palette.text_primary,
            size=15,
            weight="700",
            anchor="start",
        )
        self.text(
            28,
            48,
            subtitle,
            fill=self.palette.text_muted,
            size=11.5,
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
        label_offset: tuple[float, float] = (0.0, -10.0),
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
        tw = max(len(label) * 6.8 + 10.0, 34.0)
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
            size=10.5,
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
        bw = max(len(badge_text) * 6.6 + 10.0, 20.0)
        self.rect(
            bx - bw / 2,
            by - 9.5,
            bw,
            19.0,
            fill=self.palette.badge_bg,
            stroke=color,
            stroke_width=1.5,
            rx=9.5,
        )
        self.text(
            bx,
            by + 0.5,
            badge_text,
            fill=color,
            size=10.0,
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
                size=10.0,
                weight="600",
                mono=True,
                anchor=anchor,
            )

    def to_xml_string(self) -> str:
        ET.indent(self.root, space="  ")
        xml_bytes = ET.tostring(self.root, encoding="unicode")
        return xml_bytes + "\n"


# --------------------------------------------------------------------------- #
# 3D-to-2D Projection & Polyline Simplification Utilities
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
    epsilon: float = 0.50,
) -> np.ndarray:
    """Simplify a 2D trajectory while preserving exact sharp vertices at bounces."""
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
    """1. 3D perspective wireframe of all 17 standardized FIP court landmarks."""
    svg = SvgCanvas(
        960,
        540,
        "PadelKit 17 Standardized 3D Court Landmarks",
        "Axonometric 3D view of the 17 CourtLandmark positions: 1-13 on floor (Z=0m) and 14-17 on back walls (Z=4.0m).",
        palette,
    )
    svg.header(
        "17 Standardized 3D Court Landmarks (CourtLandmark)",
        "Floor landmarks 1–13 (Z = 0.0 m)  |  Back-wall top corners 14–17 (Z = 4.0 m)  |  CoordinateSystem.CENTERED",
    )
    svg.rect(
        24,
        64,
        615,
        452,
        fill=palette.bg_panel,
        stroke=palette.border,
        rx=10,
    )
    svg.rect(
        652,
        64,
        284,
        452,
        fill=palette.bg_panel,
        stroke=palette.border,
        rx=10,
    )

    court = Court.fip_standard()
    pts_3d = court.landmarks_3d(CoordinateSystem.CENTERED)

    cam = Camera(
        intrinsics=CameraIntrinsics.from_fov(
            width_px=615, height_px=452, horizontal_fov_deg=44.0
        ),
        extrinsics=CameraExtrinsics.from_look_at(
            position=(-13.5, -18.8, 11.2),
            target=(0.2, 0.2, 1.0),
        ),
    )

    def proj(xyz: Sequence[float]) -> tuple[float, float]:
        uv, _ = cam.project_points(np.asarray([xyz], dtype=np.float64))
        return float(uv[0, 0]) + 24.0, float(uv[0, 1]) + 64.0

    # Court floor polygon
    fl_poly = [
        proj((-5.0, -10.0, 0.0)),
        proj((5.0, -10.0, 0.0)),
        proj((5.0, 10.0, 0.0)),
        proj((-5.0, 10.0, 0.0)),
    ]
    svg.polygon(
        fl_poly,
        fill=palette.court_floor,
        stroke=palette.court_line_fg,
        stroke_width=1.8,
    )

    # Back-to-front enclosure wireframe (far walls dashed/muted, near walls crisp)
    far_back_wall = [
        proj((-5.0, 10.0, 0.0)),
        proj((5.0, 10.0, 0.0)),
        proj((5.0, 10.0, 4.0)),
        proj((-5.0, 10.0, 4.0)),
    ]
    svg.polygon(
        far_back_wall,
        fill=palette.glass_fill,
        fill_opacity=0.20,
        stroke=palette.glass_stroke,
        stroke_width=1.3,
        dash="5 4",
    )

    # Side walls (4m corner steps + 3m center enclosure profile)
    for x_side, is_bg in [(5.0, True), (-5.0, False)]:
        profile_3d = [
            (x_side, -10.0, 0.0),
            (x_side, -10.0, 4.0),
            (x_side, -8.0, 4.0),
            (x_side, -8.0, 3.0),
            (x_side, 8.0, 3.0),
            (x_side, 8.0, 4.0),
            (x_side, 10.0, 4.0),
            (x_side, 10.0, 0.0),
        ]
        svg.polygon(
            [proj(p) for p in profile_3d],
            fill=palette.glass_fill,
            fill_opacity=0.10 if is_bg else 0.16,
            stroke=palette.court_line_bg if is_bg else palette.glass_stroke,
            stroke_width=1.1 if is_bg else 1.5,
            dash="4 4" if is_bg else None,
        )

    # Floor service lines and center line
    for p1, p2 in [
        ((-5.0, -7.0, 0.0), (5.0, -7.0, 0.0)),
        ((-5.0, 7.0, 0.0), (5.0, 7.0, 0.0)),
        ((0.0, -7.0, 0.0), (0.0, 7.0, 0.0)),
    ]:
        u1, v1 = proj(p1)
        u2, v2 = proj(p2)
        svg.line(u1, v1, u2, v2, stroke=palette.court_line_fg, stroke_width=1.4)

    # Net plane at Y = 0
    net_poly = [
        proj((-5.0, 0.0, 0.0)),
        proj((5.0, 0.0, 0.0)),
        proj((5.0, 0.0, 0.92)),
        proj((0.0, 0.0, 0.88)),
        proj((-5.0, 0.0, 0.92)),
    ]
    svg.polygon(
        net_poly,
        fill=palette.accent_secondary,
        fill_opacity=0.18,
        stroke=palette.accent_secondary,
        stroke_width=1.8,
    )

    # Near back wall (Z = 4.0m)
    near_back_wall = [
        proj((-5.0, -10.0, 0.0)),
        proj((5.0, -10.0, 0.0)),
        proj((5.0, -10.0, 4.0)),
        proj((-5.0, -10.0, 4.0)),
    ]
    svg.polygon(
        near_back_wall,
        fill=palette.glass_fill,
        fill_opacity=0.22,
        stroke=palette.glass_stroke,
        stroke_width=1.8,
    )

    # Vertical dashed elevation guides for the 4 wall-top landmarks (14-17)
    for corner_xy in [(-5.0, -10.0), (5.0, -10.0), (-5.0, 10.0), (5.0, 10.0)]:
        u_lo, v_lo = proj((corner_xy[0], corner_xy[1], 0.0))
        u_hi, v_hi = proj((corner_xy[0], corner_xy[1], 4.0))
        svg.line(
            u_lo,
            v_lo,
            u_hi,
            v_hi,
            stroke=palette.accent_secondary,
            stroke_width=1.4,
            dash="3 3",
        )

    # Draw numbered badges 1..17 with clean non-overlapping offsets
    offsets: dict[int, tuple[float, float]] = {
        1: (-18, 14),
        2: (16, 14),
        3: (-20, 8),
        4: (0, 16),
        5: (20, 8),
        6: (-22, 4),
        7: (0, 16),
        8: (22, 4),
        9: (-20, -6),
        10: (0, -15),
        11: (20, -6),
        12: (-18, -14),
        13: (18, -14),
        14: (-20, -14),
        15: (20, -14),
        16: (-20, -14),
        17: (20, -14),
    }

    members = list(CourtLandmark)
    svg.text(
        668,
        88,
        "INDEX  COURT LANDMARK ENUM        (X, Y, Z)",
        fill=palette.text_muted,
        size=9.5,
        weight="700",
        mono=True,
        anchor="start",
    )

    for idx, landmark in enumerate(members, start=1):
        xyz = pts_3d[landmark.value]
        u, v = proj(xyz)
        is_wall = idx >= 14
        color = palette.accent_secondary if is_wall else palette.accent_primary
        dx, dy = offsets[idx]
        svg.callout_badge(u, v, str(idx), color=color, offset=(dx, dy))

        # Legend row on right panel
        row_y = 96 + idx * 23.8
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
    """2. 2D FIP plan blueprint + 3D side-wall V1/V2 and net height elevation."""
    svg = SvgCanvas(
        960,
        520,
        "PadelKit Official FIP CourtDimensions Blueprint",
        "2D top-down dimension schematic and side/net elevation profile for CourtDimensions.",
        palette,
    )
    svg.header(
        "Official FIP CourtDimensions Blueprint (Meters)",
        "length = 20.0m  |  width = 10.0m  |  service_line_distance_from_back = 3.0m  |  net = 0.88m / 0.92m",
    )

    court = Court.fip_standard()
    dims = court.dimensions

    # Left panel: Horizontal 2D Court Plan (Length along X, Width along Y)
    svg.rect(
        24,
        64,
        550,
        432,
        fill=palette.bg_panel,
        stroke=palette.border,
        rx=10,
    )
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

    cx0, cy0 = 76.0, 145.0
    scale = 21.0  # 20m -> 420px, 10m -> 210px
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

    # Dimension arrows
    svg.dimension_arrow(
        cx0,
        cy0 - 26,
        cx0 + cw,
        cy0 - 26,
        f"length = {dims.length:.1f} m",
        marker_key="primary",
        color=palette.accent_primary,
        label_offset=(0, 0),
    )
    svg.dimension_arrow(
        cx0 + cw + 34,
        cy0,
        cx0 + cw + 34,
        cy0 + ch,
        f"width = {dims.width:.1f} m",
        marker_key="secondary",
        color=palette.accent_secondary,
        label_offset=(0, 0),
    )
    svg.dimension_arrow(
        cx0,
        cy0 + ch + 30,
        cx0 + svc_px,
        cy0 + ch + 30,
        f"service_line = {dims.service_line_distance_from_back:.1f} m",
        marker_key="tertiary",
        color=palette.accent_tertiary,
        label_offset=(36, 0),
    )
    svg.dimension_arrow(
        cx0 + svc_px,
        cy0 + ch + 62,
        cx0 + cw / 2,
        cy0 + ch + 62,
        "service box = 7.0 m",
        marker_key="muted",
        color=palette.text_muted,
        label_offset=(0, 0),
    )

    # Right panel top: Side Wall Profile (V1 3.0m vs V2 4.0m)
    svg.rect(
        590,
        64,
        346,
        210,
        fill=palette.bg_panel,
        stroke=palette.border,
        rx=10,
    )
    svg.text(
        608,
        88,
        "B. WALL ELEVATION (V1 vs V2)",
        fill=palette.text_primary,
        size=11.5,
        weight="700",
        mono=True,
        anchor="start",
    )

    ex0, ey_floor = 626.0, 234.0
    escale_x = 12.5  # 20m -> 250px
    escale_z = 26.0  # 4m -> 104px
    w_len = 20.0 * escale_x
    h_4m = dims.back_wall_height * escale_z
    h_3m = dims.side_wall_height * escale_z
    step_2m = 2.0 * escale_x

    # V2 full 4.0m dashed upper envelope
    svg.rect(
        ex0,
        ey_floor - h_4m,
        w_len,
        h_4m,
        fill=palette.glass_fill,
        stroke=palette.accent_secondary,
        stroke_width=1.3,
        opacity=0.25,
        dash="4 3",
    )
    # V1 stepped profile (4m corners, 3m central side wall)
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
        fill=palette.glass_fill,
        fill_opacity=0.35,
        stroke=palette.accent_primary,
        stroke_width=2.0,
    )
    svg.dimension_arrow(
        ex0 + w_len + 24,
        ey_floor - h_4m,
        ex0 + w_len + 24,
        ey_floor,
        "4.0m",
        marker_key="primary",
        color=palette.accent_primary,
        label_offset=(0, 0),
    )
    svg.text(
        ex0 + w_len / 2,
        ey_floor - h_3m - 10,
        "side_wall_height: 3.0m (V1) / 4.0m (V2)",
        fill=palette.text_primary,
        size=9.5,
        weight="600",
        mono=True,
    )
    svg.text(
        ex0 + w_len / 2,
        ey_floor + 16,
        "back_wall_height = 4.0m (Both V1 & V2)",
        fill=palette.text_muted,
        size=9.5,
        mono=True,
    )

    # Right panel bottom: Net Height Profile (0.92m posts vs 0.88m center sag)
    svg.rect(
        590,
        286,
        346,
        210,
        fill=palette.bg_panel,
        stroke=palette.border,
        rx=10,
    )
    svg.text(
        608,
        310,
        "C. NET CATENARY PROFILE (WIDTH = 10.0m)",
        fill=palette.text_primary,
        size=11.5,
        weight="700",
        mono=True,
        anchor="start",
    )

    nx0, ny_floor = 636.0, 456.0
    nw = 250.0
    post_h = 92.0
    center_h = 74.0  # Exaggerated sag for visual clarity of 0.88m vs 0.92m

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
        opacity=0.45,
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
        offset=(18, -18),
    )
    svg.callout_badge(
        nx0 + nw / 2,
        ny_floor - center_h + 7,
        f"center: {dims.net_height_center:.2f}m",
        color=palette.accent_tertiary,
        offset=(0, -22),
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

    for sys_enum, px, title, subtitle in systems:
        svg.rect(
            px,
            64,
            444,
            352,
            fill=palette.bg_panel,
            stroke=palette.border,
            rx=10,
        )
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
        # Render court vertically (Width X horizontal, Length Y vertical upwards)
        cx_mid = px + 222.0
        cy_mid = 256.0
        sx, sy = 15.0, 11.2  # 10m -> 150px, 20m -> 224px

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

        # Service lines and net
        for k_a, k_b, col, dash in [
            ("service_near_left", "service_near_right", palette.court_line_fg, None),
            ("service_far_left", "service_far_right", palette.court_line_fg, None),
            ("service_near_center", "service_far_center", palette.court_line_fg, None),
            ("net_left", "net_right", palette.accent_secondary, "4 3"),
        ]:
            u1, v1 = to_uv(pts[k_a])
            u2, v2 = to_uv(pts[k_b])
            svg.line(u1, v1, u2, v2, stroke=col, stroke_width=1.6, dash=dash)

        # Origin (0, 0) & +X / +Y coordinate axes
        origin_key = (
            "center" if sys_enum is CoordinateSystem.CENTERED else "floor_near_left"
        )
        ox, oy = to_uv(pts[origin_key])
        svg.line(
            ox,
            oy,
            ox + 56,
            oy,
            stroke=palette.accent_danger,
            stroke_width=2.4,
            marker_end="arrow-danger",
        )
        svg.text(
            ox + 68,
            oy,
            "+X",
            fill=palette.accent_danger,
            size=11.0,
            weight="700",
            mono=True,
        )
        svg.line(
            ox,
            oy,
            ox,
            oy - 56,
            stroke=palette.accent_primary,
            stroke_width=2.4,
            marker_end="arrow-primary",
        )
        svg.text(
            ox,
            oy - 68,
            "+Y",
            fill=palette.accent_primary,
            size=11.0,
            weight="700",
            mono=True,
        )
        svg.circle(ox, oy, 5.0, fill=palette.accent_danger, stroke=palette.bg_panel)

        # Key landmark coordinate badges
        for key, off in [
            ("floor_near_left", (-62, 16)),
            ("floor_near_right", (62, 16)),
            ("center", (66, 0)),
            ("floor_far_left", (-62, -16)),
            ("floor_far_right", (62, -16)),
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

    return svg.to_xml_string()


def render_camera_frustum_3d(palette: ThemePalette) -> str:
    """4. 3D court with camera presets, viewing frustum pyramid, and coordinate frames."""
    svg = SvgCanvas(
        960,
        500,
        "PadelKit 3D Camera Frustum & Coordinate Frames",
        "3D perspective schematic of Camera.broadcast_near() frustum pyramid and World/Camera/Sensor coordinate frames.",
        palette,
    )
    svg.header(
        "Projective Camera Frustum & Coordinate Systems (padelkit.camera)",
        "1. World (X, Y, Z)  ->  2. OpenCV Camera (+X right, +Y down, +Z forward)  ->  3. Sensor Pixels (u, v)",
    )
    svg.rect(
        24,
        64,
        580,
        412,
        fill=palette.bg_panel,
        stroke=palette.border,
        rx=10,
    )
    svg.rect(
        618,
        64,
        318,
        412,
        fill=palette.bg_panel,
        stroke=palette.border,
        rx=10,
    )

    court = Court.fip_standard()
    bcast_cam = Camera.broadcast_near(court=court)

    observer = Camera(
        intrinsics=CameraIntrinsics.from_fov(
            width_px=580, height_px=412, horizontal_fov_deg=48.0
        ),
        extrinsics=CameraExtrinsics.from_look_at(
            position=(-16.5, -18.5, 11.5),
            target=(0.0, -2.0, 1.5),
        ),
    )

    def proj(xyz: Sequence[float]) -> tuple[float, float]:
        uv, _ = observer.project_points(np.asarray([xyz], dtype=np.float64))
        return float(uv[0, 0]) + 24.0, float(uv[0, 1]) + 64.0

    # Court floor
    floor_corners = [
        proj((-5.0, -10.0, 0.0)),
        proj((5.0, -10.0, 0.0)),
        proj((5.0, 10.0, 0.0)),
        proj((-5.0, 10.0, 0.0)),
    ]
    svg.polygon(
        floor_corners,
        fill=palette.court_floor,
        stroke=palette.court_line_fg,
        stroke_width=1.8,
    )
    for p1, p2, col in [
        ((-5.0, -7.0, 0.0), (5.0, -7.0, 0.0), palette.court_line_fg),
        ((-5.0, 7.0, 0.0), (5.0, 7.0, 0.0), palette.court_line_fg),
        ((0.0, -7.0, 0.0), (0.0, 7.0, 0.0), palette.court_line_fg),
        ((-5.0, 0.0, 0.0), (5.0, 0.0, 0.0), palette.accent_primary),
    ]:
        svg.line(*proj(p1), *proj(p2), stroke=col, stroke_width=1.4)

    # Frustum geometry from Camera.frustum_corners_world()
    frustum = bcast_cam.frustum_corners_world(near_m=2.2, far_m=15.5)
    cam_pos = bcast_cam.extrinsics.position
    c_uv = proj(cam_pos)
    near_uvs = [proj(p) for p in frustum["near"]]
    far_uvs = [proj(p) for p in frustum["far"]]

    for f_uv in far_uvs:
        svg.line(
            c_uv[0],
            c_uv[1],
            f_uv[0],
            f_uv[1],
            stroke=palette.accent_secondary,
            stroke_width=1.2,
            dash="4 3",
            opacity=0.75,
        )
    svg.polygon(
        far_uvs,
        fill=palette.accent_secondary,
        fill_opacity=0.08,
        stroke=palette.accent_secondary,
        stroke_width=1.4,
        dash="5 3",
    )
    svg.polygon(
        near_uvs,
        fill=palette.accent_secondary,
        fill_opacity=0.24,
        stroke=palette.accent_secondary,
        stroke_width=2.0,
    )

    # Optical axis ray from broadcast_near camera to court center
    center_uv = proj((0.0, 0.0, 0.0))
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
        offset=(0, -22),
    )
    svg.callout_badge(
        center_uv[0],
        center_uv[1],
        "World (0,0,0)",
        color=palette.accent_primary,
        offset=(52, 16),
    )

    # Other camera presets markers
    for label, pos_xyz in [
        ("overhead_zenith", (0.0, 0.0, 12.0)),
        ("corner_near_left", (-4.8, -9.8, 3.6)),
        ("side_net_right", (5.8, 0.0, 2.4)),
    ]:
        pu, pv = proj(pos_xyz)
        svg.circle(pu, pv, 4.5, fill=palette.accent_tertiary, stroke=palette.bg_panel)
        svg.text(
            pu + 8,
            pv - 6,
            label,
            fill=palette.text_muted,
            size=9.5,
            mono=True,
            anchor="start",
        )

    # Right panel: Coordinate frame transformation summary
    frames = [
        (
            "1. World Frame (Meters)",
            "(X, Y, Z) at Court Net Center",
            "+X: Right  |  +Y: Far Wall  |  +Z: Up",
            palette.accent_primary,
            106.0,
        ),
        (
            "2. Camera Frame (OpenCV vs OpenGL)",
            "Extrinsics: R (3×3), t = -R @ C",
            "OpenCV: +X right, +Y down, +Z forward",
            palette.accent_secondary,
            228.0,
        ),
        (
            "3. Image Sensor Plane (Pixels)",
            "Intrinsics Matrix K (fx, fy, cx, cy)",
            "u = fx*(X_c/Z_c)+cx, v = fy*(Y_c/Z_c)+cy",
            palette.accent_tertiary,
            350.0,
        ),
    ]
    for f_title, f_sub, f_axes, f_col, fy in frames:
        svg.rect(
            636,
            fy,
            282,
            92,
            fill=palette.bg_canvas,
            stroke=f_col,
            stroke_width=1.5,
            rx=8,
        )
        svg.text(
            650,
            fy + 24,
            f_title,
            fill=f_col,
            size=11.5,
            weight="700",
            anchor="start",
        )
        svg.text(
            650,
            fy + 46,
            f_sub,
            fill=palette.text_primary,
            size=10.0,
            mono=True,
            anchor="start",
        )
        svg.text(
            650,
            fy + 68,
            f_axes,
            fill=palette.text_muted,
            size=9.5,
            mono=True,
            anchor="start",
        )

    return svg.to_xml_string()


def render_camera_sensor_projection(palette: ThemePalette) -> str:
    """5. 1920x1080 sensor view showing all 17 projected landmarks and principal point."""
    svg = SvgCanvas(
        900,
        500,
        "PadelKit 1080p Sensor Landmark Projection & Intrinsics",
        "2D sensor projection of the 17 CourtLandmark points using Camera.broadcast_near().project_court_landmarks().",
        palette,
    )
    svg.header(
        "Sensor Plane Projection & CameraIntrinsics (1920 × 1080 px)",
        "cam = Camera.broadcast_near()  |  landmarks_px = cam.project_court_landmarks()  |  Principal Point (cx=960, cy=540)",
    )

    sx0, sy0 = 48.0, 82.0
    sw, sh = 640.0, 360.0  # Exact 16:9 scaled from 1920x1080 (scale = 1/3)
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

    # Sensor pixel grid & principal point crosshair (cx, cy)
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

    cx_px = sx0 + 960.0 * scale
    cy_px = sy0 + 540.0 * scale
    svg.line(
        cx_px - 14,
        cy_px,
        cx_px + 14,
        cy_px,
        stroke=palette.accent_danger,
        stroke_width=1.5,
    )
    svg.line(
        cx_px,
        cy_px - 14,
        cx_px,
        cy_px + 14,
        stroke=palette.accent_danger,
        stroke_width=1.5,
    )
    svg.callout_badge(
        cx_px,
        cy_px,
        "(cx, cy)",
        color=palette.accent_danger,
        offset=(-52, -18),
    )

    court = Court.fip_standard()
    cam = Camera.broadcast_near(court=court)
    proj_pts = cam.project_court_landmarks(court=court)

    def to_sensor(name: str) -> tuple[float, float]:
        u, v = proj_pts[name]
        return sx0 + u * scale, sy0 + v * scale

    # Projected court floor & service lines on sensor
    floor_poly = [
        to_sensor("floor_near_left"),
        to_sensor("floor_near_right"),
        to_sensor("floor_far_right"),
        to_sensor("floor_far_left"),
    ]
    svg.polygon(
        floor_poly,
        fill=palette.court_floor,
        stroke=palette.court_line_fg,
        stroke_width=1.8,
    )
    for a, b, col in [
        ("service_near_left", "service_near_right", palette.court_line_fg),
        ("service_far_left", "service_far_right", palette.court_line_fg),
        ("service_near_center", "service_far_center", palette.court_line_fg),
        ("net_left", "net_right", palette.accent_secondary),
        ("floor_near_left", "wall_top_near_left", palette.accent_secondary),
        ("floor_near_right", "wall_top_near_right", palette.accent_secondary),
        ("floor_far_left", "wall_top_far_left", palette.accent_secondary),
        ("floor_far_right", "wall_top_far_right", palette.accent_secondary),
        ("wall_top_near_left", "wall_top_near_right", palette.accent_secondary),
        ("wall_top_far_left", "wall_top_far_right", palette.accent_secondary),
    ]:
        svg.line(*to_sensor(a), *to_sensor(b), stroke=col, stroke_width=1.4)

    for idx, lm in enumerate(CourtLandmark, start=1):
        u_s, v_s = to_sensor(lm.value)
        col = palette.accent_secondary if idx >= 14 else palette.accent_primary
        svg.circle(u_s, v_s, 4.5, fill=col, stroke=palette.bg_panel)
        svg.text(
            u_s,
            v_s - 9,
            str(idx),
            fill=col,
            size=9.5,
            weight="700",
            mono=True,
        )

    # Pixel axes (0,0) top-left
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
        sx0 + 82,
        sy0 - 8,
        "+u (width_px = 1920)",
        fill=palette.accent_tertiary,
        size=10.0,
        weight="700",
        mono=True,
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
        sx0 - 10,
        sy0 + 74,
        "+v",
        fill=palette.accent_tertiary,
        size=10.0,
        weight="700",
        mono=True,
    )

    # Right callout panel: Calibration matrix K & unprojection
    svg.rect(
        706,
        82,
        170,
        360,
        fill=palette.bg_panel,
        stroke=palette.border,
        rx=8,
    )
    svg.text(
        791,
        110,
        "Intrinsic Matrix K",
        fill=palette.text_primary,
        size=11.5,
        weight="700",
    )
    k_lines = [
        "[ fx   s  cx ]",
        "[  0  fy  cy ]",
        "[  0   0   1 ]",
        "",
        f"fx = {cam.intrinsics.fx:.1f} px",
        f"fy = {cam.intrinsics.fy:.1f} px",
        f"cx = {cam.intrinsics.cx:.1f} px",
        f"cy = {cam.intrinsics.cy:.1f} px",
        f"HFOV = {cam.intrinsics.fov_horizontal_deg:.1f}°",
        "",
        "center_uv:",
        f"({proj_pts['center'][0]:.0f}, {proj_pts['center'][1]:.1f})",
    ]
    for i, line_txt in enumerate(k_lines):
        svg.text(
            720,
            138 + i * 22,
            line_txt,
            fill=palette.accent_secondary if i < 3 else palette.text_muted,
            size=9.8,
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
        "Subdivided 3D court & grid lines (N = 48 samples/segment) projected via Camera.project_points()",
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
            "k1=-0.22, k2=0.05 (Barrel)",
            CameraDistortion.brown_conrady(k1=-0.22, k2=0.05, p1=0.001, p2=-0.001),
            palette.accent_secondary,
            336.0,
        ),
        (
            "3. FISHEYE (Kannala-Brandt)",
            "Equidistant Wide Action Lens",
            CameraDistortion.fisheye(k1=-0.08, k2=0.02, k3=-0.003, k4=0.0005),
            palette.accent_tertiary,
            648.0,
        ),
    ]

    intr = CameraIntrinsics.from_fov(
        width_px=260, height_px=190, horizontal_fov_deg=92.0
    )
    extr = CameraExtrinsics.from_look_at(
        position=(0.0, -12.2, 5.2),
        target=(0.0, 0.0, 0.2),
    )

    # 3D court segments to project with 48-point subdivision
    court_segments = [
        ((-5.0, -10.0, 0.0), (5.0, -10.0, 0.0)),
        ((5.0, -10.0, 0.0), (5.0, 10.0, 0.0)),
        ((5.0, 10.0, 0.0), (-5.0, 10.0, 0.0)),
        ((-5.0, 10.0, 0.0), (-5.0, -10.0, 0.0)),
        ((-5.0, -7.0, 0.0), (5.0, -7.0, 0.0)),
        ((-5.0, 7.0, 0.0), (5.0, 7.0, 0.0)),
        ((0.0, -7.0, 0.0), (0.0, 7.0, 0.0)),
        ((-5.0, 0.0, 0.0), (5.0, 0.0, 0.0)),
        ((-5.0, -10.0, 4.0), (5.0, -10.0, 4.0)),
        ((-5.0, 10.0, 4.0), (5.0, 10.0, 4.0)),
    ]

    for title, subtitle, dist_model, accent, px in models:
        svg.rect(
            px,
            64,
            288,
            274,
            fill=palette.bg_panel,
            stroke=palette.border,
            rx=10,
        )
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

        vp_x, vp_y = px + 14.0, 122.0
        svg.rect(
            vp_x,
            vp_y,
            260,
            190,
            fill=palette.bg_canvas,
            stroke=accent,
            stroke_width=1.4,
            rx=6,
        )

        # Background sensor distortion grid via CameraDistortion.distort()
        for norm_c in np.linspace(-0.75, 0.75, 7):
            h_pts = np.column_stack([np.linspace(-1.05, 1.05, 48), np.full(48, norm_c)])
            v_pts = np.column_stack([np.full(48, norm_c), np.linspace(-0.75, 0.75, 48)])
            for grid_pts in (h_pts, v_pts):
                warped = dist_model.distort_normalized(grid_pts)
                uv = np.column_stack(
                    [
                        vp_x + 130.0 + warped[:, 0] * 105.0,
                        vp_y + 95.0 + warped[:, 1] * 105.0,
                    ]
                )
                in_bounds = (
                    (uv[:, 0] >= vp_x + 2)
                    & (uv[:, 0] <= vp_x + 258)
                    & (uv[:, 1] >= vp_y + 2)
                    & (uv[:, 1] <= vp_y + 188)
                )
                if np.count_nonzero(in_bounds) >= 2:
                    svg.polyline(
                        rdp_simplify_2d(uv[in_bounds], epsilon=0.35),
                        stroke=palette.grid_line,
                        stroke_width=1.0,
                    )

        cam = Camera(intrinsics=intr, extrinsics=extr, distortion=dist_model)
        for seg_a, seg_b in court_segments:
            uv = project_polyline_3d(cam, [seg_a, seg_b], subdivide=48)
            uv[:, 0] += vp_x
            uv[:, 1] += vp_y
            in_vp = (
                (uv[:, 0] >= vp_x + 2)
                & (uv[:, 0] <= vp_x + 258)
                & (uv[:, 1] >= vp_y + 2)
                & (uv[:, 1] <= vp_y + 188)
            )
            if np.count_nonzero(in_vp) >= 2:
                svg.polyline(
                    rdp_simplify_2d(uv[in_vp], epsilon=0.30),
                    stroke=accent,
                    stroke_width=1.8,
                )

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
    svg.rect(
        24,
        64,
        520,
        332,
        fill=palette.bg_panel,
        stroke=palette.border,
        rx=10,
    )
    svg.rect(
        560,
        64,
        316,
        332,
        fill=palette.bg_panel,
        stroke=palette.border,
        rx=10,
    )

    bx, by = 260.0, 220.0
    r_ball = 48.0

    # Airflow streamlines
    for dy in (-68, -42, 42, 68):
        svg.line(
            70,
            by + dy,
            450,
            by + dy,
            stroke=palette.grid_line,
            stroke_width=1.2,
            dash="6 4",
        )

    # Spinning padel ball body & seam
    svg.circle(
        bx,
        by,
        r_ball,
        fill=palette.court_floor,
        stroke=palette.accent_tertiary,
        stroke_width=2.5,
    )
    seam_d = (
        f"M {_fmt(bx - 34)} {_fmt(by - 34)} "
        f"Q {_fmt(bx + 18)} {_fmt(by)} {_fmt(bx - 34)} {_fmt(by + 34)}"
    )
    svg.path(seam_d, stroke=palette.accent_tertiary, stroke_width=1.8, dash="4 3")

    # Spin arc around ball (w)
    spin_arc = (
        f"M {_fmt(bx - 64)} {_fmt(by - 18)} "
        f"A 66 66 0 0 1 {_fmt(bx + 18)} {_fmt(by - 64)}"
    )
    svg.path(
        spin_arc,
        stroke=palette.accent_tertiary,
        stroke_width=2.0,
        marker_end="arrow-tertiary",
    )
    svg.callout_badge(
        bx - 42,
        by - 64,
        "ω (Spin rad/s)",
        color=palette.accent_tertiary,
    )

    # Force & Velocity vectors from ball center
    # 1. Velocity v (forward-upward)
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
        "v (Velocity m/s)",
        color=palette.accent_primary,
        offset=(10, -18),
    )

    # 2. Aerodynamic Drag F_drag (opposes v)
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
        offset=(-10, 22),
    )

    # 3. Gravity F_g (downward -Z)
    svg.line(
        bx,
        by,
        bx,
        by + 118,
        stroke=palette.court_line_fg,
        stroke_width=2.4,
        marker_end="arrow-fg",
    )
    svg.callout_badge(
        bx,
        by + 118,
        "F_g = m·g (-Z)",
        color=palette.court_line_fg,
        offset=(64, 0),
    )

    # 4. Spindt Magnus Lift F_magnus (perpendicular: w x v)
    svg.line(
        bx,
        by,
        bx - 26,
        by - 122,
        stroke=palette.accent_secondary,
        stroke_width=2.8,
        marker_end="arrow-secondary",
    )
    svg.callout_badge(
        bx - 26,
        by - 122,
        "F_magnus ∝ ω × v",
        color=palette.accent_secondary,
        offset=(56, -8),
    )

    # Right panel: Equations & 9D state summary using BallState.from_shot()
    sample = BallState.from_shot(
        position=(0.0, -6.0, 1.2),
        velocity=(0.0, 22.0, 3.5),
        topspin_rpm=2100.0,
        sidespin_rpm=-450.0,
    )
    wx, wy, wz = sample.angular_velocity
    lines = [
        ("1. Quadratic Felt Drag", palette.accent_danger),
        ("Cd = Cd0 + fuzz_factor (0.507 + 0.04)", palette.text_muted),
        ("F_drag = -½ ρ A Cd |v| v", palette.text_primary),
        ("2. Spindt Non-Linear Magnus Lift", palette.accent_secondary),
        ("Spin Ratio S = (r · |ω|) / |v|", palette.text_muted),
        ("Cl = 1 / (2.022 + 0.981 / S)", palette.text_primary),
        ("F_magnus = ½ ρ A Cl |v|² (ω × v)/|ω × v|", palette.text_primary),
        ("3. Sample BallState.from_shot()", palette.accent_primary),
        (
            f"Speed: {sample.speed_kmh:.1f} km/h | Spin: {sample.spin_rpm:.0f} RPM",
            palette.text_muted,
        ),
        (
            f"ω = ({wx:.0f}, {wy:.0f}, {wz:.0f}) rad/s",
            palette.text_muted,
        ),
    ]
    for i, (txt, col) in enumerate(lines):
        svg.text(
            578,
            96 + i * 28.5,
            txt,
            fill=col,
            size=10.2,
            weight="700" if txt[:2].endswith(".") else "500",
            mono=True,
            anchor="start",
        )

    return svg.to_xml_string()


def render_physics_trajectories(palette: ThemePalette) -> str:
    """8. RK4-simulated side-view trajectory comparison with sharp bounce cusps."""
    svg = SvgCanvas(
        960,
        440,
        "PadelKit RK4 Simulated Spin Trajectories (Y-Z Elevation)",
        "Side-elevation comparison of Topspin Smash, Flat Drive, and Backspin Bandeja simulated via BallPhysicsEngine.simulate().",
        palette,
    )
    svg.header(
        "RK4 Spin Trajectory Comparison (BallPhysicsEngine.simulate)",
        "Side Elevation (Y ∈ [-10m, +10m], Z ∈ [0m, 4.5m])  |  dt = 0.002s  |  Sharp bounce cusps preserved",
    )
    svg.rect(
        24,
        64,
        912,
        352,
        fill=palette.bg_panel,
        stroke=palette.border,
        rx=10,
    )

    engine = BallPhysicsEngine()

    shots = [
        (
            "Topspin Smash (+2400 RPM)",
            BallState.from_shot(
                position=(0.0, -4.5, 2.55),
                velocity=(0.0, 21.5, -1.6),
                topspin_rpm=2400.0,
            ),
            palette.accent_danger,
        ),
        (
            "Flat Drive (0 RPM)",
            BallState.from_shot(
                position=(0.0, -8.2, 1.15),
                velocity=(0.0, 21.0, 2.7),
                topspin_rpm=0.0,
            ),
            palette.accent_secondary,
        ),
        (
            "Backspin Bandeja (-1800 RPM)",
            BallState.from_shot(
                position=(0.0, -3.5, 2.20),
                velocity=(0.0, 14.8, -0.6),
                topspin_rpm=-1800.0,
            ),
            palette.accent_primary,
        ),
    ]

    # Map Y in [-10, 10] -> X in [80, 880] (40 px/m), Z in [0, 4.5] -> Y in [366, 114] (56 px/m)
    x0, y_floor = 480.0, 366.0
    sx, sz = 40.0, 56.0

    def yz_to_uv(y_m: float, z_m: float) -> tuple[float, float]:
        return x0 + y_m * sx, y_floor - z_m * sz

    # Reference elevation grid
    for z_grid in (1.0, 2.0, 3.0, 4.0):
        _, gv = yz_to_uv(0.0, z_grid)
        svg.line(
            80, gv, 880, gv, stroke=palette.grid_line, stroke_width=1.0, dash="4 4"
        )
        svg.text(
            68,
            gv,
            f"{z_grid:.0f}m",
            fill=palette.text_muted,
            size=9.5,
            mono=True,
            anchor="end",
        )

    # Court floor, service lines, net, and 4m back glass walls
    svg.line(80, y_floor, 880, y_floor, stroke=palette.court_line_fg, stroke_width=2.4)
    svg.line(
        80,
        y_floor,
        80,
        y_floor - 4.0 * sz,
        stroke=palette.glass_stroke,
        stroke_width=3.0,
    )
    svg.line(
        880,
        y_floor,
        880,
        y_floor - 4.0 * sz,
        stroke=palette.glass_stroke,
        stroke_width=3.0,
    )
    svg.line(
        x0,
        y_floor,
        x0,
        y_floor - 0.88 * sz,
        stroke=palette.accent_tertiary,
        stroke_width=3.0,
    )

    for y_tick, lbl in [
        (-10.0, "Y = -10m (Near Glass)"),
        (-7.0, "-7m"),
        (0.0, "Y = 0m (Net 0.88m)"),
        (7.0, "+7m"),
        (10.0, "Y = +10m (Far Glass)"),
    ]:
        tu, _ = yz_to_uv(y_tick, 0.0)
        svg.text(tu, y_floor + 20, lbl, fill=palette.text_muted, size=9.5, mono=True)

    # Simulate and draw each trajectory with cusp-preserving RDP simplification
    for idx, (label, init_state, color) in enumerate(shots):
        traj = engine.simulate(init_state, duration=1.65, dt=0.002)
        pos = traj.positions
        uv_raw = np.column_stack([x0 + pos[:, 1] * sx, y_floor - pos[:, 2] * sz])

        bounce_idxs: list[int] = []
        for b in traj.bounces:
            b_idx = int(np.argmin(np.abs(traj.timestamps - b.timestamp)))
            bounce_idxs.append(b_idx)

        uv_clean = simplify_trajectory_preserve_cusps(uv_raw, bounce_idxs, epsilon=0.45)
        svg.polyline(uv_clean, stroke=color, stroke_width=2.4)

        # Mark initial shot origin and bounce events
        svg.circle(uv_raw[0, 0], uv_raw[0, 1], 4.5, fill=color, stroke=palette.bg_panel)
        for b in traj.bounces:
            bu, bv = yz_to_uv(b.position[1], b.position[2])
            svg.circle(
                bu, bv, 5.0, fill=palette.bg_panel, stroke=color, stroke_width=2.2
            )

        # Legend entry at top of viewport
        lx = 110.0 + idx * 270.0
        svg.line(lx, 92, lx + 28, 92, stroke=color, stroke_width=2.8)
        svg.text(
            lx + 36,
            92,
            label,
            fill=color,
            size=10.5,
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

    panels = [
        (
            "1. ContactRegime.SLIDING",
            "Tempered Glass (μ = 0.20 < μ_crit)",
            "High tangential slip; spin slides smoothly",
            "v_t' = v_t - s·μ·(1 + e)·v_n",
            palette.accent_secondary,
            24.0,
            (180, 175),
            (255, 255),
            (340, 210),
        ),
        (
            "2. ContactRegime.ROLLING",
            "Sandy Turf Floor (μ = 0.55 ≥ μ_crit)",
            "Full surface grip; backspin bites low & slow",
            "v_t' = 5/7·v_t + 2/7·r·(ω × n)",
            palette.accent_primary,
            336.0,
            (490, 165),
            (575, 255),
            (655, 232),
        ),
        (
            "3. ContactRegime.DAMPED",
            "Net & Metallic Fence (e = 0.22 / 0.45)",
            "Viscoelastic mesh energy absorption",
            "v_n' = -e_mesh · v_n  (Deadened rebound)",
            palette.accent_danger,
            648.0,
            (795, 165),
            (880, 255),
            (922, 240),
        ),
    ]

    for title, sub, desc, formula, col, px, p_in, p_hit, p_out in panels:
        svg.rect(
            px,
            64,
            288,
            292,
            fill=palette.bg_panel,
            stroke=palette.border,
            rx=10,
        )
        svg.text(
            px + 16,
            88,
            title,
            fill=col,
            size=11.5,
            weight="700",
            mono=True,
            anchor="start",
        )
        svg.text(
            px + 16,
            106,
            sub,
            fill=palette.text_primary,
            size=10.0,
            weight="600",
            mono=True,
            anchor="start",
        )
        svg.text(
            px + 16,
            124,
            desc,
            fill=palette.text_muted,
            size=9.5,
            anchor="start",
        )

        # Impact surface horizontal bar at y = 255
        surf_y = 255.0
        svg.rect(
            px + 20,
            surf_y,
            248,
            14,
            fill=palette.court_floor,
            stroke=palette.court_line_fg,
            stroke_width=1.6,
            rx=3,
        )
        # Surface normal n
        hx = px + 144.0
        svg.line(
            hx,
            surf_y,
            hx,
            surf_y - 78,
            stroke=palette.text_muted,
            stroke_width=1.3,
            dash="3 3",
            marker_end="arrow-muted",
        )
        svg.text(
            hx + 12, surf_y - 72, "n̂", fill=palette.text_muted, size=10.0, mono=True
        )

        # Incident velocity v_in and rebound velocity v_out
        in_x = hx - (p_hit[0] - p_in[0])
        out_x = hx + (p_out[0] - p_hit[0])
        svg.line(
            in_x,
            p_in[1],
            hx - 8,
            surf_y - 10,
            stroke=palette.text_muted,
            stroke_width=2.0,
            marker_end="arrow-muted",
        )
        svg.text(
            in_x + 8,
            p_in[1] - 10,
            "v_in",
            fill=palette.text_muted,
            size=10.0,
            mono=True,
        )
        svg.line(
            hx + 8,
            surf_y - 10,
            out_x,
            p_out[1],
            stroke=col,
            stroke_width=2.4,
            marker_end=(
                "arrow-secondary"
                if col == palette.accent_secondary
                else (
                    "arrow-primary" if col == palette.accent_primary else "arrow-danger"
                )
            ),
        )
        svg.text(
            out_x - 10,
            p_out[1] - 12,
            "v_out",
            fill=col,
            size=10.5,
            weight="700",
            mono=True,
        )
        svg.circle(
            hx, surf_y - 12, 11.0, fill=palette.bg_canvas, stroke=col, stroke_width=2.2
        )

        # Formula box at bottom
        svg.rect(
            px + 16,
            296,
            256,
            42,
            fill=palette.bg_canvas,
            stroke=col,
            stroke_width=1.2,
            rx=6,
        )
        svg.text(
            px + 144,
            317,
            formula,
            fill=col,
            size=10.0,
            weight="700",
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
    svg.rect(
        24,
        64,
        540,
        352,
        fill=palette.bg_panel,
        stroke=palette.border,
        rx=10,
    )
    svg.rect(
        580,
        64,
        356,
        352,
        fill=palette.bg_panel,
        stroke=palette.border,
        rx=10,
    )

    # Horizontal court in left panel
    cx0, cy0 = 64.0, 124.0
    scale = 22.0  # 20m -> 440px, 10m -> 220px
    cw, ch = 20.0 * scale, 10.0 * scale
    svc = 3.0 * scale

    svg.rect(
        cx0,
        cy0,
        cw,
        ch,
        fill=palette.court_floor,
        stroke=palette.court_line_fg,
        stroke_width=2.0,
    )
    # Highlight target diagonal service boxes
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

    # Diagonal serve trajectories (Right/Deuce bottom-left -> top-right; Left/Ad top-left -> bottom-right)
    svg.line(
        cx0 + 42,
        cy0 + ch * 0.78,
        cx0 + cw * 0.68,
        cy0 + ch * 0.24,
        stroke=palette.accent_primary,
        stroke_width=2.2,
        marker_end="arrow-primary",
    )
    svg.callout_badge(
        cx0 + 42,
        cy0 + ch * 0.78,
        "S (right)",
        color=palette.accent_primary,
    )
    svg.callout_badge(
        cx0 + cw * 0.80,
        cy0 + ch * 0.22,
        "R (right)",
        color=palette.accent_primary,
    )

    svg.line(
        cx0 + 42,
        cy0 + ch * 0.22,
        cx0 + cw * 0.68,
        cy0 + ch * 0.76,
        stroke=palette.accent_secondary,
        stroke_width=2.2,
        dash="5 3",
        marker_end="arrow-secondary",
    )
    svg.callout_badge(
        cx0 + 42,
        cy0 + ch * 0.22,
        "S (left)",
        color=palette.accent_secondary,
    )
    svg.callout_badge(
        cx0 + cw * 0.80,
        cy0 + ch * 0.78,
        "R (left)",
        color=palette.accent_secondary,
    )

    # Right panel: Compute actual 4-game rotation states via ServingEngine
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
        92,
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
        ry = 114.0 + g_idx * 72.0
        col = (
            palette.accent_primary
            if st_even.team == TeamId.A
            else palette.accent_secondary
        )
        svg.rect(
            598,
            ry,
            320,
            58,
            fill=palette.bg_canvas,
            stroke=col,
            stroke_width=1.4,
            rx=8,
        )
        svg.text(
            612,
            ry + 20,
            f"Game {g_idx + 1} (total_games={g_idx}) -> Team {st_even.team.value}",
            fill=col,
            size=10.5,
            weight="700",
            mono=True,
            anchor="start",
        )
        svg.text(
            612,
            ry + 41,
            f"Server: {st_even.player.name} | Deuce Recv: {st_even.receiver.name}",
            fill=palette.text_muted,
            size=9.5,
            mono=True,
            anchor="start",
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

MAX_SVG_BYTES = 30_720


def build_all_schematics_in_memory() -> dict[str, str]:
    """Generate all 20 themed schematic SVG strings (`{name}-{light|dark}.svg`)."""
    outputs: dict[str, str] = {}
    for name, fn in SCHEMATIC_GENERATORS.items():
        for palette in (LIGHT_PALETTE, DARK_PALETTE):
            filename = f"{name}-{palette.mode}.svg"
            xml_str = fn(palette)
            # Validate XML well-formedness & size invariants
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

    # Also write fallback docs/images/court-landmarks-3d.svg
    fallback_path = out_dir.parent / "court-landmarks-3d.svg"
    fallback_path.write_text(generated["court-landmarks-3d-dark.svg"], encoding="utf-8")
    print(f"Generated {len(generated)} SVG schematics in {out_dir}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
