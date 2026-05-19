from .entities import Player, Team, TeamId, ServingState, MatchConfiguration


class ServingEngine:
    """Pure engine responsible for calculating serving states based on configurations and score metrics."""

    def __init__(self, config: MatchConfiguration):
        self.config = config

    def calculate_serving_state(
        self,
        teams: dict[TeamId, Team] | None,
        points_played: int,
        total_games: int,
        current_set: int,
        games_a: int,
        games_b: int,
        in_tiebreak: bool,
        in_super_tiebreak: bool,
        tiebreak_starter: TeamId | None,
    ) -> ServingState | None:
        """Determines the team and player currently serving based on score state."""
        # 1. Determine active server team:
        if in_tiebreak or in_super_tiebreak:
            is_odd = ((points_played + 1) // 2) % 2 != 0
            if is_odd:
                server_team = TeamId.B if tiebreak_starter == TeamId.A else TeamId.A
            else:
                server_team = tiebreak_starter
        else:
            if self.config.starting_server_team == TeamId.A:
                server_team = TeamId.B if total_games % 2 != 0 else TeamId.A
            else:
                server_team = TeamId.A if total_games % 2 != 0 else TeamId.B

        # 2. Determine active server player:
        server_player = None
        if teams and server_team is not None:
            team = teams.get(server_team)
            if team:
                starting_server = self.config.set_starting_servers.get(current_set, {}).get(server_team)
                if starting_server not in (team.player1, team.player2):
                    starting_server = team.player1
                second_server = team.player2 if starting_server == team.player1 else team.player1

                if in_tiebreak or in_super_tiebreak:
                    # Count points served by server_team in this tie-break
                    pts_served_by_team = 0
                    for i in range(points_played):
                        pt_is_odd = ((i + 1) // 2) % 2 != 0
                        if pt_is_odd:
                            pt_server_team = TeamId.B if tiebreak_starter == TeamId.A else TeamId.A
                        else:
                            pt_server_team = tiebreak_starter
                        if pt_server_team == server_team:
                            pts_served_by_team += 1

                    if server_team == tiebreak_starter:
                        turn_index = (pts_served_by_team + 1) // 2
                    else:
                        turn_index = pts_served_by_team // 2

                    if turn_index % 2 == 0:
                        server_player = starting_server
                    else:
                        server_player = second_server
                else:
                    games_served_before = (games_a + games_b) // 2
                    if games_served_before % 2 == 0:
                        server_player = starting_server
                    else:
                        server_player = second_server

        # 3. Determine court side and receiver:
        receiver = None
        court_side = None
        if server_team is not None:
            court_side = "right" if points_played % 2 == 0 else "left"
            if teams:
                recv_team_id = TeamId.B if server_team == TeamId.A else TeamId.A
                recv_team = teams.get(recv_team_id)
                if recv_team:
                    p1 = recv_team.player1
                    p2 = recv_team.player2
                    if p1.side == "right" and p2.side != "right":
                        right_player, left_player = p1, p2
                    elif p1.side == "left" and p2.side != "left":
                        right_player, left_player = p2, p1
                    elif p2.side == "right" and p1.side != "right":
                        right_player, left_player = p2, p1
                    elif p2.side == "left" and p1.side != "left":
                        right_player, left_player = p1, p2
                    else:
                        right_player, left_player = p1, p2

                    receiver = right_player if court_side == "right" else left_player

        if server_team is None:
            return None
        return ServingState(
            team=server_team,
            player=server_player,
            receiver=receiver,
            court_side=court_side,
        )
