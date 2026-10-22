import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class CameraExtrinsics:
    """Extrinsic 6-DoF pose (position and orientation) of a camera in 3D space.

    Uses the standard PadelKit 3D world reference frame:
    - ``+X``: Court width (left to right from the NEAR side).
    - ``+Y``: Court length (from NEAR back wall towards FAR back wall).
    - ``+Z``: Height above the court floor (in meters).

    The internal camera coordinate frame follows the standard Computer Vision
    (OpenCV) convention:
    - ``+X_cam``: Right across image columns ``u``.
    - ``+Y_cam``: Down across image rows ``v``.
    - ``+Z_cam``: Forward along the optical axis into the scene.

    A 3D world point ``P_w`` transforms to camera coordinates via:
    ``P_cam = R @ (P_w - position) = R @ P_w + t``.
    """

    position: tuple[float, float, float]
    rotation_matrix: tuple[
        tuple[float, float, float],
        tuple[float, float, float],
        tuple[float, float, float],
    ]

    def __post_init__(self) -> None:
        if len(self.position) != 3:
            raise ValueError("Camera position must be a 3-element (x, y, z) tuple.")
        rot = np.asarray(self.rotation_matrix, dtype=np.float64)
        if rot.shape != (3, 3):
            raise ValueError("rotation_matrix must have shape (3, 3).")
        det = float(np.linalg.det(rot))
        if not np.allclose(rot @ rot.T, np.eye(3), atol=1e-4) or abs(det - 1.0) > 1e-3:
            raise ValueError(
                "rotation_matrix must be a valid 3x3 special orthogonal matrix (SO(3))."
            )

    # ------------------------------------------------------------------ #
    # Class methods (Factory constructors)
    # ------------------------------------------------------------------ #

    @classmethod
    def from_look_at(
        cls,
        position: tuple[float, float, float] | Sequence[float],
        target: tuple[float, float, float] | Sequence[float] = (0.0, 0.0, 0.0),
        roll_deg: float = 0.0,
        world_up: tuple[float, float, float] | Sequence[float] = (0.0, 0.0, 1.0),
    ) -> "CameraExtrinsics":
        """Creates :class:`CameraExtrinsics` oriented towards a 3D target point.

        Handles zenith/nadir views gracefully: if the viewing direction is
        collinear with ``world_up``, ``(0.0, 1.0, 0.0)`` is automatically used
        as the image-up reference so that the court's ``+Y`` axis points up
        in overhead views.
        """
        pos = np.asarray(position, dtype=np.float64)
        tgt = np.asarray(target, dtype=np.float64)
        up_ref = np.asarray(world_up, dtype=np.float64)

        if pos.shape != (3,) or tgt.shape != (3,) or up_ref.shape != (3,):
            raise ValueError("position, target, and world_up must be 3D vectors.")

        diff = tgt - pos
        dist = float(np.linalg.norm(diff))
        if dist < 1e-9:
            raise ValueError("Camera position and target cannot be identical.")

        forward = diff / dist
        up_norm = float(np.linalg.norm(up_ref))
        if up_norm < 1e-9:
            raise ValueError("world_up vector cannot have zero length.")
        up_unit = up_ref / up_norm

        # Handle zenith/nadir singularity (e.g. overhead camera looking straight down)
        if abs(float(np.dot(forward, up_unit))) > 0.9999:
            up_unit = np.array([0.0, 1.0, 0.0], dtype=np.float64)
            if abs(float(np.dot(forward, up_unit))) > 0.9999:
                up_unit = np.array([1.0, 0.0, 0.0], dtype=np.float64)

        right = np.cross(forward, up_unit)
        right = right / np.linalg.norm(right)

        # In CV convention, +Y_cam points DOWN in the image: down = forward x right
        down = np.cross(forward, right)
        down = down / np.linalg.norm(down)

        if abs(roll_deg) > 1e-12:
            rad = math.radians(roll_deg)
            c, s = math.cos(rad), math.sin(rad)
            right_rolled = c * right + s * down
            down_rolled = -s * right + c * down
            right, down = right_rolled, down_rolled

        rot = np.stack([right, down, forward], axis=0)
        return cls(
            position=(float(pos[0]), float(pos[1]), float(pos[2])),
            rotation_matrix=_matrix_to_tuple(rot),
        )

    @classmethod
    def from_euler(
        cls,
        position: tuple[float, float, float] | Sequence[float],
        yaw_deg: float = 0.0,
        pitch_deg: float = 0.0,
        roll_deg: float = 0.0,
    ) -> "CameraExtrinsics":
        """Creates :class:`CameraExtrinsics` from intuitive pan/tilt/roll angles.

        Angle convention:
        - ``yaw_deg = 0`` points along ``+Y`` (from NEAR to FAR side).
          Positive ``yaw_deg`` pans clockwise when viewed from above
          (``yaw_deg = 90`` points along ``+X``, ``yaw_deg = 180`` points along ``-Y``).
        - ``pitch_deg = 0`` is horizontal. Negative ``pitch_deg`` tilts the
          camera downwards towards the court floor.
        - ``roll_deg`` rotates the camera around its optical axis.
        """
        yaw = math.radians(yaw_deg)
        pitch = math.radians(pitch_deg)

        cos_p = math.cos(pitch)
        fx = math.sin(yaw) * cos_p
        fy = math.cos(yaw) * cos_p
        fz = math.sin(pitch)
        forward = np.array([fx, fy, fz], dtype=np.float64)

        # Horizontal right vector at yaw_deg
        right = np.array([math.cos(yaw), -math.sin(yaw), 0.0], dtype=np.float64)
        down = np.cross(forward, right)
        down = down / np.linalg.norm(down)

        if abs(roll_deg) > 1e-12:
            rad = math.radians(roll_deg)
            c, s = math.cos(rad), math.sin(rad)
            right, down = c * right + s * down, -s * right + c * down

        pos = tuple(float(v) for v in position)
        if len(pos) != 3:
            raise ValueError("position must have 3 elements (x, y, z).")

        rot = np.stack([right, down, forward], axis=0)
        return cls(
            position=(pos[0], pos[1], pos[2]),
            rotation_matrix=_matrix_to_tuple(rot),
        )

    @classmethod
    def from_rt(
        cls,
        r_matrix: np.ndarray | Sequence[Sequence[float]],
        t_vector: np.ndarray | Sequence[float],
    ) -> "CameraExtrinsics":
        """Creates :class:`CameraExtrinsics` from OpenCV ``R`` (3x3) and ``t`` (3,).

        Computes the world camera center as ``position = -R.T @ t``.
        """
        rot = np.asarray(r_matrix, dtype=np.float64)
        t_vec = np.asarray(t_vector, dtype=np.float64).reshape(3)
        center = -(rot.T @ t_vec)
        return cls(
            position=(float(center[0]), float(center[1]), float(center[2])),
            rotation_matrix=_matrix_to_tuple(rot),
        )

    # ------------------------------------------------------------------ #
    # Matrices & Vectors
    # ------------------------------------------------------------------ #

    @property
    def R(self) -> np.ndarray:  # noqa: N802
        """3x3 world-to-camera rotation matrix ``R`` (OpenCV convention)."""
        return np.asarray(self.rotation_matrix, dtype=np.float64)

    @property
    def center(self) -> np.ndarray:
        """3D camera optical center ``C`` in world coordinates as a NumPy array."""
        return np.asarray(self.position, dtype=np.float64)

    @property
    def t(self) -> np.ndarray:
        """3D world-to-camera translation vector ``t = -R @ center``."""
        return -(self.R @ self.center)

    @property
    def right(self) -> tuple[float, float, float]:
        """Unit vector pointing right (``+X_cam``) in world coordinates."""
        return self.rotation_matrix[0]

    @property
    def down(self) -> tuple[float, float, float]:
        """Unit vector pointing down (``+Y_cam``) in world coordinates."""
        return self.rotation_matrix[1]

    @property
    def up(self) -> tuple[float, float, float]:
        """Unit vector pointing up in the image (``-Y_cam``) in world coordinates."""
        d = self.rotation_matrix[1]
        return (-d[0], -d[1], -d[2])

    @property
    def forward(self) -> tuple[float, float, float]:
        """Unit optical axis vector (``+Z_cam``) in world coordinates."""
        return self.rotation_matrix[2]

    @property
    def world_to_camera_matrix(self) -> np.ndarray:
        """4x4 homogeneous world-to-camera transformation matrix (OpenCV frame)."""
        mat = np.eye(4, dtype=np.float64)
        mat[:3, :3] = self.R
        mat[:3, 3] = self.t
        return mat

    @property
    def camera_to_world_matrix(self) -> np.ndarray:
        """4x4 homogeneous camera-to-world transformation matrix (OpenCV frame)."""
        mat = np.eye(4, dtype=np.float64)
        mat[:3, :3] = self.R.T
        mat[:3, 3] = self.center
        return mat

    @property
    def opengl_camera_to_world_matrix(self) -> np.ndarray:
        """4x4 camera-to-world matrix in OpenGL / Three.js / Blender convention.

        In OpenGL/Three.js/Blender camera space, ``+X`` points right, ``+Y``
        points up in the image, and the camera looks down ``-Z``.
        """
        cv_to_gl = np.diag([1.0, -1.0, -1.0])
        rot_c2w_gl = self.R.T @ cv_to_gl
        mat = np.eye(4, dtype=np.float64)
        mat[:3, :3] = rot_c2w_gl
        mat[:3, 3] = self.center
        return mat

    def look_at_point(self, distance_m: float = 10.0) -> tuple[float, float, float]:
        """Returns a 3D point along the optical axis at ``distance_m`` meters."""
        f = self.forward
        p = self.position
        return (
            p[0] + f[0] * distance_m,
            p[1] + f[1] * distance_m,
            p[2] + f[2] * distance_m,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializes the extrinsic pose to a plain dictionary."""
        return {
            "position": list(self.position),
            "forward": list(self.forward),
            "up": list(self.up),
            "right": list(self.right),
            "rotation_matrix": [list(row) for row in self.rotation_matrix],
            "t": [float(v) for v in self.t],
        }


def _matrix_to_tuple(
    mat: np.ndarray,
) -> tuple[
    tuple[float, float, float],
    tuple[float, float, float],
    tuple[float, float, float],
]:
    return (
        (float(mat[0, 0]), float(mat[0, 1]), float(mat[0, 2])),
        (float(mat[1, 0]), float(mat[1, 1]), float(mat[1, 2])),
        (float(mat[2, 0]), float(mat[2, 1]), float(mat[2, 2])),
    )
