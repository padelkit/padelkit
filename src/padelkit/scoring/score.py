from dataclasses import dataclass
from typing import Optional
from .entities import TeamId, Team

@dataclass(frozen=True)
class MatchScore:
    """An immutable snapshot of the match score at a given point in time."""
    points_A: int | str
    points_B: int | str
    games_A: int
    games_B: int
    sets_A: int
    sets_B: int
    completed_sets: list[tuple[int, int]]
    server: TeamId | None = None
    teams: dict[TeamId, Team] | None = None

    def __str__(self) -> str:
        # Determine team labels
        team_a_label = "TEAM A"
        team_b_label = "TEAM B"
        
        if self.teams:
            team_a = self.teams.get(TeamId.A)
            if team_a and team_a.name:
                team_a_label = f"TEAM A ({team_a.name})"
            elif team_a and team_a.player1.name and team_a.player2.name:
                team_a_label = f"TEAM A ({team_a.player1.name} / {team_a.player2.name})"
                
            team_b = self.teams.get(TeamId.B)
            if team_b and team_b.name:
                team_b_label = f"TEAM B ({team_b.name})"
            elif team_b and team_b.player1.name and team_b.player2.name:
                team_b_label = f"TEAM B ({team_b.player1.name} / {team_b.player2.name})"

        # Formatting
        sets_str_a = " ".join(str(s[0]) for s in self.completed_sets)
        sets_str_b = " ".join(str(s[1]) for s in self.completed_sets)
        
        pad_len = max(len(team_a_label), len(team_b_label))
        team_a_label = team_a_label.ljust(pad_len)
        team_b_label = team_b_label.ljust(pad_len)

        serve_a = " *" if self.server == TeamId.A else ""
        serve_b = " *" if self.server == TeamId.B else ""

        a_line = f"{team_a_label} | {sets_str_a} | {self.games_A} | {self.points_A:>2}{serve_a}"
        b_line = f"{team_b_label} | {sets_str_b} | {self.games_B} | {self.points_B:>2}{serve_b}"
        
        # Clean double spaces in case of no sets
        a_line = a_line.replace("|  |", "|").strip()
        b_line = b_line.replace("|  |", "|").strip()

        return f"{a_line}\n{b_line}"

class MatchScoreHistory:
    """Tracks the history of a match and recalculates the score upon changes."""
    POINTS_SEQUENCE = [0, 15, 30, 40]

    def __init__(self, teams: dict[TeamId, Team] | None = None):
        self._points_history: list[TeamId] = []
        self.teams = teams

    def add_point(self, team: TeamId) -> MatchScore:
        """Adds a point to the history and returns the new MatchScore state."""
        self._points_history.append(team)
        return self.get_current_score()

    def modify_point(self, index: int, team: TeamId) -> MatchScore:
        """Modifies a specific point in the history and recalculates the score."""
        if 0 <= index < len(self._points_history):
            self._points_history[index] = team
        else:
            raise IndexError("Point index out of range.")
        return self.get_current_score()

    def get_current_score(self) -> MatchScore:
        """Recalculates the entire state from the history of points."""
        points_a = 0
        points_b = 0
        advantage: TeamId | None = None
        
        games_a = 0
        games_b = 0
        sets_a = 0
        sets_b = 0
        completed_sets: list[tuple[int, int]] = []
        
        # Simple server logic: Team A starts, then alternates every game.
        # This doesn't take into account tiebreaks right now.
        total_games = 0

        for team in self._points_history:
            if advantage is not None:
                if advantage == team:
                    # Win game from advantage
                    points_a = 0
                    points_b = 0
                    advantage = None
                    if team == TeamId.A:
                        games_a += 1
                    else:
                        games_b += 1
                    total_games += 1
                else:
                    # Back to deuce
                    advantage = None
            else:
                if team == TeamId.A:
                    if points_a == 3: # 40
                        if points_b == 3: # 40-40
                            advantage = TeamId.A
                        else:
                            # Win game
                            points_a = 0
                            points_b = 0
                            games_a += 1
                            total_games += 1
                    else:
                        points_a += 1
                else:
                    if points_b == 3: # 40
                        if points_a == 3: # 40-40
                            advantage = TeamId.B
                        else:
                            # Win game
                            points_a = 0
                            points_b = 0
                            games_b += 1
                            total_games += 1
                    else:
                        points_b += 1

            # Check if a set was won (6 games with diff 2, or 7 games)
            # Note: The logic in the original was just testing if games >= 6 and diff >= 2
            # but it has to be evaluated only when games_a or games_b is updated.
            if games_a >= 6 or games_b >= 6:
                if (games_a >= 6 and games_a - games_b >= 2) or games_a == 7:
                    completed_sets.append((games_a, games_b))
                    sets_a += 1
                    games_a = 0
                    games_b = 0
                elif (games_b >= 6 and games_b - games_a >= 2) or games_b == 7:
                    completed_sets.append((games_a, games_b))
                    sets_b += 1
                    games_a = 0
                    games_b = 0

        # Current Server: Alternates every game
        server = TeamId.B if total_games % 2 != 0 else TeamId.A

        # Format points
        if advantage == TeamId.A:
            disp_points_a, disp_points_b = "AD", 40
        elif advantage == TeamId.B:
            disp_points_a, disp_points_b = 40, "AD"
        else:
            disp_points_a = self.POINTS_SEQUENCE[points_a]
            disp_points_b = self.POINTS_SEQUENCE[points_b]

        return MatchScore(
            points_A=disp_points_a,
            points_B=disp_points_b,
            games_A=games_a,
            games_B=games_b,
            sets_A=sets_a,
            sets_B=sets_b,
            completed_sets=completed_sets.copy(),
            server=server,
            teams=self.teams
        )
