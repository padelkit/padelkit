from dataclasses import dataclass, field
from typing import Literal
from enum import Enum


class TeamId(str, Enum):
    A = "A"
    B = "B"


@dataclass
class Player:
    """Represents a padel player."""
    name: str
    side: Literal["left", "right"] | None = None
    nationality: str | None = None


@dataclass
class Team:
    """Represents a padel team composed of two players."""
    id: TeamId
    player1: Player
    player2: Player
    serve_formation: Literal["standard", "australian"] = "standard"
    name: str | None = None

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name
        return f"{self.player1.name} / {self.player2.name}"


@dataclass(frozen=True)
class ServingState:
    """Represents the active serving team and player at a specific point."""
    team: TeamId
    player: Player | None = None


@dataclass
class MatchConfiguration:
    """Encapsulates all rules, formats, and structural configurations for a padel match."""
    best_of_sets: int = 3
    advantage_method: Literal["advantage", "gold_point"] = "advantage"
    set_format: Literal["standard", "mini"] = "standard"
    deciding_set_format: Literal["regular", "tiebreak", "super_tiebreak"] = "regular"
    starting_server_team: TeamId = TeamId.A
    set_starting_servers: dict[int, dict[TeamId, Player]] = field(default_factory=dict)

