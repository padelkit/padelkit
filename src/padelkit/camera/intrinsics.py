import math
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class CameraIntrinsics:
    """Intrinsic pinhole camera parameters and image sensor resolution.

    Represents the upper-triangular camera calibration matrix ``K``:

    .. code-block:: text

        [[fx, skew, cx],
         [ 0,   fy, cy],
         [ 0,    0,  1]]

    All pixel measurements (`width_px`, `height_px`, `fx`, `fy`, `cx`, `cy`)
    are expressed in pixels, with `(0, 0)` at the top-left corner of the image.
    """

    width_px: int
    height_px: int
    fx: float
    fy: float
    cx: float
    cy: float
    skew: float = 0.0

    def __post_init__(self) -> None:
        if self.width_px <= 0 or self.height_px <= 0:
            raise ValueError(
                "Camera resolution (width_px, height_px) must be strictly positive."
            )
        if self.fx <= 0.0 or self.fy <= 0.0:
            raise ValueError(
                "Focal lengths (fx, fy) must be strictly positive numbers."
            )

    # ------------------------------------------------------------------ #
    # Class methods (Factory constructors)
    # ------------------------------------------------------------------ #

    @classmethod
    def from_fov(
        cls,
        width_px: int = 1920,
        height_px: int = 1080,
        horizontal_fov_deg: float = 80.0,
        cx: float | None = None,
        cy: float | None = None,
        skew: float = 0.0,
    ) -> "CameraIntrinsics":
        """Creates a :class:`CameraIntrinsics` instance from horizontal FOV.

        Assumes square pixels (``fx == fy``). If ``cx`` or ``cy`` are omitted,
        the principal point defaults to the exact optical center of the image
        ``(width_px / 2, height_px / 2)``.
        """
        if not (1.0 <= horizontal_fov_deg < 179.0):
            raise ValueError(
                "horizontal_fov_deg must be in the range [1.0, 179.0) degrees."
            )
        half_fov_rad = math.radians(horizontal_fov_deg) / 2.0
        fx = (width_px / 2.0) / math.tan(half_fov_rad)
        fy = fx
        principal_x = cx if cx is not None else width_px / 2.0
        principal_y = cy if cy is not None else height_px / 2.0
        return cls(
            width_px=width_px,
            height_px=height_px,
            fx=fx,
            fy=fy,
            cx=principal_x,
            cy=principal_y,
            skew=skew,
        )

    @classmethod
    def from_sensor(
        cls,
        width_px: int = 1920,
        height_px: int = 1080,
        focal_length_mm: float = 18.0,
        sensor_width_mm: float = 36.0,
        sensor_height_mm: float | None = None,
        cx: float | None = None,
        cy: float | None = None,
    ) -> "CameraIntrinsics":
        """Creates a :class:`CameraIntrinsics` instance from physical lens parameters.

        Args:
            width_px: Horizontal image resolution in pixels.
            height_px: Vertical image resolution in pixels.
            focal_length_mm: Physical focal length of the lens in millimeters.
            sensor_width_mm: Physical sensor width in millimeters (defaults to
                36.0 mm full-frame).
            sensor_height_mm: Physical sensor height in millimeters. If ``None``,
                it is derived proportionally from the image aspect ratio.
            cx: Horizontal principal point in pixels. Defaults to ``width_px / 2``.
            cy: Vertical principal point in pixels. Defaults to ``height_px / 2``.
        """
        if focal_length_mm <= 0.0 or sensor_width_mm <= 0.0:
            raise ValueError(
                "focal_length_mm and sensor_width_mm must be strictly positive."
            )
        eff_sensor_h = (
            sensor_height_mm
            if sensor_height_mm is not None
            else sensor_width_mm * (height_px / width_px)
        )
        if eff_sensor_h <= 0.0:
            raise ValueError("sensor_height_mm must be strictly positive.")

        fx = (focal_length_mm / sensor_width_mm) * width_px
        fy = (focal_length_mm / eff_sensor_h) * height_px
        principal_x = cx if cx is not None else width_px / 2.0
        principal_y = cy if cy is not None else height_px / 2.0
        return cls(
            width_px=width_px,
            height_px=height_px,
            fx=fx,
            fy=fy,
            cx=principal_x,
            cy=principal_y,
        )

    @classmethod
    def full_hd(cls, horizontal_fov_deg: float = 80.0) -> "CameraIntrinsics":
        """Standard Full HD (1920x1080) camera intrinsics preset."""
        return cls.from_fov(
            width_px=1920,
            height_px=1080,
            horizontal_fov_deg=horizontal_fov_deg,
        )

    @classmethod
    def uhd_4k(cls, horizontal_fov_deg: float = 80.0) -> "CameraIntrinsics":
        """Standard 4K UHD (3840x2160) camera intrinsics preset."""
        return cls.from_fov(
            width_px=3840,
            height_px=2160,
            horizontal_fov_deg=horizontal_fov_deg,
        )

    # ------------------------------------------------------------------ #
    # Computed properties
    # ------------------------------------------------------------------ #

    @property
    def aspect_ratio(self) -> float:
        """Image width-to-height aspect ratio."""
        return self.width_px / self.height_px

    @property
    def fov_horizontal_deg(self) -> float:
        """Horizontal field of view in degrees."""
        return math.degrees(2.0 * math.atan(self.width_px / (2.0 * self.fx)))

    @property
    def fov_vertical_deg(self) -> float:
        """Vertical field of view in degrees."""
        return math.degrees(2.0 * math.atan(self.height_px / (2.0 * self.fy)))

    @property
    def fov_diagonal_deg(self) -> float:
        """Diagonal field of view in degrees."""
        diag_norm = math.hypot(
            self.width_px / (2.0 * self.fx),
            self.height_px / (2.0 * self.fy),
        )
        return math.degrees(2.0 * math.atan(diag_norm))

    @property
    def matrix(self) -> np.ndarray:
        """Returns the 3x3 intrinsic calibration matrix ``K`` as a NumPy array."""
        return np.array(
            [
                [self.fx, self.skew, self.cx],
                [0.0, self.fy, self.cy],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )

    @property
    def inverse_matrix(self) -> np.ndarray:
        """Returns the analytical 3x3 inverse intrinsic matrix ``K^-1``."""
        inv_fx = 1.0 / self.fx
        inv_fy = 1.0 / self.fy
        skew_term = -self.skew / (self.fx * self.fy)
        cx_term = (self.skew * self.cy - self.cx * self.fy) / (self.fx * self.fy)
        cy_term = -self.cy / self.fy
        return np.array(
            [
                [inv_fx, skew_term, cx_term],
                [0.0, inv_fy, cy_term],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializes the intrinsic parameters to a plain dictionary."""
        return {
            "width_px": self.width_px,
            "height_px": self.height_px,
            "fx": self.fx,
            "fy": self.fy,
            "cx": self.cx,
            "cy": self.cy,
            "skew": self.skew,
            "fov_horizontal_deg": round(self.fov_horizontal_deg, 4),
            "fov_vertical_deg": round(self.fov_vertical_deg, 4),
        }
