from pathlib import Path

from padelkit import (
    Camera,
    Court,
    FrameState,
    MatchTimeline,
    PadelVisualizer,
    PlayerPose,
)


def test_match_timeline_demo_and_csv_roundtrip(tmp_path: Path):
    court = Court.fip_standard()
    timeline = MatchTimeline.demo_rally(court=court, fps=30.0)

    assert len(timeline) > 100
    assert timeline.duration_seconds > 7.0

    csv_file = tmp_path / "rally_replay.csv"
    saved_path = timeline.to_csv(csv_file)
    assert saved_path.exists()

    loaded = MatchTimeline.from_csv(saved_path, court=court)
    assert len(loaded) == len(timeline)
    assert loaded.frames[0].ball_position == timeline.frames[0].ball_position
    assert loaded.frames[-1].event == "point_won_A"
    assert "P1" in loaded.frames[0].players


def test_padel_visualizer_html_and_config(tmp_path: Path):
    court = Court.fip_standard()
    timeline = MatchTimeline(
        frames=[
            FrameState(
                timestamp=0.0,
                ball_position=(0.0, 0.0, 1.0),
                players={
                    "P1": PlayerPose("P1", x=2.0, y=-6.0, yaw_deg=0.0, team="A"),
                    "P2": PlayerPose("P2", x=-2.0, y=-3.0, yaw_deg=0.0, team="A"),
                    "P3": PlayerPose("P3", x=-2.0, y=6.0, yaw_deg=180.0, team="B"),
                    "P4": PlayerPose("P4", x=2.0, y=6.0, yaw_deg=180.0, team="B"),
                },
                score="0-0 | 15-0",
                event="serve",
            )
        ],
        fps=60.0,
        court=court,
    )
    viz = PadelVisualizer(
        court=court,
        cameras=[Camera.broadcast_near(court=court)],
        timeline=timeline,
    )
    viz.add_camera(Camera.overhead_zenith())
    assert len(viz.cameras) == 2

    html_path = viz.export_html(tmp_path / "viewer.html")
    assert html_path.exists()
    content = html_path.read_text(encoding="utf-8")
    assert "PadelKit 3D Studio" in content
    assert "broadcast_near" in content
    assert "overhead_zenith" in content

    jupyter_iframe = viz._repr_html_()
    assert "<iframe" in jupyter_iframe


