import sqlite3

def update_names():
    db_path = 'cs2_history.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Mapping relative to user request
    # Old Name -> New Name
    name_map = {
        "Ghoufa": "magon",
        "Borri": "zugzwxng",
        "3omda": "hiyox",
        "Gasta": "Gastafix",
        "Zak": "zak",
        "Chajra": "jardin public",
        "Zbat": "zbat",
        "Kfox": "ABU_GHALI",
        "Didi": "walker-bassit",
        "Zebda": "Ta9ess",
        "Chab": "Tbastina"
    }

    print("Updating player names in database...")
    for old, new in name_map.items():
        # Check if old name exists
        c.execute("SELECT name FROM players WHERE name = ?", (old,))
        if c.fetchone():
            print(f"Updating {old} -> {new}")
            try:
                # Update name in players table
                # We use UPDATE OR IGNORE or handle constraint if new name already exists (unlikely given the list)
                c.execute("UPDATE players SET name = ? WHERE name = ?", (new, old))
                
                # Also update player_match_stats if we have historical stats linked by name
                # (Though match stats might come from demos with the NEW name already, 
                # but if we have old manual records or older analyses with the old name)
                c.execute("UPDATE player_match_stats SET player_name = ? WHERE player_name = ?", (new, old))
                
            except sqlite3.IntegrityError as e:
                print(f"Skipping {old} -> {new}: New name might already exist? {e}")
        else:
            print(f"Player {old} not found in players table.")

    conn.commit()
    conn.close()
    print("Database update complete.")

if __name__ == "__main__":
    update_names()
