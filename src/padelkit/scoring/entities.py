from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


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

    def __post_init__(self) -> None:
        if self.player1 == self.player2 or self.player1.name == self.player2.name:
            raise ValueError(
                "A team must consist of two different players with unique names."
            )

    @property
    def display_name(self) -> str:
        if self.name:
            return self.name
        return f"{self.player1.name} / {self.player2.name}"


@dataclass(frozen=True)
class ServingState:
    """Represents the active serving team, serving player, receiver, and court side
    at a specific point."""

    team: TeamId
    player: Player | None = None
    receiver: Player | None = None
    court_side: Literal["left", "right"] | None = None


@dataclass
class MatchConfiguration:
    """Encapsulates all rules, formats, and structural configurations for a padel
    match."""

    best_of_sets: int = 3
    advantage_method: Literal["advantage", "gold_point"] = "advantage"
    set_format: Literal["standard", "mini"] = "standard"
    deciding_set_format: Literal["regular", "tiebreak", "super_tiebreak"] = "regular"
    starting_server_team: TeamId = TeamId.A
    set_starting_servers: dict[int, dict[TeamId, Player]] = field(default_factory=dict)

    def validate(self) -> None:
        if (
            not isinstance(self.best_of_sets, int)
            or self.best_of_sets <= 0
            or self.best_of_sets % 2 == 0
        ):
            raise ValueError("best_of_sets must be a positive odd integer.")
        if self.advantage_method not in ("advantage", "gold_point"):
            raise ValueError(
                "advantage_method must be either 'advantage' or 'gold_point'."
            )
        if self.set_format not in ("standard", "mini"):
            raise ValueError("set_format must be either 'standard' or 'mini'.")
        if self.deciding_set_format not in ("regular", "tiebreak", "super_tiebreak"):
            raise ValueError(
                "deciding_set_format must be 'regular', 'tiebreak', or "
                "'super_tiebreak'."
            )
        if self.starting_server_team not in (TeamId.A, TeamId.B):
            raise ValueError("starting_server_team must be TeamId.A or TeamId.B.")
        if not isinstance(self.set_starting_servers, dict):
            raise ValueError("set_starting_servers must be a dictionary.")
        for set_idx, servers in self.set_starting_servers.items():
            if not isinstance(set_idx, int) or set_idx <= 0:
                raise ValueError("set_starting_servers keys must be positive integers.")
            if not isinstance(servers, dict):
                raise ValueError("set_starting_servers values must be dictionaries.")
            for team_id, player in list(servers.items()):
                if team_id not in (TeamId.A, TeamId.B):
                    raise ValueError(
                        "set_starting_servers team keys must be TeamId.A or TeamId.B."
                    )
                if not isinstance(player, Player):
                    raise ValueError(
                        "set_starting_servers values must be Player instances."
                    )

    def __post_init__(self) -> None:
        self.validate()

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if (
            hasattr(self, "best_of_sets")
            and hasattr(self, "advantage_method")
            and hasattr(self, "set_format")
            and hasattr(self, "deciding_set_format")
            and hasattr(self, "starting_server_team")
            and hasattr(self, "set_starting_servers")
        ):
            self.validate()
