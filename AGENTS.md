# PadelKit — Agent & Architecture Guide (`AGENTS.md`)

This document serves as the single source of truth regarding the architecture, development workflow, and conventions of **PadelKit** for AI coding agents and contributors.

## Overview
**PadelKit** is an open-source (Apache 2.0) Python library for padel analytics, 3D court geometry, camera calibration & projection, 9D ball aerodynamics & rebound physics, interactive 3D visualization, and match scoring.

## Development Workflow & Commands
- **Python & Virtual Environment:** Always use **`uv`** and the local virtual environment in `.venv/`:
  - Sync environment: `uv sync --extra dev`
  - Run tests: `.venv/bin/pytest`
  - Run linter: `.venv/bin/ruff check .`
  - Format code: `.venv/bin/ruff format .`
- **Build Backend:** `hatchling` (configured in `pyproject.toml`, Python `>= 3.10`).
- **Core Runtime Dependencies:** `numpy>=1.24.0`, `pandas>=2.0.0`, `pyarrow>=14.0.0`.
- **Optional Extras:**
  - `padelkit[dev]`: `pytest`, `ruff`, `build`, `twine`
  - `padelkit[blender]`: `bpy>=4.0.0` (for headless photorealistic synthetic rendering)

## Versioning & Documentation (`docs/`)
- **Current Version:** `0.1.0` (unreleased; `0.0.1` is the initial published version on PyPI). While `0.1.0` remains unreleased, accumulate all changes under `## [0.1.0] - Unreleased` in `CHANGELOG.md`.
- **Single Source of Truth for Version:** `pyproject.toml` defines `version = "X.Y.Z"`. `src/padelkit/__init__.py` reads it dynamically via `importlib.metadata.version("padelkit")`, and `tests/test_version_and_docs.py` verifies consistency across `pyproject.toml`, `padelkit.__version__`, `CHANGELOG.md`, and `docs/docs.config.json`.
- **Branching & CI/CD Workflow:**
  - `develop` is the integration branch for all contributor Pull Requests (`CONTRIBUTING.md`). Pushing to `docs/**` on `develop` triggers the Vercel Preview Deploy Hook (`VERCEL_PREVIEW_DEPLOY_HOOK_URL`).
  - `main` is the production branch. Merging `develop` into `main` triggers the Vercel Production Deploy Hook (`VERCEL_DEPLOY_HOOK_URL`) for `https://padelkit.dev`.
  - Publishing a GitHub Release (`vX.Y.Z`) on `main` triggers `.github/workflows/release.yml` to verify tag/version parity, run tests, and publish to PyPI via Trusted Publishing.
- **Decoupled Docs Architecture:**
  - `docs/` in this repository contains the `.mdx` content pages, custom SVG icons (`docs/icons/`), and `docs/docs.config.json`.
  - A separate private Next.js repository (`padelkit-docs`) syncs `docs/` during build and deploys to `https://padelkit.dev` via Vercel.
  - **MDX Rules (enforced by `tests/test_version_and_docs.py`):**
    1. Do **not** include `export const metadata = { ... }` at the top of `.mdx` files (`padelkit-docs/scripts/sync-docs.mjs` injects it automatically from `docs/docs.config.json`).
    2. Register every new page in `docs/docs.config.json` under `"pages"` (with `"min": "0.1.0"` for `0.1.0` features), `"navigation"`, and optionally `"intro_cards"`.
    3. Follow the modular 2-column layout (`<Row>`, `<Col>`, `<Col sticky>`, `<Properties>`, `<Property>`, `<CodeGroup>`, `<Schematic>`).
    4. Static light/dark vector schematics in `docs/images/schematics/` are generated deterministically via `.venv/bin/python scripts/generate_schematics.py` (and verified via `--check` in `tests/test_docs_schematics.py`).

---

## Code Architecture (`src/padelkit/`)

The library exposes its functionality through modular subpackages and re-exports core classes at the root (`padelkit`).

### 1. `court` Module (`src/padelkit/court/`)
Defines the dimensions, landmarks, and coordinate system of an official padel court.

