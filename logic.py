# logic.py
import sqlite3
import itertools
import random

# logic.py
# ... (Keep your existing get_best_combinations function) ...

def pick_captains(team1, team2):
    import random
    return random.choice(team1), random.choice(team2)

def get_best_combinations(active_names):
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    player_data = []
    for n in active_names:
        stats = c.execute("SELECT aim, util, team_play FROM players WHERE name=?", (n,)).fetchone()
        # Your specific weighting: 0.5 Aim, 0.3 Util, 0.2 TeamPlay
        power = (stats[0]*0.5 + stats[1]*0.3 + stats[2]*0.2)
        player_data.append({'name': n, 'power': power})
    conn.close()

    roommates = {"Ghoufa", "Chajra"}
    valid_combinations = []
    
    for combo_indices in itertools.combinations(range(10), 5):
        t1 = [player_data[i] for i in combo_indices]
        t2 = [player_data[i] for i in range(10) if i not in combo_indices]
        
        t1_names = [p['name'] for p in t1]
        t2_names = [p['name'] for p in t2]
        
        active_rm = roommates.intersection(set(active_names))
        if len(active_rm) == 2:
            if not (all(rm in t1_names for rm in active_rm) or all(rm in t2_names for rm in active_rm)):
                continue
        
        p1_sum = sum(p['power'] for p in t1)
        p2_sum = sum(p['power'] for p in t2)
        
        # Calculate averages
        avg1 = round(p1_sum / 5, 2)
        avg2 = round(p2_sum / 5, 2)
        gap = abs(p1_sum - p2_sum)
        
        valid_combinations.append((t1_names, t2_names, avg1, avg2, round(gap, 2)))

    valid_combinations.sort(key=lambda x: x[4])
    return valid_combinations
