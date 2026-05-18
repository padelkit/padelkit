# PadelKit - Knowledge File (KNOWLEDGE.md)

This document serves as the single source of truth regarding the architecture, infrastructure, and current business logic of the **PadelKit** project. Its goal is to keep the context aligned for future development sessions.

## Overview
**PadelKit** is an open-source Python library designed for padel analytics. The goal of the initial version (`0.0.1`) is to establish a modern package structure and provide the most basic domain models, such as court geometry and the scoring system, without yet including heavy inference logic or large dependencies (like OpenCV or PyTorch).

## Infrastructure and Technology Stack
- **Language:** Python >= 3.10
- **Build Backend:** `hatchling` (configured in `pyproject.toml`)
- **Testing:** `pytest` (tests located in the `tests/` directory)
- **Linting and Formatting:** `ruff` (strict configuration validated in CI)
- **Continuous Integration (CI):** GitHub Actions (`.github/workflows/ci.yml`) configured to run linting, tests, and package builds on Python 3.10, 3.11, and 3.12.
- **Distribution:** Standard packaging using `build` and `twine`, generating an `sdist` (.tar.gz) and a `wheel` (.whl) ready for PyPI.

## Code Architecture (`src/padelkit/`)

The library exposes its functionality through very specific submodules. The initial public API exposes the `Court` and `MatchScore` classes directly from the root (`padelkit`).

### 1. `court` Module (Court Geometry)
Defines the dimensions, landmarks, and coordinate system of an official padel court.

- **`CourtDimensions`:** Dataclass housing the official measurements. The `fip_standard()` method returns the measurements established by the International Padel Federation (20.0m length x 10.0m width).
- **Coordinate System:** 
  - The origin `(0.0, 0.0)` is exactly at the **center** of the court.
  - The **X** axis represents the width (left to right, from `-5.0` to `5.0`).
  - The **Y** axis represents the length (back to back, from `-10.0` to `10.0`).
  - All units are in **meters**.
- **`CourtLandmark`:** Enumeration for standardized 2D positions (e.g., `CENTER`, `TOP_LEFT`, `NET_RIGHT`).
- **`Court`:** Main geometry class. It can be instantiated via `Court.fip_standard()`. It provides methods like `landmarks_2d()` (a dictionary with all coordinates) and `point(name)` (specific coordinates of a landmark).

### 2. `scoring` Module (Scoring System)
Implements the logic of the match state and score progression.

- **`TeamId`:** Enumeration to identify teams (`A` and `B`).
- **`MatchScore`:** Handles the full state of the match.
  - **Points:** Traditional sequence (`0`, `15`, `30`, `40`).
  - **Deuce/Advantage:** Supports the classic advantage rule (if both reach 40, winning the advantage point is required, or it goes back to deuce if the opposing team ties).
  - **Games and Sets:** Automatic game advancement. The current system considers a set won upon reaching 6 games with a difference of 2, or upon reaching 7. There is no tie-break implementation in this first iteration.
  - **Match:** Configured as best of 3 sets (the first to win 2 sets wins the match).

## Dependencies
- Currently, the main package **has no external runtime dependencies**.
- Development dependencies (`[dev]`) include: `pytest`, `ruff`, `build`, and `twine`.
- Any future inclusion of dependencies like NumPy, OpenCV, Pandas, etc., must be rigorously justified to keep the package as lightweight as possible.

---
*Note: This file must be updated whenever architectural changes, new entities in the domain model, or significant changes to the technology stack are introduced.*
