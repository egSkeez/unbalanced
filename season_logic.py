from datetime import date
import sqlite3
import pandas as pd

def get_current_season_info():
    """
    Returns (season_name, start_date, end_date) for the current season.
    """
    today = date.today()
    # Season 2 2026 Logic: Jan 1 2026 - Mar 31 2026 (User Override)
    # The user said "New season started 1st Jan 2026 end of March" -> Is this Season 2?
    # User said "The current season is season 2... matches manually added... are from season 1".
    
    # Let's align with user's specific naming:
    # Season 1: < Jan 1 2026
    # Season 2: Jan 1 2026 - Mar 31 2026
    
    if today >= date(2026, 1, 1) and today <= date(2026, 3, 31):
        return "Season 2", date(2026, 1, 1), date(2026, 3, 31)
    
    # Future/Generic Logic if outside that range
    return f"Season {((today.month-1)//3)+1} {today.year}", date(today.year, 1, 1), date(today.year, 12, 31)

def get_all_seasons():
    """
    Returns a dictionary of Season Name -> (start_date, end_date)
    Special handling: start_date=None means 'Beginning of time'
    """
    return {
        "Season 1 (Manual)": (None, date(2025, 12, 31)),
        "Season 2 (Demos)": (date(2026, 1, 1), date(2026, 3, 31)),
        # Add filtering for "All Time" handled in UI logic, usually combining both or showing raw tables
    }
