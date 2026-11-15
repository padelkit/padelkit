import pytest

from padelkit.court import (
    CoordinateSystem,
    Court,
    CourtDimensions,
    CourtLandmark,
    CourtLocation,
    CourtSetting,
    CourtSurfaceColor,
    DoorState,
    EnclosureType,
    EnclosureVariant,
    SafetyZone,
    SideAccess,
    SideEnclosurePanel,
    SideWallProfile,
)
from padelkit.court.enums import CourtOrientation

# ---------------------------------------------------------------------------
# CourtDimensions
# ---------------------------------------------------------------------------


def test_fip_standard_dimensions():
    court = Court.fip_standard()
    assert court.length == 20.0
    assert court.width == 10.0


def test_fip_standard_wall_heights():
    dims = CourtDimensions.fip_standard()
    assert dims.back_wall_height == 4.0, "Back wall must be 4 m (FIP)"
    assert dims.side_wall_height == 3.0, "Side wall defaults to 3 m (Variant 1)"


# ---------------------------------------------------------------------------
# Court — optional fields
# ---------------------------------------------------------------------------


def test_padel_court_optional_fields_default_to_none():
    court = Court.fip_standard()
    assert court.enclosure_type is None
    assert court.enclosure_variant is None
    assert court.orientation is None
    assert court.turf_color is None
    assert court.door_left is None
    assert court.door_right is None
    assert court.location is None
    assert court.setting is None


def test_padel_court_with_all_optional_fields():
    court = Court(
        dimensions=CourtDimensions.fip_standard(),
        enclosure_type=EnclosureType.GLASS,
        enclosure_variant=EnclosureVariant.V1,
        orientation=CourtOrientation.NORTH_SOUTH,
        turf_color="blue",
        door_left=DoorState.OPEN,
        door_right=DoorState.CLOSED,
        setting=CourtSetting.OUTDOOR,
        location=CourtLocation(
            club="Padel Club Madrid",
            city="Madrid",
            country="Spain",
            latitude=40.4168,
            longitude=-3.7038,
        ),
    )
    assert court.enclosure_type is EnclosureType.GLASS
    assert court.enclosure_variant is EnclosureVariant.V1
    assert court.door_left is DoorState.OPEN
    assert court.door_right is DoorState.CLOSED
    assert court.setting is CourtSetting.OUTDOOR
    assert court.location.city == "Madrid"
    assert court.location.latitude == pytest.approx(40.4168)


# ---------------------------------------------------------------------------
# landmarks_2d — CENTERED system (default)
# ---------------------------------------------------------------------------


def test_landmarks_2d_centered_corners():
    court = Court.fip_standard()
    lm = court.landmarks_2d()

    assert lm[CourtLandmark.FLOOR_NEAR_LEFT.value] == (-5.0, -10.0)
    assert lm[CourtLandmark.FLOOR_NEAR_RIGHT.value] == (5.0, -10.0)
    assert lm[CourtLandmark.FLOOR_FAR_LEFT.value] == (-5.0, 10.0)
    assert lm[CourtLandmark.FLOOR_FAR_RIGHT.value] == (5.0, 10.0)


def test_landmarks_2d_centered_net():
    court = Court.fip_standard()
    lm = court.landmarks_2d()

    assert lm[CourtLandmark.CENTER.value] == (0.0, 0.0)
    assert lm[CourtLandmark.NET_LEFT.value] == (-5.0, 0.0)
    assert lm[CourtLandmark.NET_RIGHT.value] == (5.0, 0.0)


def test_landmarks_2d_centered_service_lines():
    court = Court.fip_standard()
    lm = court.landmarks_2d()

    # service_line_distance_from_back = 3.0  → svc = 10.0 - 3.0 = 7.0
    assert lm[CourtLandmark.SERVICE_NEAR_CENTER.value] == pytest.approx((0.0, -7.0))
    assert lm[CourtLandmark.SERVICE_FAR_CENTER.value] == pytest.approx((0.0, 7.0))


