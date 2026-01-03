# cybershoke.py
import sqlite3

def init_cybershoke_db():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    # Table to store the active lobby link
    c.execute('''CREATE TABLE IF NOT EXISTS active_lobby 
                 (id INTEGER PRIMARY KEY, url TEXT)''')
    conn.commit()
    conn.close()

def set_lobby_link(url):
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("DELETE FROM active_lobby") # Clear old lobbies
    c.execute("INSERT INTO active_lobby (id, url) VALUES (1, ?)", (url,))
    conn.commit()
    conn.close()

def get_lobby_link():
    conn = sqlite3.connect('cs2_history.db')
    c = conn.cursor()
    c.execute("SELECT url FROM active_lobby WHERE id=1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def clear_lobby_link():
    conn = sqlite3.connect('cs2_history.db')
    conn.execute("DELETE FROM active_lobby")
    conn.commit()
    conn.close()
