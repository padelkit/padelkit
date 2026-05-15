from dataclasses import dataclass


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