def test_landmarks_2d_has_all_13_floor_points():
    court = Court.fip_standard()
    lm = court.landmarks_2d()
    assert len(lm) == 13


# ---------------------------------------------------------------------------
# landmarks_2d — CORNER_BASED system
# ---------------------------------------------------------------------------


def test_landmarks_2d_corner_based_origin():
    court = Court.fip_standard()
    lm = court.landmarks_2d(coordinate_system=CoordinateSystem.CORNER_BASED)

    assert lm[CourtLandmark.FLOOR_NEAR_LEFT.value] == pytest.approx((0.0, 0.0))
    assert lm[CourtLandmark.FLOOR_NEAR_RIGHT.value] == pytest.approx((10.0, 0.0))
    assert lm[CourtLandmark.FLOOR_FAR_LEFT.value] == pytest.approx((0.0, 20.0))
    assert lm[CourtLandmark.FLOOR_FAR_RIGHT.value] == pytest.approx((10.0, 20.0))


def test_landmarks_2d_corner_based_center():
    court = Court.fip_standard()
    lm = court.landmarks_2d(coordinate_system=CoordinateSystem.CORNER_BASED)

    assert lm[CourtLandmark.CENTER.value] == pytest.approx((5.0, 10.0))


# ---------------------------------------------------------------------------
# landmarks_3d
# ---------------------------------------------------------------------------


def test_landmarks_3d_has_all_17_points():
    court = Court.fip_standard()
    lm = court.landmarks_3d()
    assert len(lm) == 17


def test_landmarks_3d_floor_points_z_zero():
    court = Court.fip_standard()
    lm = court.landmarks_3d()

    floor_keys = [lm_name for lm_name in lm if not lm_name.startswith("wall")]
    for key in floor_keys:
        assert lm[key][2] == 0.0, f"Floor landmark {key} must have Z=0"


def test_landmarks_3d_wall_points_z_equals_back_wall_height():
    court = Court.fip_standard()
    lm = court.landmarks_3d()
    wall_height = court.dimensions.back_wall_height  # 4.0

    wall_keys = [
        CourtLandmark.WALL_TOP_NEAR_LEFT.value,
        CourtLandmark.WALL_TOP_NEAR_RIGHT.value,
        CourtLandmark.WALL_TOP_FAR_LEFT.value,
        CourtLandmark.WALL_TOP_FAR_RIGHT.value,
    ]
    for key in wall_keys:
        assert lm[key][2] == pytest.approx(wall_height), (
            f"Wall landmark {key} must have Z={wall_height}"
        )


def test_landmarks_3d_corner_based_near_left_wall_top():
    court = Court.fip_standard()
    lm = court.landmarks_3d(coordinate_system=CoordinateSystem.CORNER_BASED)

    x, y, z = lm[CourtLandmark.WALL_TOP_NEAR_LEFT.value]
    assert x == pytest.approx(0.0)
    assert y == pytest.approx(0.0)
    assert z == pytest.approx(4.0)


# ---------------------------------------------------------------------------
# point()
# ---------------------------------------------------------------------------


def test_point_retrieval_centered():
    court = Court.fip_standard()
    assert court.point("center") == (0.0, 0.0)
    assert court.point(CourtLandmark.FLOOR_NEAR_LEFT.value) == (-5.0, -10.0)


def test_point_retrieval_corner_based():
    court = Court.fip_standard()
    result = court.point("center", CoordinateSystem.CORNER_BASED)
    assert result == pytest.approx((5.0, 10.0))


def test_invalid_point():
    court = Court.fip_standard()
    with pytest.raises(ValueError):
        court.point("invalid_landmark")


# ---------------------------------------------------------------------------
# Enclosure Variants & SideWallProfile
# ---------------------------------------------------------------------------


def test_court_dimensions_variant_2_helpers():
    dims_v2 = CourtDimensions.fip_standard(variant=EnclosureVariant.V2)
    assert dims_v2.back_wall_height == 4.0
    assert dims_v2.side_wall_height == 4.0
    assert CourtDimensions.fip_variant_2() == dims_v2


