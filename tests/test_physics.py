from pathlib import Path

import numpy as np
import pytest

from padelkit import (
    BallColor,
    BallPhysicsEngine,
    BallProperties,
    BallState,
    ContactRegime,
    CoordinateSystem,
    Court,
    CourtDimensions,
    DoorState,
    EnclosureType,
    EnclosureVariant,
    EnvironmentConditions,
    SideAccess,
    SideWallProfile,
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


def test_side_wall_profile_and_variant_collision_surfaces():
    # Impact right wall (x = 5.0) at dist_from_back = 3.0m (y = 7.0) and z ≈ 2.5m
    shot_2_to_4m = BallState(position=(4.2, 7.0, 2.5), velocity=(12.0, 0.0, 0.5))

    stepped_glass_engine = BallPhysicsEngine(
        court=Court(
            enclosure_type=EnclosureType.GLASS,
            enclosure_variant=EnclosureVariant.V1,
            side_wall_profile=SideWallProfile.STEPPED,
        )
    )
    traj_stepped = stepped_glass_engine.simulate(shot_2_to_4m, duration_s=0.15)
    assert [b.surface for b in traj_stepped.bounces] == [SurfaceType.SIDE_FENCE]

    uniform_glass_engine = BallPhysicsEngine(
        court=Court(
            enclosure_type=EnclosureType.GLASS,
            enclosure_variant=EnclosureVariant.V1,
            side_wall_profile=SideWallProfile.UNIFORM,
        )
    )
    traj_uniform = uniform_glass_engine.simulate(shot_2_to_4m, duration_s=0.15)
    assert [b.surface for b in traj_uniform.bounces] == [SurfaceType.SIDE_GLASS]

    # Impact central side zone (y = 4.0, dist_from_back = 6.0m) at z ≈ 3.5m:
    # V1 exits above 3.0m mesh, V2 hits 4.0m fence
    shot_high_center = BallState(position=(4.2, 4.0, 3.5), velocity=(12.0, 0.0, 0.4))
    v1_engine = BallPhysicsEngine(
        court=Court(
            enclosure_type=EnclosureType.GLASS,
            enclosure_variant=EnclosureVariant.V1,
        )
    )
    v2_engine = BallPhysicsEngine(
        court=Court(
            enclosure_type=EnclosureType.GLASS,
            enclosure_variant=EnclosureVariant.V2,
        )
    )
    assert v1_engine.simulate(shot_high_center, duration_s=0.15).bounces == []
    assert [
        b.surface for b in v2_engine.simulate(shot_high_center, duration_s=0.15).bounces
    ] == [SurfaceType.SIDE_FENCE]


def test_doorway_passthrough_lintel_and_closed_door():
    # 1. Open single doorway (2.0 x 2.2m): ball at y=0, z=1.2 exits cleanly outside
    open_engine = BallPhysicsEngine(court=Court.fip_standard())
    door_shot = BallState(position=(-4.4, 0.0, 1.2), velocity=(-12.0, 0.0, 1.0))
    traj_open = open_engine.simulate(door_shot, duration_s=0.35)
    assert SurfaceType.SIDE_FENCE not in [b.surface for b in traj_open.bounces]
    assert traj_open.states[-1, 0] < -5.5

    # 2. Above doorway height (z=2.6m > 2.2m): hits overhead metallic mesh lintel
    lintel_shot = BallState(position=(-4.4, 0.0, 2.6), velocity=(-12.0, 0.0, 0.0))
    traj_lintel = open_engine.simulate(lintel_shot, duration_s=0.15)
    assert [b.surface for b in traj_lintel.bounces] == [SurfaceType.SIDE_FENCE]
    assert traj_lintel.states[-1, 0] > -5.0

    # 3. Closed doorway (DoorState.CLOSED) or no_access() rebounds off fence
    closed_engine = BallPhysicsEngine(court=Court(door_left=DoorState.CLOSED))
    traj_closed = closed_engine.simulate(door_shot, duration_s=0.15)
    assert [b.surface for b in traj_closed.bounces] == [SurfaceType.SIDE_FENCE]

    no_door_engine = BallPhysicsEngine(court=Court(access_left=SideAccess.no_access()))
    traj_no_door = no_door_engine.simulate(door_shot, duration_s=0.15)
    assert [b.surface for b in traj_no_door.bounces] == [SurfaceType.SIDE_FENCE]

    # 4. Dual access: center pillar at y=0.0 rebounds, opening at y=0.6 exits
    dual_engine = BallPhysicsEngine(
        court=Court(access_left=SideAccess.fip_dual_access(center_pillar_width=0.20))
    )
    pillar_shot = BallState(position=(-4.4, 0.0, 1.2), velocity=(-12.0, 0.0, 0.5))
    side_open_shot = BallState(position=(-4.4, 0.6, 1.2), velocity=(-12.0, 0.0, 0.5))
    assert [
        b.surface for b in dual_engine.simulate(pillar_shot, duration_s=0.15).bounces
    ] == [SurfaceType.SIDE_FENCE]
    traj_dual_exit = dual_engine.simulate(side_open_shot, duration_s=0.25)
    assert SurfaceType.SIDE_FENCE not in [b.surface for b in traj_dual_exit.bounces]
    assert traj_dual_exit.states[-1, 0] < -5.5

    # 5. Vectorized simulate_batch respects doorway openings vs overhead lintel
    batch = np.array(
        [
            [-4.4, 0.0, 1.2, -12.0, 0.0, 0.5, 0.0, 0.0, 0.0],
            [-4.4, 0.0, 2.6, -12.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ],
        dtype=np.float64,
    )
    batch_out = open_engine.simulate_batch(batch, num_steps=30, dt=1.0 / 240.0)
    assert batch_out[0, -1, 0] < -5.5
    assert batch_out[1, -1, 0] > -5.0


def test_ball_colors_high_altitude_and_fip_compliance():
    # Official and tournament color normalization
    magenta_ball = BallProperties(color=BallColor.MAGENTA)
    assert magenta_ball.effective_color == "magenta"
    assert magenta_ball.is_fip_compliant()
    assert not magenta_ball.is_fip_compliant(strict_colors=True)

    orange_ball = BallProperties(color="orange")
    assert orange_ball.effective_color == "orange"
    assert orange_ball.is_fip_compliant()
    assert not orange_ball.is_fip_compliant(strict_colors=True)

    yellow_ball = BallProperties.fip_standard()
    assert yellow_ball.effective_color == "yellow"
    assert yellow_ball.is_fip_compliant(strict_colors=True)

    # Serialization round-trip + legacy fallback
    assert BallProperties.from_dict(magenta_ball.to_dict()) == magenta_ball
    legacy_payload = yellow_ball.to_dict()
    legacy_payload.pop("color")
    legacy_payload.pop("bounce_restitution_factor")
    legacy_restored = BallProperties.from_dict(legacy_payload)
    assert legacy_restored.color == BallColor.YELLOW
    assert legacy_restored.bounce_restitution_factor == pytest.approx(1.0)

    # High-altitude ball (>500 m) rebounds lower than sea-level FIP standard
    std_engine = BallPhysicsEngine(ball=BallProperties.fip_standard())
    ha_ball = BallProperties.high_altitude()
    assert ha_ball.bounce_restitution_factor == pytest.approx(0.955)
    assert ha_ball.is_fip_compliant()
    ha_engine = BallPhysicsEngine(ball=ha_ball)

    drop = BallState(position=(0.0, -3.0, 2.54), velocity=(0.0, 0.0, 0.0))
    std_traj = std_engine.simulate(drop, duration_s=1.6)
    ha_traj = ha_engine.simulate(drop, duration_s=1.6)
    assert float(np.max(ha_traj.states[len(ha_traj) // 2 :, 2])) < float(
        np.max(std_traj.states[len(std_traj) // 2 :, 2])
    )


def test_ceiling_collision_single_and_batch():
    # Indoor court with 6.5m ceiling vs unobstructed court (ceiling_height=None)
    high_lob = BallState(position=(0.0, -4.0, 5.8), velocity=(0.0, 3.0, 10.0))

    open_sky_engine = BallPhysicsEngine(court=Court(ceiling_height=None))
    open_traj = open_sky_engine.simulate(high_lob, duration_s=0.4)
    assert SurfaceType.CEILING not in [b.surface for b in open_traj.bounces]
    assert float(np.max(open_traj.states[:, 2])) > 7.5

    ceiling_engine = BallPhysicsEngine(court=Court(ceiling_height=6.5))
    ceil_traj = ceiling_engine.simulate(high_lob, duration_s=0.4)
    assert SurfaceType.CEILING in [b.surface for b in ceil_traj.bounces]
    assert float(np.max(ceil_traj.states[:, 2])) <= 6.5 + 1e-6

    # Batch simulation honors ceiling_height too
    batch = np.array(
        [[0.0, -4.0, 5.8, 0.0, 3.0, 10.0, 0.0, 0.0, 0.0]], dtype=np.float64
    )
    batch_ceil = ceiling_engine.simulate_batch(batch, num_steps=96, dt=1.0 / 240.0)
    assert float(np.max(batch_ceil[0, :, 2])) <= 6.5 + 1e-6
