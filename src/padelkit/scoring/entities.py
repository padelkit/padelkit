from dataclasses import dataclass
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