def test_side_wall_profile_defaults_and_overrides():
    assert Court.fip_standard().side_wall_profile is None
    assert Court.fip_standard().effective_side_wall_profile is SideWallProfile.UNIFORM

    wall_court = Court(enclosure_type=EnclosureType.WALL)
    assert wall_court.effective_side_wall_profile is SideWallProfile.STEPPED

    stepped_glass = Court(
        enclosure_type=EnclosureType.GLASS,
        enclosure_variant=EnclosureVariant.V1,
        side_wall_profile=SideWallProfile.STEPPED,
    )
    assert stepped_glass.effective_side_wall_profile is SideWallProfile.STEPPED


@pytest.mark.parametrize(
    ("variant", "profile", "expected_at_1m", "expected_at_3m", "expected_at_6m"),
    [
        (
            EnclosureVariant.V1,
            SideWallProfile.STEPPED,
            (3.0, 4.0),
            (2.0, 3.0),
            (0.0, 3.0),
        ),
        (
            EnclosureVariant.V2,
            SideWallProfile.STEPPED,
            (3.0, 4.0),
            (2.0, 4.0),
            (0.0, 4.0),
        ),
        (
            EnclosureVariant.V1,
            SideWallProfile.UNIFORM,
            (3.0, 4.0),
            (3.0, 3.0),
            (0.0, 3.0),
        ),
        (
            EnclosureVariant.V2,
            SideWallProfile.UNIFORM,
            (3.0, 4.0),
            (3.0, 4.0),
            (0.0, 4.0),
        ),
    ],
)
def test_side_wall_heights_across_all_four_fip_variants(
    variant,
    profile,
    expected_at_1m,
    expected_at_3m,
    expected_at_6m,
):
    court = Court(
        dimensions=CourtDimensions.fip_standard(variant=variant),
        enclosure_type=EnclosureType.GLASS,
        enclosure_variant=variant,
        side_wall_profile=profile,
    )
    assert court.side_wall_heights_at(1.0) == expected_at_1m
    assert court.side_wall_heights_at(3.0) == expected_at_3m
    assert court.side_wall_heights_at(6.0) == expected_at_6m

    segs = court.side_enclosure_segments(doorway_half_width=1.0)
    assert [(s.y_start_from_back, s.y_end_from_back) for s in segs] == [
        (0.0, 2.0),
        (2.0, 4.0),
        (4.0, 9.0),
    ]
    assert segs[0].mesh_height == pytest.approx(1.0)
    assert segs[1].solid_height == pytest.approx(expected_at_3m[0])
    assert segs[1].total_height == pytest.approx(expected_at_3m[1])


def test_court_dict_round_trip_with_side_wall_profile_and_legacy_payload():
    court = Court(
        dimensions=CourtDimensions.fip_variant_2(),
        enclosure_type=EnclosureType.GLASS,
        enclosure_variant=EnclosureVariant.V2,
        side_wall_profile=SideWallProfile.STEPPED,
    )
    payload = court.to_dict()
    assert payload["side_wall_profile"] == "stepped"
    assert Court.from_dict(payload) == court

    # Legacy payloads omitting side_wall_profile deserialize with None
    legacy = dict(payload)
    legacy.pop("side_wall_profile")
    restored_legacy = Court.from_dict(legacy)
    assert restored_legacy.side_wall_profile is None


