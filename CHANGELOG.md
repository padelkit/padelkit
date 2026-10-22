# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - Unreleased

### Added
- `padelkit.camera` module (`Camera`, `CameraIntrinsics`, `CameraExtrinsics`, `CameraDistortion`, `CameraPreset`, `DistortionModel`) for 3D-to-2D projection, lens distortion (Brown-Conrady & Fisheye), and 2D-to-3D ray/plane intersection.
- `padelkit.viz` module (`PadelVisualizer`, `MatchTimeline`, `FrameState`, `PlayerPose`) with an interactive Three.js 3D court studio, CSV replay mode, real-time SSE streaming mode, and computer vision render passes (RGB, Semantic Segmentation, Depth, and 17 Court Landmarks).

## [0.0.1] - 2026-05-14

### Added
- Project initialization with `pyproject.toml` and CI via GitHub Actions.
- `padelkit.court` module with `Court`, `CourtDimensions`, `CourtLocation`, 17-point 2D/3D `CourtLandmark` model, and `CENTERED` / `CORNER_BASED` coordinate systems.
- `padelkit.scoring` module with `Match`, `MatchConfiguration`, `MatchScore`, `MatchScoreHistory`, `Team`, `Player`, `ServingState`, and `ServingEngine`.
