import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..court.court import Court


@dataclass(frozen=True)
class PlayerPose:
    """Kinematic pose and animation state of a padel player at a single timestamp.

    Coordinates ``(x, y, z)`` are expressed in meters in the centered court
    coordinate system. ``yaw_deg`` follows the same convention as
    :class:`CameraExtrinsics` (``0`` faces ``+Y``, ``180`` faces ``-Y``).
    """

    player_id: str
    x: float
    y: float
    z: float = 0.0
    yaw_deg: float = 0.0
    animation: str = "idle"
    team: str = "A"
    swing_phase: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serializes the player pose to a dictionary."""
        return {
            "player_id": self.player_id,
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "z": round(self.z, 4),
            "yaw_deg": round(self.yaw_deg, 2),
            "animation": self.animation,
            "team": self.team,
            "swing_phase": round(self.swing_phase, 3),
        }


@dataclass(frozen=True)
class FrameState:
    """Complete 3D state of the court, ball, and players at a specific instant ``t``."""

    timestamp: float
    ball_position: tuple[float, float, float]
    ball_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    players: dict[str, PlayerPose] = field(default_factory=dict)
    score: str = "0-0 | 0-0"
    event: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializes the frame state for JSON / WebSocket / Three.js consumption."""
        return {
            "t": round(self.timestamp, 4),
            "ball": [
                round(self.ball_position[0], 4),
                round(self.ball_position[1], 4),
                round(self.ball_position[2], 4),
            ],
            "ball_vel": [
                round(self.ball_velocity[0], 3),
                round(self.ball_velocity[1], 3),
                round(self.ball_velocity[2], 3),
            ],
            "players": {pid: p.to_dict() for pid, p in self.players.items()},
            "score": self.score,
            "event": self.event,
        }