def test_side_access_presets_and_validation():
    single = SideAccess.fip_single_access()
    assert single.count == 1
    assert single.width == pytest.approx(2.0)
    assert single.height == pytest.approx(2.2)
    assert single.opening_y_intervals() == ((-1.0, 1.0),)
    assert single.is_fip_compliant() is True

    dual = SideAccess.fip_dual_access()
    assert dual.count == 2
    assert dual.opening_y_intervals() == (
        pytest.approx((-1.08, -0.08)),
        pytest.approx((0.08, 1.08)),
    )
    assert dual.is_fip_compliant() is True

    none_acc = SideAccess.no_access()
    assert none_acc.count == 0
    assert none_acc.opening_y_intervals() == ()
    assert none_acc.is_fip_compliant() is True

    # Non-FIP dimensions are permitted for custom clubs, flagged by is_fip_compliant()
    narrow = SideAccess(count=1, width=0.9, height=2.2)
    assert narrow.is_fip_compliant() is False
    oversize_dual = SideAccess(count=2, width=1.2, height=2.2)
    assert oversize_dual.is_fip_compliant() is False

    with pytest.raises(ValueError):
        SideAccess(count=3)
    with pytest.raises(ValueError):
        SideAccess(count=1, width=0.0)
    with pytest.raises(ValueError):
        SideAccess(count=1, height=0.0)


def test_court_doorways_panels_and_serialization():
    std = Court.fip_standard()
    assert std.effective_access_left == SideAccess.fip_single_access()
    assert std.is_doorway_opening_at("left", 0.0, 1.5, radius=0.033) is True
    assert std.is_doorway_opening_at("left", 0.0, 2.5, radius=0.033) is False
    assert std.is_doorway_opening_at("left", 2.0, 1.0, radius=0.033) is False
    assert std.has_fip_compliant_access() is True
    assert std.has_fip_compliant_access(out_of_court_play=True) is False

    # Open default single access produces overhead mesh lintel 2.2..3.0m over [-1, 1]
    panels_open = std.side_enclosure_panels("left")
    lintel = [
        p
        for p in panels_open
        if abs(p.y_start + 1.0) < 1e-6 and abs(p.y_end - 1.0) < 1e-6
    ]
    assert lintel == [SideEnclosurePanel(-1.0, 1.0, 2.2, 3.0, False)]

    # Closed door adds bottom gate panel (0..2.2m) in addition to lintel
    closed_court = Court(door_left=DoorState.CLOSED)
    assert closed_court.is_doorway_opening_at("left", 0.0, 1.5, radius=0.033) is False
    closed_center = [
        p
        for p in closed_court.side_enclosure_panels("left")
        if abs(p.y_start + 1.0) < 1e-6 and abs(p.y_end - 1.0) < 1e-6
    ]
    assert closed_center == [
        SideEnclosurePanel(-1.0, 1.0, 0.0, 2.2, False),
        SideEnclosurePanel(-1.0, 1.0, 2.2, 3.0, False),
    ]

    # Asymmetric court: no left door + dual right door for out-of-court check
    asym = Court(
        access_left=SideAccess.no_access(),
        access_right=SideAccess.fip_dual_access(),
    )
    assert asym.is_doorway_opening_at("left", 0.0, 1.2) is False
    assert asym.is_doorway_opening_at("right", 0.0, 1.2) is False  # center pillar
    assert asym.is_doorway_opening_at("right", 0.5, 1.2) is True
    assert asym.has_fip_compliant_access() is True
    assert asym.has_fip_compliant_access(out_of_court_play=True) is False

    dual_both = Court(
        access_left=SideAccess.fip_dual_access(),
        access_right=SideAccess.fip_dual_access(),
    )
    assert dual_both.has_fip_compliant_access(out_of_court_play=True) is True

    # Serialization round-trip + legacy backward compatibility
    payload = asym.to_dict()
    assert Court.from_dict(payload) == asym
    legacy = dict(payload)
    legacy.pop("access_left")
    legacy.pop("access_right")
    restored_legacy = Court.from_dict(legacy)
    assert restored_legacy.access_left is None
    assert restored_legacy.access_right is None


