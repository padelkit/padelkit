from padelkit.scoring import MatchScoreHistory, TeamId


def test_initial_score():
    history = MatchScoreHistory()
    score = history.get_current_score()
    assert (score.points_A, score.points_B) == (0, 0)
    assert score.games_A == 0
    assert score.games_B == 0


def test_point_progression():
    history = MatchScoreHistory()
    
    score = history.add_point(TeamId.A)
    assert (score.points_A, score.points_B) == (15, 0)
    
    score = history.add_point(TeamId.B)
    assert (score.points_A, score.points_B) == (15, 15)
    
    score = history.add_point(TeamId.A)
    assert (score.points_A, score.points_B) == (30, 15)
    
    score = history.add_point(TeamId.A)
    assert (score.points_A, score.points_B) == (40, 15)


def test_game_win():
    history = MatchScoreHistory()
    for _ in range(3):
        history.add_point(TeamId.A)
    
    score = history.add_point(TeamId.A)
    assert score.games_A == 1
    assert score.games_B == 0
    assert (score.points_A, score.points_B) == (0, 0)


def test_deuce_and_advantage():
    history = MatchScoreHistory()
    
    # Get to 40-40
    for _ in range(3):
        history.add_point(TeamId.A)
        history.add_point(TeamId.B)
        
    score = history.get_current_score()
    assert (score.points_A, score.points_B) == (40, 40)
    
    # A gets advantage
    score = history.add_point(TeamId.A)
    assert (score.points_A, score.points_B) == ("AD", 40)
    
    # B ties (back to deuce)
    score = history.add_point(TeamId.B)
    assert (score.points_A, score.points_B) == (40, 40)
    
    # B gets advantage
    score = history.add_point(TeamId.B)
    assert (score.points_A, score.points_B) == (40, "AD")
    
    # B wins game
    score = history.add_point(TeamId.B)
    assert score.games_A == 0
    assert score.games_B == 1
    assert (score.points_A, score.points_B) == (0, 0)


def test_set_win():
    history = MatchScoreHistory()
    
    # Team A wins 6 games straight
    for _ in range(5):
        for _ in range(4):
            history.add_point(TeamId.A)
            
    # Last game to win the set
    for _ in range(3):
        history.add_point(TeamId.A)
    score = history.add_point(TeamId.A)
            
    assert score.sets_A == 1
    assert score.sets_B == 0
    assert score.completed_sets == [(6, 0)]


def test_modify_point():
    history = MatchScoreHistory()
    history.add_point(TeamId.A)
    history.add_point(TeamId.B)
    history.add_point(TeamId.A)
    
    score = history.get_current_score()
    assert (score.points_A, score.points_B) == (30, 15)
    
    # Modify second point (index 1) to be won by A instead of B
    score = history.modify_point(1, TeamId.A)
    assert (score.points_A, score.points_B) == (40, 0)
