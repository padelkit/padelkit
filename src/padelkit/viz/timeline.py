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
    ball_spin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    players: dict[str, PlayerPose] = field(default_factory=dict)
    score: str = "0-0 | 0-0"
    event: str | None = None

    @property
    def ball_speed_ms(self) -> float:
        """Linear ball speed in ``m/s``."""
        vx, vy, vz = self.ball_velocity
        return math.sqrt(vx * vx + vy * vy + vz * vz)

    @property
    def ball_speed_kmh(self) -> float:
        """Linear ball speed in ``km/h``."""
        return self.ball_speed_ms * 3.6

    @property
    def ball_spin_rpm(self) -> float:
        """Ball angular speed in revolutions per minute (``RPM``)."""
        wx, wy, wz = self.ball_spin
        return (math.sqrt(wx * wx + wy * wy + wz * wz) * 60.0) / (2.0 * math.pi)

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
            "ball_spin": [
                round(self.ball_spin[0], 2),
                round(self.ball_spin[1], 2),
                round(self.ball_spin[2], 2),
            ],
            "ball_speed_kmh": round(self.ball_speed_kmh, 1),
            "ball_spin_rpm": round(self.ball_spin_rpm, 0),
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
                "ball_wx": f.ball_spin[0],
                "ball_wy": f.ball_spin[1],
                "ball_wz": f.ball_spin[2],
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
            bwx = float(row.get("ball_wx", 0.0))
            bwy = float(row.get("ball_wy", 0.0))
            bwz = float(row.get("ball_wz", 0.0))
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
                    ball_spin=(bwx, bwy, bwz),
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
    # 9D Physics-Driven Demo Rally Generator
    # ------------------------------------------------------------------ #

    @classmethod
    def demo_rally(
        cls,
        court: Court | None = None,
        fps: float = 60.0,
    ) -> "MatchTimeline":
        """Generates a 3D padel rally simulated with :class:`BallPhysicsEngine`.

        Each shot in the rally is integrated using 9D RK4 aerodynamics (gravity,
        felt drag, Spindt Magnus lift) and Coulomb Sliding/Rolling rebounds:

        1. **Serve (P1, Team A):** Underhand slice serve into the FAR-left box.
        2. **Forehand Return (P3, Team B):** Topspin cross-court return after bounce.
        3. **Bandeja Volley (P2, Team A):** Heavy backspin cross-court volley
           bouncing on the floor (``ROLLING``) and off the back glass (``SLIDING``).
        4. **Defensive Lob (P4, Team B):** High lob off the back glass over the net.
        5. **Topspin Smash (P1, Team A):** Overhead smash bouncing deep, kicking
           high off the FAR back glass and returning towards the net to win the point.
        """
        from ..physics.engine import BallPhysicsEngine
        from ..physics.models import BallState

        c = court or Court.fip_standard()
        engine = BallPhysicsEngine(court=c)
        dt = 1.0 / fps

        # Shot specifications:
        # (duration_s, shot_event, hitter_id, pos_override, vel_xyz, topspin, sidespin)
        shot_specs: list[
            tuple[
                float,
                str,
                str,
                tuple[float, float, float] | None,
                tuple[float, float, float],
                float,
                float,
            ]
        ] = [
            # 1. P1 Serve: diagonal slice serve from right near box to far left box
            (
                1.35,
                "serve",
                "P1",
                (1.8, -7.1, 0.95),
                (-4.3, 13.8, 3.3),
                -950.0,
                380.0,
            ),
            # 2. P3 Return: topspin drive back towards P2 at the net
            (
                1.00,
                "shot_forehand",
                "P3",
                None,
                (1.5, -12.6, 4.4),
                1650.0,
                -150.0,
            ),
            # 3. P2 Bandeja: sliced cross-court into far right corner + back glass
            (
                1.60,
                "shot_bandeja",
                "P2",
                None,
                (4.1, 12.2, 2.2),
                -2100.0,
                -420.0,
            ),
            # 4. P4 Defensive Lob: high trajectory over P1
            (
                1.60,
                "shot_lob",
                "P4",
                None,
                (-1.0, -9.2, 9.6),
                850.0,
                0.0,
            ),
            # 5. P1 Power Topspin Smash: bounces deep, kicks high off back glass
            (
                1.95,
                "shot_smash",
                "P1",
                None,
                (-2.8, 19.5, -3.2),
                2900.0,
                250.0,
            ),
        ]

        # Simulate each shot sequentially with BallPhysicsEngine
        shot_trajectories = []
        shot_start_times: list[float] = []
        hit_events: list[tuple[float, str, str, tuple[float, float, float]]] = []

        t_cursor = 0.0
        last_pos = (1.8, -7.1, 0.95)

        for (
            dur,
            ev_name,
            hitter,
            pos_override,
            vel,
            topspin,
            sidespin,
        ) in shot_specs:
            start_pos = pos_override if pos_override is not None else last_pos
            # Clamp start_pos height to playable strike height if needed
            strike_pos = (
                float(np.clip(start_pos[0], -4.6, 4.6)),
                float(np.clip(start_pos[1], -9.6, 9.6)),
                float(np.clip(start_pos[2], 0.55, 2.75)),
            )
            init_state = BallState.from_shot(
                position=strike_pos,
                velocity=vel,
                topspin_rpm=topspin,
                sidespin_rpm=sidespin,
            )
            traj = engine.simulate(init_state, duration_s=dur, dt=0.002)
            shot_trajectories.append((t_cursor, traj))
            shot_start_times.append(t_cursor)
            hit_events.append((t_cursor, ev_name, hitter, strike_pos))

            end_state = traj.state_at(traj.duration_seconds)
            last_pos = end_state.position
            t_cursor += dur

        total_t = t_cursor

        # Build tactical player tracks anchored to exact ball interception positions
        p1_hit_0 = hit_events[0][3]
        p3_hit_1 = hit_events[1][3]
        p2_hit_2 = hit_events[2][3]
        p4_hit_3 = hit_events[3][3]
        p1_hit_4 = hit_events[4][3]

        player_tracks: dict[str, list[tuple[float, float, float]]] = {
            "P1": [
                (0.0, p1_hit_0[0], p1_hit_0[1] - 0.25),
                (0.9, 1.8, -6.2),
                (2.3, 1.6, -2.8),
                (4.0, 1.7, -2.5),
                (5.55, p1_hit_4[0] + 0.25, p1_hit_4[1] - 0.2),
                (total_t, 1.6, -2.8),
            ],
            "P2": [
                (0.0, -2.1, -3.2),
                (1.35, -1.9, -2.7),
                (2.35, p2_hit_2[0] - 0.25, p2_hit_2[1] - 0.15),
                (4.2, -1.9, -3.5),
                (5.6, -2.1, -4.0),
                (total_t, -1.8, -2.8),
            ],
            "P3": [
                (0.0, -2.6, 7.5),
                (1.35, p3_hit_1[0] - 0.25, p3_hit_1[1] + 0.2),
                (2.8, -2.3, 7.2),
                (4.5, -2.2, 6.8),
                (6.2, -2.6, 7.5),
                (total_t, -1.8, 3.8),
            ],
            "P4": [
                (0.0, 2.3, 7.4),
                (2.0, 2.2, 7.2),
                (3.95, p4_hit_3[0] + 0.25, p4_hit_3[1] + 0.2),
                (5.5, 2.3, 7.2),
                (total_t, 2.1, 6.6),
            ],
        }

        num_steps = int(round(total_t * fps)) + 1
        frames: list[FrameState] = []

        for step in range(num_steps):
            t = min(step * dt, total_t)
            ball_state = BallState()
            frame_event: str | None = None

            # Locate active shot segment
            for seg_idx, (t0, traj) in enumerate(shot_trajectories):
                t1 = t0 + traj.duration_seconds
                if t0 <= t <= t1 + 1e-9 or seg_idx == len(shot_trajectories) - 1:
                    local_t = float(np.clip(t - t0, 0.0, traj.duration_seconds))
                    ball_state = traj.state_at(local_t)

                    # Check shot start event
                    if abs(t - t0) < dt * 0.55:
                        frame_event = hit_events[seg_idx][1]
                    else:
                        # Check bounce events within this shot
                        for b in traj.bounces:
                            if abs(b.timestamp - local_t) <= dt * 0.55:
                                frame_event = (
                                    f"bounce_{b.surface.value}_{b.regime.value}"
                                )
                                break
                    break

            if step == num_steps - 1:
                frame_event = "point_won_A"

            score_str = "0-0 | 15-0 *" if step == num_steps - 1 else "0-0 | 0-0 *"
            bx, by, bz = ball_state.position

            players_dict: dict[str, PlayerPose] = {}
            for pid, waypoints in player_tracks.items():
                px, py, pvx, pvy = _interp_player_xy(waypoints, t)
                speed = math.hypot(pvx, pvy)

                dx_ball = bx - px
                dy_ball = by - py
                yaw_deg = math.degrees(math.atan2(dx_ball, dy_ball))

                swing_phase = 0.0
                anim = "run" if speed > 0.6 else "idle"
                for hit_t, ev_name, hitter, _ in hit_events:
                    if hitter == pid and abs(t - hit_t) <= 0.28:
                        swing_phase = float(1.0 - min(abs(t - hit_t) / 0.28, 1.0))
                        anim = ev_name
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
                    ball_position=(float(bx), float(by), float(max(bz, 0.0325))),
                    ball_velocity=ball_state.velocity,
                    ball_spin=ball_state.angular_velocity,
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
            s = u * u * (3.0 - 2.0 * u)
            ds_dt = 6.0 * u * (1.0 - u) / span
            x = x0 + (x1 - x0) * s
            y = y0 + (y1 - y0) * s
            vx = (x1 - x0) * ds_dt
            vy = (y1 - y0) * ds_dt
            return x, y, vx, vy

    return waypoints[-1][1], waypoints[-1][2], 0.0, 0.0
