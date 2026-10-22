from enum import Enum


class DistortionModel(str, Enum):
    """Supported optical lens distortion models.

    Attributes:
        NONE: Ideal pinhole camera with no lens distortion.
        BROWN_CONRADY: Standard radial and tangential distortion model
            parameterized by ``(k1, k2, p1, p2, k3)``, compatible with OpenCV.
        FISHEYE: Equidistant fisheye lens distortion model parameterized by
            ``(k1, k2, k3, k4)``, ideal for wide-angle action cameras mounted
            close to the padel court glass walls.
    """

    NONE = "none"
    BROWN_CONRADY = "brown_conrady"
    FISHEYE = "fisheye"


class CameraPreset(str, Enum):
    """Standardized camera placement presets around a regulation padel court.

    All presets use the ``CoordinateSystem.CENTERED`` reference frame where
    ``(0, 0, 0)`` is at the center of the net on the floor, ``-Y`` is the
    NEAR side, and ``+Y`` is the FAR side.
    """

    BROADCAST_NEAR = "broadcast_near"
    BROADCAST_FAR = "broadcast_far"
    OVERHEAD_ZENITH = "overhead_zenith"
    CORNER_NEAR_LEFT = "corner_near_left"
    CORNER_NEAR_RIGHT = "corner_near_right"
    CORNER_FAR_LEFT = "corner_far_left"
    CORNER_FAR_RIGHT = "corner_far_right"
    SIDE_NET_LEFT = "side_net_left"
    SIDE_NET_RIGHT = "side_net_right"
