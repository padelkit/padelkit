from dataclasses import dataclass, field
from typing import Any, Literal

from .dimensions import CourtDimensions
from .enums import (
    CoordinateSystem,
    CourtOrientation,
    CourtSetting,
    CourtSurfaceColor,
    DoorState,
    EnclosureType,
    EnclosureVariant,
    SideWallProfile,
)
from .landmarks import CourtLandmark
from .location import CourtLocation


@dataclass(frozen=True)
class SideEnclosureSegment:
    """One longitudinal segment along a half-side enclosure (from back wall toward net).

    All distances and heights are expressed in meters.
    """

    y_start_from_back: float
    """Start distance from the nearest back wall in meters."""
    y_end_from_back: float
    """End distance from the nearest back wall in meters."""
    solid_height: float
    """Height of the solid glass or masonry wall section in meters."""
    total_height: float
    """Total enclosure height including overhead metallic mesh in meters."""

    @property
    def length(self) -> float:
        """Segment length along the court sideline in meters."""
        return max(0.0, self.y_end_from_back - self.y_start_from_back)

    @property
    def mesh_height(self) -> float:
        """Vertical span of metallic mesh above the solid wall/glass in meters."""
        return max(0.0, self.total_height - self.solid_height)


@dataclass(frozen=True)
class SideEnclosurePanel:
    """One rectangular wall/mesh panel in CENTERED sideline coordinates.

    Attributes:
        y_start: Start Y coordinate along the sideline in meters.
        y_end: End Y coordinate along the sideline in meters.
        z_start: Bottom elevation above the court floor in meters.
        z_end: Top elevation above the court floor in meters.
        is_solid: ``True`` for tempered glass or masonry wall panels, ``False``
            for metallic mesh panels (including doorway lintels and closed doors).
    """

    y_start: float
    """Start Y coordinate along the sideline in CENTERED meters."""
    y_end: float
    """End Y coordinate along the sideline in CENTERED meters."""
    z_start: float
    """Bottom elevation above the court floor in meters."""
    z_end: float
    """Top elevation above the court floor in meters."""
    is_solid: bool
    """`True` for glass/wall panels; `False` for metallic mesh or closed gates."""


