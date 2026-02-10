
import sqlite3
import pandas as pd

def check_leaderboard():
    conn = sqlite3.connect('cs2_history.db')
    
    print("--- Simulating Leaderboard Query (Season 2) ---")
    # I'll just remove date filters to see if any data shows up at all first
    query = '''
        SELECT 
            pms.player_name,
            COUNT(*) as matches,
            ROUND(AVG(NULLIF(pms.rating, 0)), 2) as rating,
            SUM(pms.kills) as total_kills
        FROM player_match_stats pms
        JOIN match_details md ON pms.match_id = md.match_id
        GROUP BY pms.player_name
        HAVING matches >= 1
        ORDER BY rating DESC
        LIMIT 10
    '''
    df = pd.read_sql_query(query, conn)
    print(df)
    
    print("\n--- Check Dates of Valid Ratings ---")
    c = conn.cursor()
    c.execute('''
        SELECT md.date_analyzed, pms.rating 
        FROM player_match_stats pms
        JOIN match_details md ON pms.match_id = md.match_id
        WHERE pms.rating IS NOT NULL AND pms.rating > 0
        LIMIT 5
    ''')
    print(c.fetchall())

    conn.close()

if __name__ == "__main__":
    check_leaderboard()
