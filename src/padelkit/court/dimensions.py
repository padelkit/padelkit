from dataclasses import dataclass
from typing import Any

from .enums import EnclosureVariant


@dataclass(frozen=True)
class CourtDimensions:
    """Official dimensions of a padel court in meters.

    All height and length measurements follow FIP regulations:
    - ``length=20.0``, ``width=10.0`` interior dimensions (0.5% tolerance).
    - ``service_line_distance_from_back=3.0`` (``6.95 m`` from the net),
      ``service_line_extension=0.20`` beyond each service line, ``line_width=0.05``.
    - ``net_height_center=0.88``, ``net_height_posts=0.92`` (0.005 m tolerance),
      ``net_post_height=1.05`` max structural post height.
    - ``back_wall_height=4.0`` always; ``side_wall_height`` is ``3.0`` (V1) or
      ``4.0`` (V2); ``free_height=6.0`` minimum overhead clearance (``8.0 m``
      recommended for new constructions).
    """

    length: float
    """Interior court length along the Y axis in meters (FIP: `20.0` m)."""
    width: float
    """Interior court width along the X axis in meters (FIP: `10.0` m)."""
    net_height_center: float
    """Net height at the center strap (`X = 0`) in meters (FIP: `0.88` m)."""
    net_height_posts: float
    """Net height at the side posts (`X = ±5.0`) in meters (FIP: `0.92` m)."""
    service_line_distance_from_back: float
    """Distance from each back wall to its service line in meters (FIP: `3.0` m)."""
    back_wall_height: float
    """Total height of both back walls (wall + mesh) in meters (FIP: `4.0` m)."""
    side_wall_height: float
    """Central `16.0` m side enclosure height in meters (`3.0` V1, `4.0` V2)."""
    line_width: float = 0.05
    """Width of all painted court lines in meters (FIP: `0.05` m)."""
    service_line_extension: float = 0.20
    """Extension of the center line past each service line in meters (`0.20`)."""
    net_post_height: float = 1.05
    """Maximum structural height of the net posts in meters (FIP max: `1.05` m)."""
    free_height: float = 6.0
    """Minimum unobstructed vertical clearance in meters (`6.0` m, or `8.0` m new)."""

    @classmethod
    def fip_standard(
        cls,
        variant: EnclosureVariant = EnclosureVariant.V1,
        new_construction: bool = False,
    ) -> "CourtDimensions":
        """Standard dimensions as defined by the FIP.

        Args:
            variant: Regulatory enclosure height variant. Defaults to
                ``EnclosureVariant.V1`` (``side_wall_height=3.0`` m in the
                central 16 m). Pass ``EnclosureVariant.V2`` for a uniform
                ``4.0`` m lateral enclosure.
            new_construction: If ``True``, sets ``free_height=8.0`` m as
                recommended by FIP for new court constructions (otherwise
                ``6.0`` m regulatory minimum).
        """
        side_h = 4.0 if variant is EnclosureVariant.V2 else 3.0
        return cls(
            length=20.0,
            width=10.0,
            net_height_center=0.88,
            net_height_posts=0.92,
            service_line_distance_from_back=3.0,
            back_wall_height=4.0,
            side_wall_height=side_h,
            line_width=0.05,
            service_line_extension=0.20,
            net_post_height=1.05,
            free_height=8.0 if new_construction else 6.0,
        )

    @classmethod
    def fip_variant_2(cls, new_construction: bool = False) -> "CourtDimensions":
        """Standard FIP dimensions configured for Enclosure Variant 2 (4.0 m sides)."""
        return cls.fip_standard(
            variant=EnclosureVariant.V2,
            new_construction=new_construction,
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
            "line_width": self.line_width,
            "service_line_extension": self.service_line_extension,
            "net_post_height": self.net_post_height,
            "free_height": self.free_height,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CourtDimensions":
        """Reconstructs a `CourtDimensions` instance from a dictionary."""
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
            line_width=float(data.get("line_width", std.line_width)),
            service_line_extension=float(
                data.get("service_line_extension", std.service_line_extension)
            ),
            net_post_height=float(data.get("net_post_height", std.net_post_height)),
            free_height=float(data.get("free_height", std.free_height)),
        )
