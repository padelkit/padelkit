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


def test_gold_point():
    # 40-40, then golden point decides the game without AD
    history = MatchScoreHistory(advantage_method="gold_point")
    
    # Get to 40-40 (3-3)
    for _ in range(3):
        history.add_point(TeamId.A)
        history.add_point(TeamId.B)
        
    score = history.get_current_score()
    assert (score.points_A, score.points_B) == (40, 40)
    assert score.is_gold_point is True
    
    # Next point won by B wins game directly
    score = history.add_point(TeamId.B)
    assert score.games_B == 1
    assert score.games_A == 0
    assert (score.points_A, score.points_B) == (0, 0)
    assert score.is_gold_point is False


def test_mini_set():
    # Mini set format to 4 games. At 4-4, plays tie-break.
    history = MatchScoreHistory(set_format="mini")
    
    # A wins 3 games straight, B wins 3 games straight (score 3-3)
    for _ in range(3):
        for _ in range(4):
            history.add_point(TeamId.A)
        for _ in range(4):
            history.add_point(TeamId.B)
            
    score = history.get_current_score()
    assert score.games_A == 3
    assert score.games_B == 3
    
    # A wins game 4 -> 4-3
    for _ in range(4):
        history.add_point(TeamId.A)
    score = history.get_current_score()
    assert score.games_A == 4
    assert score.games_B == 3
    assert score.completed_sets == [] # Not won yet (needs diff 2, or tie-break)
    
    # B wins game 4 -> 4-4, should enter tie-break
    for _ in range(4):
        history.add_point(TeamId.B)
    score = history.get_current_score()
    assert score.games_A == 4
    assert score.games_B == 4
    assert score.in_tiebreak is True
    
    # Play tie-break to 7 points with difference of 2. Let's make B win 7-5.
    # Points 1-5 to A, 1-7 to B
    for _ in range(5):
        history.add_point(TeamId.A)
        history.add_point(TeamId.B)
    # Score is 5-5. B wins two more points.
    history.add_point(TeamId.B)
    score = history.add_point(TeamId.B)
    
    assert score.completed_sets == [(4, 5)] # B wins mini set 5-4
    assert score.sets_B == 1
    assert score.in_tiebreak is False


def test_deciding_set_tiebreak():
    # Best of 3. Deciding set format = "tiebreak" (7 points)
    history = MatchScoreHistory(best_of_sets=3, deciding_set_format="tiebreak")
    
    # Set 1: A wins 6-0
    for _ in range(6):
        for _ in range(4):
            history.add_point(TeamId.A)
            
    # Set 2: B wins 6-0
    for _ in range(6):
        for _ in range(4):
            history.add_point(TeamId.B)
            
    score = history.get_current_score()
    assert score.sets_A == 1
    assert score.sets_B == 1
    assert score.completed_sets == [(6, 0), (0, 6)]
    # Since deciding_set_format is "tiebreak", before the first point is played,
    # the 3rd set should immediately be recognized as a tie-break!
    assert score.in_tiebreak is True
    assert score.games_A == 0
    assert score.games_B == 0
    
    # B wins 7-3 in tie-break
    for _ in range(3):
        history.add_point(TeamId.A)
        history.add_point(TeamId.B)
    # score is 3-3. B wins 4 more points to win the match tie-break.
    for _ in range(4):
        score = history.add_point(TeamId.B)
        
    assert score.sets_A == 1
    assert score.sets_B == 2
    assert score.completed_sets == [(6, 0), (0, 6), (0, 1)] # Replaces set final, games score 0-1
    assert score.in_tiebreak is False


def test_deciding_set_super_tiebreak():
    # Best of 3. Deciding set format = "super_tiebreak" (10 points)
    history = MatchScoreHistory(best_of_sets=3, deciding_set_format="super_tiebreak")
    
    # Set 1: A wins 6-0
    for _ in range(6):
        for _ in range(4):
            history.add_point(TeamId.A)
            
    # Set 2: B wins 6-0
    for _ in range(6):
        for _ in range(4):
            history.add_point(TeamId.B)
            
    score = history.get_current_score()
    assert score.sets_A == 1
    assert score.sets_B == 1
    # 3rd set starts directly as super tie-break
    assert score.in_super_tiebreak is True
    
    # Play to 10 points. Let's make A win 10-8.
    for _ in range(8):
        history.add_point(TeamId.A)
        history.add_point(TeamId.B)
    # 8-8. A wins 2 more points.
    history.add_point(TeamId.A)
    score = history.add_point(TeamId.A)
    
    assert score.sets_A == 2
    assert score.sets_B == 1
    assert score.completed_sets == [(6, 0), (0, 6), (1, 0)]
    assert score.in_super_tiebreak is False


def test_tiebreak_server_rotation():
    # In any tie-break, server alternates every 2 points after the first point.
    history = MatchScoreHistory(set_format="mini")
    
    # Get to 4-4 (A wins 4 games, B wins 4 games)
    for _ in range(4):
        for _ in range(4):
            history.add_point(TeamId.A)
        for _ in range(4):
            history.add_point(TeamId.B)
            
    score = history.get_current_score()
    assert score.in_tiebreak is True
    assert score.server is not None
    assert score.server.team == TeamId.A # 1st point served by Team A
    
    # Point 1 won by A. Score 1-0. points_played = 1.
    score = history.add_point(TeamId.A)
    assert score.server is not None
    assert score.server.team == TeamId.B # 2nd point served by Team B
    
    # Point 2 won by B. Score 1-1. points_played = 2.
    score = history.add_point(TeamId.B)
    assert score.server is not None
    assert score.server.team == TeamId.B # 3rd point served by Team B
    
    # Point 3 won by A. Score 2-1. points_played = 3.
    score = history.add_point(TeamId.A)
    assert score.server is not None
    assert score.server.team == TeamId.A # 4th point served by Team A
    
    # Point 4 won by B. Score 2-2. points_played = 4.
    score = history.add_point(TeamId.B)
    assert score.server is not None
    assert score.server.team == TeamId.A # 5th point served by Team A
    
    # Point 5 won by A. Score 3-2. points_played = 5.
    score = history.add_point(TeamId.A)
    assert score.server is not None
    assert score.server.team == TeamId.B # 6th point served by Team B

