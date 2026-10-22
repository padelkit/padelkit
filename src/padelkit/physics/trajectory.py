import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..court.court import Court
from ..court.enums import CoordinateSystem
from ..viz.timeline import FrameState, MatchTimeline
from .enums import ContactRegime, SurfaceType
from .models import BallState


@dataclass(frozen=True)
class BounceEvent:
    """Detailed record of a ball collision and bounce against a court surface."""

    timestamp: float
    surface: SurfaceType
    position: tuple[float, float, float]
    velocity_before: tuple[float, float, float]
    velocity_after: tuple[float, float, float]
    angular_velocity_before: tuple[float, float, float]
    angular_velocity_after: tuple[float, float, float]
    regime: ContactRegime

    @property
    def speed_before(self) -> float:
        """Ball speed immediately before impact in ``m/s``."""
        vx, vy, vz = self.velocity_before
        return math.sqrt(vx * vx + vy * vy + vz * vz)

    @property
    def speed_after(self) -> float:
        """Ball speed immediately after impact in ``m/s``."""
        vx, vy, vz = self.velocity_after
        return math.sqrt(vx * vx + vy * vy + vz * vz)

    @property
    def spin_rpm_before(self) -> float:
        """Ball spin rate immediately before impact in ``RPM``."""
        wx, wy, wz = self.angular_velocity_before
        return (math.sqrt(wx * wx + wy * wy + wz * wz) * 60.0) / (2.0 * math.pi)

    @property
    def spin_rpm_after(self) -> float:
        """Ball spin rate immediately after impact in ``RPM``."""
        wx, wy, wz = self.angular_velocity_after
        return (math.sqrt(wx * wx + wy * wy + wz * wz) * 60.0) / (2.0 * math.pi)

    def to_dict(self) -> dict[str, Any]:
        """Serializes the bounce event to a plain dictionary."""
        return {
            "timestamp": round(self.timestamp, 4),
            "surface": self.surface.value,
            "regime": self.regime.value,
            "position": [round(c, 4) for c in self.position],
            "velocity_before": [round(c, 4) for c in self.velocity_before],
            "velocity_after": [round(c, 4) for c in self.velocity_after],
            "speed_before_ms": round(self.speed_before, 3),
            "speed_after_ms": round(self.speed_after, 3),
            "spin_rpm_before": round(self.spin_rpm_before, 1),
            "spin_rpm_after": round(self.spin_rpm_after, 1),
        }


