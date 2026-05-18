from padelkit.scoring import Match, TeamId, Team, Player, ServingState

def test_match_winner():
    match = Match(best_of_sets=3)
    
    # Team B wins 2 sets (best of 3 means 2 sets to win)
    for _ in range(2): # 2 sets
        for _ in range(6): # 6 games
            for _ in range(4): # 4 points
                match.history.add_point(TeamId.B)
                
    assert match.is_completed is True
    assert match.winner == match.teams.get(TeamId.B)

def test_match_formatting_no_names():
    match = Match(teams={})
    match.history.add_point(TeamId.A)
    match.history.add_point(TeamId.B)
    score = match.history.get_current_score()
    
    # Without names, should fallback to TEAM A and TEAM B
    output = str(score)
    assert "TEAM A | 0 | 15 *" in output
    assert "TEAM B | 0 | 15" in output

def test_match_formatting_with_names():
    teams = {
        TeamId.A: Team(TeamId.A, Player("Player 1"), Player("Player 2"), name="The Pros"),
        TeamId.B: Team(TeamId.B, Player("Player 3"), Player("Player 4"))
    }
    match = Match(teams=teams)
    
    for _ in range(4): # A wins game 1
        match.history.add_point(TeamId.A)
        
    score = match.history.get_current_score()
    output = str(score)
    
    assert "TEAM A (The Pros)            | 1 |  0" in output
    assert "TEAM B (Player 3 / Player 4) | 0 |  0 *" in output


def test_match_server_propagation():
    player3 = Player("Player 3")
    player4 = Player("Player 4")
    player1 = Player("Player 1")
    player2 = Player("Player 2")
    
    teams = {
        TeamId.A: Team(TeamId.A, player1, player2),
        TeamId.B: Team(TeamId.B, player3, player4),
    }
    
    set_starting_servers = {
        1: {
            TeamId.B: player4,
            TeamId.A: player2
        }
    }
    
    match = Match(
        teams=teams,
        starting_server_team=TeamId.B,
        set_starting_servers=set_starting_servers
    )
    
    assert match.starting_server_team == TeamId.B
    assert match.set_starting_servers == set_starting_servers
    
    score = match.history.get_current_score()
    assert score.server is not None
    assert score.server.team == TeamId.B
    assert score.server.player == player4


def test_match_dynamic_server_updates():
    player1 = Player("Player 1")
    player2 = Player("Player 2")
    player3 = Player("Player 3")
    player4 = Player("Player 4")
    
    teams = {
        TeamId.A: Team(TeamId.A, player1, player2),
        TeamId.B: Team(TeamId.B, player3, player4),
    }
    
    match = Match(teams=teams)
    
    assert match.starting_server_team == TeamId.A
    score = match.history.get_current_score()
    assert score.server is not None
    assert score.server.team == TeamId.A
    assert score.server.player == player1
    
    match.starting_server_team = TeamId.B
    score = match.history.get_current_score()
    assert score.server is not None
    assert score.server.team == TeamId.B
    assert score.server.player == player3
    
    match.set_set_starting_server(1, TeamId.B, player4)
    score = match.history.get_current_score()
    assert score.server is not None
    assert score.server.team == TeamId.B
    assert score.server.player == player4


def test_server_player_regular_rotation():
    player1 = Player("P1")
    player2 = Player("P2")
    player3 = Player("P3")
    player4 = Player("P4")
    
    teams = {
        TeamId.A: Team(TeamId.A, player1, player2),
        TeamId.B: Team(TeamId.B, player3, player4),
    }
    
    set_starting_servers = {
        1: {
            TeamId.A: player1,
            TeamId.B: player4
        }
    }
    match = Match(teams=teams, starting_server_team=TeamId.A, set_starting_servers=set_starting_servers)
    
    # Game 1: Served by Team A, Player 1
    score = match.history.get_current_score()
    assert score.server is not None
    assert score.server.team == TeamId.A
    assert score.server.player == player1
    
    # Win Game 1 for A
    for _ in range(4):
        match.history.add_point(TeamId.A)
        
    # Game 2: Served by Team B, Player 4
    score = match.history.get_current_score()
    assert score.server is not None
    assert score.server.team == TeamId.B
    assert score.server.player == player4
    
    # Win Game 2 for B
    for _ in range(4):
        match.history.add_point(TeamId.B)
        
    # Game 3: Served by Team A, Player 2
    score = match.history.get_current_score()
    assert score.server is not None
    assert score.server.team == TeamId.A
    assert score.server.player == player2
    
    # Win Game 3 for A
    for _ in range(4):
        match.history.add_point(TeamId.A)
        
    # Game 4: Served by Team B, Player 3
    score = match.history.get_current_score()
    assert score.server is not None
    assert score.server.team == TeamId.B
    assert score.server.player == player3
    
    # Win Game 4 for B
    for _ in range(4):
        match.history.add_point(TeamId.B)
        
    # Game 5: Served by Team A, Player 1
    score = match.history.get_current_score()
    assert score.server is not None
    assert score.server.team == TeamId.A
    assert score.server.player == player1


