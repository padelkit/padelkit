import base64
import html
import json
import queue
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from ..camera.camera import Camera
from ..camera.enums import CameraPreset
from ..court.court import Court
from ..court.enums import CoordinateSystem
from ..physics.models import BallProperties
from .template import render_viewer_html
from .timeline import FrameState, MatchTimeline


class PadelVisualizer:
    """Interactive 3D Three.js visualizer and synthetic pass inspector for PadelKit.

    Supports three operating modes:
    1. **Parquet / CSV / Timeline Replay Mode**: Load a `MatchTimeline`,
       `.parquet`, or `.csv` file via `from_parquet` / `from_csv`
       and scrub through the match at any speed or camera angle.
    2. **Real-Time Live Streaming Mode**: Start a local server with `serve`
       and stream `FrameState` updates in real time via `push_frame`.
    3. **Standalone HTML / Jupyter Notebook Mode**: Export a zero-dependency
       offline HTML file with `export_html` (with embedded Three.js by
       default, or optional CDN loading via `offline=False`) or render
       directly inside a Jupyter cell.
    """

    def __init__(
        self,
        court: Court | None = None,
        cameras: list[Camera] | None = None,
        timeline: MatchTimeline | None = None,
        animation_library_dir: str | Path | None = None,
        offline: bool = True,
        ball_properties: BallProperties | None = None,
    ) -> None:
        """Initializes an interactive 3D Three.js visualizer.

        Args:
            court: Reference `Court` geometry. Defaults to timeline court or
                `Court.fip_standard()`.
            cameras: List of `Camera` presets/calibrated views shown in the HUD.
                Defaults to 5 standard viewpoints (broadcast, zenith, corner, side).
            timeline: `MatchTimeline` to replay. Defaults to a physics-simulated
                `MatchTimeline.demo_rally()`.
            animation_library_dir: Optional folder containing `manifest.json`
                and Mixamo `.glb` player animations.
            offline: If `True`, embeds the Three.js runtime inside exported HTML
                for zero-network playback; if `False`, loads via CDN import map.
            ball_properties: Visual ball color/radius settings.
        """
        self.timeline: MatchTimeline = (
            timeline
            if timeline is not None
            else MatchTimeline.demo_rally(court=court or Court.fip_standard())
        )
        self.court: Court = court or self.timeline.court
        self.ball_properties: BallProperties = (
            ball_properties or self.timeline.ball_properties
        )
        if cameras is not None:
            self.cameras: list[Camera] = list(cameras)
        else:
            self.cameras = [
                Camera.broadcast_near(court=self.court),
                Camera.broadcast_far(court=self.court),
                Camera.overhead_zenith(),
                Camera.from_preset(CameraPreset.CORNER_NEAR_LEFT, court=self.court),
                Camera.from_preset(CameraPreset.SIDE_NET_RIGHT, court=self.court),
            ]
        self.animation_library_dir: Path | None = (
            Path(animation_library_dir) if animation_library_dir is not None else None
        )
        self.offline: bool = bool(offline)
        self._subscribers: list[queue.Queue[str]] = []
        self._server: ThreadingHTTPServer | None = None

    # ------------------------------------------------------------------ #
    # Factory constructors & Configuration
    # ------------------------------------------------------------------ #

    @classmethod
    def from_csv(
        cls,
        csv_path: str | Path,
        court: Court | None = None,
        cameras: list[Camera] | None = None,
        animation_library_dir: str | Path | None = None,
        offline: bool = True,
    ) -> "PadelVisualizer":
        """Creates a `PadelVisualizer` pre-loaded with a CSV match timeline."""
        c = court or Court.fip_standard()
        timeline = MatchTimeline.from_csv(csv_path, court=c)
        return cls(
            court=c,
            cameras=cameras,
            timeline=timeline,
            animation_library_dir=animation_library_dir,
            offline=offline,
        )

    @classmethod
    def from_parquet(
        cls,
        parquet_path: str | Path,
        court: Court | None = None,
        cameras: list[Camera] | None = None,
        animation_library_dir: str | Path | None = None,
        offline: bool = True,
    ) -> "PadelVisualizer":
        """Creates a `PadelVisualizer` pre-loaded with a Parquet match file."""
        timeline = MatchTimeline.from_parquet(parquet_path, court=court)
        return cls(
            court=timeline.court,
            cameras=cameras,
            timeline=timeline,
            animation_library_dir=animation_library_dir,
            offline=offline,
        )

    def add_camera(self, camera: Camera) -> "PadelVisualizer":
        """Registers an additional `Camera` viewpoint in the 3D scene."""
        self.cameras.append(camera)
        return self

    def load_csv(self, csv_path: str | Path) -> "PadelVisualizer":
        """Replaces the active timeline with data loaded from ``csv_path``."""
        self.timeline = MatchTimeline.from_csv(csv_path, court=self.court)
        return self

    def load_parquet(self, parquet_path: str | Path) -> "PadelVisualizer":
        """Replaces the active timeline and court metadata from ``parquet_path``."""
        self.timeline = MatchTimeline.from_parquet(parquet_path)
        self.court = self.timeline.court
        return self

    def load_animation_library(
        self, animation_library_dir: str | Path
    ) -> "PadelVisualizer":
        """Attaches a ``padelkit-animator`` GLB animation library directory."""
        self.animation_library_dir = Path(animation_library_dir)
        return self

    def _build_animation_library_config(
        self, live_stream_url: str | None = None
    ) -> dict[str, Any] | None:
        if self.animation_library_dir is None:
            return None
        manifest_path = self.animation_library_dir / "manifest.json"
        if not manifest_path.exists():
            return None

        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        glb_sources: dict[str, str] = {}
        for entry in manifest_data.get("animations", []):
            clip_id = entry.get("clip_id")
            glb_rel = entry.get("glb_path")
            if not clip_id or not glb_rel:
                continue
            safe_name = Path(glb_rel).name
            glb_file = self.animation_library_dir / safe_name
            if not glb_file.exists():
                continue
            if live_stream_url is not None:
                glb_sources[clip_id] = f"/animations/{safe_name}"
            else:
                b64 = base64.b64encode(glb_file.read_bytes()).decode("ascii")
                glb_sources[clip_id] = f"data:model/gltf-binary;base64,{b64}"

        female_file = self.animation_library_dir / "avatar_female.glb"
        if female_file.exists():
            if live_stream_url is not None:
                glb_sources["avatar_female"] = "/animations/avatar_female.glb"
            else:
                b64_fem = base64.b64encode(female_file.read_bytes()).decode("ascii")
                glb_sources["avatar_female"] = (
                    f"data:model/gltf-binary;base64,{b64_fem}"
                )

        return {
            "manifest": manifest_data,
            "glb_sources": glb_sources,
        }

    def build_config(self, live_stream_url: str | None = None) -> dict[str, Any]:
        """Serializes the court geometry, 17 landmarks, cameras, and timeline."""
        dims = self.court.dimensions
        lm_3d = self.court.landmarks_3d(coordinate_system=CoordinateSystem.CENTERED)
        return {
            "court": {
                "dimensions": {
                    "length": dims.length,
                    "width": dims.width,
                    "net_height_center": dims.net_height_center,
                    "net_height_posts": dims.net_height_posts,
                    "service_line_distance_from_back": (
                        dims.service_line_distance_from_back
                    ),
                    "back_wall_height": dims.back_wall_height,
                    "side_wall_height": dims.side_wall_height,
                    "line_width": dims.line_width,
                    "service_line_extension": dims.service_line_extension,
                    "net_post_height": dims.net_post_height,
                    "free_height": dims.free_height,
                },
                "turf_color": self.court.effective_turf_color,
                "setting": (
                    self.court.setting.value if self.court.setting is not None else None
                ),
                "ceiling_height": self.court.ceiling_height,
                "safety_zone_left": (
                    self.court.safety_zone_left.to_dict()
                    if self.court.safety_zone_left is not None
                    else None
                ),
                "safety_zone_right": (
                    self.court.safety_zone_right.to_dict()
                    if self.court.safety_zone_right is not None
                    else None
                ),
                "enclosure_type": self.court.effective_enclosure_type.value,
                "enclosure_variant": self.court.effective_enclosure_variant.value,
                "side_wall_profile": self.court.effective_side_wall_profile.value,
                "door_left": (
                    door_left.value
                    if (door_left := self.court.door_state_for("left")) is not None
                    else "open"
                ),
                "door_right": (
                    door_right.value
                    if (door_right := self.court.door_state_for("right")) is not None
                    else "open"
                ),
                "access_left": self.court.effective_access_left.to_dict(),
                "access_right": self.court.effective_access_right.to_dict(),
                "side_panels_left": [
                    {
                        "y_start": p.y_start,
                        "y_end": p.y_end,
                        "z_start": p.z_start,
                        "z_end": p.z_end,
                        "is_solid": p.is_solid,
                    }
                    for p in self.court.side_enclosure_panels("left")
                ],
                "side_panels_right": [
                    {
                        "y_start": p.y_start,
                        "y_end": p.y_end,
                        "z_start": p.z_start,
                        "z_end": p.z_end,
                        "is_solid": p.is_solid,
                    }
                    for p in self.court.side_enclosure_panels("right")
                ],
            },
            "landmarks_3d": {k: list(v) for k, v in lm_3d.items()},
            "ball": {
                "color": self.ball_properties.effective_color,
                "radius": self.ball_properties.radius,
                "mass": self.ball_properties.mass,
                "pressure_psi": self.ball_properties.pressure_psi,
            },
            "cameras": [cam.to_dict() for cam in self.cameras],
            "timeline": self.timeline.to_dict(),
            "animation_library": self._build_animation_library_config(
                live_stream_url=live_stream_url
            ),
            "live_stream_url": live_stream_url,
        }

    # ------------------------------------------------------------------ #
    # HTML Export & Jupyter Notebook Integration
    # ------------------------------------------------------------------ #

    def to_html(
        self,
        live_stream_url: str | None = None,
        offline: bool | None = None,
    ) -> str:
        """Generates the Three.js HTML application string.

        Args:
            live_stream_url: Optional SSE endpoint URL used by `serve`.
            offline: If `True`, embeds the minified Three.js bundle directly in
                the HTML so it works with zero internet access (including
                `file://` URLs). If `False`, uses a jsDelivr CDN import map.
                Defaults to `self.offline` (`True`).
        """
        use_offline = self.offline if offline is None else bool(offline)
        cfg = self.build_config(live_stream_url=live_stream_url)
        return render_viewer_html(cfg, offline=use_offline)

    def export_html(
        self,
        path: str | Path,
        offline: bool | None = None,
    ) -> Path:
        """Writes the standalone Three.js 3D viewer to an HTML file on disk."""
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(self.to_html(offline=offline), encoding="utf-8")
        return out_path

    def _repr_html_(self) -> str:
        """Renders the interactive 3D viewer inline inside Jupyter / Colab notebooks."""
        escaped = html.escape(self.to_html(), quote=True)
        return (
            f'<iframe srcdoc="{escaped}" width="100%" height="640" '
            'style="border:1px solid #334155; border-radius:12px;" '
            "allowfullscreen></iframe>"
        )

    # ------------------------------------------------------------------ #
    # Real-Time Streaming Mode (HTTP + Server-Sent Events)
    # ------------------------------------------------------------------ #

    def push_frame(self, frame: FrameState) -> None:
        """Broadcasts a `FrameState` in real time to connected browsers."""
        self.timeline.append(frame)
        payload = json.dumps(frame.to_dict())
        for q in list(self._subscribers):
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass

    def serve(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        open_browser: bool = True,
        background: bool = False,
        offline: bool | None = None,
    ) -> ThreadingHTTPServer:
        """Starts the local interactive 3D visualization and live-streaming server."""
        visualizer = self

        class _ViewerHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path in ("/", "/index.html"):
                    body = visualizer.to_html(
                        live_stream_url="/events",
                        offline=offline,
                    ).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                elif self.path == "/events":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.end_headers()
                    q: queue.Queue[str] = queue.Queue(maxsize=120)
                    visualizer._subscribers.append(q)
                    try:
                        while True:
                            data = q.get()
                            msg = f"data: {data}\n\n".encode()
                            self.wfile.write(msg)
                            self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    finally:
                        if q in visualizer._subscribers:
                            visualizer._subscribers.remove(q)
                elif self.path.startswith("/animations/"):
                    if visualizer.animation_library_dir is None:
                        self.send_error(404)
                        return
                    rel_name = Path(
                        unquote(self.path.removeprefix("/animations/"))
                    ).name
                    glb_path = (visualizer.animation_library_dir / rel_name).resolve()
                    if (
                        not glb_path.exists()
                        or glb_path.parent != visualizer.animation_library_dir.resolve()
                    ):
                        self.send_error(404)
                        return
                    body = glb_path.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "model/gltf-binary")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_error(404)

            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                return

        server = ThreadingHTTPServer((host, port), _ViewerHandler)
        self._server = server
        url = f"http://{host}:{port}/"

        if open_browser:
            webbrowser.open(url)

        if background:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            return server

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()
        return server

    def stop_server(self) -> None:
        """Stops the background HTTP visualization server if running."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