class MatchTimeline:
    """Time-indexed sequence of :class:`FrameState` snapshots for replay and export.

    Supports lossless serialization to and from CSV files and Pandas DataFrames
    so recorded tracking data, batch simulations, and Three.js / Blender renderers
    share a single standardized schema.
    """

    PLAYER_IDS: tuple[str, str, str, str] = ("P1", "P2", "P3", "P4")

    def __init__(
        self,
        frames: list[FrameState] | None = None,
        fps: float = 60.0,
        court: Court | None = None,
    ) -> None:
        if fps <= 0.0:
            raise ValueError("fps must be strictly positive.")
        self.frames: list[FrameState] = list(frames) if frames else []
        self.fps: float = float(fps)
        self.court: Court = court or Court.fip_standard()

    def __len__(self) -> int:
        return len(self.frames)

    @property
    def duration_seconds(self) -> float:
        """Total duration of the timeline in seconds."""
        if not self.frames:
            return 0.0
        return float(self.frames[-1].timestamp - self.frames[0].timestamp)

    def append(self, frame: FrameState) -> None:
        """Appends a :class:`FrameState` snapshot to the timeline."""
        self.frames.append(frame)

    # ------------------------------------------------------------------ #
    # CSV & DataFrame I/O
    # ------------------------------------------------------------------ #

    def to_dataframe(self) -> pd.DataFrame:
        """Exports the timeline into a tabular :class:`pandas.DataFrame`."""
        rows: list[dict[str, Any]] = []
        for f in self.frames:
            row: dict[str, Any] = {
                "timestamp": f.timestamp,
                "ball_x": f.ball_position[0],
                "ball_y": f.ball_position[1],
                "ball_z": f.ball_position[2],
                "ball_vx": f.ball_velocity[0],
                "ball_vy": f.ball_velocity[1],
                "ball_vz": f.ball_velocity[2],
                "score": f.score,
                "event": f.event if f.event is not None else "",
            }
            for pid in self.PLAYER_IDS:
                key = pid.lower()
                p = f.players.get(pid)
                if p is not None:
                    row[f"{key}_x"] = p.x
                    row[f"{key}_y"] = p.y
                    row[f"{key}_z"] = p.z
                    row[f"{key}_yaw"] = p.yaw_deg
                    row[f"{key}_anim"] = p.animation
                    row[f"{key}_team"] = p.team
                    row[f"{key}_swing"] = p.swing_phase
                else:
                    row[f"{key}_x"] = np.nan
                    row[f"{key}_y"] = np.nan
                    row[f"{key}_z"] = 0.0
                    row[f"{key}_yaw"] = 0.0
                    row[f"{key}_anim"] = "idle"
                    row[f"{key}_team"] = "A" if pid in ("P1", "P2") else "B"
                    row[f"{key}_swing"] = 0.0
            rows.append(row)
        return pd.DataFrame(rows)

    def to_csv(self, path: str | Path) -> Path:
        """Saves the timeline to a CSV file and returns the resolved path."""
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df = self.to_dataframe()
        df.to_csv(out_path, index=False)
        return out_path

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        court: Court | None = None,
        fps: float | None = None,
    ) -> "MatchTimeline":
        """Reconstructs a :class:`MatchTimeline` from a Pandas DataFrame."""
        required = {"timestamp", "ball_x", "ball_y", "ball_z"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(
                f"DataFrame is missing required columns: {sorted(missing)}"
            )

        frames: list[FrameState] = []
        for _, row in df.iterrows():
            t = float(row["timestamp"])
            bx = float(row["ball_x"])
            by = float(row["ball_y"])
            bz = float(row["ball_z"])
            bvx = float(row.get("ball_vx", 0.0))
            bvy = float(row.get("ball_vy", 0.0))
            bvz = float(row.get("ball_vz", 0.0))
            score_val = str(row.get("score", "0-0 | 0-0"))
            raw_event = row.get("event", "")
            event_val = (
                str(raw_event)
                if pd.notna(raw_event) and str(raw_event).strip() != ""
                else None
            )

            players: dict[str, PlayerPose] = {}
            for pid in cls.PLAYER_IDS:
                key = pid.lower()
                if f"{key}_x" in df.columns and pd.notna(row[f"{key}_x"]):
                    default_team = "A" if pid in ("P1", "P2") else "B"
                    players[pid] = PlayerPose(
                        player_id=pid,
                        x=float(row[f"{key}_x"]),
                        y=float(row[f"{key}_y"]),
                        z=float(row.get(f"{key}_z", 0.0)),
                        yaw_deg=float(row.get(f"{key}_yaw", 0.0)),
                        animation=str(row.get(f"{key}_anim", "idle")),
                        team=str(row.get(f"{key}_team", default_team)),
                        swing_phase=float(row.get(f"{key}_swing", 0.0)),
                    )

            frames.append(
                FrameState(
                    timestamp=t,
                    ball_position=(bx, by, bz),
                    ball_velocity=(bvx, bvy, bvz),
                    players=players,
                    score=score_val,
                    event=event_val,
                )
            )

        inferred_fps = fps
        if inferred_fps is None:
            if len(frames) >= 2:
                dt = frames[1].timestamp - frames[0].timestamp
                inferred_fps = round(1.0 / dt, 2) if dt > 1e-6 else 60.0
            else:
                inferred_fps = 60.0

        return cls(frames=frames, fps=inferred_fps, court=court)

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        court: Court | None = None,
    ) -> "MatchTimeline":
        """Loads a :class:`MatchTimeline` from a CSV file on disk."""
        df = pd.read_csv(path)
        return cls.from_dataframe(df, court=court)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the timeline metadata and frames to a JSON-compatible dict."""
        return {
            "fps": self.fps,
            "duration_seconds": round(self.duration_seconds, 4),
            "frame_count": len(self.frames),
            "frames": [f.to_dict() for f in self.frames],
        }

    # ------------------------------------------------------------------ #
    # Physics-informed Demo Rally Generator
    # ------------------------------------------------------------------ #

    @classmethod
    def demo_rally(
        cls,
        court: Court | None = None,
        fps: float = 60.0,
    ) -> "MatchTimeline":
        """Generates a realistic 3D padel rally with ball physics and 4 moving players.

        The rally includes:
        1. Underhand diagonal serve from ``P1`` (Team A right side) into the
           FAR left service box.
        2. Cross-court return by ``P3`` (Team B) after floor bounce.
        3. Net volley by ``P2`` (Team A) deep into the FAR corner.
        4. Floor + back glass wall rebound defended with a high lob by ``P4``.
        5. Overhead *bandeja/smash* by ``P1`` bouncing off the FAR glass wall,
           winning the point for Team A.
        """
        c = court or Court.fip_standard()
        dt = 1.0 / fps

        # Waypoints: (time_s, ball_xyz, hitting_player_or_event)
        segments: list[
            tuple[
                float,
                float,
                tuple[float, float, float],
                tuple[float, float, float],
                float,
                str | None,
                str | None,
            ]
        ] = [
            # (t0, t1, start_xyz, end_xyz, arc_z_boost, event_at_start, hitter_id)
            (0.0, 0.85, (1.8, -7.2, 0.95), (-2.1, 4.8, 0.04), 0.75, "serve", "P1"),
            (
                0.85,
                1.35,
                (-2.1, 4.8, 0.04),
                (-3.1, 7.8, 0.92),
                0.35,
                "bounce_floor",
                None,
            ),
            (
                1.35,
                2.35,
                (-3.1, 7.8, 0.92),
                (-1.8, -2.5, 1.15),
                1.05,
                "shot_forehand",
                "P3",
            ),
            (
                2.35,
                3.15,
                (-1.8, -2.5, 1.15),
                (2.8, 7.6, 0.04),
                0.55,
                "shot_volley",
                "P2",
            ),
            (
                3.15,
                3.55,
                (2.8, 7.6, 0.04),
                (3.4, 9.95, 1.45),
                0.28,
                "bounce_floor",
                None,
            ),
            (
                3.55,
                3.95,
                (3.4, 9.95, 1.45),
                (2.7, 7.9, 1.10),
                0.20,
                "bounce_glass",
                None,
            ),
            (3.95, 5.55, (2.7, 7.9, 1.10), (1.6, -4.2, 2.45), 3.60, "shot_lob", "P4"),
            (
                5.55,
                6.20,
                (1.6, -4.2, 2.45),
                (-2.6, 6.5, 0.04),
                0.15,
                "shot_smash",
                "P1",
            ),
            (
                6.20,
                6.65,
                (-2.6, 6.5, 0.04),
                (-3.3, 9.95, 2.65),
                0.45,
                "bounce_floor",
                None,
            ),
            (
                6.65,
                7.50,
                (-3.3, 9.95, 2.65),
                (-1.2, 1.5, 0.04),
                0.85,
                "bounce_glass",
                None,
            ),
        ]

        # Keyframed tactical player paths: dict[pid, list[(t, x, y)]]
        player_tracks: dict[str, list[tuple[float, float, float]]] = {
            "P1": [
                (0.0, 1.9, -7.4),
                (0.8, 1.8, -6.5),
                (2.2, 1.5, -3.0),
                (4.0, 1.8, -2.4),
                (5.55, 1.6, -4.3),
                (7.5, 1.7, -2.8),
            ],
            "P2": [
                (0.0, -2.1, -3.2),
                (1.5, -2.0, -2.6),
                (2.35, -1.8, -2.5),
                (4.2, -1.9, -3.5),
                (5.6, -2.1, -4.0),
                (7.5, -1.8, -2.8),
            ],
            "P3": [
                (0.0, -2.6, 7.6),
                (1.35, -3.1, 7.9),
                (2.8, -2.4, 7.4),
                (4.5, -2.2, 6.8),
                (6.2, -2.8, 7.8),
                (7.5, -2.0, 4.5),
            ],
            "P4": [
                (0.0, 2.4, 7.4),
                (2.0, 2.2, 7.2),
                (3.5, 3.1, 8.4),
                (3.95, 2.7, 8.0),
                (5.5, 2.3, 7.2),
                (7.5, 2.1, 6.8),
            ],
        }

        total_t = segments[-1][1]
        num_steps = int(round(total_t * fps)) + 1
        frames: list[FrameState] = []

        for step in range(num_steps):
            t = min(step * dt, total_t)
            bx, by, bz = (0.0, 0.0, 0.5)
            vx, vy, vz = (0.0, 0.0, 0.0)
            frame_event: str | None = None

            for t0, t1, p_start, p_end, arc_z, ev_name, _ in segments:
                if t0 <= t <= t1 + 1e-9:
                    span = max(t1 - t0, 1e-6)
                    u = np.clip((t - t0) / span, 0.0, 1.0)
                    bx = p_start[0] + (p_end[0] - p_start[0]) * u
                    by = p_start[1] + (p_end[1] - p_start[1]) * u
                    bz = (
                        p_start[2]
                        + (p_end[2] - p_start[2]) * u
                        + 4.0 * arc_z * u * (1.0 - u)
                    )
                    vx = (p_end[0] - p_start[0]) / span
                    vy = (p_end[1] - p_start[1]) / span
                    vz = (
                        (p_end[2] - p_start[2]) + 4.0 * arc_z * (1.0 - 2.0 * u)
                    ) / span
                    if abs(t - t0) < dt * 0.6:
                        frame_event = ev_name
                    break

            if step == num_steps - 1:
                frame_event = "point_won_A"

            score_str = "0-0 | 15-0 *" if step == num_steps - 1 else "0-0 | 0-0 *"

            players_dict: dict[str, PlayerPose] = {}
            for pid, waypoints in player_tracks.items():
                px, py, pvx, pvy = _interp_player_xy(waypoints, t)
                speed = math.hypot(pvx, pvy)

                # Look towards the ball horizontally
                dx_ball = bx - px
                dy_ball = by - py
                yaw_deg = math.degrees(math.atan2(dx_ball, dy_ball))

                # Check if player is swinging near a shot timestamp
                swing_phase = 0.0
                anim = "run" if speed > 0.6 else "idle"
                for t0, _, _, _, _, ev_name, hitter in segments:
                    if hitter == pid and abs(t - t0) <= 0.28:
                        swing_phase = float(1.0 - min(abs(t - t0) / 0.28, 1.0))
                        anim = ev_name or "swing"
                        break

                players_dict[pid] = PlayerPose(
                    player_id=pid,
                    x=px,
                    y=py,
                    z=0.0,
                    yaw_deg=yaw_deg,
                    animation=anim,
                    team="A" if pid in ("P1", "P2") else "B",
                    swing_phase=swing_phase,
                )

            frames.append(
                FrameState(
                    timestamp=round(t, 4),
                    ball_position=(float(bx), float(by), float(max(bz, 0.033))),
                    ball_velocity=(float(vx), float(vy), float(vz)),
                    players=players_dict,
                    score=score_str,
                    event=frame_event,
                )
            )

        return cls(frames=frames, fps=fps, court=c)


def _interp_player_xy(
    waypoints: list[tuple[float, float, float]],
    t: float,
) -> tuple[float, float, float, float]:
    if t <= waypoints[0][0]:
        return waypoints[0][1], waypoints[0][2], 0.0, 0.0
    if t >= waypoints[-1][0]:
        return waypoints[-1][1], waypoints[-1][2], 0.0, 0.0

    for i in range(len(waypoints) - 1):
        t0, x0, y0 = waypoints[i]
        t1, x1, y1 = waypoints[i + 1]
        if t0 <= t <= t1:
            span = max(t1 - t0, 1e-6)
            u = (t - t0) / span
            # Smoothstep interpolation for natural human acceleration/deceleration
            s = u * u * (3.0 - 2.0 * u)
            ds_dt = 6.0 * u * (1.0 - u) / span
            x = x0 + (x1 - x0) * s
            y = y0 + (y1 - y0) * s
            vx = (x1 - x0) * ds_dt
            vy = (y1 - y0) * ds_dt
            return x, y, vx, vy

    return waypoints[-1][1], waypoints[-1][2], 0.0, 0.0
