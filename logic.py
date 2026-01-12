# logic.py
import itertools
import random
from database import get_player_stats

def get_best_combinations(selected_players, force_split=None, force_together=None):
    """
    Generates balanced team combinations.
    force_split: A list of 2 player names that MUST be on opposite teams.
    force_together: A list of player names that MUST be on the same team.
    """
    df = get_player_stats()
    subset = df[df['name'].isin(selected_players)].copy()
    scores = dict(zip(subset['name'], subset['overall']))
    
    all_combos = list(itertools.combinations(selected_players, 5))
    valid_combos = []
    
    for team1 in all_combos:
        team2 = [p for p in selected_players if p not in team1]
        
        # 1. Force Split Check (e.g. Top 2 players)
        if force_split and len(force_split) == 2:
            p1, p2 = force_split
            if (p1 in team1 and p2 in team1) or (p1 in team2 and p2 in team2):
                continue

        # 2. Force Together Check (e.g. Chajra & Ghoufa)
        if force_together and len(force_together) >= 2:
            # Check if the "together" group is split between t1 and t2
            # We check if some are in t1 and some are in t2
            in_t1 = any(p in team1 for p in force_together)
            in_t2 = any(p in team2 for p in force_together)
            
            # If present in both teams, it means they were split -> Invalid
            if in_t1 and in_t2:
                continue

        s1 = sum(scores[p] for p in team1)
        s2 = sum(scores[p] for p in team2)
        
        avg1 = s1 / 5
        avg2 = s2 / 5
        diff = abs(s1 - s2)
        
        valid_combos.append((list(team1), team2, avg1, avg2, diff))
    
    valid_combos.sort(key=lambda x: x[4])
    return valid_combos

def pick_captains(t1, t2):
    """
    Picks a RANDOM captain for each team.
    """
    return random.choice(t1), random.choice(t2)

def cycle_new_captain(team_list, current_captain):
    """
    Rotates the captaincy to the next player in the list.
    """
    if current_captain not in team_list:
        return team_list[0]
    
    # Create a list of potential captains excluding the current one
    candidates = [p for p in team_list if p != current_captain]
    
    if not candidates:
        return current_captain
        
    return random.choice(candidates)
