# PadelKit

PadelKit is an open source toolkit for developers building padel analytics tools.

![PyPI - Version](https://img.shields.io/pypi/v/padelkit)
![License](https://img.shields.io/github/license/padelkit/padelkit)

> **Status:** Early Alpha. This is a very early version focusing on core domain models. 

## Installation

```bash
pip install padelkit
```

## Quickstart

```python
from padelkit.court import PadelCourt
from padelkit.scoring import MatchScore

# Court Geometry
court = PadelCourt.fip_standard()
print(f"Court dimensions: {court.length}m x {court.width}m")

# Scoring
score = MatchScore()
score.point_won_by("A")
print(score)
```

## Features

- **Court Geometry:** Official dimensions and 2D coordinate system.
- **Scoring System:** Basic match, set and game scoring logic.

## Roadmap

- Extended landmarks and 3D geometries.
- Event structures (serve, rally, etc.).
- Camera calibration and world-to-image projections.

## License

Apache 2.0 License.

## Links

- **Documentation:** [https://padelkit.dev](https://padelkit.dev)
- **Source Code:** [GitHub](https://github.com/padelkit/padelkit)
