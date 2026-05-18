from datetime import datetime

from ..court.court import Court
from .entities import Player, Team, TeamId, MatchConfiguration
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
        if teams is None:
            teams = {
                TeamId.A: Team(TeamId.A, Player("Player 1"), Player("Player 2")),
                TeamId.B: Team(TeamId.B, Player("Player 3"), Player("Player 4")),
            }
        self.teams = teams
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
            teams=self.teams,
            config=self.config,
        )
        self.duration_minutes = duration_minutes
        self.date = date
        self.court = court

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

    def set_set_starting_server(self, set_index: int, team_id: TeamId, player: Player) -> None:
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
