import sqlite3

def list_tables():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = c.fetchall()
    print("Tables:", [t[0] for t in tables])
    
    # Check if there is a table for matches/lobbies
    possible_tables = ['matches', 'lobbies', 'lobby_history', 'match_history']
    for t in tables:
        t_name = t[0]
        print(f"\n--- {t_name} Top 5 rows ---")
        try:
            c.execute(f"SELECT * FROM {t_name} LIMIT 5")
            cols = [description[0] for description in c.description]
            print("Columns:", cols)
            rows = c.fetchall()
            for row in rows:
                print(row)
        except Exception as e:
            print(f"Error reading {t_name}: {e}")
            
    conn.close()

if __name__ == "__main__":
    list_tables()
