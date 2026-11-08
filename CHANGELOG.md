# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Unreleased

### Added
- `padelkit.camera` module (`Camera`, `CameraIntrinsics`, `CameraExtrinsics`, `CameraDistortion`, `CameraPreset`, `DistortionModel`) for 3D-to-2D projection, lens distortion (Brown-Conrady & Fisheye), 2D-to-3D ray/plane intersection, and automatic 6-DoF camera calibration from 2D court landmarks (`Camera.from_landmarks()`, `floor_homography`).
- `padelkit.physics` module (`BallPhysicsEngine`, `BallState`, `BallTrajectory`, `BounceEvent`, `BallProperties`, `EnvironmentConditions`, `SurfaceMaterials`, `SurfaceType`, `ContactRegime`) with 9D RK4 aerodynamics (quadratic drag with felt fuzz factor + Spindt Magnus lift), Coulomb Sliding/Rolling rebound physics across all padel court surfaces, and vectorized batch simulation.
- `padelkit.viz` module (`PadelVisualizer`, `MatchTimeline`, `FrameState`, `PlayerPose`) with an interactive Three.js 3D court studio, 9D physics telemetry HUD, Hawk-Eye bounce markers, CSV replay mode, real-time SSE streaming mode, Mixamo `.glb` skeletal animation library playback (`animation_library_dir` + `manifest.json` with `contact_swing_phase` synchronization), and computer vision render passes (RGB, Semantic Segmentation, Depth, and 17 Court Landmarks).
- Zero-dependency SVG technical schematic generator (`scripts/generate_schematics.py`) and drift test suite (`tests/test_docs_schematics.py`) producing 10 paired light/dark vector diagrams (`docs/images/schematics/`) across court geometry, camera frustums/distortion, 9D ball aerodynamics/rebounds, and serving rotations.
- Contributor governance, automated version synchronization (`importlib.metadata`), documentation integrity test suite (`tests/test_version_and_docs.py`), `CONTRIBUTING.md`, GitHub PR/Issue templates, and PyPI release workflow (`.github/workflows/release.yml`).

## [0.0.1] - 2026-05-14

### Added
- Project initialization with `pyproject.toml` and CI via GitHub Actions.
- `padelkit.court` module with `Court`, `CourtDimensions`, `CourtLocation`, 17-point 2D/3D `CourtLandmark` model, and `CENTERED` / `CORNER_BASED` coordinate systems.
- `padelkit.scoring` module with `Match`, `MatchConfiguration`, `MatchScore`, `MatchScoreHistory`, `Team`, `Player`, `ServingState`, and `ServingEngine`.

[0.1.0]: https://github.com/padelkit/padelkit/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/padelkit/padelkit/releases/tag/v0.0.1
