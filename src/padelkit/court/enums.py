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
    WALL = "wall"  # Concrete or brick wall


class EnclosureVariant(int, Enum):
    """Regulatory enclosure variant as defined by the FIP.

    V1:
        Side enclosure reaches 4.0 m at the two 2.0 m end zones adjacent to
        the back walls, and 3.0 m across the central 16.0 m.
    V2:
        Side enclosure reaches a uniform 4.0 m height along the entire
        20.0 m court length.
    """

    V1 = 1
    V2 = 2


class SideWallProfile(str, Enum):
    """Geometry profile of the solid side-wall panels near the back corners.

    According to the official FIP Rules of Padel (Enclosures / Side walls):

    STEPPED:
        Two stepped solid panels at each end (for masonry/brick walls or
        stepped glass): 3.0 m high x 2.0 m long adjacent to the back wall,
        stepping down to 2.0 m high x 2.0 m long toward the center.
    UNIFORM:
        Continuous non-stepped solid panel ("sin escalón" / Variant Crystal):
        3.0 m high x 4.0 m long at each end with a flat 3.0 m top edge.
    """

    STEPPED = "stepped"
    UNIFORM = "uniform"


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


class CourtSurfaceColor(str, Enum):
    """Surface turf colors including FIP official and championship palettes.

    Per FIP regulations (*Suelo*, p. 9), standard outdoor/indoor colors are
    blue, green, and terracotta (*pardo-terroso*), while black turf is allowed
    exclusively on indoor courts. Professional championships may also use
    custom high-contrast colors (e.g., purple, red, gray, navy, pink).
    """

    BLUE = "blue"
    GREEN = "green"
    TERRACOTTA = "terracotta"
    BLACK = "black"
    PURPLE = "purple"
    RED = "red"
    ORANGE = "orange"
    GRAY = "gray"
    NAVY = "navy"
    TEAL = "teal"
    PINK = "pink"