class BallTrajectory:
    """Time-resolved 9D ball trajectory with recorded bounce events and analytics."""

    def __init__(
        self,
        timestamps: np.ndarray,
        states: np.ndarray,
        bounces: list[BounceEvent] | None = None,
        coordinate_system: CoordinateSystem = CoordinateSystem.CENTERED,
    ) -> None:
        t_arr = np.asarray(timestamps, dtype=np.float64).ravel()
        s_arr = np.asarray(states, dtype=np.float64)
        if s_arr.ndim != 2 or s_arr.shape[1] != 9:
            raise ValueError("states must be a 2D array of shape (N, 9).")
        if t_arr.shape[0] != s_arr.shape[0]:
            raise ValueError("timestamps and states must have the same length N.")

        self.timestamps: np.ndarray = t_arr
        self.states: np.ndarray = s_arr
        self.bounces: list[BounceEvent] = list(bounces) if bounces else []
        self.coordinate_system: CoordinateSystem = coordinate_system

    def __len__(self) -> int:
        return int(self.timestamps.shape[0])

    # ------------------------------------------------------------------ #
    # Kinematic Arrays & Summary Metrics
    # ------------------------------------------------------------------ #

    @property
    def positions(self) -> np.ndarray:
        """Array of 3D positions ``(N, 3)`` in meters."""
        return self.states[:, 0:3]

    @property
    def velocities(self) -> np.ndarray:
        """Array of 3D linear velocities ``(N, 3)`` in ``m/s``."""
        return self.states[:, 3:6]

    @property
    def angular_velocities(self) -> np.ndarray:
        """Array of 3D angular velocities ``(N, 3)`` in ``rad/s``."""
        return self.states[:, 6:9]

    @property
    def speeds(self) -> np.ndarray:
        """Array of linear speeds ``(N,)`` in ``m/s``."""
        return np.linalg.norm(self.velocities, axis=1)

    @property
    def spin_rpms(self) -> np.ndarray:
        """Array of spin rates ``(N,)`` in ``RPM``."""
        return np.linalg.norm(self.angular_velocities, axis=1) * (
            60.0 / (2.0 * math.pi)
        )

    @property
    def duration_seconds(self) -> float:
        """Total duration of the trajectory in seconds."""
        if len(self.timestamps) < 2:
            return 0.0
        return float(self.timestamps[-1] - self.timestamps[0])

    @property
    def max_height(self) -> float:
        """Maximum height ``Z`` reached along the trajectory in meters."""
        return float(np.max(self.states[:, 2]))

    @property
    def max_speed(self) -> float:
        """Peak linear speed along the trajectory in ``m/s``."""
        return float(np.max(self.speeds))

    def state_at(self, timestamp: float) -> BallState:
        """Interpolates the 9D :class:`BallState` at an arbitrary ``timestamp``."""
        if timestamp <= self.timestamps[0]:
            return BallState.from_vector(self.states[0])
        if timestamp >= self.timestamps[-1]:
            return BallState.from_vector(self.states[-1])

        idx = int(np.searchsorted(self.timestamps, timestamp))
        t0, t1 = self.timestamps[idx - 1], self.timestamps[idx]
        alpha = (timestamp - t0) / max(t1 - t0, 1e-12)
        interp = (1.0 - alpha) * self.states[idx - 1] + alpha * self.states[idx]
        return BallState.from_vector(interp)

    # ------------------------------------------------------------------ #
    # Export to DataFrame, CSV & 3D Visualizer Timeline
    # ------------------------------------------------------------------ #

    def to_dataframe(self) -> pd.DataFrame:
        """Exports the trajectory states and bounce labels to a DataFrame."""
        df = pd.DataFrame(
            {
                "timestamp": self.timestamps,
                "x": self.states[:, 0],
                "y": self.states[:, 1],
                "z": self.states[:, 2],
                "vx": self.states[:, 3],
                "vy": self.states[:, 4],
                "vz": self.states[:, 5],
                "wx": self.states[:, 6],
                "wy": self.states[:, 7],
                "wz": self.states[:, 8],
                "speed_ms": self.speeds,
                "spin_rpm": self.spin_rpms,
            }
        )
        return df

    def to_csv(self, path: str | Path) -> Path:
        """Saves the trajectory DataFrame to a CSV file on disk."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self.to_dataframe().to_csv(out, index=False)
        return out

    def to_timeline(
        self,
        court: Court | None = None,
        fps: float = 60.0,
    ) -> MatchTimeline:
        """Resamples the trajectory into a :class:`MatchTimeline` for 3D viewing."""
        c = court or Court.fip_standard()
        dt = 1.0 / fps
        t_start = float(self.timestamps[0])
        t_end = float(self.timestamps[-1])
        num_frames = max(1, int(round((t_end - t_start) * fps)) + 1)

        frames: list[FrameState] = []
        for i in range(num_frames):
            t = min(t_start + i * dt, t_end)
            bs = self.state_at(t)
            pos = bs.position
            if self.coordinate_system is CoordinateSystem.CORNER_BASED:
                pos = (pos[0] - c.width / 2.0, pos[1] - c.length / 2.0, pos[2])

            ev_str: str | None = None
            for b in self.bounces:
                if abs(b.timestamp - t) <= dt * 0.55:
                    ev_str = f"bounce_{b.surface.value}"
                    break

            frames.append(
                FrameState(
                    timestamp=round(t, 4),
                    ball_position=pos,
                    ball_velocity=bs.velocity,
                    players={},
                    score=f"{bs.speed_kmh:.0f} km/h | {bs.spin_rpm:.0f} RPM",
                    event=ev_str,
                )
            )
        return MatchTimeline(frames=frames, fps=fps, court=c)
