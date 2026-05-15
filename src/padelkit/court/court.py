from dataclasses import dataclass

from .dimensions import CourtDimensions
from .enums import (
    CoordinateSystem,
    CourtOrientation,
    DoorState,
    EnclosureType,
    EnclosureVariant,
)
from .landmarks import Landmark
from .location import CourtLocation


@dataclass(frozen=True)
class PadelCourt:
    """Represents a padel court with its geometry, physical
    characteristics, and metadata.

    Coordinates are expressed in meters. By default, the CENTERED system is used:
    the origin (0, 0, 0) is at the midpoint of the net, X is the width axis,
    Y is the length axis, and Z is the height above the court floor.

    Pass ``coordinate_system=CoordinateSystem.CORNER_BASED`` to any landmark
    method to obtain coordinates with the origin at the bottom-left corner,
    compatible with the padelamix camera-calibration pipeline.
    """

    dimensions: CourtDimensions

    # Physical characteristics
    enclosure_type: EnclosureType | None = None
    enclosure_variant: EnclosureVariant | None = None
    orientation: CourtOrientation | None = None
    turf_color: str | None = None

    # Access doors (one per lateral side)
    # "left" and "right" are from the perspective of a player
    # on the NEAR side facing the net.
    door_left: DoorState | None = None
    door_right: DoorState | None = None

    # Location
    location: CourtLocation | None = None

    # ------------------------------------------------------------------ #
    # Class methods
    # ------------------------------------------------------------------ #

    @classmethod
    def fip_standard(cls) -> "PadelCourt":
        """Creates a standard FIP padel court with no optional metadata."""
        return cls(dimensions=CourtDimensions.fip_standard())

    # ------------------------------------------------------------------ #
    # Simple dimension properties
    # ------------------------------------------------------------------ #

    @property
    def length(self) -> float:
        """Total length of the court in meters."""
        return self.dimensions.length

    @property
    def width(self) -> float:
        """Total width of the court in meters."""
        return self.dimensions.width

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _offset(self) -> tuple[float, float]:
        """Returns the (dx, dy) shift to convert CENTERED → CORNER_BASED."""
        return self.width / 2, self.length / 2

    def _apply_system(
        self,
        x: float,
        y: float,
        coordinate_system: CoordinateSystem,
    ) -> tuple[float, float]:
        dx, dy = self._offset()
        if coordinate_system is CoordinateSystem.CORNER_BASED:
            return x + dx, y + dy
        return x, y

    def _apply_system_3d(
        self,
        x: float,
        y: float,
        z: float,
        coordinate_system: CoordinateSystem,
    ) -> tuple[float, float, float]:
        x2, y2 = self._apply_system(x, y, coordinate_system)
        return x2, y2, z

    # ------------------------------------------------------------------ #
    # Landmark methods
    # ------------------------------------------------------------------ #

    def landmarks_2d(
        self,
        coordinate_system: CoordinateSystem = CoordinateSystem.CENTERED,
    ) -> dict[str, tuple[float, float]]:
        """Returns all standard 2D floor landmarks as (X, Y) coordinate pairs.

        Args:
            coordinate_system: The reference frame for the returned coordinates.
                Defaults to ``CoordinateSystem.CENTERED``.

        Returns:
            A dictionary mapping each :class:`Landmark` name to its (X, Y) position.
        """
        hw = self.width / 2
        hl = self.length / 2
        svc = hl - self.dimensions.service_line_distance_from_back

        raw: dict[str, tuple[float, float]] = {
            Landmark.FLOOR_NEAR_LEFT.value:      (-hw, -hl),
            Landmark.FLOOR_NEAR_RIGHT.value:     ( hw, -hl),
            Landmark.SERVICE_NEAR_LEFT.value:    (-hw, -svc),
            Landmark.SERVICE_NEAR_CENTER.value:  (0.0, -svc),
            Landmark.SERVICE_NEAR_RIGHT.value:   ( hw, -svc),
            Landmark.NET_LEFT.value:             (-hw,  0.0),
            Landmark.CENTER.value:               (0.0,  0.0),
            Landmark.NET_RIGHT.value:            ( hw,  0.0),
            Landmark.SERVICE_FAR_LEFT.value:     (-hw,  svc),
            Landmark.SERVICE_FAR_CENTER.value:   (0.0,  svc),
            Landmark.SERVICE_FAR_RIGHT.value:    ( hw,  svc),
            Landmark.FLOOR_FAR_LEFT.value:       (-hw,  hl),
            Landmark.FLOOR_FAR_RIGHT.value:      ( hw,  hl),
        }

        return {
            name: self._apply_system(x, y, coordinate_system)
            for name, (x, y) in raw.items()
        }

    def landmarks_3d(
        self,
        coordinate_system: CoordinateSystem = CoordinateSystem.CENTERED,
    ) -> dict[str, tuple[float, float, float]]:
        """Returns all 17 standard landmarks as (X, Y, Z) coordinate triples.

        Floor points (landmarks 1-13) have Z = 0.
        Back-wall top points (landmarks 14-17) have Z = ``dimensions.back_wall_height``.

        Args:
            coordinate_system: The reference frame for the returned coordinates.
                Defaults to ``CoordinateSystem.CENTERED``.

        Returns:
            A dictionary mapping each :class:`Landmark` name to its (X, Y, Z) position.
        """
        hw = self.width / 2
        hl = self.length / 2
        svc = hl - self.dimensions.service_line_distance_from_back
        wh = self.dimensions.back_wall_height

        raw: dict[str, tuple[float, float, float]] = {
            # Floor points
            Landmark.FLOOR_NEAR_LEFT.value:      (-hw, -hl,   0.0),
            Landmark.FLOOR_NEAR_RIGHT.value:     ( hw, -hl,   0.0),
            Landmark.SERVICE_NEAR_LEFT.value:    (-hw, -svc,  0.0),
            Landmark.SERVICE_NEAR_CENTER.value:  (0.0, -svc,  0.0),
            Landmark.SERVICE_NEAR_RIGHT.value:   ( hw, -svc,  0.0),
            Landmark.NET_LEFT.value:             (-hw,  0.0,  0.0),
            Landmark.CENTER.value:               (0.0,  0.0,  0.0),
            Landmark.NET_RIGHT.value:            ( hw,  0.0,  0.0),
            Landmark.SERVICE_FAR_LEFT.value:     (-hw,  svc,  0.0),
            Landmark.SERVICE_FAR_CENTER.value:   (0.0,  svc,  0.0),
            Landmark.SERVICE_FAR_RIGHT.value:    ( hw,  svc,  0.0),
            Landmark.FLOOR_FAR_LEFT.value:       (-hw,  hl,   0.0),
            Landmark.FLOOR_FAR_RIGHT.value:      ( hw,  hl,   0.0),
            # Back wall top points
            Landmark.WALL_TOP_NEAR_LEFT.value:   (-hw, -hl,   wh),
            Landmark.WALL_TOP_NEAR_RIGHT.value:  ( hw, -hl,   wh),
            Landmark.WALL_TOP_FAR_LEFT.value:    (-hw,  hl,   wh),
            Landmark.WALL_TOP_FAR_RIGHT.value:   ( hw,  hl,   wh),
        }

        return {
            name: self._apply_system_3d(x, y, z, coordinate_system)
            for name, (x, y, z) in raw.items()
        }

    def point(
        self,
        name: str,
        coordinate_system: CoordinateSystem = CoordinateSystem.CENTERED,
    ) -> tuple[float, float]:
        """Returns the (X, Y) coordinates of a specific 2D landmark.

        Args:
            name: A :class:`Landmark` value string (e.g., ``"center"``).
            coordinate_system: The reference frame for the returned coordinates.
                Defaults to ``CoordinateSystem.CENTERED``.

        Raises:
            ValueError: If *name* does not match any known landmark.
        """
        landmarks = self.landmarks_2d(coordinate_system=coordinate_system)
        if name not in landmarks:
            raise ValueError(
                f"Unknown landmark: '{name}'. "
                f"Available: {sorted(landmarks.keys())}"
            )
        return landmarks[name]
