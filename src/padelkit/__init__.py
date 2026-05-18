__version__ = "0.0.1"

from padelkit.court.court import PadelCourt
from padelkit.court.dimensions import CourtDimensions
from padelkit.court.enums import (
    CoordinateSystem,
    CourtOrientation,
    CourtSetting,
    DoorState,
    EnclosureType,
    EnclosureVariant,
)
from padelkit.court.landmarks import Landmark
from padelkit.court.location import CourtLocation
from padelkit.scoring import Match, MatchScore, MatchScoreHistory, Player, Team, TeamId

__all__ = [
    # Court geometry
    "PadelCourt",
    "CourtDimensions",
    "CourtLocation",
    "Landmark",
    "CoordinateSystem",
    "EnclosureType",
    "EnclosureVariant",
    "CourtOrientation",
    "DoorState",
    "CourtSetting",

    # Scoring
    "MatchScore",
    "MatchScoreHistory",
    "Match",
    "TeamId",
    "Team",
    "Player",
    # Package
    "__version__",
]
