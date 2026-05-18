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
    in_tiebreak: bool = False
    in_super_tiebreak: bool = False
    is_gold_point: bool = False

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

    def __init__(
        self,
        teams: dict[TeamId, Team] | None = None,
        best_of_sets: int = 3,
        advantage_method: str = "advantage",
        set_format: str = "standard",
        deciding_set_format: str = "regular"
    ):
        self._points_history: list[TeamId] = []
        self.teams = teams
        self.best_of_sets = best_of_sets
        self.advantage_method = advantage_method
        self.set_format = set_format
        self.deciding_set_format = deciding_set_format

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
        
        total_games = 0
        
        in_tiebreak = False
        in_super_tiebreak = False
        tiebreak_starter: TeamId | None = None
        tiebreak_points_played = 0

        sets_to_win = (self.best_of_sets // 2) + 1

        for team in self._points_history:
            # If match is already won, ignore further points
            if sets_a >= sets_to_win or sets_b >= sets_to_win:
                break

            # Before processing the point, if we are at the start of a set,
            # check if this is the deciding set and we need to play a tie-break or super tie-break.
            if (
                games_a == 0
                and games_b == 0
                and points_a == 0
                and points_b == 0
                and not in_tiebreak
                and not in_super_tiebreak
            ):
                is_deciding_set = (
                    sets_a + sets_b == self.best_of_sets - 1
                    and sets_a == sets_b
                    and self.deciding_set_format in ["tiebreak", "super_tiebreak"]
                )
                if is_deciding_set:
                    if self.deciding_set_format == "super_tiebreak":
                        in_super_tiebreak = True
                    else:
                        in_tiebreak = True
                    tiebreak_starter = TeamId.B if total_games % 2 != 0 else TeamId.A
                    tiebreak_points_played = 0

            # 1. Processing under a tie-break (either regular set tie-break, or match deciding tie-break)
            if in_tiebreak or in_super_tiebreak:
                if team == TeamId.A:
                    points_a += 1
                else:
                    points_b += 1
                tiebreak_points_played += 1

                target = 10 if in_super_tiebreak else 7

                if (points_a >= target and points_a - points_b >= 2) or (points_b >= target and points_b - points_a >= 2):
                    # Tie-break ends! Determine the winner
                    winner_team = TeamId.A if points_a > points_b else TeamId.B

                    # Check if this is a match-deciding tie-break (i.e. games score is 0-0)
                    if games_a == 0 and games_b == 0:
                        if winner_team == TeamId.A:
                            sets_a += 1
                            completed_sets.append((1, 0))
                        else:
                            sets_b += 1
                            completed_sets.append((0, 1))
                        # Reset tie-break/points
                        points_a = 0
                        points_b = 0
                        in_tiebreak = False
                        in_super_tiebreak = False
                        tiebreak_starter = None
                        tiebreak_points_played = 0
                    else:
                        # It was a regular set tie-break
                        if winner_team == TeamId.A:
                            games_a += 1  # becomes 7 (standard) or 5 (mini)
                            completed_sets.append((games_a, games_b))
                            sets_a += 1
                        else:
                            games_b += 1  # becomes 7 (standard) or 5 (mini)
                            completed_sets.append((games_a, games_b))
                            sets_b += 1
                        total_games += 1
                        # Reset for next set
                        games_a = 0
                        games_b = 0
                        points_a = 0
                        points_b = 0
                        in_tiebreak = False
                        tiebreak_starter = None
                        tiebreak_points_played = 0
            
            # 2. Processing a regular game
            else:
                if self.advantage_method == "gold_point":
                    if team == TeamId.A:
                        if points_a == 3:  # 40
                            if points_b == 3:  # 40-40, golden point!
                                # A wins game
                                games_a += 1
                                total_games += 1
                                points_a = 0
                                points_b = 0
                            else:
                                # A wins game
                                games_a += 1
                                total_games += 1
                                points_a = 0
                                points_b = 0
                        else:
                            points_a += 1
                    else:  # team == TeamId.B
                        if points_b == 3:  # 40
                            if points_a == 3:  # 40-40, golden point!
                                # B wins game
                                games_b += 1
                                total_games += 1
                                points_a = 0
                                points_b = 0
                            else:
                                # B wins game
                                games_b += 1
                                total_games += 1
                                points_a = 0
                                points_b = 0
                        else:
                            points_b += 1
                else:  # advantage method
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
                            if points_a == 3:  # 40
                                if points_b == 3:  # 40-40
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
                            if points_b == 3:  # 40
                                if points_a == 3:  # 40-40
                                    advantage = TeamId.B
                                else:
                                    # Win game
                                    points_a = 0
                                    points_b = 0
                                    games_b += 1
                                    total_games += 1
                            else:
                                points_b += 1

                # Check if a game finishing wins the set or triggers a tie-break
                if points_a == 0 and points_b == 0:
                    limit = 4 if self.set_format == "mini" else 6
                    if games_a == limit and games_b == limit:
                        in_tiebreak = True
                        tiebreak_starter = TeamId.B if total_games % 2 != 0 else TeamId.A
                        tiebreak_points_played = 0
                    else:
                        is_set_won_a = False
                        is_set_won_b = False

                        if games_a >= limit and games_a - games_b >= 2:
                            is_set_won_a = True
                        elif games_b >= limit and games_b - games_a >= 2:
                            is_set_won_b = True

                        if is_set_won_a:
                            completed_sets.append((games_a, games_b))
                            sets_a += 1
                            games_a = 0
                            games_b = 0
                        elif is_set_won_b:
                            completed_sets.append((games_a, games_b))
                            sets_b += 1
                            games_a = 0
                            games_b = 0

        # Check if we should be in a deciding set tie-break or super tie-break after the loop as well
        if (
            sets_a < sets_to_win
            and sets_b < sets_to_win
            and games_a == 0
            and games_b == 0
            and points_a == 0
            and points_b == 0
            and not in_tiebreak
            and not in_super_tiebreak
        ):
            is_deciding_set = (
                sets_a + sets_b == self.best_of_sets - 1
                and sets_a == sets_b
                and self.deciding_set_format in ["tiebreak", "super_tiebreak"]
            )
            if is_deciding_set:
                if self.deciding_set_format == "super_tiebreak":
                    in_super_tiebreak = True
                else:
                    in_tiebreak = True
                tiebreak_starter = TeamId.B if total_games % 2 != 0 else TeamId.A
                tiebreak_points_played = 0

        # After processing all points, let's format the return values:
        # 1. Determine active server:
        if in_tiebreak or in_super_tiebreak:
            points_played = points_a + points_b
            is_odd = ((points_played + 1) // 2) % 2 != 0
            if is_odd:
                server = TeamId.B if tiebreak_starter == TeamId.A else TeamId.A
            else:
                server = tiebreak_starter
        else:
            server = TeamId.B if total_games % 2 != 0 else TeamId.A

        # 2. Determine display points:
        if in_tiebreak or in_super_tiebreak:
            disp_points_a = points_a
            disp_points_b = points_b
        else:
            if advantage == TeamId.A:
                disp_points_a, disp_points_b = "AD", 40
            elif advantage == TeamId.B:
                disp_points_a, disp_points_b = 40, "AD"
            else:
                disp_points_a = self.POINTS_SEQUENCE[points_a]
                disp_points_b = self.POINTS_SEQUENCE[points_b]

        # 3. Determine is_gold_point:
        is_gold_point = (
            not in_tiebreak
            and not in_super_tiebreak
            and self.advantage_method == "gold_point"
            and points_a == 3
            and points_b == 3
        )

        return MatchScore(
            points_A=disp_points_a,
            points_B=disp_points_b,
            games_A=games_a,
            games_B=games_b,
            sets_A=sets_a,
            sets_B=sets_b,
            completed_sets=completed_sets.copy(),
            server=server,
            teams=self.teams,
            in_tiebreak=in_tiebreak,
            in_super_tiebreak=in_super_tiebreak,
            is_gold_point=is_gold_point
        )
