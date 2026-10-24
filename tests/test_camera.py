import math

import numpy as np
import pytest

from padelkit import (
    Camera,
    CameraDistortion,
    CameraExtrinsics,
    CameraIntrinsics,
    CameraPreset,
    CoordinateSystem,
    Court,
    CourtLandmark,
    DistortionModel,
)


def test_camera_intrinsics_from_fov():
    intr = CameraIntrinsics.from_fov(
        width_px=1920,
        height_px=1080,
        horizontal_fov_deg=90.0,
    )
    assert intr.width_px == 1920
    assert intr.height_px == 1080
    assert intr.cx == pytest.approx(960.0)
    assert intr.cy == pytest.approx(540.0)
    assert intr.fx == pytest.approx(960.0)
    assert intr.fy == pytest.approx(960.0)
    assert intr.fov_horizontal_deg == pytest.approx(90.0)
    assert intr.aspect_ratio == pytest.approx(16.0 / 9.0)

    k_mat = intr.matrix
    k_inv = intr.inverse_matrix
    assert np.allclose(k_mat @ k_inv, np.eye(3), atol=1e-12)


def test_camera_intrinsics_from_sensor():
    intr = CameraIntrinsics.from_sensor(
        width_px=1920,
        height_px=1080,
        focal_length_mm=18.0,
        sensor_width_mm=36.0,
    )
    assert intr.fx == pytest.approx(960.0)
    assert intr.fy == pytest.approx(960.0)
    assert intr.fov_horizontal_deg == pytest.approx(90.0)


def test_camera_intrinsics_validation():
    with pytest.raises(ValueError):
        CameraIntrinsics(width_px=0, height_px=1080, fx=500, fy=500, cx=0, cy=0)
    with pytest.raises(ValueError):
        CameraIntrinsics(width_px=1920, height_px=1080, fx=-10, fy=500, cx=0, cy=0)
    with pytest.raises(ValueError):
        CameraIntrinsics.from_fov(horizontal_fov_deg=185.0)


def test_camera_distortion_brown_conrady_roundtrip():
    dist = CameraDistortion.brown_conrady(
        k1=-0.18,
        k2=0.04,
        p1=0.001,
        p2=-0.002,
        k3=-0.005,
    )
    assert dist.model is DistortionModel.BROWN_CONRADY
    assert not dist.is_identity

    pts = np.array(
        [
            [0.0, 0.0],
            [0.25, -0.15],
            [-0.4, 0.35],
            [0.12, 0.28],
        ],
        dtype=np.float64,
    )
    distorted = dist.distort_normalized(pts)
    recovered = dist.undistort_normalized(distorted, iterations=15)
    assert np.allclose(pts, recovered, atol=1e-9)


def test_camera_distortion_fisheye_roundtrip():
    dist = CameraDistortion.fisheye(k1=-0.08, k2=0.02, k3=-0.004, k4=0.001)
    assert dist.model is DistortionModel.FISHEYE

    pts = np.array(
        [
            [0.0, 0.0],
            [0.3, -0.2],
            [-0.5, 0.4],
        ],
        dtype=np.float64,
    )
    distorted = dist.distort_normalized(pts)
    recovered = dist.undistort_normalized(distorted, iterations=15)
    assert np.allclose(pts, recovered, atol=1e-9)


def test_camera_extrinsics_look_at_and_zenith():
    extr = CameraExtrinsics.from_look_at(
        position=(0.0, -14.0, 6.0),
        target=(0.0, 0.0, 0.0),
    )
    assert extr.position == (0.0, -14.0, 6.0)
    # Camera is on -Y looking toward origin: right should be +X = (1, 0, 0)
    assert extr.right == pytest.approx((1.0, 0.0, 0.0))
    assert extr.forward[1] > 0.0 and extr.forward[2] < 0.0

    w2c = extr.world_to_camera_matrix
    c2w = extr.camera_to_world_matrix
    assert np.allclose(w2c @ c2w, np.eye(4), atol=1e-12)

    # Overhead zenith camera looking straight down along -Z
    zenith = CameraExtrinsics.from_look_at(
        position=(0.0, 0.0, 14.0),
        target=(0.0, 0.0, 0.0),
    )
    assert zenith.forward == pytest.approx((0.0, 0.0, -1.0))
    assert zenith.up == pytest.approx((0.0, 1.0, 0.0))
    assert zenith.right == pytest.approx((1.0, 0.0, 0.0))


def test_camera_extrinsics_euler_and_from_rt():
    extr = CameraExtrinsics.from_euler(
        position=(1.0, -12.0, 5.0),
        yaw_deg=0.0,
        pitch_deg=-20.0,
        roll_deg=0.0,
    )
    assert extr.forward[0] == pytest.approx(0.0)
    assert extr.forward[1] == pytest.approx(math.cos(math.radians(-20.0)))
    assert extr.forward[2] == pytest.approx(math.sin(math.radians(-20.0)))

    rt_extr = CameraExtrinsics.from_rt(extr.R, extr.t)
    assert rt_extr.position == pytest.approx(extr.position)
    assert np.allclose(rt_extr.R, extr.R)


