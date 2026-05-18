import pytest

from padelkit.court import (
    CoordinateSystem,
    CourtDimensions,
    CourtLocation,
    CourtSetting,
    DoorState,
    EnclosureType,
    EnclosureVariant,
    CourtLandmark,
    Court,
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
