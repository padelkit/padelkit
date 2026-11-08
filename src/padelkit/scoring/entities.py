from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal


class TeamId(str, Enum):
    A = "A"
    B = "B"


@dataclass
class Player:
    """Represents a padel player."""

    name: str
    side: Literal["left", "right"] | None = None
    nationality: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializes the player to a dictionary."""
        return {
            "name": self.name,
            "side": self.side,
            "nationality": self.nationality,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Player":
        """Reconstructs a :class:`Player` instance from a dictionary."""
        return cls(
            name=str(data["name"]),
            side=data.get("side"),
            nationality=data.get("nationality"),
        )


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

    def to_dict(self) -> dict[str, Any]:
        """Serializes the team to a dictionary."""
        return {
            "id": self.id.value,
            "player1": self.player1.to_dict(),
            "player2": self.player2.to_dict(),
            "serve_formation": self.serve_formation,
            "name": self.name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Team":
        """Reconstructs a :class:`Team` instance from a dictionary."""
        return cls(
            id=TeamId(data["id"]),
            player1=Player.from_dict(data["player1"]),
            player2=Player.from_dict(data["player2"]),
            serve_formation=data.get("serve_formation", "standard"),
            name=data.get("name"),
        )


@dataclass(frozen=True)
class ServingState:
    """Represents the active serving team, serving player, receiver, and court side
    at a specific point."""

    team: TeamId
    player: Player | None = None
    receiver: Player | None = None
    court_side: Literal["left", "right"] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializes the serving state to a dictionary."""
        return {
            "team": self.team.value,
            "player": self.player.to_dict() if self.player else None,
            "receiver": self.receiver.to_dict() if self.receiver else None,
            "court_side": self.court_side,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ServingState":
        """Reconstructs a :class:`ServingState` instance from a dictionary."""
        return cls(
            team=TeamId(data["team"]),
            player=Player.from_dict(data["player"]) if data.get("player") else None,
            receiver=(
                Player.from_dict(data["receiver"]) if data.get("receiver") else None
            ),
            court_side=data.get("court_side"),
        )


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

    def to_dict(self) -> dict[str, Any]:
        """Serializes the match configuration to a dictionary."""
        return {
            "best_of_sets": self.best_of_sets,
            "advantage_method": self.advantage_method,
            "set_format": self.set_format,
            "deciding_set_format": self.deciding_set_format,
            "starting_server_team": self.starting_server_team.value,
            "set_starting_servers": {
                str(set_idx): {
                    tid.value: p.to_dict() for tid, p in team_servers.items()
                }
                for set_idx, team_servers in self.set_starting_servers.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MatchConfiguration":
        """Reconstructs a :class:`MatchConfiguration` instance from a dictionary."""
        raw_servers = data.get("set_starting_servers") or {}
        parsed_servers: dict[int, dict[TeamId, Player]] = {}
        for k, team_map in raw_servers.items():
            parsed_servers[int(k)] = {
                TeamId(tid): Player.from_dict(p_data)
                for tid, p_data in team_map.items()
            }
        return cls(
            best_of_sets=int(data.get("best_of_sets", 3)),
            advantage_method=data.get("advantage_method", "advantage"),
            set_format=data.get("set_format", "standard"),
            deciding_set_format=data.get("deciding_set_format", "regular"),
            starting_server_team=TeamId(data.get("starting_server_team", "A")),
            set_starting_servers=parsed_servers,
        )