def test_camera_projection_and_ray_intersection():
    court = Court.fip_standard()
    cam = Camera.broadcast_near(court=court)

    # Target point (0.0, -0.5, 0.5) should project exactly to principal point (cx, cy)
    uv_center = cam.world_to_image((0.0, -0.5, 0.5))
    assert uv_center is not None
    assert uv_center[0] == pytest.approx(cam.intrinsics.cx, abs=1e-6)
    assert uv_center[1] == pytest.approx(cam.intrinsics.cy, abs=1e-6)

    # Point behind the camera should return None
    assert cam.world_to_image((0.0, -25.0, 6.0)) is None

    # Project all 17 court landmarks
    landmarks_2d = cam.project_court_landmarks(court=court)
    assert len(landmarks_2d) == 17
    assert landmarks_2d[CourtLandmark.CENTER.value] is not None

    # Unproject center of net back onto floor plane Z=0
    uv_net = landmarks_2d[CourtLandmark.CENTER.value]
    assert uv_net is not None
    floor_pt = cam.project_pixel_to_plane(uv_net, plane_z=0.0)
    assert floor_pt is not None
    assert floor_pt == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)

    # Corner-based coordinate system consistency
    uv_cb = cam.world_to_image(
        (5.0, 10.0, 0.0),
        coordinate_system=CoordinateSystem.CORNER_BASED,
        court=court,
    )
    assert uv_cb == pytest.approx(uv_net, abs=1e-6)


def test_camera_presets_and_frustum():
    for preset in CameraPreset:
        cam = Camera.from_preset(preset)
        assert cam.name == preset.value
        frustum = cam.frustum_corners_world(near_m=0.5, far_m=20.0)
        assert len(frustum["near"]) == 4
        assert len(frustum["far"]) == 4
        data = cam.to_dict()
        assert data["name"] == preset.value


def test_camera_floor_homography_and_from_landmarks():
    court = Court.fip_standard()
    gt_cam = Camera.broadcast_near(court=court)

    # 1. Verify analytical floor_homography matches world_to_image on Z=0
    h_mat = gt_cam.floor_homography
    h_inv = gt_cam.inverse_floor_homography
    p_floor = np.array([2.5, -4.0, 1.0], dtype=np.float64)
    p_px_hom = h_mat @ p_floor
    u_h, v_h = p_px_hom[0] / p_px_hom[2], p_px_hom[1] / p_px_hom[2]
    uv_proj = gt_cam.world_to_image((2.5, -4.0, 0.0))
    assert uv_proj is not None
    assert (u_h, v_h) == pytest.approx(uv_proj, abs=1e-6)

    p_rec = h_inv @ np.array([u_h, v_h, 1.0])
    assert (p_rec[0] / p_rec[2], p_rec[1] / p_rec[2]) == pytest.approx(
        (2.5, -4.0), abs=1e-6
    )

    # 2. Calibrate Camera.from_landmarks from only the 4 floor corners (unknown focal!)
    all_lm = gt_cam.project_court_landmarks(court=court)
    four_corners = {
        "floor_near_left": all_lm["floor_near_left"],
        "floor_near_right": all_lm["floor_near_right"],
        "floor_far_right": all_lm["floor_far_right"],
        "floor_far_left": all_lm["floor_far_left"],
    }
    cal_cam = Camera.from_landmarks(four_corners, court=court)  # type: ignore[arg-type]
    assert cal_cam.reprojection_error(four_corners, court=court) < 1e-3  # type: ignore[arg-type]
    assert cal_cam.intrinsics.fx == pytest.approx(gt_cam.intrinsics.fx, rel=1e-3)
    assert cal_cam.extrinsics.position == pytest.approx(
        gt_cam.extrinsics.position, abs=1e-2
    )

    # 3. Calibrate with 3D wall corners included + known intrinsics
    eight_pts = {
        **four_corners,
        "service_near_center": all_lm["service_near_center"],
        "service_far_center": all_lm["service_far_center"],
        "wall_top_far_left": all_lm["wall_top_far_left"],
        "wall_top_far_right": all_lm["wall_top_far_right"],
    }
    cal_3d = Camera.from_landmarks(
        eight_pts,  # type: ignore[arg-type]
        court=court,
        intrinsics=gt_cam.intrinsics,
    )
    assert cal_3d.reprojection_error(eight_pts, court=court) < 1e-4  # type: ignore[arg-type]
    assert cal_3d.extrinsics.position == pytest.approx(
        gt_cam.extrinsics.position, abs=1e-4
    )

