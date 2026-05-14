from padelkit.scoring import MatchScore
from padelkit.scoring.score import TeamId


def test_initial_score():
    score = MatchScore()
    assert score.game_points == (0, 0)
    assert score.games_A == 0
    assert score.games_B == 0


def test_point_progression():
    score = MatchScore()
    score.point_won_by("A")
    assert score.game_points == (15, 0)
    score.point_won_by("B")
    assert score.game_points == (15, 15)
    score.point_won_by("A")
    assert score.game_points == (30, 15)
    score.point_won_by("A")
    assert score.game_points == (40, 15)


def test_game_win():
    score = MatchScore()
    for _ in range(4):
        score.point_won_by(TeamId.A)
    
    assert score.games_A == 1
    assert score.games_B == 0
    assert score.game_points == (0, 0)


def test_deuce_and_advantage():
    score = MatchScore()
    
    # Get to 40-40
    for _ in range(3):
        score.point_won_by("A")
        score.point_won_by("B")
        
    assert score.game_points == (40, 40)
    assert score.advantage is None
    
    # A gets advantage
    score.point_won_by("A")
    assert score.game_points == ("AD", 40)
    assert score.advantage == TeamId.A
    
    # B ties (back to deuce)
    score.point_won_by("B")
    assert score.game_points == (40, 40)
    assert score.advantage is None
    
    # B gets advantage
    score.point_won_by("B")
    assert score.game_points == (40, "AD")
    assert score.advantage == TeamId.B
    
    # B wins game
    score.point_won_by("B")
    assert score.games_A == 0
    assert score.games_B == 1
    assert score.game_points == (0, 0)


def test_set_win():
    score = MatchScore()
    
    # Team A wins 6 games straight
    for _ in range(6):
        for _ in range(4):
            score.point_won_by("A")
            
    assert score.sets_A == 1
    assert score.sets_B == 0
    assert score.completed_sets == [(6, 0)]