def test_court_dimensions_new_fip_fields():
    dims_default = CourtDimensions.fip_standard()
    assert dims_default.line_width == pytest.approx(0.05)
    assert dims_default.service_line_extension == pytest.approx(0.20)
    assert dims_default.net_post_height == pytest.approx(1.05)
    assert dims_default.free_height == pytest.approx(6.0)

    dims_new = CourtDimensions.fip_standard(new_construction=True)
    assert dims_new.free_height == pytest.approx(8.0)

    dims_v2_new = CourtDimensions.fip_variant_2(new_construction=True)
    assert dims_v2_new.free_height == pytest.approx(8.0)
    assert dims_v2_new.side_wall_height == pytest.approx(4.0)

    assert CourtDimensions.from_dict(dims_new.to_dict()) == dims_new
    # Backward compatibility when loading old dict without new keys
    legacy_dims = {
        "length": 20.0,
        "width": 10.0,
        "service_line_distance_from_back": 3.0,
        "net_height_center": 0.88,
        "net_height_posts": 0.92,
        "back_wall_height": 3.0,
        "side_wall_height": 3.0,
    }
    restored_legacy_dims = CourtDimensions.from_dict(legacy_dims)
    assert restored_legacy_dims.free_height == pytest.approx(6.0)
    assert restored_legacy_dims.line_width == pytest.approx(0.05)


def test_turf_colors_safety_zone_ceiling_and_fip_compliance():
    # Surface colors: enum normalization + custom CSS hex strings
    court_blue = Court()
    assert court_blue.effective_turf_color == "blue"

    court_black_outdoor = Court(
        setting=CourtSetting.OUTDOOR, turf_color=CourtSurfaceColor.BLACK
    )
    assert court_black_outdoor.effective_turf_color == "black"
    assert not court_black_outdoor.is_fip_compliant()
    assert any(
        "black" in issue.lower()
        for issue in court_black_outdoor.fip_compliance_issues()
    )

    court_black_indoor = Court(
        setting=CourtSetting.INDOOR,
        turf_color=CourtSurfaceColor.BLACK,
        ceiling_height=6.5,
    )
    assert court_black_indoor.effective_turf_color == "black"
    assert court_black_indoor.is_fip_compliant()
    assert Court(
        setting=CourtSetting.INDOOR, turf_color="BLACK", ceiling_height=6.5
    ).is_fip_compliant()

    court_low_ceiling = Court(setting=CourtSetting.INDOOR, ceiling_height=5.5)
    assert not court_low_ceiling.is_fip_compliant()
    assert any("ceiling_height" in i for i in court_low_ceiling.fip_compliance_issues())

    assert Court(turf_color=CourtSurfaceColor.GREEN).is_fip_compliant()
    assert Court(turf_color=CourtSurfaceColor.TERRACOTTA).is_fip_compliant()

    court_custom_hex = Court(turf_color="#2563EB")
    assert court_custom_hex.effective_turf_color == "#2563EB"
    assert not court_custom_hex.is_fip_compliant()

    # SafetyZone & Rule 16 out-of-court play
    sz = SafetyZone.fip_standard()
    assert sz.is_fip_compliant()
    assert not SafetyZone.none().is_fip_compliant()

    default_court = Court()
    assert not default_court.is_out_of_court_play_allowed()
    assert default_court.is_fip_compliant()

    ooc_court = Court(
        access_left=SideAccess.fip_dual_access(),
        access_right=SideAccess.fip_dual_access(),
        safety_zone_left=SafetyZone.fip_standard(),
        safety_zone_right=SafetyZone.fip_standard(),
    )
    assert ooc_court.is_out_of_court_play_allowed()
    assert ooc_court.is_fip_compliant(out_of_court_play=True)

    # One-sided closed court is FIP compliant for normal play, not for out-of-court
    club_court = Court(access_right=SideAccess.no_access())
    assert club_court.is_fip_compliant()
    assert not club_court.is_fip_compliant(out_of_court_play=True)

    # Zero accesses on both sides is non-FIP compliant
    sealed_court = Court(
        access_left=SideAccess.no_access(),
        access_right=SideAccess.no_access(),
    )
    assert not sealed_court.is_fip_compliant()

    # Full serialization round-trip
    restored = Court.from_dict(ooc_court.to_dict())
    assert restored == ooc_court
    restored_black = Court.from_dict(court_black_indoor.to_dict())
    assert restored_black.ceiling_height == pytest.approx(6.5)
    assert restored_black.effective_turf_color == "black"
