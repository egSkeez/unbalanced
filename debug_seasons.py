
import sqlite3
import pandas as pd

def check_season2():
    conn = sqlite3.connect('cs2_history.db')
    
    print("--- Season 2 (>= 2026-01-01) ---")
    query = '''
        SELECT 
            pms.player_name,
            COUNT(*) as matches,
            ROUND(AVG(NULLIF(pms.rating, 0)), 2) as rating
        FROM player_match_stats pms
        JOIN match_details md ON pms.match_id = md.match_id
        WHERE date(md.date_analyzed) >= '2026-01-01'
        GROUP BY pms.player_name
    '''
    df = pd.read_sql_query(query, conn)
    print(df)

    print("\n--- Season 1 (< 2026-01-01) ---")
    query_s1 = '''
        SELECT 
            pms.player_name,
            COUNT(*) as matches,
            ROUND(AVG(NULLIF(pms.rating, 0)), 2) as rating
        FROM player_match_stats pms
        JOIN match_details md ON pms.match_id = md.match_id
        WHERE date(md.date_analyzed) < '2026-01-01'
        GROUP BY pms.player_name
        LIMIT 10
    '''
    df_s1 = pd.read_sql_query(query_s1, conn)
    print(df_s1)

    conn.close()

if __name__ == "__main__":
    check_season2()
