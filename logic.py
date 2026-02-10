# logic.py
import itertools
import random
from database import get_player_stats

def get_best_combinations(selected_players, force_split=None, force_together=None, metric="overall"):
    """
    Generates balanced team combinations.
    force_split: A list of 2 player names that MUST be on opposite teams.
    force_together: A list of player names that MUST be on the same team.
    metric: The dataframe column to use for balancing (default: 'overall', can be 'avg_kd' or 'hltv').
    """
    df = get_player_stats()
    subset = df[df['name'].isin(selected_players)].copy()
    
    # Select scoring metric
    if metric == "avg_kd":
        # Ensure we don't have NaNs for logic
        subset['avg_kd'] = subset['avg_kd'].fillna(0.0)
        scores = dict(zip(subset['name'], subset['avg_kd']))
    elif metric == "hltv":
        subset['avg_rating'] = subset['avg_rating'].fillna(1.0)
        scores = dict(zip(subset['name'], subset['avg_rating']))
    else:
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

        # 2. Force Together Check (e.g. Chajra & Ghoufa -> Must be on same team)
        if force_together:
            # Normalize to list of lists if single list of strings provided
            groups = []
            if isinstance(force_together[0], list):
                groups = force_together
            else:
                groups = [force_together]
            
            is_split = False
            for group in groups:
                 if len(group) < 2: continue
                 
                 # Check if this specific group is split
                 # To be valid, ALL members of the group present in the draft must be in T1 
                 # OR ALL members must be in T2.
                 
                 # Filter group members that are actually in the current selection
                 # (Just in case a roommate isn't playing today)
                 active_members = [p for p in group if p in selected_players]
                 if len(active_members) < 2: continue

                 in_t1 = any(p in team1 for p in active_members)
                 in_t2 = any(p in team2 for p in active_members)
                 
                 if in_t1 and in_t2:
                     is_split = True
                     break
            
            if is_split:
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
