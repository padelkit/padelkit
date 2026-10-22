from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..court.court import Court
from ..court.enums import CoordinateSystem
from .distortion import CameraDistortion
from .enums import CameraPreset
from .extrinsics import CameraExtrinsics
from .intrinsics import CameraIntrinsics


@dataclass(frozen=True)
class Camera:
    """Complete projective camera model with intrinsics, extrinsics, and distortion.

    All 3D world coordinates follow the PadelKit court coordinate system
    (by default :attr:`CoordinateSystem.CENTERED`, where ``(0, 0, 0)`` is at
    the midpoint of the net on the court floor).
    """

    intrinsics: CameraIntrinsics
    extrinsics: CameraExtrinsics
    distortion: CameraDistortion = field(default_factory=CameraDistortion.none)
    name: str = "camera"

    # ------------------------------------------------------------------ #
    # Presets & Factory Classmethods
    # ------------------------------------------------------------------ #

    @classmethod
    def broadcast_near(
        cls,
        court: Court | None = None,
        height_m: float = 5.8,
        distance_from_back_m: float = 3.8,
        target_y_m: float = -0.5,
        horizontal_fov_deg: float = 78.0,
        width_px: int = 1920,
        height_px: int = 1080,
        distortion: CameraDistortion | None = None,
    ) -> "Camera":
        """Creates a standard TV broadcast camera behind the NEAR back wall."""
        c = court or Court.fip_standard()
        hl = c.length / 2.0
        intr = CameraIntrinsics.from_fov(
            width_px=width_px,
            height_px=height_px,
            horizontal_fov_deg=horizontal_fov_deg,
        )
        extr = CameraExtrinsics.from_look_at(
            position=(0.0, -(hl + distance_from_back_m), height_m),
            target=(0.0, target_y_m, 0.5),
        )
        return cls(
            intrinsics=intr,
            extrinsics=extr,
            distortion=distortion or CameraDistortion.none(),
            name=CameraPreset.BROADCAST_NEAR.value,
        )

    @classmethod
    def broadcast_far(
        cls,
        court: Court | None = None,
        height_m: float = 5.8,
        distance_from_back_m: float = 3.8,
        target_y_m: float = 0.5,
        horizontal_fov_deg: float = 78.0,
        width_px: int = 1920,
        height_px: int = 1080,
        distortion: CameraDistortion | None = None,
    ) -> "Camera":
        """Creates a standard TV broadcast camera behind the FAR back wall."""
        c = court or Court.fip_standard()
        hl = c.length / 2.0
        intr = CameraIntrinsics.from_fov(
            width_px=width_px,
            height_px=height_px,
            horizontal_fov_deg=horizontal_fov_deg,
        )
        extr = CameraExtrinsics.from_look_at(
            position=(0.0, hl + distance_from_back_m, height_m),
            target=(0.0, target_y_m, 0.5),
        )
        return cls(
            intrinsics=intr,
            extrinsics=extr,
            distortion=distortion or CameraDistortion.none(),
            name=CameraPreset.BROADCAST_FAR.value,
        )

    @classmethod
    def overhead_zenith(
        cls,
        height_m: float = 14.5,
        horizontal_fov_deg: float = 82.0,
        width_px: int = 1920,
        height_px: int = 1080,
        distortion: CameraDistortion | None = None,
    ) -> "Camera":
        """Creates a top-down tactical zenith camera directly above the net center."""
        intr = CameraIntrinsics.from_fov(
            width_px=width_px,
            height_px=height_px,
            horizontal_fov_deg=horizontal_fov_deg,
        )
        extr = CameraExtrinsics.from_look_at(
            position=(0.0, 0.0, height_m),
            target=(0.0, 0.0, 0.0),
        )
        return cls(
            intrinsics=intr,
            extrinsics=extr,
            distortion=distortion or CameraDistortion.none(),
            name=CameraPreset.OVERHEAD_ZENITH.value,
        )

    @classmethod
    def from_preset(
        cls,
        preset: CameraPreset | str,
        court: Court | None = None,
        width_px: int = 1920,
        height_px: int = 1080,
        distortion: CameraDistortion | None = None,
    ) -> "Camera":
        """Creates a :class:`Camera` from a named :class:`CameraPreset`."""
        preset_enum = (
            preset if isinstance(preset, CameraPreset) else CameraPreset(preset)
        )
        c = court or Court.fip_standard()
        hw = c.width / 2.0
        hl = c.length / 2.0
        dist_cfg = distortion or CameraDistortion.none()

        if preset_enum is CameraPreset.BROADCAST_NEAR:
            return cls.broadcast_near(
                court=c, width_px=width_px, height_px=height_px, distortion=dist_cfg
            )
        if preset_enum is CameraPreset.BROADCAST_FAR:
            return cls.broadcast_far(
                court=c, width_px=width_px, height_px=height_px, distortion=dist_cfg
            )
        if preset_enum is CameraPreset.OVERHEAD_ZENITH:
            return cls.overhead_zenith(
                width_px=width_px, height_px=height_px, distortion=dist_cfg
            )

        preset_configs: dict[
            CameraPreset,
            tuple[tuple[float, float, float], tuple[float, float, float], float],
        ] = {
            CameraPreset.CORNER_NEAR_LEFT: (
                (-hw - 0.8, -hl - 0.8, 4.4),
                (0.5, 0.5, 0.8),
                92.0,
            ),
            CameraPreset.CORNER_NEAR_RIGHT: (
                (hw + 0.8, -hl - 0.8, 4.4),
                (-0.5, 0.5, 0.8),
                92.0,
            ),
            CameraPreset.CORNER_FAR_LEFT: (
                (-hw - 0.8, hl + 0.8, 4.4),
                (0.5, -0.5, 0.8),
                92.0,
            ),
            CameraPreset.CORNER_FAR_RIGHT: (
                (hw + 0.8, hl + 0.8, 4.4),
                (-0.5, -0.5, 0.8),
                92.0,
            ),
            CameraPreset.SIDE_NET_LEFT: ((-hw - 4.5, 0.0, 3.2), (0.0, 0.0, 0.9), 84.0),
            CameraPreset.SIDE_NET_RIGHT: ((hw + 4.5, 0.0, 3.2), (0.0, 0.0, 0.9), 84.0),
        }
        pos, tgt, fov = preset_configs[preset_enum]
        intr = CameraIntrinsics.from_fov(
            width_px=width_px, height_px=height_px, horizontal_fov_deg=fov
        )
        extr = CameraExtrinsics.from_look_at(position=pos, target=tgt)
        return cls(
            intrinsics=intr,
            extrinsics=extr,
            distortion=dist_cfg,
            name=preset_enum.value,
        )

    # ------------------------------------------------------------------ #
    # 3D -> 2D Projection Methods
    # ------------------------------------------------------------------ #

    def _to_centered_array(
        self,
        points_3d: np.ndarray | Sequence[Any],
        coordinate_system: CoordinateSystem,
        court: Court | None = None,
    ) -> np.ndarray:
        pts = np.asarray(points_3d, dtype=np.float64)
        if coordinate_system is CoordinateSystem.CORNER_BASED:
            c = court or Court.fip_standard()
            offset = np.array([c.width / 2.0, c.length / 2.0, 0.0], dtype=np.float64)
            pts = pts - offset
        return pts

    def world_to_camera(
        self,
        points_3d: np.ndarray | Sequence[Any],
        coordinate_system: CoordinateSystem = CoordinateSystem.CENTERED,
        court: Court | None = None,
    ) -> np.ndarray:
        """Transforms 3D world point(s) into the camera coordinate frame.

        Args:
            points_3d: A 3D point ``(X, Y, Z)`` or an array of shape ``(..., 3)``.
            coordinate_system: Reference frame of the input points.
            court: Optional :class:`Court` used when converting from ``CORNER_BASED``.

        Returns:
            NumPy array of the same shape ``(..., 3)`` in camera coordinates
            ``(X_cam, Y_cam, Z_cam)``.
        """
        pts = self._to_centered_array(points_3d, coordinate_system, court)
        if pts.shape[-1] != 3:
            raise ValueError("Input points_3d must have last dimension of size 3.")
        rel = pts - self.extrinsics.center
        return rel @ self.extrinsics.R.T

    def project_points(
        self,
        points_3d: np.ndarray | Sequence[Sequence[float]],
        coordinate_system: CoordinateSystem = CoordinateSystem.CENTERED,
        court: Court | None = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Projects an array of 3D world points ``(N, 3)`` onto 2D image pixels.

        Args:
            points_3d: Sequence or NumPy array of shape ``(N, 3)``.
            coordinate_system: Coordinate system of ``points_3d``.
            court: Optional :class:`Court` instance for ``CORNER_BASED`` conversion.

        Returns:
            A tuple ``(uv_pixels, visible_mask)`` where:
            - ``uv_pixels`` has shape ``(N, 2)`` containing ``(u, v)`` coordinates
              (``np.nan`` for points behind the camera).
            - ``visible_mask`` is a boolean array of shape ``(N,)`` that is ``True``
              when the point is in front of the camera (``Z_cam > 1e-6``) and falls
              within ``[0, width_px) x [0, height_px)``.
        """
        pts_cam = self.world_to_camera(points_3d, coordinate_system, court)
        single_input = pts_cam.ndim == 1
        if single_input:
            pts_cam = pts_cam[np.newaxis, :]

        z_cam = pts_cam[:, 2]
        in_front = z_cam > 1e-6

        uv = np.full((pts_cam.shape[0], 2), np.nan, dtype=np.float64)
        if np.any(in_front):
            valid_cam = pts_cam[in_front]
            xy_norm = valid_cam[:, :2] / valid_cam[:, 2:3]
            xy_dist = self.distortion.distort_normalized(xy_norm)
            x_d = xy_dist[:, 0]
            y_d = xy_dist[:, 1]

            u = (
                self.intrinsics.fx * x_d
                + self.intrinsics.skew * y_d
                + self.intrinsics.cx
            )
            v = self.intrinsics.fy * y_d + self.intrinsics.cy
            uv[in_front, 0] = u
            uv[in_front, 1] = v

        in_bounds = (
            in_front
            & (uv[:, 0] >= 0.0)
            & (uv[:, 0] <= float(self.intrinsics.width_px))
            & (uv[:, 1] >= 0.0)
            & (uv[:, 1] <= float(self.intrinsics.height_px))
        )
        return uv, in_bounds

    def world_to_image(
        self,
        point_3d: tuple[float, float, float] | Sequence[float],
        coordinate_system: CoordinateSystem = CoordinateSystem.CENTERED,
        court: Court | None = None,
        clip_to_sensor: bool = False,
    ) -> tuple[float, float] | None:
        """Projects a single 3D world point ``(X, Y, Z)`` to 2D pixel ``(u, v)``.

        Args:
            point_3d: 3D world coordinates ``(X, Y, Z)`` in meters.
            coordinate_system: Reference frame of ``point_3d``.
            court: Optional :class:`Court` when using ``CORNER_BASED``.
            clip_to_sensor: If ``True``, returns ``None`` when the projected pixel
                falls outside ``[0, width_px] x [0, height_px]``.

        Returns:
            ``(u, v)`` pixel coordinates, or ``None`` if the point lies behind
            the camera (or outside sensor bounds when ``clip_to_sensor=True``).
        """
        uv, visible = self.project_points([point_3d], coordinate_system, court)
        if np.isnan(uv[0, 0]):
            return None
        if clip_to_sensor and not bool(visible[0]):
            return None
        return (float(uv[0, 0]), float(uv[0, 1]))

    def project_court_landmarks(
        self,
        court: Court | None = None,
        only_visible: bool = False,
    ) -> dict[str, tuple[float, float] | None]:
        """Projects all 17 standardized 3D court landmarks onto the image plane.

        Args:
            court: The :class:`Court` instance to project. Defaults to
                :meth:`Court.fip_standard`.
            only_visible: If ``True``, landmarks that project outside the image
                sensor bounds are omitted from the returned dictionary.

        Returns:
            Dictionary mapping each :class:`CourtLandmark` string name to its
            ``(u, v)`` pixel coordinate (or ``None`` if behind the camera).
        """
        c = court or Court.fip_standard()
        lm_3d = c.landmarks_3d(coordinate_system=CoordinateSystem.CENTERED)
        names = list(lm_3d.keys())
        coords = np.array([lm_3d[k] for k in names], dtype=np.float64)
        uv, visible = self.project_points(coords)

        result: dict[str, tuple[float, float] | None] = {}
        for idx, name in enumerate(names):
            if only_visible and not bool(visible[idx]):
                continue
            if np.isnan(uv[idx, 0]):
                result[name] = None
            else:
                result[name] = (float(uv[idx, 0]), float(uv[idx, 1]))
        return result

    # ------------------------------------------------------------------ #
    # 2D -> 3D Unprojection & Ray-casting Methods
    # ------------------------------------------------------------------ #

    def image_to_ray(
        self,
        pixel_2d: tuple[float, float] | Sequence[float],
    ) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        """Unprojects a 2D pixel ``(u, v)`` into a 3D world ray ``(origin, direction)``.

        Automatically removes lens distortion before rotating the ray into the
        world coordinate system.
        """
        if len(pixel_2d) != 2:
            raise ValueError("pixel_2d must be a 2-element (u, v) coordinate.")
        u, v = float(pixel_2d[0]), float(pixel_2d[1])

        y_d = (v - self.intrinsics.cy) / self.intrinsics.fy
        x_d = (u - self.intrinsics.cx - self.intrinsics.skew * y_d) / self.intrinsics.fx

        xy_undist = self.distortion.undistort_normalized(
            np.array([[x_d, y_d]], dtype=np.float64)
        )[0]
        dir_cam = np.array([xy_undist[0], xy_undist[1], 1.0], dtype=np.float64)
        dir_cam = dir_cam / np.linalg.norm(dir_cam)

        dir_world = self.extrinsics.R.T @ dir_cam
        dir_world = dir_world / np.linalg.norm(dir_world)

        return (
            self.extrinsics.position,
            (float(dir_world[0]), float(dir_world[1]), float(dir_world[2])),
        )

    def project_pixel_to_plane(
        self,
        pixel_2d: tuple[float, float] | Sequence[float],
        plane_z: float = 0.0,
    ) -> tuple[float, float, float] | None:
        """Intersects the 3D ray through ``pixel_2d`` with plane ``Z = plane_z``.

        Useful for mapping a 2D player foot detection or ball bounce pixel directly
        to ``(X, Y, 0.0)`` court floor coordinates.

        Returns:
            ``(X, Y, plane_z)`` in meters, or ``None`` if the ray does not
            intersect the plane in front of the camera.
        """
        origin, direction = self.image_to_ray(pixel_2d)
        dz = direction[2]
        if abs(dz) < 1e-9:
            return None
        t_param = (plane_z - origin[2]) / dz
        if t_param <= 0.0:
            return None
        return (
            origin[0] + t_param * direction[0],
            origin[1] + t_param * direction[1],
            float(plane_z),
        )

    def frustum_corners_world(
        self,
        near_m: float = 0.5,
        far_m: float = 25.0,
    ) -> dict[str, list[tuple[float, float, float]]]:
        """Computes the 3D world coordinates of the near and far frustum planes."""
        if near_m <= 0.0 or far_m <= near_m:
            raise ValueError("Require 0 < near_m < far_m.")
        w, h = float(self.intrinsics.width_px), float(self.intrinsics.height_px)
        corners_px = [(0.0, 0.0), (w, 0.0), (w, h), (0.0, h)]
        near_pts: list[tuple[float, float, float]] = []
        far_pts: list[tuple[float, float, float]] = []

        origin = np.asarray(self.extrinsics.position, dtype=np.float64)
        forward = np.asarray(self.extrinsics.forward, dtype=np.float64)

        for px in corners_px:
            _, ray_dir = self.image_to_ray(px)
            d_vec = np.asarray(ray_dir, dtype=np.float64)
            cos_angle = float(np.dot(d_vec, forward))
            scale = 1.0 / max(cos_angle, 1e-4)
            p_near = origin + d_vec * (near_m * scale)
            p_far = origin + d_vec * (far_m * scale)
            near_pts.append((float(p_near[0]), float(p_near[1]), float(p_near[2])))
            far_pts.append((float(p_far[0]), float(p_far[1]), float(p_far[2])))

        return {"near": near_pts, "far": far_pts}

    def to_dict(self) -> dict[str, Any]:
        """Serializes the full camera configuration to a dictionary."""
        return {
            "name": self.name,
            "intrinsics": self.intrinsics.to_dict(),
            "extrinsics": self.extrinsics.to_dict(),
            "distortion": self.distortion.to_dict(),
        }
