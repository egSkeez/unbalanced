
import sys
from cybershoke import get_lobby_player_stats

def check_web_stats(match_id):
    print(f"Checking web stats for {match_id}...")
    stats = get_lobby_player_stats(match_id)
    if stats:
        print("Found stats:")
        for p, k in stats.items():
            print(f"  {p}: {k} kills")
    else:
        print("No stats found or parsing failed.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        check_web_stats(sys.argv[1])
    else:
        print("Usage: python verify_web_stats.py <match_id>")
