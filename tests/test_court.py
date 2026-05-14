import pytest

from padelkit.court import PadelCourt


def test_fip_standard_dimensions():
    court = PadelCourt.fip_standard()
    assert court.length == 20.0
    assert court.width == 10.0


def test_landmarks_2d_center_and_corners():
    court = PadelCourt.fip_standard()
    landmarks = court.landmarks_2d()
    
    # Center
    assert landmarks["center"] == (0.0, 0.0)
    
    # Corners
    assert landmarks["bottom_left"] == (-5.0, -10.0)
    assert landmarks["bottom_right"] == (5.0, -10.0)
    assert landmarks["top_left"] == (-5.0, 10.0)
    assert landmarks["top_right"] == (5.0, 10.0)


def test_point_retrieval():
    court = PadelCourt.fip_standard()
    assert court.point("center") == (0.0, 0.0)
    assert court.point("top_left") == (-5.0, 10.0)


def test_invalid_point():
    court = PadelCourt.fip_standard()
    with pytest.raises(ValueError):
        court.point("invalid_landmark")
