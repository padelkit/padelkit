from pathlib import Path

import numpy as np
import pytest

from padelkit import (
    BallPhysicsEngine,
    BallProperties,
    BallState,
    ContactRegime,
    CoordinateSystem,
    Court,
    CourtDimensions,
    EnclosureType,
    EnvironmentConditions,
    SurfaceType,
)


def test_ball_properties_and_presets():
    ball = BallProperties.fip_standard()
    assert ball.mass == pytest.approx(0.058)
    assert ball.radius == pytest.approx(0.033)
    assert ball.drag_coefficient == pytest.approx(0.50)
    assert ball.inertia_ratio == pytest.approx(0.55, rel=0.05)

    worn = BallProperties.worn(fuzz_factor=0.8)
    assert worn.drag_coefficient > ball.drag_coefficient

    wet = BallProperties.wet(absorbed_water_g=2.5)
    assert wet.mass == pytest.approx(0.0605)

    with pytest.raises(ValueError):
        BallProperties(mass=-0.01)
    with pytest.raises(ValueError):
        BallProperties(fuzz_factor=1.5)


def test_environment_conditions_atmosphere():
    sea_level = EnvironmentConditions.from_atmosphere(
        altitude_m=0.0,
        temperature_c=20.0,
        relative_humidity=0.5,
    )
    madrid = EnvironmentConditions.from_atmosphere(
        altitude_m=650.0,
        temperature_c=25.0,
        relative_humidity=0.3,
    )
    # Air density in Madrid at 650m & 25C must be lower than sea level at 20C
    assert madrid.air_density < sea_level.air_density
    assert 1.05 < madrid.air_density < 1.15


def test_magnus_effect_topspin_vs_backspin():
    engine = BallPhysicsEngine()

    # Shot travelling along +Y at 20 m/s
    flat = BallState.from_shot(
        position=(0.0, -5.0, 1.5),
        velocity=(0.0, 20.0, 2.0),
        topspin_rpm=0.0,
    )
    topspin = BallState.from_shot(
        position=(0.0, -5.0, 1.5),
        velocity=(0.0, 20.0, 2.0),
        topspin_rpm=2500.0,
    )
    backspin = BallState.from_shot(
        position=(0.0, -5.0, 1.5),
        velocity=(0.0, 20.0, 2.0),
        topspin_rpm=-2500.0,
    )

    acc_flat, _ = engine.compute_acceleration(flat)
    acc_top, _ = engine.compute_acceleration(topspin)
    acc_back, _ = engine.compute_acceleration(backspin)

    # Topspin pushes the ball downwards (more negative az than flat)
    assert acc_top[2] < acc_flat[2]
    # Backspin / slice lifts the ball upwards (less negative az than flat)
    assert acc_back[2] > acc_flat[2]


def test_sliding_vs_rolling_contact_regimes():
    # Glass wall (low friction mu=0.25) vs Concrete wall (high friction mu=0.70)
    engine = BallPhysicsEngine()

    # Steep impact with small tangential slip -> Rolling on rough surface
    steep_state = BallState(
        position=(0.0, 0.0, 0.033),
        velocity=(1.0, 0.0, -12.0),
        angular_velocity=(0.0, 0.0, 0.0),
    )
    _, regime_roll = engine.resolve_collision(
        steep_state.vector_9d,
        normal=np.array([0.0, 0.0, 1.0]),
        cor=0.75,
        friction=0.70,
    )
    assert regime_roll is ContactRegime.ROLLING

    # Fast grazing slice impact on low-friction glass/floor -> Sliding
    grazing_slice = BallState.from_shot(
        position=(0.0, 0.0, 0.033),
        velocity=(0.0, 18.0, -2.5),
        topspin_rpm=-2800.0,
    )
    _, regime_slide = engine.resolve_collision(
        grazing_slice.vector_9d,
        normal=np.array([0.0, 0.0, 1.0]),
        cor=0.85,
        friction=0.22,
    )
    assert regime_slide is ContactRegime.SLIDING


def test_trajectory_simulation_floor_and_back_glass_bounce(tmp_path: Path):
    court = Court(
        dimensions=CourtDimensions.fip_standard(),
        enclosure_type=EnclosureType.GLASS,
    )
    engine = BallPhysicsEngine(court=court)

    # Deep drive from near side (y = -6.0) towards far side (y > 0)
    shot = BallState.from_shot(
        position=(0.0, -6.0, 1.2),
        velocity=(0.5, 19.5, 3.2),
        topspin_rpm=-1500.0,
    )
    traj = engine.simulate(shot, duration_s=1.8, dt=1.0 / 240.0)

    assert len(traj) > 100
    assert traj.max_height > 1.2
    surfaces_hit = [b.surface for b in traj.bounces]
    assert SurfaceType.FLOOR in surfaces_hit
    assert SurfaceType.BACK_GLASS in surfaces_hit

    # Test interpolation and exports
    mid_state = traj.state_at(0.5)
    assert isinstance(mid_state, BallState)

    csv_path = traj.to_csv(tmp_path / "shot_traj.csv")
    assert csv_path.exists()

    timeline = traj.to_timeline(court=court, fps=60.0)
    assert len(timeline) > 50


def test_net_collision_detection():
    engine = BallPhysicsEngine()
    # Low shot into the net at y = 0.0, z = 0.45m (< 0.88m net height)
    into_net = BallState(
        position=(0.0, -2.0, 0.5),
        velocity=(0.0, 15.0, 0.0),
    )
    traj = engine.simulate(into_net, duration_s=0.3, dt=1.0 / 240.0)
    surfaces_hit = [b.surface for b in traj.bounces]
    assert SurfaceType.NET in surfaces_hit


def test_vectorized_batch_simulation():
    engine = BallPhysicsEngine(coordinate_system=CoordinateSystem.CORNER_BASED)
    batch_init = np.zeros((32, 9), dtype=np.float64)
    batch_init[:, 0] = 5.0
    batch_init[:, 1] = 3.0
    batch_init[:, 2] = 1.2
    batch_init[:, 4] = np.linspace(12.0, 22.0, 32)
    batch_init[:, 5] = 3.5

    trajs = engine.simulate_batch(batch_init, num_steps=120, dt=1.0 / 120.0)
    assert trajs.shape == (32, 121, 9)
    assert np.all(trajs[:, :, 2] >= engine.ball.radius - 1e-6)
