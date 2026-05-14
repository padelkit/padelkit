from padelkit.scoring import Match, TeamId, Team, Player

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