@dataclass(frozen=True)
class SideAccess:
    """Access doorway configuration for one lateral side of a padel court.

    Per official FIP regulations (*Accesos*, pages 10-11), lateral openings are
    symmetric around the net post (`Y = 0`) and topped by metallic mesh up to
    the full enclosure height:

    - Single access (`count=1`): ``1.05–2.00 m`` wide × ``2.00–2.20 m`` high.
    - Dual access (`count=2`): two openings each ``0.72–1.00 m`` wide ×
      ``2.00–2.20 m`` high separated by a central structural post.
    - No access (`count=0`): continuous metallic mesh along the sideline
      (legal on one side when out-of-court play is disabled, or common in clubs).
    """

    count: int = 1
    """Number of doorway openings on this sideline (`0`, `1`, or `2`)."""
    width: float = 2.0
    """Clear doorway width in meters (`1.05-2.00` single, `0.72-1.00` dual)."""
    height: float = 2.2
    """Clear doorway height from floor in meters (FIP: `2.00-2.20` m)."""
    center_pillar_width: float = 0.16
    """Width of the central post between dual doors at `Y = 0` in meters."""

    def __post_init__(self) -> None:
        if self.count not in (0, 1, 2):
            raise ValueError(f"SideAccess count must be 0, 1, or 2 (got {self.count}).")
        if self.count > 0:
            if self.width <= 0.0:
                raise ValueError(
                    f"SideAccess width must be positive (got {self.width})."
                )
            if self.height <= 0.0:
                raise ValueError(
                    f"SideAccess height must be positive (got {self.height})."
                )
        if self.center_pillar_width < 0.0:
            raise ValueError(
                "SideAccess center_pillar_width must be non-negative "
                f"(got {self.center_pillar_width})."
            )

    @classmethod
    def fip_single_access(
        cls,
        width: float = 2.0,
        height: float = 2.2,
    ) -> "SideAccess":
        """Single central doorway at maximum FIP dimensions (``2.00 m × 2.20 m``)."""
        return cls(count=1, width=width, height=height, center_pillar_width=0.0)

    @classmethod
    def fip_dual_access(
        cls,
        width: float = 1.0,
        height: float = 2.2,
        center_pillar_width: float = 0.16,
    ) -> "SideAccess":
        """Dual symmetric FIP doorways (``1.00 m × 2.20 m`` each)."""
        return cls(
            count=2,
            width=width,
            height=height,
            center_pillar_width=center_pillar_width,
        )

    @classmethod
    def no_access(cls) -> "SideAccess":
        """Closed sideline with no doorway opening (continuous metallic mesh)."""
        return cls(count=0, width=0.0, height=0.0, center_pillar_width=0.0)

    def opening_y_intervals(
        self,
        half_length: float = 10.0,
    ) -> tuple[tuple[float, float], ...]:
        """Returns sorted ``(y_min, y_max)`` intervals in CENTERED coordinates."""
        if self.count == 0 or self.width <= 0.0 or self.height <= 0.0:
            return ()
        limit = max(0.0, float(half_length))
        if self.count == 1:
            hw_open = 0.5 * float(self.width)
            y0, y1 = max(-limit, -hw_open), min(limit, hw_open)
            return ((y0, y1),) if y1 > y0 else ()
        gap_half = 0.5 * float(self.center_pillar_width)
        near = (max(-limit, -gap_half - float(self.width)), min(limit, -gap_half))
        far = (max(-limit, gap_half), min(limit, gap_half + float(self.width)))
        intervals = [pair for pair in (near, far) if pair[1] > pair[0]]
        return tuple(intervals)

    def is_fip_compliant(self) -> bool:
        """Returns whether dimensions fall inside official FIP *Accesos* bounds."""
        if self.count == 0:
            return True
        if not (2.00 <= self.height <= 2.20):
            return False
        if self.count == 1:
            return 1.05 <= self.width <= 2.00
        return 0.72 <= self.width <= 1.00

    def to_dict(self) -> dict[str, Any]:
        """Serializes the access configuration to a dictionary."""
        return {
            "count": int(self.count),
            "width": float(self.width),
            "height": float(self.height),
            "center_pillar_width": float(self.center_pillar_width),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SideAccess":
        """Reconstructs a `SideAccess` from a dictionary."""
        return cls(
            count=int(data.get("count", 1)),
            width=float(data.get("width", 2.0)),
            height=float(data.get("height", 2.2)),
            center_pillar_width=float(data.get("center_pillar_width", 0.16)),
        )


@dataclass(frozen=True)
class SafetyZone:
    """Exterior safety & out-of-court play clearance for one court sideline.

    Per FIP regulations (*Zona de seguridad y juego exterior*, p. 11), each side
    requires an obstacle-free exterior volume of at least ``2.0 m`` width,
    ``4.0 m`` length to each side of the net (``8.0 m`` total), and ``3.0 m``
    vertical height, plus ``>= 2 cm`` shock-absorbing padding around doorways
    and net posts.
    """

    width: float = 2.0
    """Exterior clearance width outside the sideline in meters (FIP `>= 2.0`)."""
    half_length: float = 4.0
    """Clearance half-length along Y on each side of the net in meters (`>= 4.0`)."""
    height: float = 3.0
    """Vertical clearance height over the exterior safety zone in meters (`>= 3.0`)."""
    doorway_padding_thickness: float = 0.02
    """Protective padding thickness on doorway frames/posts in meters (`>= 0.02`)."""

    def __post_init__(self) -> None:
        if (
            self.width < 0.0
            or self.half_length < 0.0
            or self.height < 0.0
            or self.doorway_padding_thickness < 0.0
        ):
            raise ValueError("SafetyZone dimensions must be non-negative.")

    @classmethod
    def fip_standard(cls) -> "SafetyZone":
        """Minimum official FIP exterior clearance for out-of-court play."""
        return cls()

    @classmethod
    def none(cls) -> "SafetyZone":
        """Represents a court sideline with no exterior out-of-court clearance."""
        return cls(
            width=0.0,
            half_length=0.0,
            height=0.0,
            doorway_padding_thickness=0.0,
        )

    def is_fip_compliant(self) -> bool:
        """Returns ``True`` when exterior clearance satisfies FIP p. 11 rules."""
        return (
            self.width >= 2.0
            and self.half_length >= 4.0
            and self.height >= 3.0
            and self.doorway_padding_thickness >= 0.02
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializes the safety zone to a dictionary."""
        return {
            "width": float(self.width),
            "half_length": float(self.half_length),
            "height": float(self.height),
            "doorway_padding_thickness": float(self.doorway_padding_thickness),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SafetyZone":
        """Reconstructs a `SafetyZone` from a dictionary."""
        return cls(
            width=float(data.get("width", 2.0)),
            half_length=float(data.get("half_length", 4.0)),
            height=float(data.get("height", 3.0)),
            doorway_padding_thickness=float(
                data.get("doorway_padding_thickness", 0.02)
            ),
        )


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
    """Geometric dimensions of the court in meters (`CourtDimensions`)."""

    # Physical characteristics
    enclosure_type: EnclosureType | None = None
    """Enclosure material (`GLASS` or `WALL`). Defaults to `GLASS` when unset."""
    enclosure_variant: EnclosureVariant | None = None
    """Regulatory enclosure height profile (`V1` stepped `3m` or `V2` uniform `4m`)."""
    side_wall_profile: SideWallProfile | None = None
    """Corner solid side-wall shape (`STEPPED` or `UNIFORM`)."""
    orientation: CourtOrientation | None = None
    """Cardinal compass orientation of the court length axis."""
    turf_color: CourtSurfaceColor | str | None = None
    """Playing surface color (`CourtSurfaceColor` or custom hex/color string)."""
    setting: CourtSetting | None = None
    """Venue environment (`INDOOR`, `OUTDOOR`, or `SEMI_COVERED`)."""

    # Access doors (one or two openings per lateral side)
    # "left" and "right" are from the perspective of a player
    # on the NEAR side facing the net.
    door_left: DoorState | None = None
    """Open/closed state of the left (`X = -width/2`) access doorway."""
    door_right: DoorState | None = None
    """Open/closed state of the right (`X = +width/2`) access doorway."""
    access_left: SideAccess | None = None
    """Geometric doorway specification for the left (`X = -width/2`) sideline."""
    access_right: SideAccess | None = None
    """Geometric doorway specification for the right (`X = +width/2`) sideline."""
    safety_zone_left: SafetyZone | None = None
    """Exterior Rule 16 safety clearance outside the left (`X < -width/2`) sideline."""
    safety_zone_right: SafetyZone | None = None
    """Exterior Rule 16 safety clearance outside the right (`X > +width/2`) sideline."""
    ceiling_height: float | None = None
    """Actual ceiling height in meters (`Z` boundary for indoor roof, or `None`)."""

    # Location
    location: CourtLocation | None = None
    """Optional venue metadata (`club`, `city`, GPS coordinates)."""

    def __post_init__(self) -> None:
        if self.ceiling_height is not None and self.ceiling_height <= 0.0:
            raise ValueError("ceiling_height must be strictly positive when set.")

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

    @property
    def effective_turf_color(self) -> str:
        """Resolved court surface color string (defaults to ``'blue'``)."""
        if isinstance(self.turf_color, CourtSurfaceColor):
            return self.turf_color.value
        return self.turf_color or CourtSurfaceColor.BLUE.value

    @property
    def effective_enclosure_type(self) -> EnclosureType:
        """Resolved enclosure material (defaults to ``EnclosureType.GLASS``)."""
        return (
            self.enclosure_type
            if self.enclosure_type is not None
            else EnclosureType.GLASS
        )

    @property
    def effective_enclosure_variant(self) -> EnclosureVariant:
        """Resolved regulatory enclosure variant (``V1`` or ``V2``)."""
        if self.enclosure_variant is not None:
            return self.enclosure_variant
        if self.dimensions.side_wall_height >= 4.0:
            return EnclosureVariant.V2
        return EnclosureVariant.V1

    @property
    def effective_side_wall_profile(self) -> SideWallProfile:
        """Resolved side-wall solid profile (``STEPPED`` or ``UNIFORM``).

        When ``side_wall_profile`` is unset (``None``), masonry/brick courts
        (``EnclosureType.WALL``) default to ``SideWallProfile.STEPPED`` and
        glass courts (``EnclosureType.GLASS``) default to
        ``SideWallProfile.UNIFORM``.
        """
        if self.side_wall_profile is not None:
            return self.side_wall_profile
        if self.effective_enclosure_type is EnclosureType.WALL:
            return SideWallProfile.STEPPED
        return SideWallProfile.UNIFORM

    @property
    def effective_access_left(self) -> SideAccess:
        """Resolved left sideline access configuration (defaults to FIP 2.0m x 2.2m)."""
        return (
            self.access_left
            if self.access_left is not None
            else SideAccess.fip_single_access()
        )

    @property
    def effective_access_right(self) -> SideAccess:
        """Resolved right sideline access (defaults to FIP 2.0m x 2.2m)."""
        return (
            self.access_right
            if self.access_right is not None
            else SideAccess.fip_single_access()
        )

    def effective_access(self, side: Literal["left", "right"]) -> SideAccess:
        """Returns the resolved `SideAccess` for `'left'` or `'right'`."""
        if side == "left":
            return self.effective_access_left
        if side == "right":
            return self.effective_access_right
        raise ValueError(f"side must be 'left' or 'right' (got {side!r}).")

    def door_state_for(self, side: Literal["left", "right"]) -> DoorState | None:
        """Returns `door_left` or `door_right` for `side`."""
        if side == "left":
            return self.door_left
        if side == "right":
            return self.door_right
        raise ValueError(f"side must be 'left' or 'right' (got {side!r}).")

    def has_fip_compliant_access(self, out_of_court_play: bool = False) -> bool:
        """Returns whether lateral openings satisfy FIP rules.

        Args:
            out_of_court_play: If ``True``, both sides must have 2 compliant
                openings (FIP *Zona de seguridad y juego exterior*, p. 11). If
                ``False``, at least one side must have 1 or 2 compliant openings.
        """
        left = self.effective_access_left
        right = self.effective_access_right
        if not (left.is_fip_compliant() and right.is_fip_compliant()):
            return False
        if out_of_court_play:
            return left.count == 2 and right.count == 2
        return (left.count + right.count) >= 1

    def is_out_of_court_play_allowed(self) -> bool:
        """Returns ``True`` when doors and exterior safety zones permit Rule 16."""
        if not self.has_fip_compliant_access(out_of_court_play=True):
            return False
        for zone in (self.safety_zone_left, self.safety_zone_right):
            if zone is not None and not zone.is_fip_compliant():
                return False
        return True

    def fip_compliance_issues(self, out_of_court_play: bool = False) -> list[str]:
        """Returns a list of regulatory deviations against FIP court rules."""
        issues: list[str] = []
        d = self.dimensions
        if abs(d.length - 20.0) > 20.0 * 0.005:
            issues.append(f"length {d.length}m outside 20.0m +/- 0.5% tolerance.")
        if abs(d.width - 10.0) > 10.0 * 0.005:
            issues.append(f"width {d.width}m outside 10.0m +/- 0.5% tolerance.")
        if abs(d.net_height_center - 0.88) > 0.005:
            issues.append(
                f"net_height_center {d.net_height_center}m outside 0.88m +/- 0.005m."
            )
        if d.net_height_posts > 0.92 + 0.005:
            issues.append(
                f"net_height_posts {d.net_height_posts}m exceeds 0.92m + 0.005m."
            )
        if d.net_post_height > 1.05 + 1e-6:
            issues.append(f"net_post_height {d.net_post_height}m exceeds 1.05m max.")
        if abs(d.line_width - 0.05) > 1e-6:
            issues.append(f"line_width {d.line_width}m must be 0.05m.")
        if abs(d.service_line_extension - 0.20) > 1e-6:
            issues.append(
                f"service_line_extension {d.service_line_extension}m must be 0.20m."
            )
        if abs(d.back_wall_height - 4.0) > 1e-6:
            issues.append(f"back_wall_height {d.back_wall_height}m must be 4.0m.")
        if not any(abs(d.side_wall_height - h) <= 1e-6 for h in (3.0, 4.0)):
            issues.append(
                f"side_wall_height {d.side_wall_height}m "
                "must be 3.0m (V1) or 4.0m (V2)."
            )
        if d.free_height < 6.0 - 1e-6:
            issues.append(f"free_height {d.free_height}m is below 6.0m FIP minimum.")
        if self.ceiling_height is not None and self.ceiling_height < 6.0 - 1e-6:
            issues.append(
                f"ceiling_height {self.ceiling_height}m is below 6.0m FIP minimum."
            )
        if not self.has_fip_compliant_access(out_of_court_play=out_of_court_play):
            issues.append(
                "lateral access openings do not satisfy FIP dimensions/count."
            )
        if out_of_court_play and not self.is_out_of_court_play_allowed():
            issues.append("safety zone clearance does not satisfy FIP Rule 16.")
        if self.turf_color is not None:
            color = self.effective_turf_color.lower()
            if color == "black" and self.setting is not CourtSetting.INDOOR:
                issues.append("black turf is only FIP-approved on indoor courts.")
            elif color not in {"blue", "green", "terracotta", "black"}:
                issues.append(
                    f"turf_color {color!r} is outside FIP standard surface palette."
                )
        return issues

    def is_fip_compliant(self, out_of_court_play: bool = False) -> bool:
        """Returns ``True`` when the court passes all FIP regulatory checks."""
        return len(self.fip_compliance_issues(out_of_court_play=out_of_court_play)) == 0

    def is_doorway_opening_at(
        self,
        side: Literal["left", "right"],
        y_centered: float,
        z: float,
        *,
        radius: float = 0.0,
    ) -> bool:
        """Returns ``True`` when ``(y_centered, z)`` lies inside a passable doorway.

        A doorway is passable when ``count > 0``, the door is not
        ``DoorState.CLOSED``, ``0 <= z <= access.height - radius``, and
        ``y_centered`` falls cleanly inside one of the opening Y intervals.
        """
        if self.door_state_for(side) is DoorState.CLOSED:
            return False
        access = self.effective_access(side)
        if access.count == 0 or z < 0.0:
            return False
        r = max(0.0, float(radius))
        if z > access.height - r:
            return False
        for y0, y1 in access.opening_y_intervals(half_length=self.length / 2.0):
            if (y0 + r) <= y_centered <= (y1 - r):
                return True
        return False

    def side_enclosure_panels(
        self,
        side: Literal["left", "right"] = "left",
    ) -> list[SideEnclosurePanel]:
        """Returns full-length ``[-length/2, +length/2]`` panels including lintels."""
        half_len = self.length / 2.0
        access = self.effective_access(side)
        door_state = self.door_state_for(side)
        openings = access.opening_y_intervals(half_length=half_len)

        breaks = {
            -half_len,
            -half_len + 2.0,
            -half_len + 4.0,
            half_len - 4.0,
            half_len - 2.0,
            half_len,
        }
        for y0, y1 in openings:
            breaks.add(y0)
            breaks.add(y1)
        sorted_breaks = sorted(breaks)

        panels: list[SideEnclosurePanel] = []
        for y_a, y_b in zip(sorted_breaks, sorted_breaks[1:]):
            if y_b <= y_a + 1e-9:
                continue
            y_mid = 0.5 * (y_a + y_b)
            dist_from_back = half_len - abs(y_mid)
            solid_h, total_h = self.side_wall_heights_at(dist_from_back)

            in_opening = any(o0 - 1e-9 <= y_mid <= o1 + 1e-9 for o0, o1 in openings)
            if in_opening:
                door_top = min(access.height, total_h)
                if door_state is DoorState.CLOSED and door_top > 0.0:
                    panels.append(SideEnclosurePanel(y_a, y_b, 0.0, door_top, False))
                if total_h > door_top:
                    panels.append(
                        SideEnclosurePanel(y_a, y_b, door_top, total_h, False)
                    )
                continue

            if solid_h > 0.0:
                panels.append(SideEnclosurePanel(y_a, y_b, 0.0, solid_h, True))
            if total_h > solid_h:
                panels.append(SideEnclosurePanel(y_a, y_b, solid_h, total_h, False))
        return panels

    def side_wall_heights_at(self, dist_from_back: float) -> tuple[float, float]:
        """Returns ``(solid_height_m, total_height_m)`` at distance from back wall.

        Args:
            dist_from_back: Distance in meters measured inward from the nearest
                back wall (``0.0`` at the corner to ``length / 2`` at the net).

        Returns:
            Tuple ``(solid_height_m, total_height_m)`` where ``solid_height_m``
            is the top of the solid wall/glass panel (``0.0`` in pure mesh
            zones) and ``total_height_m`` is the overall enclosure height.
        """
        d = max(0.0, float(dist_from_back))
        back_h = self.dimensions.back_wall_height
        is_v2 = self.effective_enclosure_variant is EnclosureVariant.V2
        central_total_h = (
            max(back_h, self.dimensions.side_wall_height)
            if is_v2
            else min(back_h, self.dimensions.side_wall_height)
        )
        total_h = back_h if d <= 2.0 else central_total_h

        solid_cap = min(3.0, back_h)
        if self.effective_side_wall_profile is SideWallProfile.STEPPED:
            if d <= 2.0:
                solid_h = solid_cap
            elif d <= 4.0:
                solid_h = min(2.0, solid_cap)
            else:
                solid_h = 0.0
        else:
            solid_h = solid_cap if d <= 4.0 else 0.0

        solid_h = min(solid_h, total_h)
        return solid_h, total_h

    def side_enclosure_segments(
        self,
        doorway_half_width: float = 1.0,
    ) -> list[SideEnclosureSegment]:
        """Returns the half-side enclosure segments from back wall toward the net.

        Args:
            doorway_half_width: Half-width of the central net-side access
                opening in meters (defaults to ``1.0`` m, i.e., a ``2.0`` m
                central doorway). Pass ``0.0`` for a continuous side mesh.
        """
        half_len = self.length / 2.0
        mesh_end = max(0.0, half_len - max(0.0, float(doorway_half_width)))
        breaks = sorted({0.0, min(2.0, mesh_end), min(4.0, mesh_end), mesh_end})
        segments: list[SideEnclosureSegment] = []
        for start, end in zip(breaks, breaks[1:]):
            if end <= start + 1e-9:
                continue
            mid = 0.5 * (start + end)
            solid_h, total_h = self.side_wall_heights_at(mid)
            segments.append(
                SideEnclosureSegment(
                    y_start_from_back=start,
                    y_end_from_back=end,
                    solid_height=solid_h,
                    total_height=total_h,
                )
            )
        return segments

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
            A dictionary mapping each `CourtLandmark` name to its (X, Y) position.
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
            A dictionary mapping each `CourtLandmark` name to its (X, Y, Z) position.
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
            name: A `CourtLandmark` value string (e.g., `"center"`).
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
            "side_wall_profile": (
                self.side_wall_profile.value
                if self.side_wall_profile is not None
                else None
            ),
            "orientation": (
                self.orientation.value if self.orientation is not None else None
            ),
            "turf_color": (
                self.turf_color.value
                if isinstance(self.turf_color, CourtSurfaceColor)
                else self.turf_color
            ),
            "setting": self.setting.value if self.setting is not None else None,
            "door_left": self.door_left.value if self.door_left is not None else None,
            "door_right": (
                self.door_right.value if self.door_right is not None else None
            ),
            "access_left": (
                self.access_left.to_dict() if self.access_left is not None else None
            ),
            "access_right": (
                self.access_right.to_dict() if self.access_right is not None else None
            ),
            "safety_zone_left": (
                self.safety_zone_left.to_dict()
                if self.safety_zone_left is not None
                else None
            ),
            "safety_zone_right": (
                self.safety_zone_right.to_dict()
                if self.safety_zone_right is not None
                else None
            ),
            "ceiling_height": self.ceiling_height,
            "location": self.location.to_dict() if self.location is not None else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Court":
        """Reconstructs a `Court` instance from a dictionary."""
        dims_data = data.get("dimensions")
        dims = (
            CourtDimensions.from_dict(dims_data)
            if isinstance(dims_data, dict)
            else CourtDimensions.fip_standard()
        )
        loc_data = data.get("location")
        loc = CourtLocation.from_dict(loc_data) if isinstance(loc_data, dict) else None
        acc_left_data = data.get("access_left")
        acc_right_data = data.get("access_right")
        sz_left_data = data.get("safety_zone_left")
        sz_right_data = data.get("safety_zone_right")
        ceil_raw = data.get("ceiling_height")
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
            side_wall_profile=(
                SideWallProfile(data["side_wall_profile"])
                if data.get("side_wall_profile") is not None
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
            access_left=(
                SideAccess.from_dict(acc_left_data)
                if isinstance(acc_left_data, dict)
                else None
            ),
            access_right=(
                SideAccess.from_dict(acc_right_data)
                if isinstance(acc_right_data, dict)
                else None
            ),
            safety_zone_left=(
                SafetyZone.from_dict(sz_left_data)
                if isinstance(sz_left_data, dict)
                else None
            ),
            safety_zone_right=(
                SafetyZone.from_dict(sz_right_data)
                if isinstance(sz_right_data, dict)
                else None
            ),
            ceiling_height=float(ceil_raw) if ceil_raw is not None else None,
            location=loc,
        )
