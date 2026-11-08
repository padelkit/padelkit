from datetime import datetime
from typing import Any

from ..court.court import Court
from .entities import MatchConfiguration, Player, Team, TeamId
from .score import MatchScoreHistory


class Match:
    """Represents a full padel match, including score history and metadata."""

    def __init__(
        self,
        teams: dict[TeamId, Team] | None = None,
        best_of_sets: int = 3,
        duration_minutes: int | None = None,
        date: datetime | None = None,
        court: Court | None = None,
        advantage_method: str = "advantage",
        set_format: str = "standard",
        deciding_set_format: str = "regular",
        starting_server_team: TeamId = TeamId.A,
        set_starting_servers: dict[int, dict[TeamId, Player]] | None = None,
        config: MatchConfiguration | None = None,
    ):
        if config is not None:
            self.config = config
        else:
            self.config = MatchConfiguration(
                best_of_sets=best_of_sets,
                advantage_method=advantage_method,
                set_format=set_format,
                deciding_set_format=deciding_set_format,
                starting_server_team=starting_server_team,
                set_starting_servers=set_starting_servers or {},
            )
        self.history = MatchScoreHistory(
            teams=None,
            config=self.config,
        )
        if teams is None:
            teams = {
                TeamId.A: Team(TeamId.A, Player("Player 1"), Player("Player 2")),
                TeamId.B: Team(TeamId.B, Player("Player 3"), Player("Player 4")),
            }
        self.teams = teams
        self.duration_minutes = duration_minutes
        self.date = date
        self.court = court

    @property
    def teams(self) -> dict[TeamId, Team] | None:
        return self.history.teams

    @teams.setter
    def teams(self, value: dict[TeamId, Team] | None) -> None:
        self.history.teams = value

    @property
    def best_of_sets(self) -> int:
        return self.config.best_of_sets

    @best_of_sets.setter
    def best_of_sets(self, value: int) -> None:
        self.config.best_of_sets = value

    @property
    def advantage_method(self) -> str:
        return self.config.advantage_method

    @advantage_method.setter
    def advantage_method(self, value: str) -> None:
        self.config.advantage_method = value

    @property
    def set_format(self) -> str:
        return self.config.set_format

    @set_format.setter
    def set_format(self, value: str) -> None:
        self.config.set_format = value

    @property
    def deciding_set_format(self) -> str:
        return self.config.deciding_set_format

    @deciding_set_format.setter
    def deciding_set_format(self, value: str) -> None:
        self.config.deciding_set_format = value

    @property
    def starting_server_team(self) -> TeamId:
        """The team that starts serving in the match."""
        return self.config.starting_server_team

    @starting_server_team.setter
    def starting_server_team(self, team_id: TeamId) -> None:
        self.config.starting_server_team = team_id

    @property
    def set_starting_servers(self) -> dict[int, dict[TeamId, Player]]:
        """The custom starting servers defined for each set and team."""
        return self.config.set_starting_servers

    @set_starting_servers.setter
    def set_starting_servers(self, value: dict[int, dict[TeamId, Player]]) -> None:
        self.config.set_starting_servers = value
        self.history._validate_player_membership()

    def set_set_starting_server(
        self, set_index: int, team_id: TeamId, player: Player
    ) -> None:
        """Sets the starting server for a specific set (1-indexed) and team."""
        self.history.set_set_starting_server(set_index, team_id, player)

    @property
    def winner(self) -> Team | None:
        """Determines if a team has won the match based on best_of_sets."""
        score = self.history.get_current_score()
        sets_to_win = (self.best_of_sets // 2) + 1

        if score.sets_A >= sets_to_win:
            return self.teams.get(TeamId.A)
        elif score.sets_B >= sets_to_win:
            return self.teams.get(TeamId.B)

        return None

    @property
    def is_completed(self) -> bool:
        """Returns True if the match has been won by a team."""
        return self.winner is not None

    def to_dict(self) -> dict[str, Any]:
        """Serializes the match configuration, teams, court, and point history."""
        return {
            "teams": (
                {tid.value: team.to_dict() for tid, team in self.teams.items()}
                if self.teams
                else None
            ),
            "config": self.config.to_dict(),
            "points_history": [tid.value for tid in self.history._points_history],
            "duration_minutes": self.duration_minutes,
            "date": self.date.isoformat() if self.date else None,
            "court": self.court.to_dict() if self.court else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Match":
        """Reconstructs a :class:`Match` instance from a dictionary."""
        raw_teams = data.get("teams")
        teams = (
            {TeamId(tid): Team.from_dict(t_data) for tid, t_data in raw_teams.items()}
            if isinstance(raw_teams, dict)
            else None
        )
        cfg_data = data.get("config")
        config = (
            MatchConfiguration.from_dict(cfg_data)
            if isinstance(cfg_data, dict)
            else None
        )
        court_data = data.get("court")
        court = Court.from_dict(court_data) if isinstance(court_data, dict) else None
        date_str = data.get("date")
        date_val = datetime.fromisoformat(date_str) if date_str else None

        match = cls(
            teams=teams,
            config=config,
            duration_minutes=data.get("duration_minutes"),
            date=date_val,
            court=court,
        )
        for pt_team in data.get("points_history", []):
            match.history.add_point(TeamId(pt_team))
        return match
