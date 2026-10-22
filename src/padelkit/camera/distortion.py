from dataclasses import dataclass
from typing import Any

import numpy as np

from .enums import DistortionModel


@dataclass(frozen=True)
class CameraDistortion:
    """Optical lens distortion parameters and forward/inverse distortion math.

    Supports three optical models:
    - :attr:`DistortionModel.NONE`: Pinhole projection (identity mapping).
    - :attr:`DistortionModel.BROWN_CONRADY`: Radial ``(k1, k2, k3)`` and
      tangential ``(p1, p2)`` distortion, matching OpenCV's 5-parameter model.
    - :attr:`DistortionModel.FISHEYE`: Kannala-Brandt equidistant fisheye
      distortion ``(k1, k2, k3, k4)``, matching ``cv2.fisheye``.
    """

    model: DistortionModel = DistortionModel.NONE
    k1: float = 0.0
    k2: float = 0.0
    p1: float = 0.0
    p2: float = 0.0
    k3: float = 0.0
    k4: float = 0.0

    # ------------------------------------------------------------------ #
    # Factory constructors
    # ------------------------------------------------------------------ #

    @classmethod
    def none(cls) -> "CameraDistortion":
        """Returns a distortion-free pinhole lens configuration."""
        return cls(model=DistortionModel.NONE)

    @classmethod
    def brown_conrady(
        cls,
        k1: float = 0.0,
        k2: float = 0.0,
        p1: float = 0.0,
        p2: float = 0.0,
        k3: float = 0.0,
    ) -> "CameraDistortion":
        """Creates a Brown-Conrady radial/tangential distortion configuration."""
        return cls(
            model=DistortionModel.BROWN_CONRADY,
            k1=k1,
            k2=k2,
            p1=p1,
            p2=p2,
            k3=k3,
        )

    @classmethod
    def fisheye(
        cls,
        k1: float = 0.0,
        k2: float = 0.0,
        k3: float = 0.0,
        k4: float = 0.0,
    ) -> "CameraDistortion":
        """Creates a Kannala-Brandt equidistant fisheye distortion configuration."""
        return cls(
            model=DistortionModel.FISHEYE,
            k1=k1,
            k2=k2,
            k3=k3,
            k4=k4,
        )

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def is_identity(self) -> bool:
        """Returns ``True`` if no effective lens distortion is present."""
        if self.model is DistortionModel.NONE:
            return True
        return all(
            abs(c) < 1e-12
            for c in (self.k1, self.k2, self.p1, self.p2, self.k3, self.k4)
        )

    @property
    def coefficients(self) -> tuple[float, ...]:
        """Returns the model-specific distortion coefficients tuple."""
        if self.model is DistortionModel.BROWN_CONRADY:
            return (self.k1, self.k2, self.p1, self.p2, self.k3)
        if self.model is DistortionModel.FISHEYE:
            return (self.k1, self.k2, self.k3, self.k4)
        return ()

    # ------------------------------------------------------------------ #
    # Distortion & Undistortion math
    # ------------------------------------------------------------------ #

    def distort_normalized(self, xy: np.ndarray) -> np.ndarray:
        """Applies forward lens distortion to normalized camera coordinates.

        Args:
            xy: Array of shape ``(..., 2)`` holding normalized pinhole
                coordinates ``(x_n, y_n) = (X_cam / Z_cam, Y_cam / Z_cam)``.

        Returns:
            Array of shape ``(..., 2)`` with distorted normalized coordinates.
        """
        pts = np.asarray(xy, dtype=np.float64)
        if self.is_identity and self.model is not DistortionModel.FISHEYE:
            return pts.copy()

        x = pts[..., 0]
        y = pts[..., 1]
        r2 = x * x + y * y

        if self.model is DistortionModel.BROWN_CONRADY:
            r4 = r2 * r2
            r6 = r4 * r2
            radial = 1.0 + self.k1 * r2 + self.k2 * r4 + self.k3 * r6
            dx_tang = 2.0 * self.p1 * x * y + self.p2 * (r2 + 2.0 * x * x)
            dy_tang = self.p1 * (r2 + 2.0 * y * y) + 2.0 * self.p2 * x * y
            x_d = x * radial + dx_tang
            y_d = y * radial + dy_tang
            return np.stack([x_d, y_d], axis=-1)

        if self.model is DistortionModel.FISHEYE:
            r = np.sqrt(r2)
            theta = np.arctan(r)
            theta2 = theta * theta
            theta4 = theta2 * theta2
            theta6 = theta4 * theta2
            theta8 = theta4 * theta4
            theta_d = theta * (
                1.0
                + self.k1 * theta2
                + self.k2 * theta4
                + self.k3 * theta6
                + self.k4 * theta8
            )
            scale = np.ones_like(r, dtype=np.float64)
            np.divide(theta_d, r, out=scale, where=r > 1e-10)
            return np.stack([x * scale, y * scale], axis=-1)

        return pts.copy()

    def undistort_normalized(
        self,
        xy_distorted: np.ndarray,
        iterations: int = 12,
    ) -> np.ndarray:
        """Inverts lens distortion to recover ideal normalized coordinates.

        Args:
            xy_distorted: Array of shape ``(..., 2)`` containing distorted
                normalized coordinates ``(x_d, y_d)``.
            iterations: Number of fixed-point / Newton-Raphson refinement steps.

        Returns:
            Array of shape ``(..., 2)`` with undistorted normalized coordinates.
        """
        pts_d = np.asarray(xy_distorted, dtype=np.float64)
        if self.is_identity and self.model is not DistortionModel.FISHEYE:
            return pts_d.copy()

        x_d = pts_d[..., 0]
        y_d = pts_d[..., 1]

        if self.model is DistortionModel.BROWN_CONRADY:
            x = x_d.copy()
            y = y_d.copy()
            for _ in range(iterations):
                r2 = x * x + y * y
                r4 = r2 * r2
                r6 = r4 * r2
                radial = 1.0 + self.k1 * r2 + self.k2 * r4 + self.k3 * r6
                dx_tang = 2.0 * self.p1 * x * y + self.p2 * (r2 + 2.0 * x * x)
                dy_tang = self.p1 * (r2 + 2.0 * y * y) + 2.0 * self.p2 * x * y
                x = (x_d - dx_tang) / radial
                y = (y_d - dy_tang) / radial
            return np.stack([x, y], axis=-1)

        if self.model is DistortionModel.FISHEYE:
            theta_d = np.hypot(x_d, y_d)
            theta = theta_d.copy()
            for _ in range(iterations):
                t2 = theta * theta
                t4 = t2 * t2
                t6 = t4 * t2
                t8 = t4 * t4
                f = (
                    theta
                    * (1.0 + self.k1 * t2 + self.k2 * t4 + self.k3 * t6 + self.k4 * t8)
                    - theta_d
                )
                df = (
                    1.0
                    + 3.0 * self.k1 * t2
                    + 5.0 * self.k2 * t4
                    + 7.0 * self.k3 * t6
                    + 9.0 * self.k4 * t8
                )
                theta = theta - f / np.where(np.abs(df) > 1e-10, df, 1.0)
            r = np.tan(theta)
            scale = np.ones_like(theta_d, dtype=np.float64)
            np.divide(r, theta_d, out=scale, where=theta_d > 1e-10)
            return np.stack([x_d * scale, y_d * scale], axis=-1)

        return pts_d.copy()

    def to_dict(self) -> dict[str, Any]:
        """Serializes the distortion configuration to a plain dictionary."""
        return {
            "model": self.model.value,
            "k1": self.k1,
            "k2": self.k2,
            "p1": self.p1,
            "p2": self.p2,
            "k3": self.k3,
            "k4": self.k4,
        }
