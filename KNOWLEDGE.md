# PadelKit - Knowledge File (KNOWLEDGE.md)

This document serves as the single source of truth regarding the architecture, infrastructure, and current business logic of the **PadelKit** project. Its goal is to keep the context aligned for future development sessions.

## Overview
**PadelKit** is an open-source Python library designed for padel analytics, 3D computer vision, physics-informed simulation, and synthetic data generation.

## Infrastructure and Technology Stack
- **Language:** Python >= 3.10 (managed via `uv`)
- **Build Backend:** `hatchling` (configured in `pyproject.toml`)
- **Core Runtime Dependencies:** `numpy>=1.24.0`, `pandas>=2.0.0`
- **Optional Dependencies:**
  - `padelkit[dev]`: `pytest`, `ruff`, `build`, `twine`
  - `padelkit[blender]`: `bpy>=4.0.0` (for headless photorealistic synthetic dataset rendering)
- **Testing:** `pytest` (tests located in the `tests/` directory)
- **Linting and Formatting:** `ruff` (strict configuration validated in CI)

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
Provides projective camera geometry, optical lens distortion, and 3D-to-2D / 2D-to-3D transformations.

- **`CameraIntrinsics`:** Sensor resolution (`width_px`, `height_px`), focal lengths (`fx`, `fy`), principal point (`cx`, `cy`), and calibration matrix `K`. Includes `from_fov()`, `from_sensor()`, `full_hd()`, and `uhd_4k()`.
- **`CameraDistortion` & `DistortionModel`:** Supports `NONE`, `BROWN_CONRADY` (`k1, k2, p1, p2, k3`), and `FISHEYE` (`k1, k2, k3, k4`) forward distortion and iterative undistortion.
- **`CameraExtrinsics`:** 6-DoF camera pose in 3D court coordinates (`from_look_at()`, `from_euler()`, `from_rt()`), exposing both OpenCV (`world_to_camera_matrix`) and OpenGL/Three.js/Blender (`opengl_camera_to_world_matrix`) matrices.
- **`Camera` & `CameraPreset`:** Full camera model with presets (`broadcast_near`, `broadcast_far`, `overhead_zenith`, corners, side net) and methods `world_to_image()`, `project_points()`, `project_court_landmarks()`, `image_to_ray()`, `project_pixel_to_plane()`, and `frustum_corners_world()`.

### 3. `viz` Module (`src/padelkit/viz/`)
Provides the temporal state contract (`FrameState`, `PlayerPose`, `MatchTimeline`) and the interactive Three.js 3D studio (`PadelVisualizer`).

- **`MatchTimeline`:** Time-indexed sequence of `FrameState` snapshots with lossless CSV and Pandas DataFrame serialization (`to_csv()`, `from_csv()`, `to_dataframe()`, `from_dataframe()`, `demo_rally()`).
- **`PadelVisualizer`:** Generates a Three.js 3D padel court studio supporting:
  1. **CSV / Timeline Replay Mode** (interactive timeline scrubber and browser drag-and-drop CSV loader).
  2. **Live Real-Time Streaming Mode** (`serve()` + `push_frame()` over Server-Sent Events).
  3. **Standalone HTML & Jupyter Notebook Mode** (`export_html()` and `_repr_html_()`).
  4. **Computer Vision Render Passes** (`RGB`, `Semantic Segmentation ID`, `Depth Map`, and `17 Court Landmarks` overlay).

### 4. `physics` Module (`src/padelkit/physics/`)
Provides a 9-Dimensional (`9D`) aerodynamic and contact physics engine for padel balls (`[x, y, z, vx, vy, vz, wx, wy, wz]`).

- **`BallProperties`, `EnvironmentConditions`, `SurfaceMaterials`:** Immutable physical configuration dataclasses with presets (`BallProperties.fip_standard()`, `worn()`, `wet()`, `EnvironmentConditions.from_atmosphere()` using barometric + Tetens humid air density, `SurfaceMaterials.fip_standard()`, `fast_indoor()`, `slow_sandy()`).
- **`BallState`, `BallTrajectory`, `BounceEvent`:** `BallState.from_shot()` decomposes `topspin_rpm` and `sidespin_rpm` into 3D angular velocity. `BallTrajectory` stores full 9D history with interpolation (`state_at()`), Pandas/CSV export, and `to_timeline()` conversion for 3D visualization.
- **`BallPhysicsEngine`:** Integrates gravity, quadratic drag with felt `fuzz_factor`, and non-linear Spindt Magnus lift via 4th-order Runge-Kutta (`RK4`). Resolves collisions with analytical Coulomb `SLIDING` vs `ROLLING` transition across all court surfaces (`FLOOR`, `BACK_GLASS`, `SIDE_GLASS`, `BACK_WALL`, `SIDE_WALL`, `BACK_FENCE`, `SIDE_FENCE`, `NET`). Supports both single-trajectory `simulate()` and vectorized NumPy `simulate_batch()`.

### 5. `scoring` Module (`src/padelkit/scoring/`)
Implements match rules, event-sourced score progression (`MatchScoreHistory`), `Match`, `MatchScore`, `Team`, `Player`, `ServingState`, and `MatchConfiguration`.

---
*Note: This file must be updated whenever architectural changes, new entities in the domain model, or significant changes to the technology stack are introduced.*
