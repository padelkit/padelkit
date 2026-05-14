from datetime import datetime
from .entities import TeamId, Team, Player
from .score import MatchScoreHistory

class Match:
    """Represents a full padel match, including score history and metadata."""
    
    def __init__(
        self,
        teams: dict[TeamId, Team] | None = None,
        best_of_sets: int = 3,
        duration_minutes: int | None = None,
        date: datetime | None = None,
        location: str | None = None,
        court_type: str | None = None
    ):
        if teams is None:
            teams = {
                TeamId.A: Team(TeamId.A, Player("Player 1"), Player("Player 2")),
                TeamId.B: Team(TeamId.B, Player("Player 3"), Player("Player 4"))
            }
        self.teams = teams
        self.history = MatchScoreHistory(teams=self.teams)
        self.best_of_sets = best_of_sets
        self.duration_minutes = duration_minutes
        self.date = date
        self.location = location
        self.court_type = court_type

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
