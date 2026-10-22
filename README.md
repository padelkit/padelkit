# PadelKit 🎾

**An End-to-End 3D Computer Vision, Camera Calibration, Match Scoring & Synthetic Data Engine for Padel.**

![PyPI - Version](https://img.shields.io/pypi/v/padelkit)
![License](https://img.shields.io/github/license/padelkit/padelkit)

## Installation

```bash
pip install padelkit
```

For optional headless Blender synthetic rendering:
```bash
pip install "padelkit[blender]"
```

## Quickstart

```python
from padelkit import (
    BallPhysicsEngine,
    BallState,
    Camera,
    Court,
    Match,
    MatchTimeline,
    PadelVisualizer,
    TeamId,
)

# 1. 3D Court Geometry & 17 Official Landmarks
court = Court.fip_standard()
landmarks_3d = court.landmarks_3d()

# 2. Projective Camera & 3D-to-2D / 2D-to-3D Transformations
camera = Camera.broadcast_near(court=court)
landmarks_2d = camera.project_court_landmarks(court=court)
floor_xyz = camera.project_pixel_to_plane(landmarks_2d["center"], plane_z=0.0)

# 3. 9D Ball Aerodynamics (Drag + Spindt Magnus Lift) & Contact Physics
engine = BallPhysicsEngine(court=court)
shot = BallState.from_shot(
    position=(-2.5, -2.0, 2.3),
    velocity=(3.5, 16.0, -2.5),
    topspin_rpm=-1800.0,
)
trajectory = engine.simulate(shot, duration=2.5)

# 4. 3D Visualization, CSV Replay & Synthetic CV Passes (Three.js)
timeline = MatchTimeline.demo_rally(court=court, fps=60.0)
timeline.to_csv("demo_rally.csv")

viz = PadelVisualizer.from_csv("demo_rally.csv", court=court)
viz.export_html("padel_studio.html")

# 5. Event-Sourced Match Scoring Engine
match = Match(best_of_sets=3, advantage_method="gold_point")
match.history.add_point(TeamId.A)
print(match.history.get_current_score())
```

## Features

- **Court Geometry (`padelkit.court`):** Official FIP dimensions, enclosure variants, and 17-point 2D/3D landmark coordinate systems (`CENTERED` and `CORNER_BASED`).
- **Camera & 3D Projection (`padelkit.camera`):** Intrinsics (`FOV` & physical sensor models), 6-DoF extrinsics (`look_at`, `euler`, OpenCV/OpenGL matrices), lens distortion (`Brown-Conrady` & `Fisheye`), vectorized 3D-to-2D projection, and 2D-to-3D ray/plane intersection.
- **9D Ball Physics & Dynamics (`padelkit.physics`):** RK4 aerodynamic integrator with felt-adjusted drag, Spindt Magnus lift, atmospheric density modeling (`from_atmosphere`), analytical Coulomb Sliding-to-Rolling rebound physics across turf/glass/fence/net, and vectorized `simulate_batch()`.
- **3D Visualizer & Replay Studio (`padelkit.viz`):** Interactive Three.js 3D court studio supporting CSV match replay, real-time live streaming (`serve()` + `push_frame()`), standalone HTML/Jupyter export, and CV render passes (`RGB`, `Semantic Segmentation`, `Depth`, and `17 Landmarks`).
- **Scoring System (`padelkit.scoring`):** Full event-sourced match, set, game, tie-break, and serving rotation engine.

## License

Apache 2.0 License.

## Links

- **Documentation:** [https://padelkit.dev](https://padelkit.dev) (See [Docs Guide](./docs/README.md) for contribution instructions)
- **Source Code:** [GitHub](https://github.com/padelkit/padelkit)
