__version__ = "0.1.0"

from padelkit.camera import (
    Camera,
    CameraDistortion,
    CameraExtrinsics,
    CameraIntrinsics,
    CameraPreset,
    DistortionModel,
)
from padelkit.court.court import Court
from padelkit.court.dimensions import CourtDimensions
from padelkit.court.enums import (
    CoordinateSystem,
    CourtOrientation,
    CourtSetting,
    DoorState,
    EnclosureType,
    EnclosureVariant,
)
from padelkit.court.landmarks import CourtLandmark
from padelkit.court.location import CourtLocation
from padelkit.scoring import (
    Match,
    MatchConfiguration,
    MatchScore,
    MatchScoreHistory,
    Player,
    ServingEngine,
    ServingState,
    Team,
    TeamId,
)
from padelkit.viz import (
    FrameState,
    MatchTimeline,
    PadelVisualizer,
    PlayerPose,
)

__all__ = [
    # Court geometry
    "Court",
    "CourtDimensions",
    "CourtLocation",
    "CourtLandmark",
    "CoordinateSystem",
    "EnclosureType",
    "EnclosureVariant",
    "CourtOrientation",
    "DoorState",
    "CourtSetting",
    # Camera & 3D Projection
    "Camera",
    "CameraIntrinsics",
    "CameraExtrinsics",
    "CameraDistortion",
    "CameraPreset",
    "DistortionModel",
    # 3D Visualization & Replay Timeline
    "PadelVisualizer",
    "MatchTimeline",
    "FrameState",
    "PlayerPose",
    # Scoring
    "MatchScore",
    "MatchScoreHistory",
    "Match",
    "TeamId",
    "Team",
    "Player",
    "ServingState",
    "MatchConfiguration",
    "ServingEngine",
    # Package
    "__version__",
]
