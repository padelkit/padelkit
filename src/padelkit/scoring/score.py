from dataclasses import dataclass
from typing import Optional
from .entities import TeamId, Team, Player, ServingState, MatchConfiguration
from .serving import ServingEngine


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
    server: ServingState | None = None
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

        serve_a = " *" if self.server and self.server.team == TeamId.A else ""
        serve_b = " *" if self.server and self.server.team == TeamId.B else ""

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
        deciding_set_format: str = "regular",
        starting_server_team: TeamId = TeamId.A,
        set_starting_servers: dict[int, dict[TeamId, Player]] | None = None,
        config: MatchConfiguration | None = None,
    ):
        self._points_history: list[TeamId] = []
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
        return self.config.starting_server_team

    @starting_server_team.setter
    def starting_server_team(self, value: TeamId) -> None:
        self.config.starting_server_team = value

    @property
    def set_starting_servers(self) -> dict[int, dict[TeamId, Player]]:
        return self.config.set_starting_servers

    @set_starting_servers.setter
    def set_starting_servers(self, value: dict[int, dict[TeamId, Player]]) -> None:
        self.config.set_starting_servers = value

    def set_set_starting_server(self, set_index: int, team_id: TeamId, player: Player) -> None:
        """Sets the starting server for a specific set (1-indexed) and team."""
        if set_index not in self.config.set_starting_servers:
            self.config.set_starting_servers[set_index] = {}
        self.config.set_starting_servers[set_index][team_id] = player

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

        sets_to_win = (self.config.best_of_sets // 2) + 1

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
                    sets_a + sets_b == self.config.best_of_sets - 1
                    and sets_a == sets_b
                    and self.config.deciding_set_format in ["tiebreak", "super_tiebreak"]
                )
                if is_deciding_set:
                    if self.config.deciding_set_format == "super_tiebreak":
                        in_super_tiebreak = True
                    else:
                        in_tiebreak = True
                    if self.config.starting_server_team == TeamId.A:
                        tiebreak_starter = TeamId.B if total_games % 2 != 0 else TeamId.A
                    else:
                        tiebreak_starter = TeamId.A if total_games % 2 != 0 else TeamId.B
                    tiebreak_points_played = 0

            # 1. Processing under a tie-break (either regular set tie-break, or match deciding tie-break)
            if in_tiebreak or in_super_tiebreak:
                if team == TeamId.A:
                    points_a += 1
                else:
                    points_b += 1
                tiebreak_points_played += 1

                target = 10 if in_super_tiebreak else 7

                if (points_a >= target and points_a - points_b >= 2) or (
                    points_b >= target and points_b - points_a >= 2
                ):
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
                if self.config.advantage_method == "gold_point":
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
                    limit = 4 if self.config.set_format == "mini" else 6
                    if games_a == limit and games_b == limit:
                        in_tiebreak = True
                        if self.config.starting_server_team == TeamId.A:
                            tiebreak_starter = TeamId.B if total_games % 2 != 0 else TeamId.A
                        else:
                            tiebreak_starter = TeamId.A if total_games % 2 != 0 else TeamId.B
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
                sets_a + sets_b == self.config.best_of_sets - 1
                and sets_a == sets_b
                and self.config.deciding_set_format in ["tiebreak", "super_tiebreak"]
            )
            if is_deciding_set:
                if self.config.deciding_set_format == "super_tiebreak":
                    in_super_tiebreak = True
                else:
                    in_tiebreak = True
                if self.config.starting_server_team == TeamId.A:
                    tiebreak_starter = TeamId.B if total_games % 2 != 0 else TeamId.A
                else:
                    tiebreak_starter = TeamId.A if total_games % 2 != 0 else TeamId.B
                tiebreak_points_played = 0

        # Determine active server state using ServingEngine
        server_state = ServingEngine(self.config).calculate_serving_state(
            teams=self.teams,
            points_played=points_a + points_b,
            total_games=total_games,
            current_set=sets_a + sets_b + 1,
            games_a=games_a,
            games_b=games_b,
            in_tiebreak=in_tiebreak,
            in_super_tiebreak=in_super_tiebreak,
            tiebreak_starter=tiebreak_starter,
        )

        # 3. Determine display points:
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

        # 4. Determine is_gold_point:
        is_gold_point = (
            not in_tiebreak
            and not in_super_tiebreak
            and self.config.advantage_method == "gold_point"
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
            server=server_state,
            teams=self.teams,
            in_tiebreak=in_tiebreak,
            in_super_tiebreak=in_super_tiebreak,
            is_gold_point=is_gold_point,
        )