def test_server_player_tiebreak_rotation():
    player1 = Player("P1")
    player2 = Player("P2")
    player3 = Player("P3")
    player4 = Player("P4")
    
    teams = {
        TeamId.A: Team(TeamId.A, player1, player2),
        TeamId.B: Team(TeamId.B, player3, player4),
    }
    
    set_starting_servers = {
        1: {
            TeamId.A: player1,
            TeamId.B: player3
        }
    }
    
    match = Match(
        teams=teams,
        starting_server_team=TeamId.A,
        set_starting_servers=set_starting_servers,
        set_format="mini"
    )
    
    for _ in range(4):
        for _ in range(4):
            match.history.add_point(TeamId.A)
        for _ in range(4):
            match.history.add_point(TeamId.B)
            
    score = match.history.get_current_score()
    assert score.in_tiebreak is True
    
    # Pt 0 (Score 0-0): Team A, player1
    assert score.server is not None
    assert score.server.team == TeamId.A
    assert score.server.player == player1
    
    # Pt 1 (Score 1-0): Team B, player3 (1st serve for B in TB)
    score = match.history.add_point(TeamId.A)
    assert score.server is not None
    assert score.server.team == TeamId.B
    assert score.server.player == player3
    
    # Pt 2 (Score 1-1): Team B, player3 (2nd serve for B in TB)
    score = match.history.add_point(TeamId.B)
    assert score.server is not None
    assert score.server.team == TeamId.B
    assert score.server.player == player3
    
    # Pt 3 (Score 2-1): Team A, player2 (1st serve for A's 2nd turn in TB)
    score = match.history.add_point(TeamId.A)
    assert score.server is not None
    assert score.server.team == TeamId.A
    assert score.server.player == player2
    
    # Pt 4 (Score 2-2): Team A, player2 (2nd serve for A's 2nd turn in TB)
    score = match.history.add_point(TeamId.B)
    assert score.server is not None
    assert score.server.team == TeamId.A
    assert score.server.player == player2

    # Pt 5 (Score 3-2): Team B, player4 (1st serve for B's 2nd turn in TB)
    score = match.history.add_point(TeamId.A)
    assert score.server is not None
    assert score.server.team == TeamId.B
    assert score.server.player == player4

    # Pt 6 (Score 3-3): Team B, player4 (2nd serve for B's 2nd turn in TB)
    score = match.history.add_point(TeamId.B)
    assert score.server is not None
    assert score.server.team == TeamId.B
    assert score.server.player == player4

    # Pt 7 (Score 4-3): Team A, player1 (Rotates back to A's starting server)
    score = match.history.add_point(TeamId.A)
    assert score.server is not None
    assert score.server.team == TeamId.A
    assert score.server.player == player1


def test_serving_state_exports():
    from padelkit import ServingState as TopServingState
    from padelkit.scoring import ServingState as ScoringServingState
    assert TopServingState is ServingState
    assert ScoringServingState is ServingState


def test_match_configuration_direct_instantiation():
    from padelkit.scoring import MatchConfiguration
    
    config = MatchConfiguration(
        best_of_sets=5,
        advantage_method="gold_point",
        set_format="mini",
        deciding_set_format="super_tiebreak"
    )
    match = Match(config=config)
    
    assert match.config is config
    assert match.best_of_sets == 5
    assert match.advantage_method == "gold_point"
    assert match.set_format == "mini"
    assert match.deciding_set_format == "super_tiebreak"
    assert match.history.config is config


def test_match_configuration_property_setters():
    match = Match()
    
    match.best_of_sets = 5
    match.advantage_method = "gold_point"
    match.set_format = "mini"
    match.deciding_set_format = "super_tiebreak"
    
    assert match.config.best_of_sets == 5
    assert match.config.advantage_method == "gold_point"
    assert match.config.set_format == "mini"
    assert match.config.deciding_set_format == "super_tiebreak"
    
    assert match.history.config.best_of_sets == 5
    assert match.history.config.advantage_method == "gold_point"
    assert match.history.config.set_format == "mini"
    assert match.history.config.deciding_set_format == "super_tiebreak"