def test_padel_visualizer_with_animation_library(tmp_path: Path):
    import json

    anim_dir = tmp_path / "animations"
    anim_dir.mkdir(parents=True, exist_ok=True)
    glb_file = anim_dir / "forehand_drive.glb"
    glb_file.write_bytes(b"glTF\x02\x00\x00\x00\x14\x00\x00\x00\x02\x00\x00\x00JSON{}")

    manifest = {
        "schema_version": "1.0.0",
        "armature_convention": "mixamo",
        "animations": [
            {
                "clip_id": "forehand_drive",
                "glb_path": "forehand_drive.glb",
                "padelkit_animation_id": "shot_forehand",
                "shot_category": "FOREHAND",
                "shot_variant": "STANDARD",
                "spin": "FLAT",
                "handedness": "RIGHT",
                "racket_socket_bone": "mixamorig:RightHand",
                "in_place": True,
                "fps": 60.0,
                "total_frames": 48,
                "duration_s": 0.8,
                "contact_frame_relative": 29,
                "contact_swing_phase": 0.617,
            }
        ],
    }
    (anim_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    viz = PadelVisualizer(animation_library_dir=anim_dir)

    # 1. Standalone config embeds Base64 GLB data URI
    standalone_cfg = viz.build_config(live_stream_url=None)
    assert standalone_cfg["animation_library"] is not None
    assert standalone_cfg["animation_library"]["glb_sources"][
        "forehand_drive"
    ].startswith("data:model/gltf-binary;base64,")

    # 2. Server config uses /animations/<filename>.glb route
    server_cfg = viz.build_config(live_stream_url="/events")
    assert (
        server_cfg["animation_library"]["glb_sources"]["forehand_drive"]
        == "/animations/forehand_drive.glb"
    )


def test_domain_entities_to_dict_and_from_dict_roundtrip():
    from datetime import datetime

    from padelkit import (
        BallProperties,
        CourtDimensions,
        CourtLocation,
        CourtOrientation,
        CourtSetting,
        DoorState,
        EnclosureType,
        EnclosureVariant,
        EnvironmentConditions,
        Match,
        MatchConfiguration,
        Player,
        ServingState,
        SurfaceMaterials,
        Team,
        TeamId,
    )

    court = Court(
        dimensions=CourtDimensions.fip_standard(),
        enclosure_type=EnclosureType.GLASS,
        enclosure_variant=EnclosureVariant.V2,
        orientation=CourtOrientation.NORTH_SOUTH,
        turf_color="blue",
        setting=CourtSetting.OUTDOOR,
        door_left=DoorState.OPEN,
        door_right=DoorState.CLOSED,
        location=CourtLocation(
            club="Wizink Padel",
            city="Madrid",
            address="Av. Felipe II",
            country="Spain",
            latitude=40.4239,
            longitude=-3.6718,
        ),
    )
    assert Court.from_dict(court.to_dict()) == court

    env = EnvironmentConditions.from_atmosphere(
        temperature_c=26.5,
        altitude_m=655.0,
        relative_humidity=0.38,
        wind_velocity=(1.2, -0.5, 0.0),
    )
    restored_env = EnvironmentConditions.from_dict(env.to_dict())
    assert restored_env == env
    assert restored_env.temperature_c == 26.5
    assert restored_env.altitude_m == 655.0
    assert restored_env.relative_humidity == 0.38

    ball = BallProperties.worn()
    assert BallProperties.from_dict(ball.to_dict()) == ball

    surf = SurfaceMaterials.fast_indoor()
    assert SurfaceMaterials.from_dict(surf.to_dict()) == surf

    p1 = Player(name="Coello", side="right", nationality="ESP")
    p2 = Player(name="Tapia", side="left", nationality="ARG")
    p3 = Player(name="Galan", side="left", nationality="ESP")
    p4 = Player(name="Chingotto", side="right", nationality="ARG")

    assert Player.from_dict(p1.to_dict()) == p1

    team_a = Team(
        id=TeamId.A,
        player1=p1,
        player2=p2,
        serve_formation="australian",
        name="Golden Boys",
    )
    team_b = Team(id=TeamId.B, player1=p3, player2=p4, name="Chingalan")
    assert Team.from_dict(team_a.to_dict()) == team_a

    srv_state = ServingState(team=TeamId.A, player=p1, receiver=p3, court_side="right")
    assert ServingState.from_dict(srv_state.to_dict()) == srv_state

    cfg = MatchConfiguration(
        best_of_sets=3,
        advantage_method="gold_point",
        set_format="standard",
        deciding_set_format="super_tiebreak",
        starting_server_team=TeamId.A,
        set_starting_servers={1: {TeamId.A: p1, TeamId.B: p3}},
    )
    assert MatchConfiguration.from_dict(cfg.to_dict()) == cfg

    match = Match(
        teams={TeamId.A: team_a, TeamId.B: team_b},
        config=cfg,
        court=court,
        date=datetime(2026, 5, 10, 18, 30),
        duration_minutes=94,
    )
    match.history.add_point(TeamId.A)
    match.history.add_point(TeamId.B)
    match.history.add_point(TeamId.A)

    restored_match = Match.from_dict(match.to_dict())
    assert restored_match.teams == match.teams
    assert restored_match.config == match.config
    assert restored_match.court == match.court
    assert restored_match.duration_minutes == 94
    assert (
        restored_match.history.get_current_score() == match.history.get_current_score()
    )


def test_parquet_universal_match_format_and_skeletal_baking(tmp_path: Path):
    import numpy as np

    from padelkit import (
        H36M_JOINT_NAMES,
        BallProperties,
        CourtLocation,
        CourtSetting,
        EnvironmentConditions,
        Match,
        SurfaceMaterials,
        TeamId,
    )

    assert len(H36M_JOINT_NAMES) == 17

    # Test PlayerPose.from_world_keypoints_3d
    world_j3d = np.zeros((17, 3), dtype=np.float32)
    world_j3d[:, 0] = 2.0
    world_j3d[:, 1] = -6.5
    world_j3d[0, 2] = 0.88  # Pelvis
    world_j3d[3, 2] = 0.08  # RightAnkle
    world_j3d[6, 2] = 0.08  # LeftAnkle
    world_j3d[10, 2] = 1.66  # Head
    pose = PlayerPose.from_world_keypoints_3d(
        "P1", world_j3d, yaw_deg=15.0, animation="forehand_drive", swing_phase=0.5
    )
    assert pose.x == 2.0
    assert pose.y == -6.5
    assert np.allclose(pose.world_keypoints_3d, world_j3d, atol=1e-3)

    court = Court(
        turf_color="blue",
        setting=CourtSetting.INDOOR,
        location=CourtLocation(club="Premier Club", city="Madrid", country="Spain"),
    )
    env = EnvironmentConditions.from_atmosphere(
        temperature_c=23.0, altitude_m=650.0, relative_humidity=0.45
    )
    ball = BallProperties.fip_standard()
    surf = SurfaceMaterials.fip_standard()
    match = Match(advantage_method="gold_point", court=court)
    match.history.add_point(TeamId.A)

    timeline = MatchTimeline.demo_rally(
        court=court,
        fps=30.0,
        environment=env,
        ball_properties=ball,
        surface_materials=surf,
        match=match,
        bake_skeleton=True,
    )
    assert timeline.has_skeletal_poses

    # Stamp structured match score onto frame 0
    timeline.frames[0] = timeline.frames[0].with_match_score(
        match.history.get_current_score(),
        point_index=1,
        server_team="A",
        server_player="P1",
        golden_point_enabled=True,
    )
    assert timeline.frames[0].points_a == "15"
    assert timeline.frames[0].points_b == "0"

    parquet_path = tmp_path / "match_recording.parquet"
    timeline.to_parquet(parquet_path, compression="zstd")
    assert parquet_path.exists()

    loaded = MatchTimeline.from_parquet(parquet_path)
    assert len(loaded) == len(timeline)
    assert loaded.fps == 30.0
    assert loaded.has_skeletal_poses
    assert loaded.court == court
    assert loaded.environment == env
    assert loaded.ball_properties == ball
    assert loaded.surface_materials == surf
    assert loaded.match is not None
    assert loaded.match.history.get_current_score() == match.history.get_current_score()
    assert loaded.frames[0].points_a == "15"
    assert loaded.frames[0].point_index == 1

    p1_loaded = loaded.frames[10].players["P1"]
    p1_orig = timeline.frames[10].players["P1"]
    assert p1_loaded.keypoints_3d is not None
    assert len(p1_loaded.keypoints_3d) == 17
    assert np.asarray(p1_loaded.keypoints_3d).shape == (17, 3)
    assert np.allclose(p1_loaded.keypoints_3d, p1_orig.keypoints_3d, atol=1e-4)

    # Verify PadelVisualizer.from_parquet renders kp3dGroup in HTML
    viz = PadelVisualizer.from_parquet(parquet_path)
    assert viz.court == court
    html_str = viz.to_html()
    assert "kp3dGroup" in html_str
    assert '"kp3d"' in html_str


def test_padel_visualizer_offline_and_cdn_modes(tmp_path: Path):
    import http.client
    import importlib.resources

    from padelkit.viz.template import get_threejs_vendor_bundle

    bundle = get_threejs_vendor_bundle()
    assert "__PADELKIT_THREE_BUNDLE__" in bundle
    assert "</script" not in bundle.lower()

    license_text = (
        importlib.resources.files("padelkit.viz")
        .joinpath("vendor/THREEJS_LICENSE.txt")
        .read_text(encoding="utf-8")
    )
    assert "The MIT License" in license_text

    court = Court.fip_standard()
    timeline = MatchTimeline.demo_rally(court=court, fps=10.0, bake_skeleton=True)
    parquet_path = tmp_path / "offline_test.parquet"
    timeline.to_parquet(parquet_path)

    # 1. Default offline=True produces a fully self-contained HTML (no CDN)
    viz_offline = PadelVisualizer.from_parquet(parquet_path)
    assert viz_offline.offline is True
    offline_html = viz_offline.export_html(tmp_path / "offline.html").read_text(
        encoding="utf-8"
    )
    assert "cdn.jsdelivr.net" not in offline_html
    assert 'type="importmap"' not in offline_html
    assert "globalThis.__PADELKIT_THREE_BUNDLE__" in offline_html
    assert "WebGLRenderer" in offline_html

    # 2. Per-call override offline=False produces lightweight CDN importmap HTML
    cdn_html = viz_offline.export_html(tmp_path / "cdn.html", offline=False).read_text(
        encoding="utf-8"
    )
    assert "https://cdn.jsdelivr.net/npm/three@0.170.0/" in cdn_html
    assert 'type="importmap"' in cdn_html
    assert "globalThis.__PADELKIT_THREE_BUNDLE__" not in cdn_html
    assert len(offline_html) > len(cdn_html) + 300_000

    # 3. Instance default offline=False can also be overridden to offline=True
    viz_cdn = PadelVisualizer(court=court, timeline=timeline, offline=False)
    assert "cdn.jsdelivr.net" in viz_cdn.to_html()
    assert "cdn.jsdelivr.net" not in viz_cdn.to_html(offline=True)

    # 4. serve() honors offline parameter on "/"
    server = viz_offline.serve(port=0, open_browser=False, background=True)
    try:
        port = server.server_address[1]
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        served_html = resp.read().decode("utf-8")
        conn.close()
        assert resp.status == 200
        assert "globalThis.__PADELKIT_THREE_BUNDLE__" in served_html
        assert "cdn.jsdelivr.net" not in served_html
    finally:
        viz_offline.stop_server()

    server_cdn = viz_offline.serve(
        port=0, open_browser=False, background=True, offline=False
    )
    try:
        port = server_cdn.server_address[1]
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        served_cdn = resp.read().decode("utf-8")
        conn.close()
        assert resp.status == 200
        assert "https://cdn.jsdelivr.net/npm/three@0.170.0/" in served_cdn
        assert "globalThis.__PADELKIT_THREE_BUNDLE__" not in served_cdn
    finally:
        viz_offline.stop_server()