- **`CourtDimensions`:** Dataclass housing the official FIP measurements (`20.0m x 10.0m`, `4.0m` back wall, `3.0m`/`4.0m` side wall, `0.88m`/`0.92m` net height).
- **Coordinate System (`CoordinateSystem`):**
  - `CENTERED` (default): Origin `(0.0, 0.0, 0.0)` at the center of the net on the floor, `X` in `[-5, 5]`, `Y` in `[-10, 10]`, `Z` height in meters.
  - `CORNER_BASED`: Origin `(0.0, 0.0, 0.0)` at the bottom-left (`FLOOR_NEAR_LEFT`) corner.
- **`CourtLandmark`:** Enumeration for the 17 standardized 2D/3D positions (13 floor points + 4 back-wall top corners).
- **`Court`:** Main geometry class providing `landmarks_2d()`, `landmarks_3d()`, and `point(name)`.

### 2. `camera` Module (`src/padelkit/camera/`)
Provides projective camera geometry, optical lens distortion, 2D-to-3D calibration, and 3D-to-2D / 2D-to-3D transformations.

- **`CameraIntrinsics`:** Sensor resolution (`width_px`, `height_px`), focal lengths (`fx`, `fy`), principal point (`cx`, `cy`), and calibration matrix `K`. Includes `from_fov()`, `from_sensor()`, `full_hd()`, and `uhd_4k()`.
- **`CameraDistortion` & `DistortionModel`:** Supports `NONE`, `BROWN_CONRADY` (`k1, k2, p1, p2, k3`), and `FISHEYE` (`k1, k2, k3, k4`) forward distortion and iterative undistortion.
- **`CameraExtrinsics`:** 6-DoF camera pose in 3D court coordinates (`from_look_at()`, `from_euler()`, `from_rt()`), exposing both OpenCV (`world_to_camera_matrix`) and OpenGL/Three.js/Blender (`opengl_camera_to_world_matrix`) matrices.
- **`Camera` & `CameraPreset`:** Full camera model with presets (`broadcast_near`, `broadcast_far`, `overhead_zenith`, corners, side net), 2D-to-3D calibration from video landmarks (`Camera.from_landmarks()`, `Camera.compute_homography()`, `floor_homography`, `inverse_floor_homography`, `reprojection_error()`), and projection/unprojection methods (`world_to_image()`, `project_points()`, `project_court_landmarks()`, `image_to_ray()`, `project_pixel_to_plane()`, `frustum_corners_world()`).

### 3. `physics` Module (`src/padelkit/physics/`)
Provides a 9-Dimensional (`9D`) aerodynamic and contact physics engine for padel balls (`[x, y, z, vx, vy, vz, wx, wy, wz]`).

- **`BallProperties`, `EnvironmentConditions`, `SurfaceMaterials`:** Immutable physical configuration dataclasses with presets (`BallProperties.fip_standard()`, `worn()`, `wet()`, `EnvironmentConditions.from_atmosphere()` using barometric + Tetens humid air density, `SurfaceMaterials.fip_standard()`, `fast_indoor()`, `slow_sandy()`).
- **`BallState`, `BallTrajectory`, `BounceEvent`:** `BallState.from_shot()` decomposes `topspin_rpm` and `sidespin_rpm` into 3D angular velocity. `BallTrajectory` stores full 9D history with interpolation (`state_at()`), Pandas/CSV export, and `to_timeline()` conversion for 3D visualization.
- **`BallPhysicsEngine`:** Integrates gravity, quadratic drag with felt `fuzz_factor`, and non-linear Spindt Magnus lift via 4th-order Runge-Kutta (`RK4`). Resolves collisions with analytical Coulomb `SLIDING` vs `ROLLING` transition across all court surfaces (`FLOOR`, `BACK_GLASS`, `SIDE_GLASS`, `BACK_WALL`, `SIDE_WALL`, `BACK_FENCE`, `SIDE_FENCE`, `NET`). Supports both single-trajectory `simulate()` and vectorized NumPy `simulate_batch()`.

### 4. `viz` Module (`src/padelkit/viz/`)
Provides the temporal state contract (`FrameState`, `PlayerPose`, `MatchTimeline`) and the interactive Three.js 3D studio (`PadelVisualizer`).

