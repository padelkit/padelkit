from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from ..court.court import Court
from ..court.enums import CoordinateSystem
from ..court.landmarks import CourtLandmark
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
    # 2D-to-3D Calibration & Homography Estimation
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute_homography(
        src_points_2d: np.ndarray | Sequence[Sequence[float]],
        dst_points_2d: np.ndarray | Sequence[Sequence[float]],
    ) -> np.ndarray:
        """Computes the ``3x3`` projective homography ``H`` via Normalized DLT.

        Maps ``src_points_2d`` ``(x, y)`` to ``dst_points_2d`` ``(u, v)`` such
        that ``s * [u, v, 1]^T = H @ [x, y, 1]^T``.

        Args:
            src_points_2d: Array-like of shape ``(N, 2)`` with ``N >= 4``.
            dst_points_2d: Array-like of shape ``(N, 2)`` with ``N >= 4``.

        Returns:
            Normalized ``(3, 3)`` float64 homography matrix ``H``.
        """
        src = np.asarray(src_points_2d, dtype=np.float64)
        dst = np.asarray(dst_points_2d, dtype=np.float64)
        if src.ndim != 2 or src.shape[1] != 2 or dst.shape != src.shape:
            raise ValueError("src_points_2d and dst_points_2d must have shape (N, 2).")
        n_pts = src.shape[0]
        if n_pts < 4:
            raise ValueError("At least 4 point correspondences are required.")

        def _normalize_2d(pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
            centroid = np.mean(pts, axis=0)
            shifted = pts - centroid
            mean_dist = float(np.mean(np.linalg.norm(shifted, axis=1)))
            scale = np.sqrt(2.0) / max(mean_dist, 1e-12)
            t_mat = np.array(
                [
                    [scale, 0.0, -scale * centroid[0]],
                    [0.0, scale, -scale * centroid[1]],
                    [0.0, 0.0, 1.0],
                ],
                dtype=np.float64,
            )
            pts_norm = shifted * scale
            return pts_norm, t_mat

        src_n, t_src = _normalize_2d(src)
        dst_n, t_dst = _normalize_2d(dst)

        a_rows: list[list[float]] = []
        for i in range(n_pts):
            x, y = float(src_n[i, 0]), float(src_n[i, 1])
            u, v = float(dst_n[i, 0]), float(dst_n[i, 1])
            a_rows.append([-x, -y, -1.0, 0.0, 0.0, 0.0, u * x, u * y, u])
            a_rows.append([0.0, 0.0, 0.0, -x, -y, -1.0, v * x, v * y, v])

        a_mat = np.asarray(a_rows, dtype=np.float64)
        _, _, vt = np.linalg.svd(a_mat)
        h_norm = vt[-1].reshape(3, 3)
        h_mat = np.linalg.inv(t_dst) @ h_norm @ t_src
        if abs(h_mat[2, 2]) > 1e-12:
            h_mat = h_mat / h_mat[2, 2]
        return h_mat

    @classmethod
    def from_landmarks(
        cls,
        landmarks_2d: Mapping[str | CourtLandmark, Sequence[float]],
        court: Court | None = None,
        intrinsics: CameraIntrinsics | None = None,
        width_px: int = 1920,
        height_px: int = 1080,
        distortion: CameraDistortion | None = None,
        name: str = "calibrated",
    ) -> "Camera":
        """Calibrates a 3D :class:`Camera` from 2D pixel landmarks on a video frame.

        Accepts any dictionary of at least 4 :class:`CourtLandmark` names (or enum
        members) mapped to their observed ``(u, v)`` pixel coordinates, such as
        the 4 court floor corners ``floor_near_left``, ``floor_near_right``,
        ``floor_far_right``, ``floor_far_left``.

        If ``intrinsics`` is omitted, focal length is automatically estimated from
        the court geometry perspective vanishing points and refined jointly with
        the 6-DoF camera pose via damped Gauss-Newton (Levenberg-Marquardt)
        reprojection minimization.

        Args:
            landmarks_2d: Mapping of at least 4 landmark identifiers to ``(u, v)``
                pixel coordinates.
            court: Reference :class:`Court` instance. Defaults to
                :meth:`Court.fip_standard`.
            intrinsics: Optional known :class:`CameraIntrinsics`. If ``None``,
                focal length is estimated assuming square pixels and centered
                principal point ``(width_px / 2, height_px / 2)``.
            width_px: Sensor width in pixels (used when ``intrinsics`` is ``None``).
            height_px: Sensor height in pixels (used when ``intrinsics`` is ``None``).
            distortion: Optional :class:`CameraDistortion` model.
            name: Identifier for the calibrated camera.

        Returns:
            Calibrated :class:`Camera` instance.
        """
        c = court or Court.fip_standard()
        dist_cfg = distortion or CameraDistortion.none()
        lm_3d_map = c.landmarks_3d(coordinate_system=CoordinateSystem.CENTERED)

        pts_3d_list: list[tuple[float, float, float]] = []
        pts_2d_list: list[tuple[float, float]] = []

        for key, uv in landmarks_2d.items():
            lm_name = key.value if isinstance(key, CourtLandmark) else str(key)
            if lm_name not in lm_3d_map:
                raise ValueError(f"Unknown CourtLandmark '{lm_name}'.")
            if len(uv) != 2:
                raise ValueError(f"Landmark '{lm_name}' must map to a 2D (u, v) pair.")
            pts_3d_list.append(lm_3d_map[lm_name])
            pts_2d_list.append((float(uv[0]), float(uv[1])))

        if len(pts_3d_list) < 4:
            raise ValueError(
                "At least 4 landmark correspondences are required for calibration."
            )

        pts_3d = np.asarray(pts_3d_list, dtype=np.float64)
        pts_2d = np.asarray(pts_2d_list, dtype=np.float64)

        floor_mask = np.abs(pts_3d[:, 2]) < 1e-6
        if np.sum(floor_mask) >= 4:
            h_floor = cls.compute_homography(
                pts_3d[floor_mask, :2], pts_2d[floor_mask]
            )
        else:
            h_floor = cls.compute_homography(pts_3d[:, :2], pts_2d)

        # 1. Estimate or unpack intrinsics
        optimize_focal = intrinsics is None
        if intrinsics is None:
            cx = width_px / 2.0
            cy = height_px / 2.0
            f_init = _estimate_focal_from_homography(h_floor, cx, cy, width_px)
            intr = CameraIntrinsics(
                width_px=width_px,
                height_px=height_px,
                fx=f_init,
                fy=f_init,
                cx=cx,
                cy=cy,
            )
        else:
            intr = intrinsics

        # Undistort observed 2D points into ideal normalized coordinates for init
        y_d = (pts_2d[:, 1] - intr.cy) / intr.fy
        x_d = (pts_2d[:, 0] - intr.cx - intr.skew * y_d) / intr.fx
        xy_undist = dist_cfg.undistort_normalized(np.column_stack([x_d, y_d]))
        pts_2d_ideal = np.column_stack(
            [
                intr.fx * xy_undist[:, 0] + intr.skew * xy_undist[:, 1] + intr.cx,
                intr.fy * xy_undist[:, 1] + intr.cy,
            ]
        )

        if np.sum(floor_mask) >= 4:
            h_ideal = cls.compute_homography(
                pts_3d[floor_mask, :2], pts_2d_ideal[floor_mask]
            )
        else:
            h_ideal = h_floor

        # 2. Decompose homography H = K [r1, r2, t] for initial (R, t)
        k_inv = intr.inverse_matrix
        b_mat = k_inv @ h_ideal
        norm1 = float(np.linalg.norm(b_mat[:, 0]))
        norm2 = float(np.linalg.norm(b_mat[:, 1]))
        scale = 2.0 / max(norm1 + norm2, 1e-12)

        # Ensure points lie in front of the camera (Z_cam > 0)
        if b_mat[2, 2] * scale < 0.0:
            scale = -scale

        r1 = b_mat[:, 0] * scale
        r2 = b_mat[:, 1] * scale
        r3 = np.cross(r1, r2)
        r_raw = np.column_stack([r1, r2, r3])
        u_svd, _, vt_svd = np.linalg.svd(r_raw)
        det_uv = float(np.linalg.det(u_svd @ vt_svd))
        r_init = u_svd @ np.diag([1.0, 1.0, det_uv]) @ vt_svd
        t_init = b_mat[:, 2] * scale

        # Check mean Z_cam of all points; flip if behind
        z_test = (pts_3d @ r_init.T + t_init)[:, 2]
        if np.mean(z_test) < 0.0:
            r_init[:, 0] = -r_init[:, 0]
            r_init[:, 1] = -r_init[:, 1]
            t_init = -t_init

        # 3. Non-linear Levenberg-Marquardt refinement over all 3D landmarks
        r_opt, t_opt, f_opt = _refine_camera_lm(
            pts_3d=pts_3d,
            pts_2d=pts_2d,
            r_init=r_init,
            t_init=t_init,
            intr=intr,
            dist=dist_cfg,
            optimize_focal=optimize_focal,
        )

        if optimize_focal:
            intr = CameraIntrinsics(
                width_px=intr.width_px,
                height_px=intr.height_px,
                fx=f_opt,
                fy=f_opt,
                cx=intr.cx,
                cy=intr.cy,
                skew=intr.skew,
            )

        extr = CameraExtrinsics.from_rt(r_opt, t_opt)
        return cls(
            intrinsics=intr,
            extrinsics=extr,
            distortion=dist_cfg,
            name=name,
        )

    @property
    def floor_homography(self) -> np.ndarray:
        """Analytical ``3x3`` homography mapping centered floor ``(X, Y, 1)`` to pixels.

        Satisfies ``s * [u, v, 1]^T = floor_homography @ [X, Y, 1]^T`` for any
        point ``(X, Y, 0)`` on the court floor under the pinhole model.
        """
        r_mat = self.extrinsics.R
        t_vec = self.extrinsics.t.reshape(3, 1)
        rt_planar = np.hstack([r_mat[:, 0:2], t_vec])
        h_mat = self.intrinsics.matrix @ rt_planar
        if abs(h_mat[2, 2]) > 1e-12:
            h_mat = h_mat / h_mat[2, 2]
        return h_mat

    @property
    def inverse_floor_homography(self) -> np.ndarray:
        """Analytical ``3x3`` inverse homography mapping pixels ``(u, v, 1)`` to
        floor ``(X, Y, 1)``."""
        h_inv = np.linalg.inv(self.floor_homography)
        if abs(h_inv[2, 2]) > 1e-12:
            h_inv = h_inv / h_inv[2, 2]
        return h_inv

    def reprojection_error(
        self,
        landmarks_2d: Mapping[str | CourtLandmark, Sequence[float]],
        court: Court | None = None,
    ) -> float:
        """Computes the root-mean-square (RMSE) reprojection error in pixels."""
        c = court or Court.fip_standard()
        lm_3d = c.landmarks_3d(coordinate_system=CoordinateSystem.CENTERED)
        sq_errors: list[float] = []
        for key, uv_obs in landmarks_2d.items():
            lm_name = key.value if isinstance(key, CourtLandmark) else str(key)
            uv_pred = self.world_to_image(lm_3d[lm_name])
            if uv_pred is None:
                return float("inf")
            du = uv_pred[0] - float(uv_obs[0])
            dv = uv_pred[1] - float(uv_obs[1])
            sq_errors.append(du * du + dv * dv)
        return float(np.sqrt(np.mean(sq_errors))) if sq_errors else 0.0

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


def _estimate_focal_from_homography(
    h_mat: np.ndarray,
    cx: float,
    cy: float,
    width_px: int,
) -> float:
    """Estimates pinhole focal length ``f`` from a planar homography via Zhang's
    constraints."""
    t_center = np.array(
        [[1.0, 0.0, -cx], [0.0, 1.0, -cy], [0.0, 0.0, 1.0]], dtype=np.float64
    )
    h_c = t_center @ h_mat
    h1 = h_c[:, 0]
    h2 = h_c[:, 1]

    candidates: list[float] = []
    # Constraint 1: h1^T K^-T K^-1 h2 = 0
    denom1 = h1[2] * h2[2]
    if abs(denom1) > 1e-10:
        f2_1 = -(h1[0] * h2[0] + h1[1] * h2[1]) / denom1
        if f2_1 > 0.0:
            candidates.append(float(np.sqrt(f2_1)))

    # Constraint 2: ||K^-1 h1||^2 = ||K^-1 h2||^2
    denom2 = h1[2] * h1[2] - h2[2] * h2[2]
    if abs(denom2) > 1e-10:
        f2_2 = ((h2[0] ** 2 + h2[1] ** 2) - (h1[0] ** 2 + h1[1] ** 2)) / denom2
        if f2_2 > 0.0:
            candidates.append(float(np.sqrt(f2_2)))

    f_min = width_px * 0.25
    f_max = width_px * 4.0
    valid = [f for f in candidates if f_min <= f <= f_max]
    if valid:
        return float(np.median(valid))
    if candidates:
        return float(np.clip(candidates[0], f_min, f_max))
    # Default ~78 deg horizontal FOV
    return float(width_px / (2.0 * np.tan(np.radians(39.0))))


def _rodrigues_exp(rvec: np.ndarray) -> np.ndarray:
    """Converts a 3D rotation vector ``rvec`` into a ``3x3`` rotation matrix."""
    theta = float(np.linalg.norm(rvec))
    if theta < 1e-12:
        return np.eye(3, dtype=np.float64)
    k = rvec / theta
    kx, ky, kz = float(k[0]), float(k[1]), float(k[2])
    k_cross = np.array(
        [[0.0, -kz, ky], [kz, 0.0, -kx], [-ky, kx, 0.0]], dtype=np.float64
    )
    return (
        np.eye(3, dtype=np.float64)
        + np.sin(theta) * k_cross
        + (1.0 - np.cos(theta)) * (k_cross @ k_cross)
    )


def _rodrigues_log(r_mat: np.ndarray) -> np.ndarray:
    """Converts a ``3x3`` rotation matrix into a 3D axis-angle vector."""
    cos_theta = float(np.clip((np.trace(r_mat) - 1.0) * 0.5, -1.0, 1.0))
    theta = float(np.arccos(cos_theta))
    if theta < 1e-10:
        return np.zeros(3, dtype=np.float64)
    sin_theta = float(np.sin(theta))
    if abs(sin_theta) < 1e-8:
        eigvals, eigvecs = np.linalg.eig(r_mat)
        idx = int(np.argmin(np.abs(eigvals - 1.0)))
        axis = np.real(eigvecs[:, idx])
        axis = axis / max(float(np.linalg.norm(axis)), 1e-12)
        return axis * theta
    rx = r_mat[2, 1] - r_mat[1, 2]
    ry = r_mat[0, 2] - r_mat[2, 0]
    rz = r_mat[1, 0] - r_mat[0, 1]
    return np.array([rx, ry, rz], dtype=np.float64) * (theta / (2.0 * sin_theta))


def _refine_camera_lm(
    pts_3d: np.ndarray,
    pts_2d: np.ndarray,
    r_init: np.ndarray,
    t_init: np.ndarray,
    intr: CameraIntrinsics,
    dist: CameraDistortion,
    optimize_focal: bool,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Damped Gauss-Newton (Levenberg-Marquardt) refinement of camera pose and
    focal length."""
    rvec = _rodrigues_log(r_init)
    tvec = t_init.astype(np.float64).copy()
    f_val = float(intr.fx)

    params = (
        np.concatenate([rvec, tvec, [f_val]])
        if optimize_focal
        else np.concatenate([rvec, tvec])
    )
    n_params = params.shape[0]
    target_2d = pts_2d.ravel()

    def _project_params(p: np.ndarray) -> np.ndarray:
        r_m = _rodrigues_exp(p[0:3])
        t_v = p[3:6]
        fx = float(p[6]) if optimize_focal else intr.fx
        fy = float(p[6]) if optimize_focal else intr.fy

        pts_cam = pts_3d @ r_m.T + t_v
        z_c = np.where(np.abs(pts_cam[:, 2]) < 1e-6, 1e-6, pts_cam[:, 2])
        xy_norm = pts_cam[:, :2] / z_c[:, np.newaxis]
        xy_dist = dist.distort_normalized(xy_norm)
        u = fx * xy_dist[:, 0] + intr.skew * xy_dist[:, 1] + intr.cx
        v = fy * xy_dist[:, 1] + intr.cy
        return np.column_stack([u, v]).ravel()

    res = _project_params(params) - target_2d
    cost = float(np.dot(res, res))
    damping = 1e-3
    eps = 1e-6

    for _ in range(45):
        if cost < 1e-12:
            break
        jac = np.zeros((target_2d.shape[0], n_params), dtype=np.float64)
        for j in range(n_params):
            step = eps * max(abs(float(params[j])), 1.0)
            p_plus = params.copy()
            p_plus[j] += step
            jac[:, j] = (_project_params(p_plus) - (res + target_2d)) / step

        jtj = jac.T @ jac
        jtr = jac.T @ res
        diag = np.diag(np.maximum(np.diag(jtj), 1e-6))

        accepted = False
        for _ in range(8):
            try:
                delta = -np.linalg.solve(
                    jtj + damping * (diag + np.eye(n_params) * 1e-6), jtr
                )
            except np.linalg.LinAlgError:
                damping *= 10.0
                continue

            cand = params + delta
            if optimize_focal and cand[6] <= 50.0:
                damping *= 10.0
                continue

            res_cand = _project_params(cand) - target_2d
            cost_cand = float(np.dot(res_cand, res_cand))
            if cost_cand < cost:
                params = cand
                res = res_cand
                cost = cost_cand
                damping = max(damping * 0.3, 1e-9)
                accepted = True
                break
            damping *= 5.0

        if not accepted or float(np.linalg.norm(jtr)) < 1e-7:
            break

    r_final = _rodrigues_exp(params[0:3])
    t_final = params[3:6]
    f_final = float(params[6]) if optimize_focal else float(intr.fx)
    return r_final, t_final, f_final

