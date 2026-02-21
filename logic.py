# logic.py
import itertools
import random
import statistics
from database import get_player_stats

def get_best_combinations(
    selected_players,
    force_split=None,
    force_together=None,
    metric="overall",
    force_split_pairs=None,
    variance_weight=0.0,
):
    """
    Generates balanced team combinations.

    force_split:       [p1, p2] — these two players must be on opposite teams.
    force_split_pairs: [(p1,p2),(p3,p4)] — each pair must be on opposite teams.
    force_together:    list of player groups that must stay on the same team.
    metric:            scoring column — 'overall', 'avg_kd', or 'hltv'.
    variance_weight:   when > 0, penalises differences in within-team score
                       spread so both teams are internally even, not just
                       equal on average.
    """
    df = get_player_stats()
    subset = df[df['name'].isin(selected_players)].copy()

    if metric == "avg_kd":
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

        # 1. Legacy single force-split pair
        if force_split and len(force_split) == 2:
            p1, p2 = force_split
            if (p1 in team1 and p2 in team1) or (p1 in team2 and p2 in team2):
                continue

        # 2. Multiple force-split pairs (e.g. top-4 distributed as two pairs)
        if force_split_pairs:
            invalid = False
            for p1, p2 in force_split_pairs:
                if p1 not in selected_players or p2 not in selected_players:
                    continue
                if (p1 in team1 and p2 in team1) or (p1 in team2 and p2 in team2):
                    invalid = True
                    break
            if invalid:
                continue

        # 3. Force Together Check
        if force_together:
            groups = force_together if isinstance(force_together[0], list) else [force_together]
            is_split = False
            for group in groups:
                if len(group) < 2:
                    continue
                active_members = [p for p in group if p in selected_players]
                if len(active_members) < 2:
                    continue
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
        sum_diff = abs(s1 - s2)

        if variance_weight > 0:
            t1_scores = [scores[p] for p in team1]
            t2_scores = [scores[p] for p in team2]
            var1 = statistics.variance(t1_scores) if len(t1_scores) > 1 else 0
            var2 = statistics.variance(t2_scores) if len(t2_scores) > 1 else 0
            diff = sum_diff + variance_weight * abs(var1 - var2)
        else:
            diff = sum_diff

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
