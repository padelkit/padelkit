from enum import Enum


class TeamId(str, Enum):
    A = "A"
    B = "B"


class MatchScore:
    """
    A simple match score tracker for a padel match.
    Currently tracks points, games, and sets for a best-of-3 sets match
    without tiebreaks (wins set at 6 games with difference of 2).
    """

    POINTS_SEQUENCE = [0, 15, 30, 40]

    def __init__(self):
        # Current game points
        self._points_A = 0
        self._points_B = 0
        
        self.advantage: TeamId | None = None
        
        # Completed games in current set
        self.games_A = 0
        self.games_B = 0
        
        # Completed sets
        self.sets_A = 0
        self.sets_B = 0
        
        # History of completed sets scores e.g., [(6, 4), (7, 5)]
        self.completed_sets: list[tuple[int, int]] = []
        
        self.match_winner: TeamId | None = None

    @property
    def game_points(self) -> tuple[int | str, int | str]:
        """Returns the current game score as a tuple or string for advantage."""
        if self.advantage == TeamId.A:
            return ("AD", 40)
        elif self.advantage == TeamId.B:
            return (40, "AD")
            
        return (
            self.POINTS_SEQUENCE[self._points_A],
            self.POINTS_SEQUENCE[self._points_B],
        )

    def point_won_by(self, team: str | TeamId):
        if self.match_winner is not None:
            return  # Match is over
            
        team = TeamId(team)
        
        if self.advantage is not None:
            if self.advantage == team:
                self._win_game(team)
            else:
                # Back to deuce
                self.advantage = None
            return

        if team == TeamId.A:
            if self._points_A == 3: # 40
                if self._points_B == 3: # 40-40 Deuce
                    self.advantage = TeamId.A
                else:
                    self._win_game(team)
            else:
                self._points_A += 1
        else: # TeamId.B
            if self._points_B == 3: # 40
                if self._points_A == 3: # 40-40 Deuce
                    self.advantage = TeamId.B
                else:
                    self._win_game(team)
            else:
                self._points_B += 1

    def _win_game(self, team: TeamId):
        # Reset points
        self._points_A = 0
        self._points_B = 0
        self.advantage = None
        
        if team == TeamId.A:
            self.games_A += 1
        else:
            self.games_B += 1
            
        self._check_set_winner()

    def _check_set_winner(self):
        # Check if a team won the set (6 games with diff 2, or 7 games)
        # Simplified for now (no tiebreak implemented in this first version)
        won_a = (
            self.games_A >= 6 and self.games_A - self.games_B >= 2
        ) or self.games_A == 7
        won_b = (
            self.games_B >= 6 and self.games_B - self.games_A >= 2
        ) or self.games_B == 7
        
        if won_a or won_b:
            self.completed_sets.append((self.games_A, self.games_B))
            if won_a:
                self.sets_A += 1
            else:
                self.sets_B += 1
                
            # Reset games
            self.games_A = 0
            self.games_B = 0
            
            self._check_match_winner()

    def _check_match_winner(self):
        # Best of 3 sets
        if self.sets_A == 2:
            self.match_winner = TeamId.A
        elif self.sets_B == 2:
            self.match_winner = TeamId.B

    def __str__(self) -> str:
        if self.match_winner:
            return f"Match Won by Team {self.match_winner.value}"
            
        sets_str = " ".join(f"{s[0]}-{s[1]}" for s in self.completed_sets)
        current_set = f"{self.games_A}-{self.games_B}"
        
        pts_a, pts_b = self.game_points
        game_str = f"{pts_a}-{pts_b}"
        
        parts = []
        if sets_str:
            parts.append(sets_str)
        parts.append(current_set)
        parts.append(f"({game_str})")
        
        return " | ".join(parts)