- **`MatchTimeline`:** Time-indexed sequence of `FrameState` snapshots (including structured scoreboard state, 9D ball position/velocity/spin, player root poses, and optional 17-joint H36M 3D skeletal poses `keypoints_3d`) coupled with static domain entities (`Court`, `EnvironmentConditions`, `BallProperties`, `SurfaceMaterials`, `Match`). Supports lossless **Universal Match Format (`.parquet`)** serialization (`to_parquet()`, `from_parquet()` embedding `padelkit_metadata` in the Parquet schema header), 17-joint 3D skeletal pose baking (`bake_skeletal_poses()`), CSV/Pandas DataFrame export (`to_csv()`, `from_csv()`, `to_dataframe()`, `from_dataframe()`), and a 9D physics-driven `demo_rally()` generator.
- **`PadelVisualizer`:** Generates a Three.js 3D padel court studio supporting:
  1. **Parquet / CSV / Timeline Replay Mode** (`PadelVisualizer.from_parquet()`, `from_csv()`, interactive timeline scrubber, 9D telemetry HUD, Hawk-Eye bounce markers, and browser drag-and-drop CSV loader).
  2. **Live Real-Time Streaming Mode** (`serve()` + `push_frame()` over Server-Sent Events).
  3. **Standalone HTML & Jupyter Notebook Mode** (`export_html()` and `_repr_html_()`).
  4. **Computer Vision Render Passes** (`RGB`, `Semantic Segmentation ID`, `Depth Map`, and `17 Court Landmarks` overlay).
  5. **Mixamo GLB Skeletal Animation Library & Baked 17-Joint H36M 3D Rig Support** (`animation_library_dir` / `load_animation_library()` consuming `manifest.json` and `.glb` clips generated by `padelkit-animator`, or direct 3D playback of baked 17-joint H36M skeletons `kp3d` from `.parquet` files).

### 5. `scoring` Module (`src/padelkit/scoring/`)
Implements match rules, event-sourced score progression (`MatchScoreHistory`), `Match`, `MatchScore`, `Team`, `Player`, `ServingState`, `ServingEngine`, and `MatchConfiguration`.

---

## Roadmap & Upcoming Integrations (For Future Sessions)

1. **Physics-Informed 3D State Estimation (`padelkit.tracking` / `padelkit.estimation`):**
   - Port and adapt the particle filter & trajectory reconstructor from `padelamix` (`pipeline/physics/particle_filter.py`) into pure vectorized NumPy on top of `BallPhysicsEngine.simulate_batch()` and `Camera.project_points()`.
   - Include bootstrap particle filtering (supporting 2D `(u, v)` detections and heatmap likelihoods), mixture process noise for racket hits, and offline Rauch-Tung-Striebel (`RTS`) backward smoothing.
2. **Photorealistic Synthetic Data & 3D Assets (`padelkit.viz` & `padelkit[blender]`):**
   - Integrate high-resolution 3D assets (court, ball, racket from `padel_3d_assets` / GLTF/GLB support in `PadelVisualizer` and animated rigged player avatars).
   - Build `padelkit.synth` / Blender headless renderer (`bpy`) consuming `MatchTimeline` and `Camera` to export photorealistic RGB, depth, segmentation masks, and 2D/3D ground-truth annotations for training CV models.
3. **Batch Match & Rally Simulation (`padelkit.sim`):**
   - High-speed headless rally and match generator combining `BallPhysicsEngine`, tactical shot selection, and `MatchScoreHistory` to synthesize large-scale tabular/trajectory datasets.
4. **Optional AI Vision & Audio Inference Wrapper (`padelkit[vision]`):**
   - Lightweight optional wrappers (ONNX / PyTorch) for ball tracking (`TrackNet` / `MiniTrackNet`), 2D/3D player pose estimation (`RTMPose`), and audio shot-impact detection, feeding directly into the state estimator and `MatchTimeline`.

---
*Keep this file (`AGENTS.md`) updated whenever architectural changes, new entities in the domain model, or changes to the development stack are introduced.*
