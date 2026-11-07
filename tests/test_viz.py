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
