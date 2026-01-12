# --- INITIAL DATA & CONSTANTS ---
PLAYERS_INIT = {
    "Skeez": {"aim": 9, "util": 8, "team": 9, "elo": 1800},
    "Kim": {"aim": 6.5, "util": 8, "team": 8, "elo": 1500},
    "Ghoufa": {"aim": 7, "util": 6, "team": 8, "elo": 1450},
    "Borri": {"aim": 10, "util": 6, "team": 4, "elo": 1600},
    "Gasta": {"aim": 6, "util": 5, "team": 5, "elo": 1300},
    "Didi": {"aim": 5, "util": 3, "team": 4, "elo": 1200},
    "Zebda": {"aim": 3, "util": 2, "team": 3, "elo": 1100},
    "Kfox": {"aim": 2.5, "util": 1, "team": 5, "elo": 1050},
    "Chab": {"aim": 8, "util": 6, "team": 5, "elo": 1400},
    "Amen": {"aim": 8.5, "util": 6, "team": 7, "elo": 1550},
    "Jridi": {"aim": 2.5, "util": 2, "team": 3, "elo": 1000},
    "Bobista": {"aim": 5, "util": 5, "team": 4, "elo": 1250},
    "Zbat": {"aim": 7.5, "util": 4, "team": 5, "elo": 1350},
    "Chajra": {"aim": 5, "util": 3, "team": 4, "elo": 1200},
    "Skan": {"aim": 2, "util": 2, "team": 2, "elo": 900},
    "Zak": {"aim": 6.5, "util": 6, "team": 6, "elo": 1450}
}

SKEEZ_TITLES = ["The Best", "The One and Only", "The GOAT", "Headshot Machine", "The Prophet", "Moulay El Malik", "Daddy", "El Ostoura", "Number One", "Unfair", "Ycheati", "The Champ", "Kais Saayed", "El Capo", "El Don", "The problem"]

TEAM_NAMES = [
    "Team 9tates", "Team Dwe El Far", "Kimkim", "Team El Wawa", "Teamspeak", 
    "Teamesta", "Team haw Ybi3 Fel Birra Walla Rabi Maah", "JSK", "ASM", 
    "Wariors Can Dance", "Team Maymesech", "Team Unbalanced", 
    "Team Mefihech Borri", "Team Nchalah Moch M3a Borri", "Team No Push", 
    "Team Top Mid", "Team Je Smoke Pas", "Team Push mid", "Ah!", "Team Dont Shoot", 
    "Friendly", "Headshot Fel Ras", "Amen Yezzi", "Massadni", "Nikni But Dont Zeus Me", "El Bidha Mon Amour (Couca)", "Team Tmarti9", "Ya Didi Meghir Push", "Kimkim", "FREE PALESTINE"
]

MAP_POOL = ["Dust2", "Mirage", "Nuke", "Anubis", "Overpass", "Ancient", "Inferno"]
MAP_LOGOS = {m: f"https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main/images/de_{m.lower()}.png" for m in MAP_POOL}
