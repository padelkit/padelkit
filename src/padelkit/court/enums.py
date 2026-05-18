from enum import Enum


class CoordinateSystem(str, Enum):
    """Reference frame used to express court coordinates.

    CENTERED:
        Origin at the center of the court (midpoint of the net).
        X: width, from -5.0 (left) to +5.0 (right).
        Y: length, from -10.0 (near back wall) to +10.0 (far back wall).
        Z: height above the court floor, Z >= 0.

    CORNER_BASED:
        Origin at the bottom-left corner of the court (near side, left side).
        X: width, from 0 to 10.0.
        Y: length, from 0 to 20.0.
        Z: height above the court floor, Z >= 0.
        Compatible with the padelamix camera-calibration pipeline.
    """

    CENTERED = "centered"
    CORNER_BASED = "corner_based"


class EnclosureType(str, Enum):
    """Material used for the court enclosure walls."""

    GLASS = "glass"  # Tempered glass / methacrylate panels
    WALL = "wall"    # Concrete or brick wall


class EnclosureVariant(int, Enum):
    """Regulatory enclosure variant as defined by the FIP.

    V1:
        Side walls closed up to 3 m with metal fencing above.
        Back walls always at 4 m.
    V2:
        All walls (sides and back) fully closed at 4 m.
    """

    V1 = 1
    V2 = 2


class CourtOrientation(str, Enum):
    """Cardinal orientation of the court's main axis (length direction)."""

    NORTH_SOUTH = "north_south"
    EAST_WEST = "east_west"


class DoorState(str, Enum):
    """Open/closed state of a court access door."""

    OPEN = "open"
    CLOSED = "closed"


class CourtSetting(str, Enum):
    """Setting or environment of the court (indoor, outdoor, or semi-covered)."""

    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    SEMI_COVERED = "semi_covered"

