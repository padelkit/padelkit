from __future__ import annotations

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from ..court.court import Court
from ..physics.models import BallProperties, EnvironmentConditions, SurfaceMaterials
from ..scoring.entities import Player, Team, TeamId
from ..scoring.match import Match
from ..scoring.score import MatchScore

# Canonical 17-joint Human3.6M (H36M) skeleton ordering used by MotionBERT & PadelKit
H36M_JOINT_NAMES: tuple[str, ...] = (
    "Pelvis",
    "RightHip",
    "RightKnee",
    "RightAnkle",
    "LeftHip",
    "LeftKnee",
    "LeftAnkle",
    "Spine",
    "Thorax",
    "Neck",
    "Head",
    "LeftShoulder",
    "LeftElbow",
    "LeftWrist",
    "RightShoulder",
    "RightElbow",
    "RightWrist",
)


@dataclass(frozen=True)
class PlayerPose:
    """Kinematic pose and 3D skeletal state of a padel player at a single timestamp.

    Coordinates ``(x, y, z)`` are expressed in meters in the centered court
    coordinate system. ``yaw_deg`` follows the same convention as
    :class:`CameraExtrinsics` (``0`` faces ``+Y``, ``180`` faces ``-Y``).

    When ``keypoints_3d`` is populated, it stores the 17 H36M 3D joint coordinates
    ``((jx, jy, jz), ...)`` in the player's local frame (pelvis XY centered at
    ``(0, 0)``, ``Z`` height above floor ``0.0``, facing ``+Y``).
    """

    player_id: str
    x: float
    y: float
    z: float = 0.0
    yaw_deg: float = 0.0
    animation: str = "idle"
    team: str = "A"
    swing_phase: float = 0.0
    keypoints_3d: tuple[tuple[float, float, float], ...] | None = None

    @property
    def world_keypoints_3d(self) -> tuple[tuple[float, float, float], ...] | None:
        """Returns the 17 3D joints transformed into world coordinates ``(X, Y, Z)``."""
        if self.keypoints_3d is None:
            return None
        rad = -math.radians(self.yaw_deg)
        c, s = math.cos(rad), math.sin(rad)
        world_pts: list[tuple[float, float, float]] = []
        for jx, jy, jz in self.keypoints_3d:
            wx = self.x + (jx * c - jy * s)
            wy = self.y + (jx * s + jy * c)
            wz = self.z + jz
            world_pts.append((round(wx, 4), round(wy, 4), round(wz, 4)))
        return tuple(world_pts)

    @classmethod
    def from_world_keypoints_3d(
        cls,
        player_id: str,
        world_keypoints_3d: Sequence[Sequence[float]] | np.ndarray,
        yaw_deg: float | None = None,
        animation: str = "idle",
        team: str = "A",
        swing_phase: float = 0.0,
    ) -> PlayerPose:
        """Constructs a :class:`PlayerPose` from 17 world 3D joints ``(17, 3)``."""
        arr = np.asarray(world_keypoints_3d, dtype=np.float64)
        if arr.shape != (17, 3):
            raise ValueError(
                f"world_keypoints_3d must have shape (17, 3), got {arr.shape}."
            )
        pelvis = arr[0]
        px = float(pelvis[0])
        py = float(pelvis[1])
        min_ankle_z = float(min(arr[3, 2], arr[6, 2]))
        pz = max(0.0, min_ankle_z - 0.08)

        if yaw_deg is None:
            # Transverse hip vector: RightHip (1) -> LeftHip (4)
            hip_vec = arr[1, :2] - arr[4, :2]
            fwd_x = -float(hip_vec[1])
            fwd_y = float(hip_vec[0])
            if math.hypot(fwd_x, fwd_y) > 1e-5:
                yaw_val = math.degrees(math.atan2(fwd_x, fwd_y))
            else:
                yaw_val = 0.0
        else:
            yaw_val = float(yaw_deg)

        # Inverse rotate world joints into local player space
        rad = math.radians(yaw_val)
        c, s = math.cos(rad), math.sin(rad)
        local_pts: list[tuple[float, float, float]] = []
        for j in range(17):
            dx = float(arr[j, 0]) - px
            dy = float(arr[j, 1]) - py
            dz = float(arr[j, 2]) - pz
            lx = dx * c - dy * s
            ly = dx * s + dy * c
            local_pts.append((round(lx, 4), round(ly, 4), round(dz, 4)))

        return cls(
            player_id=player_id,
            x=round(px, 4),
            y=round(py, 4),
            z=round(pz, 4),
            yaw_deg=round(yaw_val, 2),
            animation=animation,
            team=team,
            swing_phase=swing_phase,
            keypoints_3d=tuple(local_pts),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializes the player pose to a dictionary."""
        out: dict[str, Any] = {
            "player_id": self.player_id,
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "z": round(self.z, 4),
            "yaw_deg": round(self.yaw_deg, 2),
            "animation": self.animation,
            "team": self.team,
            "swing_phase": round(self.swing_phase, 3),
        }
        if self.keypoints_3d is not None:
            out["kp3d"] = [
                [round(pt[0], 4), round(pt[1], 4), round(pt[2], 4)]
                for pt in self.keypoints_3d
            ]
        return out


@dataclass(frozen=True)
class FrameState:
    """Complete 3D state of the court, ball, players, and score at instant ``t``."""

    timestamp: float
    ball_position: tuple[float, float, float]
    ball_velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    ball_spin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    players: dict[str, PlayerPose] = field(default_factory=dict)
    score: str = "0-0 | 0-0"
    event: str | None = None
    sets_a: int = 0
    sets_b: int = 0
    games_a: int = 0
    games_b: int = 0
    points_a: str = "0"
    points_b: str = "0"
    server_team: str | None = None
    server_player: str | None = None
    point_index: int = 0
    in_tiebreak: bool = False
    is_gold_point: bool = False

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

    def with_match_score(
        self,
        match_score: MatchScore,
        point_index: int = 0,
        server_team: str | None = None,
        server_player: str | None = None,
        golden_point_enabled: bool = False,
    ) -> FrameState:
        """Returns a copy enriched with structured :class:`MatchScore` fields."""
        srv_team = server_team or (
            match_score.server.team.value if match_score.server is not None else None
        )
        srv_player = server_player or (
            match_score.server.player.name
            if match_score.server is not None and match_score.server.player is not None
            else None
        )
        serve_a = " *" if srv_team == "A" else ""
        serve_b = " *" if srv_team == "B" else ""
        compact_score = (
            f"{match_score.sets_A}-{match_score.sets_B} | "
            f"{match_score.games_A}-{match_score.games_B} | "
            f"{match_score.points_A}{serve_a}-{match_score.points_B}{serve_b}"
        )
        is_gp = bool(match_score.is_gold_point) or (
            golden_point_enabled
            and str(match_score.points_A) == "40"
            and str(match_score.points_B) == "40"
        )
        return replace(
            self,
            score=compact_score,
            sets_a=int(match_score.sets_A),
            sets_b=int(match_score.sets_B),
            games_a=int(match_score.games_A),
            games_b=int(match_score.games_B),
            points_a=str(match_score.points_A),
            points_b=str(match_score.points_B),
            server_team=srv_team,
            server_player=srv_player,
            point_index=int(point_index),
            in_tiebreak=bool(match_score.in_tiebreak or match_score.in_super_tiebreak),
            is_gold_point=is_gp,
        )

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
            "sets_a": self.sets_a,
            "sets_b": self.sets_b,
            "games_a": self.games_a,
            "games_b": self.games_b,
            "points_a": self.points_a,
            "points_b": self.points_b,
            "server_team": self.server_team,
            "server_player": self.server_player,
            "point_index": self.point_index,
            "in_tiebreak": self.in_tiebreak,
            "is_gold_point": self.is_gold_point,
            "event": self.event,
        }


class MatchTimeline:
    """Time-indexed sequence of :class:`FrameState` snapshots and match metadata.

    Supports lossless serialization to and from **Apache Parquet** (`.parquet`),
    CSV files, and Pandas DataFrames so camera-tracked matches, batch physics
    simulations, and Three.js / Blender renderers share a single universal schema.
    """

    PLAYER_IDS: tuple[str, str, str, str] = ("P1", "P2", "P3", "P4")
    PARQUET_METADATA_KEY: bytes = b"padelkit_metadata"
    SCHEMA_VERSION: str = "1.0.0"

    def __init__(
        self,
        frames: list[FrameState] | None = None,
        fps: float = 60.0,
        court: Court | None = None,
        environment: EnvironmentConditions | None = None,
        ball_properties: BallProperties | None = None,
        surface_materials: SurfaceMaterials | None = None,
        match: Match | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if fps <= 0.0:
            raise ValueError("fps must be strictly positive.")
        self.frames: list[FrameState] = list(frames) if frames else []
        self.fps: float = float(fps)
        self.court: Court = court or (
            match.court if match and match.court else Court.fip_standard()
        )
        self.environment: EnvironmentConditions = (
            environment or EnvironmentConditions.standard()
        )
        self.ball_properties: BallProperties = (
            ball_properties or BallProperties.fip_standard()
        )
        self.surface_materials: SurfaceMaterials = (
            surface_materials or SurfaceMaterials.fip_standard()
        )
        self.match: Match | None = match
        self.metadata: dict[str, Any] = dict(metadata) if metadata else {}

    def __len__(self) -> int:
        return len(self.frames)

    @property
    def duration_seconds(self) -> float:
        """Total duration of the timeline in seconds."""
        if not self.frames:
            return 0.0
        return float(self.frames[-1].timestamp - self.frames[0].timestamp)

    @property
    def has_skeletal_poses(self) -> bool:
        """Returns ``True`` if 17-joint 3D skeletal keypoints are present."""
        for f in self.frames:
            for p in f.players.values():
                if p.keypoints_3d is not None:
                    return True
        return False

    def append(self, frame: FrameState) -> None:
        """Appends a :class:`FrameState` snapshot to the timeline."""
        self.frames.append(frame)

    def build_metadata_envelope(self) -> dict[str, Any]:
        """Builds the JSON-compatible match metadata header for Parquet storage."""
        return {
            "schema_version": self.SCHEMA_VERSION,
            "fps": self.fps,
            "duration_seconds": round(self.duration_seconds, 4),
            "frame_count": len(self.frames),
            "has_skeletal_poses": self.has_skeletal_poses,
            "joint_names": list(H36M_JOINT_NAMES),
            "court": self.court.to_dict(),
            "environment": self.environment.to_dict(),
            "ball_properties": self.ball_properties.to_dict(),
            "surface_materials": self.surface_materials.to_dict(),
            "match": self.match.to_dict() if self.match is not None else None,
            "metadata": self.metadata,
        }

    # ------------------------------------------------------------------ #
    # Python Skeletal Pose Baking (Synthesize / Stitch 17-Joint 3D Poses)
    # ------------------------------------------------------------------ #

    def bake_skeletal_poses(
        self,
        kinematics_dir: str | Path | None = None,
    ) -> MatchTimeline:
        """Bakes 17-joint 3D H36M skeletal poses into every :class:`PlayerPose`.

        If ``kinematics_dir`` is provided (e.g. ``data/kinematics_3d``),
        real MotionBERT ``*_X3D_norm.npy`` clips are sampled and synchronized at
        ball impact; otherwise smooth biomechanical 17-joint poses are synthesized
        for every player action (`idle`, `run`, `serve`, `shot_forehand`,
        `shot_backhand`, `shot_volley`, `shot_bandeja`, `shot_vibora`, `shot_lob`,
        `shot_smash`).
        """
        clip_bank: dict[str, np.ndarray] = {}
        if kinematics_dir is not None:
            k_dir = Path(kinematics_dir)
            if k_dir.exists():
                for npy_file in sorted(k_dir.glob("*_X3D_norm.npy")):
                    stem = npy_file.name.removesuffix("_X3D_norm.npy")
                    arr = np.load(npy_file)
                    if arr.ndim == 3 and arr.shape[1:] == (17, 3):
                        clip_bank[stem] = arr
                        if "serve" in stem:
                            clip_bank.setdefault("serve", arr)
                        elif "forehand" in stem:
                            clip_bank.setdefault("shot_forehand", arr)
                        elif "backhand" in stem:
                            clip_bank.setdefault("shot_backhand", arr)
                        elif "bandeja" in stem:
                            clip_bank.setdefault("shot_bandeja", arr)
                        elif "smash" in stem:
                            clip_bank.setdefault("shot_smash", arr)

        n_frames = len(self.frames)
        new_frames: list[FrameState] = []

        for idx, frame in enumerate(self.frames):
            new_players: dict[str, PlayerPose] = {}
            for pid, p in frame.players.items():
                if p.keypoints_3d is not None:
                    new_players[pid] = p
                    continue

                # Determine pre-impact vs post-impact progression
                sw = p.swing_phase
                is_post = False
                if idx + 1 < n_frames:
                    next_p = self.frames[idx + 1].players.get(pid)
                    if next_p is not None and next_p.swing_phase < sw - 1e-4:
                        is_post = True

                anim = p.animation or "idle"
                if anim in clip_bank and sw > 0.0:
                    clip_arr = clip_bank[anim]
                    contact_ratio = 0.55
                    progress = (
                        contact_ratio + (1.0 - sw) * (1.0 - contact_ratio)
                        if is_post
                        else sw * contact_ratio
                    )
                    f_idx = int(
                        np.clip(
                            round(progress * (len(clip_arr) - 1)),
                            0,
                            len(clip_arr) - 1,
                        )
                    )
                    kps_arr = clip_arr[f_idx]
                    # Flip local Y so character faces +Y in PadelKit convention
                    kps = tuple(
                        (
                            round(float(-kps_arr[j, 0]), 4),
                            round(float(-kps_arr[j, 1]), 4),
                            round(float(kps_arr[j, 2]), 4),
                        )
                        for j in range(17)
                    )
                else:
                    kps = _synthesize_biomechanical_h36m_pose(
                        anim=anim,
                        t=frame.timestamp,
                        swing_phase=sw,
                        is_post_impact=is_post,
                    )

                new_players[pid] = replace(p, keypoints_3d=kps)

            new_frames.append(replace(frame, players=new_players))

        self.frames = new_frames
        return self

    # ------------------------------------------------------------------ #
    # DataFrame, CSV & Apache Parquet I/O
    # ------------------------------------------------------------------ #

    def to_dataframe(self, include_skeleton: bool = True) -> pd.DataFrame:
        """Exports the timeline into a tabular :class:`pandas.DataFrame`."""
        export_skels = include_skeleton and self.has_skeletal_poses
        rows: list[dict[str, Any]] = []
        for f in self.frames:
            row: dict[str, Any] = {
                "timestamp": float(f.timestamp),
                "point_index": int(f.point_index),
                "score": f.score,
                "sets_a": int(f.sets_a),
                "sets_b": int(f.sets_b),
                "games_a": int(f.games_a),
                "games_b": int(f.games_b),
                "points_a": str(f.points_a),
                "points_b": str(f.points_b),
                "server_team": f.server_team if f.server_team is not None else "",
                "server_player": f.server_player if f.server_player is not None else "",
                "in_tiebreak": bool(f.in_tiebreak),
                "is_gold_point": bool(f.is_gold_point),
                "event": f.event if f.event is not None else "",
                "ball_x": float(f.ball_position[0]),
                "ball_y": float(f.ball_position[1]),
                "ball_z": float(f.ball_position[2]),
                "ball_vx": float(f.ball_velocity[0]),
                "ball_vy": float(f.ball_velocity[1]),
                "ball_vz": float(f.ball_velocity[2]),
                "ball_wx": float(f.ball_spin[0]),
                "ball_wy": float(f.ball_spin[1]),
                "ball_wz": float(f.ball_spin[2]),
            }
            for pid in self.PLAYER_IDS:
                key = pid.lower()
                p = f.players.get(pid)
                if p is not None:
                    row[f"{key}_x"] = float(p.x)
                    row[f"{key}_y"] = float(p.y)
                    row[f"{key}_z"] = float(p.z)
                    row[f"{key}_yaw"] = float(p.yaw_deg)
                    row[f"{key}_anim"] = p.animation
                    row[f"{key}_team"] = p.team
                    row[f"{key}_swing"] = float(p.swing_phase)
                    if export_skels:
                        kps = p.keypoints_3d
                        for j in range(17):
                            if kps is not None and j < len(kps):
                                row[f"{key}_j{j}_x"] = np.float32(kps[j][0])
                                row[f"{key}_j{j}_y"] = np.float32(kps[j][1])
                                row[f"{key}_j{j}_z"] = np.float32(kps[j][2])
                            else:
                                row[f"{key}_j{j}_x"] = np.float32(np.nan)
                                row[f"{key}_j{j}_y"] = np.float32(np.nan)
                                row[f"{key}_j{j}_z"] = np.float32(np.nan)
                else:
                    row[f"{key}_x"] = np.nan
                    row[f"{key}_y"] = np.nan
                    row[f"{key}_z"] = 0.0
                    row[f"{key}_yaw"] = 0.0
                    row[f"{key}_anim"] = "idle"
                    row[f"{key}_team"] = "A" if pid in ("P1", "P2") else "B"
                    row[f"{key}_swing"] = 0.0
                    if export_skels:
                        for j in range(17):
                            row[f"{key}_j{j}_x"] = np.float32(np.nan)
                            row[f"{key}_j{j}_y"] = np.float32(np.nan)
                            row[f"{key}_j{j}_z"] = np.float32(np.nan)
            rows.append(row)
        return pd.DataFrame(rows)

    def to_csv(self, path: str | Path, include_skeleton: bool = False) -> Path:
        """Saves the timeline to a CSV file and returns the resolved path."""
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df = self.to_dataframe(include_skeleton=include_skeleton)
        df.to_csv(out_path, index=False)
        return out_path

    def to_parquet(
        self,
        path: str | Path,
        compression: str = "zstd",
        include_skeleton: bool = True,
    ) -> Path:
        """Saves the match timeline and metadata header to an Apache Parquet file."""
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df = self.to_dataframe(include_skeleton=include_skeleton)
        table = pa.Table.from_pandas(df, preserve_index=False)

        existing_meta = dict(table.schema.metadata or {})
        existing_meta[self.PARQUET_METADATA_KEY] = json.dumps(
            self.build_metadata_envelope()
        ).encode("utf-8")
        table = table.replace_schema_metadata(existing_meta)

        pq.write_table(table, out_path, compression=compression)
        return out_path

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame,
        court: Court | None = None,
        fps: float | None = None,
        environment: EnvironmentConditions | None = None,
        ball_properties: BallProperties | None = None,
        surface_materials: SurfaceMaterials | None = None,
        match: Match | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MatchTimeline:
        """Reconstructs a :class:`MatchTimeline` from a Pandas DataFrame."""
        required = {"timestamp", "ball_x", "ball_y", "ball_z"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(
                f"DataFrame is missing required columns: {sorted(missing)}"
            )

        cols_set = set(df.columns)
        has_kp_cols = {pid: f"{pid.lower()}_j0_x" in cols_set for pid in cls.PLAYER_IDS}

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

            raw_srv_team = row.get("server_team", "")
            srv_team = (
                str(raw_srv_team)
                if pd.notna(raw_srv_team) and str(raw_srv_team).strip() != ""
                else None
            )
            raw_srv_player = row.get("server_player", "")
            srv_player = (
                str(raw_srv_player)
                if pd.notna(raw_srv_player) and str(raw_srv_player).strip() != ""
                else None
            )

            players: dict[str, PlayerPose] = {}
            for pid in cls.PLAYER_IDS:
                key = pid.lower()
                if f"{key}_x" in cols_set and pd.notna(row[f"{key}_x"]):
                    default_team = "A" if pid in ("P1", "P2") else "B"
                    kps_tuple: tuple[tuple[float, float, float], ...] | None = None
                    if has_kp_cols[pid] and pd.notna(row[f"{key}_j0_x"]):
                        kps_list: list[tuple[float, float, float]] = []
                        for j in range(17):
                            kps_list.append(
                                (
                                    float(row[f"{key}_j{j}_x"]),
                                    float(row[f"{key}_j{j}_y"]),
                                    float(row[f"{key}_j{j}_z"]),
                                )
                            )
                        kps_tuple = tuple(kps_list)

                    players[pid] = PlayerPose(
                        player_id=pid,
                        x=float(row[f"{key}_x"]),
                        y=float(row[f"{key}_y"]),
                        z=float(row.get(f"{key}_z", 0.0)),
                        yaw_deg=float(row.get(f"{key}_yaw", 0.0)),
                        animation=str(row.get(f"{key}_anim", "idle")),
                        team=str(row.get(f"{key}_team", default_team)),
                        swing_phase=float(row.get(f"{key}_swing", 0.0)),
                        keypoints_3d=kps_tuple,
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
                    sets_a=int(row.get("sets_a", 0)),
                    sets_b=int(row.get("sets_b", 0)),
                    games_a=int(row.get("games_a", 0)),
                    games_b=int(row.get("games_b", 0)),
                    points_a=str(row.get("points_a", "0")),
                    points_b=str(row.get("points_b", "0")),
                    server_team=srv_team,
                    server_player=srv_player,
                    point_index=int(row.get("point_index", 0)),
                    in_tiebreak=bool(row.get("in_tiebreak", False)),
                    is_gold_point=bool(row.get("is_gold_point", False)),
                )
            )

        inferred_fps = fps
        if inferred_fps is None:
            if len(frames) >= 2:
                dt = frames[1].timestamp - frames[0].timestamp
                inferred_fps = round(1.0 / dt, 2) if dt > 1e-6 else 60.0
            else:
                inferred_fps = 60.0

        return cls(
            frames=frames,
            fps=inferred_fps,
            court=court,
            environment=environment,
            ball_properties=ball_properties,
            surface_materials=surface_materials,
            match=match,
            metadata=metadata,
        )

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        court: Court | None = None,
    ) -> MatchTimeline:
        """Loads a :class:`MatchTimeline` from a CSV file on disk."""
        df = pd.read_csv(path)
        return cls.from_dataframe(df, court=court)

    @classmethod
    def from_parquet(
        cls,
        path: str | Path,
        court: Court | None = None,
    ) -> MatchTimeline:
        """Loads a :class:`MatchTimeline` and embedded metadata from a Parquet file."""
        table = pq.read_table(path)
        schema_meta = table.schema.metadata or {}
        raw_meta = schema_meta.get(cls.PARQUET_METADATA_KEY)

        parsed_court = court
        parsed_env: EnvironmentConditions | None = None
        parsed_ball: BallProperties | None = None
        parsed_surf: SurfaceMaterials | None = None
        parsed_match: Match | None = None
        parsed_fps: float | None = None
        custom_meta: dict[str, Any] | None = None

        if raw_meta is not None:
            envelope = json.loads(raw_meta.decode("utf-8"))
            if parsed_fps is None and "fps" in envelope:
                parsed_fps = float(envelope["fps"])
            if parsed_court is None and isinstance(envelope.get("court"), dict):
                parsed_court = Court.from_dict(envelope["court"])
            if isinstance(envelope.get("environment"), dict):
                parsed_env = EnvironmentConditions.from_dict(envelope["environment"])
            if isinstance(envelope.get("ball_properties"), dict):
                parsed_ball = BallProperties.from_dict(envelope["ball_properties"])
            if isinstance(envelope.get("surface_materials"), dict):
                parsed_surf = SurfaceMaterials.from_dict(envelope["surface_materials"])
            if isinstance(envelope.get("match"), dict):
                parsed_match = Match.from_dict(envelope["match"])
            if isinstance(envelope.get("metadata"), dict):
                custom_meta = envelope["metadata"]

        df = table.to_pandas()
        return cls.from_dataframe(
            df=df,
            court=parsed_court,
            fps=parsed_fps,
            environment=parsed_env,
            ball_properties=parsed_ball,
            surface_materials=parsed_surf,
            match=parsed_match,
            metadata=custom_meta,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializes the timeline metadata and frames to a JSON-compatible dict."""
        return {
            "fps": self.fps,
            "duration_seconds": round(self.duration_seconds, 4),
            "frame_count": len(self.frames),
            "has_skeletal_poses": self.has_skeletal_poses,
            "environment": self.environment.to_dict(),
            "ball_properties": self.ball_properties.to_dict(),
            "surface_materials": self.surface_materials.to_dict(),
            "match": self.match.to_dict() if self.match is not None else None,
            "metadata": self.metadata,
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
        environment: EnvironmentConditions | None = None,
        ball_properties: BallProperties | None = None,
        surface_materials: SurfaceMaterials | None = None,
        match: Match | None = None,
        bake_skeleton: bool = False,
    ) -> MatchTimeline:
        """Generates a 3D padel rally simulated with :class:`BallPhysicsEngine`."""
        from ..physics.engine import BallPhysicsEngine
        from ..physics.models import BallState

        c = court or Court.fip_standard()
        env = environment or EnvironmentConditions.standard()
        ball_props = ball_properties or BallProperties.fip_standard()
        surf_mats = surface_materials or SurfaceMaterials.fip_standard()
        engine = BallPhysicsEngine(
            court=c,
            ball=ball_props,
            environment=env,
            surfaces=surf_mats,
        )
        dt = 1.0 / fps

        if match is None:
            match = Match(
                teams={
                    TeamId.A: Team(
                        TeamId.A,
                        Player("Player 1", side="right"),
                        Player("Player 2", side="left"),
                        name="Team A",
                    ),
                    TeamId.B: Team(
                        TeamId.B,
                        Player("Player 3", side="left"),
                        Player("Player 4", side="right"),
                        name="Team B",
                    ),
                },
                court=c,
            )
            add_demo_point = True
        else:
            add_demo_point = False
        initial_score = match.history.get_current_score()

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
            (
                1.35,
                "serve",
                "P1",
                (1.8, -7.1, 0.95),
                (-4.3, 13.8, 3.3),
                -950.0,
                380.0,
            ),
            (
                1.00,
                "shot_forehand",
                "P3",
                None,
                (1.5, -12.6, 4.4),
                1650.0,
                -150.0,
            ),
            (
                1.60,
                "shot_bandeja",
                "P2",
                None,
                (4.1, 12.2, 2.2),
                -2100.0,
                -420.0,
            ),
            (
                1.60,
                "shot_lob",
                "P4",
                None,
                (-1.0, -9.2, 9.6),
                850.0,
                0.0,
            ),
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

        shot_trajectories = []
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
            hit_events.append((t_cursor, ev_name, hitter, strike_pos))

            end_state = traj.state_at(traj.duration_seconds)
            last_pos = end_state.position
            t_cursor += dur

        total_t = t_cursor

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

            for seg_idx, (t0, traj) in enumerate(shot_trajectories):
                t1 = t0 + traj.duration_seconds
                if t0 <= t <= t1 + 1e-9 or seg_idx == len(shot_trajectories) - 1:
                    local_t = float(np.clip(t - t0, 0.0, traj.duration_seconds))
                    ball_state = traj.state_at(local_t)

                    if abs(t - t0) < dt * 0.55:
                        frame_event = hit_events[seg_idx][1]
                    else:
                        for b in traj.bounces:
                            if abs(b.timestamp - local_t) <= dt * 0.55:
                                frame_event = (
                                    f"bounce_{b.surface.value}_{b.regime.value}"
                                )
                                break
                    break

            if step == num_steps - 1:
                frame_event = "point_won_A"
                if add_demo_point:
                    end_score = match.history.add_point(TeamId.A)
                else:
                    end_score = initial_score
                active_score = end_score
            else:
                active_score = initial_score

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
                    if hitter == pid and abs(t - hit_t) <= 0.38:
                        swing_phase = float(1.0 - min(abs(t - hit_t) / 0.38, 1.0))
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

            srv_team = (
                active_score.server.team.value
                if active_score.server is not None
                else "A"
            )
            srv_player = (
                active_score.server.player.name
                if active_score.server is not None
                and active_score.server.player is not None
                else "Player 1"
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
                    sets_a=int(active_score.sets_A),
                    sets_b=int(active_score.sets_B),
                    games_a=int(active_score.games_A),
                    games_b=int(active_score.games_B),
                    points_a=str(active_score.points_A),
                    points_b=str(active_score.points_B),
                    server_team=srv_team,
                    server_player=srv_player,
                    point_index=1 if step == num_steps - 1 else 0,
                )
            )

        timeline = cls(
            frames=frames,
            fps=fps,
            court=c,
            environment=env,
            ball_properties=ball_props,
            surface_materials=surf_mats,
            match=match,
        )
        if bake_skeleton:
            timeline.bake_skeletal_poses()
        return timeline


