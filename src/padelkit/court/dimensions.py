from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CourtDimensions:
    """Official dimensions of a padel court in meters.

    All height measurements follow FIP regulations:
    - back_wall_height: always 4.0 m for both enclosure variants.
    - side_wall_height: 3.0 m for Variant 1, 4.0 m for Variant 2.
    """

    length: float
    width: float
    net_height_center: float
    net_height_posts: float
    service_line_distance_from_back: float
    back_wall_height: float
    side_wall_height: float

    @classmethod
    def fip_standard(cls) -> "CourtDimensions":
        """Standard dimensions as defined by the FIP (Variant 1 defaults)."""
        return cls(
            length=20.0,
            width=10.0,
            net_height_center=0.88,
            net_height_posts=0.92,
            service_line_distance_from_back=3.0,
            back_wall_height=4.0,
            side_wall_height=3.0,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializes the court dimensions to a dictionary."""
        return {
            "length": self.length,
            "width": self.width,
            "net_height_center": self.net_height_center,
            "net_height_posts": self.net_height_posts,
            "service_line_distance_from_back": self.service_line_distance_from_back,
            "back_wall_height": self.back_wall_height,
            "side_wall_height": self.side_wall_height,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CourtDimensions":
        """Reconstructs a :class:`CourtDimensions` instance from a dictionary."""
        std = cls.fip_standard()
        return cls(
            length=float(data.get("length", std.length)),
            width=float(data.get("width", std.width)),
            net_height_center=float(
                data.get("net_height_center", std.net_height_center)
            ),
            net_height_posts=float(data.get("net_height_posts", std.net_height_posts)),
            service_line_distance_from_back=float(
                data.get(
                    "service_line_distance_from_back",
                    std.service_line_distance_from_back,
                )
            ),
            back_wall_height=float(data.get("back_wall_height", std.back_wall_height)),
            side_wall_height=float(data.get("side_wall_height", std.side_wall_height)),
        )
