from dataclasses import dataclass, field
from typing import Any

from .dimensions import CourtDimensions
from .enums import (
    CoordinateSystem,
    CourtOrientation,
    CourtSetting,
    DoorState,
    EnclosureType,
    EnclosureVariant,
)
from .landmarks import CourtLandmark
from .location import CourtLocation


@dataclass(frozen=True)
class Court:
    """Represents a padel court with its geometry, physical
    characteristics, and metadata.

    Coordinates are expressed in meters. By default, the CENTERED system is used:
    the origin (0, 0, 0) is at the midpoint of the net, X is the width axis,
    Y is the length axis, and Z is the height above the court floor.

    Pass ``coordinate_system=CoordinateSystem.CORNER_BASED`` to any landmark
    method to obtain coordinates with the origin at the bottom-left corner,
    compatible with the padelamix camera-calibration pipeline.
    """

    dimensions: CourtDimensions = field(default_factory=CourtDimensions.fip_standard)

    # Physical characteristics
    enclosure_type: EnclosureType | None = None
    enclosure_variant: EnclosureVariant | None = None
    orientation: CourtOrientation | None = None
    turf_color: str | None = None
    setting: CourtSetting | None = None

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
    def fip_standard(cls) -> "Court":
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
    # CourtLandmark methods
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
            A dictionary mapping each :class:`CourtLandmark` name to its (X, Y)
            position.
        """
        hw = self.width / 2
        hl = self.length / 2
        svc = hl - self.dimensions.service_line_distance_from_back

        raw: dict[str, tuple[float, float]] = {
            CourtLandmark.FLOOR_NEAR_LEFT.value: (-hw, -hl),
            CourtLandmark.FLOOR_NEAR_RIGHT.value: (hw, -hl),
            CourtLandmark.SERVICE_NEAR_LEFT.value: (-hw, -svc),
            CourtLandmark.SERVICE_NEAR_CENTER.value: (0.0, -svc),
            CourtLandmark.SERVICE_NEAR_RIGHT.value: (hw, -svc),
            CourtLandmark.NET_LEFT.value: (-hw, 0.0),
            CourtLandmark.CENTER.value: (0.0, 0.0),
            CourtLandmark.NET_RIGHT.value: (hw, 0.0),
            CourtLandmark.SERVICE_FAR_LEFT.value: (-hw, svc),
            CourtLandmark.SERVICE_FAR_CENTER.value: (0.0, svc),
            CourtLandmark.SERVICE_FAR_RIGHT.value: (hw, svc),
            CourtLandmark.FLOOR_FAR_LEFT.value: (-hw, hl),
            CourtLandmark.FLOOR_FAR_RIGHT.value: (hw, hl),
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
            A dictionary mapping each :class:`CourtLandmark` name to its (X, Y, Z)
            position.
        """
        hw = self.width / 2
        hl = self.length / 2
        svc = hl - self.dimensions.service_line_distance_from_back
        wh = self.dimensions.back_wall_height

        raw: dict[str, tuple[float, float, float]] = {
            # Floor points
            CourtLandmark.FLOOR_NEAR_LEFT.value: (-hw, -hl, 0.0),
            CourtLandmark.FLOOR_NEAR_RIGHT.value: (hw, -hl, 0.0),
            CourtLandmark.SERVICE_NEAR_LEFT.value: (-hw, -svc, 0.0),
            CourtLandmark.SERVICE_NEAR_CENTER.value: (0.0, -svc, 0.0),
            CourtLandmark.SERVICE_NEAR_RIGHT.value: (hw, -svc, 0.0),
            CourtLandmark.NET_LEFT.value: (-hw, 0.0, 0.0),
            CourtLandmark.CENTER.value: (0.0, 0.0, 0.0),
            CourtLandmark.NET_RIGHT.value: (hw, 0.0, 0.0),
            CourtLandmark.SERVICE_FAR_LEFT.value: (-hw, svc, 0.0),
            CourtLandmark.SERVICE_FAR_CENTER.value: (0.0, svc, 0.0),
            CourtLandmark.SERVICE_FAR_RIGHT.value: (hw, svc, 0.0),
            CourtLandmark.FLOOR_FAR_LEFT.value: (-hw, hl, 0.0),
            CourtLandmark.FLOOR_FAR_RIGHT.value: (hw, hl, 0.0),
            # Back wall top points
            CourtLandmark.WALL_TOP_NEAR_LEFT.value: (-hw, -hl, wh),
            CourtLandmark.WALL_TOP_NEAR_RIGHT.value: (hw, -hl, wh),
            CourtLandmark.WALL_TOP_FAR_LEFT.value: (-hw, hl, wh),
            CourtLandmark.WALL_TOP_FAR_RIGHT.value: (hw, hl, wh),
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
            name: A :class:`CourtLandmark` value string (e.g., ``"center"``).
            coordinate_system: The reference frame for the returned coordinates.
                Defaults to ``CoordinateSystem.CENTERED``.

        Raises:
            ValueError: If *name* does not match any known landmark.
        """
        landmarks = self.landmarks_2d(coordinate_system=coordinate_system)
        if name not in landmarks:
            raise ValueError(
                f"Unknown landmark: '{name}'. Available: {sorted(landmarks.keys())}"
            )
        return landmarks[name]

    def to_dict(self) -> dict[str, Any]:
        """Serializes the court geometry and metadata to a dictionary."""
        return {
            "dimensions": self.dimensions.to_dict(),
            "enclosure_type": (
                self.enclosure_type.value if self.enclosure_type is not None else None
            ),
            "enclosure_variant": (
                self.enclosure_variant.value
                if self.enclosure_variant is not None
                else None
            ),
            "orientation": (
                self.orientation.value if self.orientation is not None else None
            ),
            "turf_color": self.turf_color,
            "setting": self.setting.value if self.setting is not None else None,
            "door_left": self.door_left.value if self.door_left is not None else None,
            "door_right": (
                self.door_right.value if self.door_right is not None else None
            ),
            "location": self.location.to_dict() if self.location is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Court":
        """Reconstructs a :class:`Court` instance from a dictionary."""
        dims_data = data.get("dimensions")
        dims = (
            CourtDimensions.from_dict(dims_data)
            if isinstance(dims_data, dict)
            else CourtDimensions.fip_standard()
        )
        loc_data = data.get("location")
        loc = CourtLocation.from_dict(loc_data) if isinstance(loc_data, dict) else None
        return cls(
            dimensions=dims,
            enclosure_type=(
                EnclosureType(data["enclosure_type"])
                if data.get("enclosure_type") is not None
                else None
            ),
            enclosure_variant=(
                EnclosureVariant(int(data["enclosure_variant"]))
                if data.get("enclosure_variant") is not None
                else None
            ),
            orientation=(
                CourtOrientation(data["orientation"])
                if data.get("orientation") is not None
                else None
            ),
            turf_color=data.get("turf_color"),
            setting=(
                CourtSetting(data["setting"])
                if data.get("setting") is not None
                else None
            ),
            door_left=(
                DoorState(data["door_left"])
                if data.get("door_left") is not None
                else None
            ),
            door_right=(
                DoorState(data["door_right"])
                if data.get("door_right") is not None
                else None
            ),
            location=loc,
        )