def _synthesize_biomechanical_h36m_pose(
    anim: str,
    t: float,
    swing_phase: float,
    is_post_impact: bool,
) -> tuple[tuple[float, float, float], ...]:
    """Synthesizes a 17-joint H36M 3D pose in local player space (facing +Y, Z up)."""
    is_run = anim == "run"
    cycle = t * 14.0
    stride = math.sin(cycle) * 0.22 if is_run else 0.0
    lift_l = max(0.0, -math.sin(cycle)) * 0.12 if is_run else 0.0
    lift_r = max(0.0, math.sin(cycle)) * 0.12 if is_run else 0.0
    bounce_z = abs(math.sin(cycle)) * 0.03 if is_run else math.sin(t * 4.0) * 0.01

    # Progress from -1 (backswing) -> 0 (impact) -> +1 (follow-through)
    swing_signed = (1.0 - swing_phase) if is_post_impact else -(1.0 - swing_phase)
    active_swing = swing_phase > 0.01

    # Base joints in local space (X right, Y forward, Z up)
    pelvis = (0.0, 0.0, 0.90 + bounce_z)
    r_hip = (0.105, 0.0, 0.88 + bounce_z)
    l_hip = (-0.105, 0.0, 0.88 + bounce_z)

    r_knee = (0.11, stride * 0.5 + 0.05, 0.48 + lift_r * 0.5)
    r_ankle = (0.11, stride, 0.08 + lift_r)
    l_knee = (-0.11, -stride * 0.5 + 0.05, 0.48 + lift_l * 0.5)
    l_ankle = (-0.11, -stride, 0.08 + lift_l)

    lean_y = 0.06 if is_run else 0.03
    spine = (0.0, lean_y * 0.5, 1.12 + bounce_z)
    thorax = (0.0, lean_y, 1.36 + bounce_z)
    neck = (0.0, lean_y * 1.1, 1.48 + bounce_z)
    head = (0.0, lean_y * 1.2, 1.66 + bounce_z)

    # Upper body coil during strokes
    coil = -swing_signed * 0.35 if active_swing else 0.0
    cos_c, sin_c = math.cos(coil), math.sin(coil)
    l_sh = (-0.18 * cos_c, -0.18 * sin_c + lean_y, 1.38 + bounce_z)
    r_sh = (0.18 * cos_c, 0.18 * sin_c + lean_y, 1.38 + bounce_z)

    l_elbow = (l_sh[0] - 0.08, l_sh[1] + 0.14 - stride * 0.3, 1.16 + bounce_z)
    l_wrist = (l_sh[0] - 0.04, l_sh[1] + 0.26 - stride * 0.5, 1.10 + bounce_z)

    if active_swing and ("smash" in anim or "bandeja" in anim or "vibora" in anim):
        # Overhead stroke arc
        r_elbow = (
            r_sh[0] + 0.12,
            r_sh[1] + 0.12 * (1.0 + swing_signed),
            1.58 + 0.12 * swing_phase,
        )
        r_wrist = (
            r_sh[0] + 0.08 - 0.12 * swing_signed,
            r_sh[1] + 0.24 * (0.4 + swing_signed),
            1.82 + 0.18 * swing_phase - 0.25 * max(0.0, swing_signed),
        )
    elif active_swing:
        # Groundstroke / serve / volley arc
        r_elbow = (
            r_sh[0] + 0.14 * (1.0 - 0.4 * swing_signed),
            r_sh[1] + 0.16 * (0.3 + swing_signed),
            1.16 + 0.06 * swing_phase,
        )
        r_wrist = (
            r_sh[0] + 0.18 - 0.22 * swing_signed,
            r_sh[1] + 0.32 * (0.35 + swing_signed),
            1.08 + 0.14 * swing_phase + 0.12 * max(0.0, swing_signed),
        )
    else:
        # Ready stance / running arm swing
        r_elbow = (r_sh[0] + 0.08, r_sh[1] + 0.14 + stride * 0.3, 1.16 + bounce_z)
        r_wrist = (r_sh[0] + 0.05, r_sh[1] + 0.28 + stride * 0.5, 1.12 + bounce_z)

    pts = (
        pelvis,
        r_hip,
        r_knee,
        r_ankle,
        l_hip,
        l_knee,
        l_ankle,
        spine,
        thorax,
        neck,
        head,
        l_sh,
        l_elbow,
        l_wrist,
        r_sh,
        r_elbow,
        r_wrist,
    )
    return tuple((round(p[0], 4), round(p[1], 4), round(p[2], 4)) for p in pts)


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
