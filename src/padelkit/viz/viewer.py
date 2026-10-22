import html
import json
import queue
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from ..camera.camera import Camera
from ..camera.enums import CameraPreset
from ..court.court import Court
from ..court.enums import CoordinateSystem
from .template import THREEJS_VIEWER_HTML_TEMPLATE
from .timeline import FrameState, MatchTimeline


class PadelVisualizer:
    """Interactive 3D Three.js visualizer and synthetic pass inspector for PadelKit.

    Supports three operating modes:
    1. **CSV / Timeline Replay Mode**: Load a :class:`MatchTimeline` or CSV file
       via :meth:`from_csv` and scrub through the match at any speed or camera angle.
    2. **Real-Time Live Streaming Mode**: Start a local server with :meth:`serve`
       and stream :class:`FrameState` updates in real time via :meth:`push_frame`.
    3. **Standalone HTML / Jupyter Notebook Mode**: Export a zero-dependency
       HTML file with :meth:`export_html` or render directly inside a Jupyter cell.
    """

    def __init__(
        self,
        court: Court | None = None,
        cameras: list[Camera] | None = None,
        timeline: MatchTimeline | None = None,
    ) -> None:
        self.court: Court = court or Court.fip_standard()
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
        self.timeline: MatchTimeline = (
            timeline
            if timeline is not None
            else MatchTimeline.demo_rally(court=self.court)
        )
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
    ) -> "PadelVisualizer":
        """Creates a :class:`PadelVisualizer` pre-loaded with a CSV match timeline."""
        c = court or Court.fip_standard()
        timeline = MatchTimeline.from_csv(csv_path, court=c)
        return cls(court=c, cameras=cameras, timeline=timeline)

    def add_camera(self, camera: Camera) -> "PadelVisualizer":
        """Registers an additional :class:`Camera` viewpoint in the 3D scene."""
        self.cameras.append(camera)
        return self

    def load_csv(self, csv_path: str | Path) -> "PadelVisualizer":
        """Replaces the active timeline with data loaded from ``csv_path``."""
        self.timeline = MatchTimeline.from_csv(csv_path, court=self.court)
        return self

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
                },
                "turf_color": self.court.turf_color or "blue",
                "enclosure_type": (
                    self.court.enclosure_type.value
                    if self.court.enclosure_type
                    else "glass"
                ),
                "enclosure_variant": (
                    self.court.enclosure_variant.value
                    if self.court.enclosure_variant
                    else 1
                ),
            },
            "landmarks_3d": {k: list(v) for k, v in lm_3d.items()},
            "cameras": [cam.to_dict() for cam in self.cameras],
            "timeline": self.timeline.to_dict(),
            "live_stream_url": live_stream_url,
        }

    # ------------------------------------------------------------------ #
    # HTML Export & Jupyter Notebook Integration
    # ------------------------------------------------------------------ #

    def to_html(self, live_stream_url: str | None = None) -> str:
        """Generates the self-contained Three.js HTML application string."""
        cfg_json = json.dumps(self.build_config(live_stream_url=live_stream_url))
        return THREEJS_VIEWER_HTML_TEMPLATE.replace(
            "__PADELKIT_CONFIG_JSON__", cfg_json
        )

    def export_html(self, path: str | Path) -> Path:
        """Writes the standalone Three.js 3D viewer to an HTML file on disk."""
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(self.to_html(), encoding="utf-8")
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
        """Broadcasts a :class:`FrameState` in real time to connected browsers."""
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
    ) -> ThreadingHTTPServer:
        """Starts the local interactive 3D visualization and live-streaming server."""
        visualizer = self

        class _ViewerHandler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if self.path in ("/", "/index.html"):
                    body = visualizer.to_html(live_stream_url="/events").encode("utf-8")
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
