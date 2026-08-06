import requests
import time
import csv
import os
import json
import datetime

# API key comes from an environment variable — set as a GitHub Actions secret
# named RIOT_API_KEY. Never hardcode the key in this file.
api_key = os.environ.get("RIOT_API_KEY")
if not api_key:
    raise SystemExit("RIOT_API_KEY environment variable is not set.")

headers = {"X-Riot-Token": api_key}

# base urls for Riot API endpoints
account_base = "https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
league_base = "https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/"
summoner_base = "https://na1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/"
players = []

# Riot returns tier as ALLCAPS ("EMERALD") and division as roman numerals ("IV").
# The JS/JSON output wants Title Case tiers and numeric divisions.
DIVISION_TO_NUM = {"I": 1, "II": 2, "III": 3, "IV": 4}
MASTER_PLUS_TIERS = {"MASTER", "GRANDMASTER", "CHALLENGER"}


def convertRank(rank):
    rankParts = rank.split(" ")
    totalRank = 0

    rank1 = rankParts[0].upper()
    if rank1.startswith("IRON"):
        totalRank = 0
    elif rank1.startswith("BRONZE"):
        totalRank = 400
    elif rank1.startswith("SILVER"):
        totalRank = 800
    elif rank1.startswith("GOLD"):
        totalRank = 1200
    elif rank1.startswith("PLATINUM"):
        totalRank = 1600
    elif rank1.startswith("EMERALD"):
        totalRank = 2000
    elif rank1.startswith("DIAMOND"):
        totalRank = 2400
    elif rank1.startswith("MASTER"):
        totalRank = 2800
    elif rank1.startswith("GRANDMASTER"):
        totalRank = 2800
    elif rank1.startswith("CHALLENGER"):
        totalRank = 2800

    rank2 = rankParts[1].upper()
    division_map = {"I": 1, "II": 2, "III": 3, "IV": 4}
    if rank2 in division_map:
        totalRank += (4 - division_map[rank2]) * 100
        rank3 = int(rankParts[2])
    else:
        rank3 = int(rank2)

    totalRank += rank3
    return totalRank


class player:
    def __init__(self, name, StartingRank, StartingWins, StartingLosses):
        self.Name = name
        self.StartingRank = int(StartingRank)
        self.StartingWins = int(StartingWins)
        self.StartingLosses = int(StartingLosses)
        self.CurrentRankValue = 0
        self.CurrentRankTier = ""
        self.CurrentRankDivision = ""
        self.CurrentRankLP = 0
        self.CurrentWins = 0
        self.CurrentLosses = 0
        self.iconID = 29


# Relative path — works both locally (run from repo root) and in GitHub Actions
csv_path = os.path.join(os.path.dirname(__file__), "data", "startingData.csv")

with open(csv_path, newline="", encoding="utf-8") as f:
    reader = csv.reader(f)
    for row in reader:
        newPlayer = player(row[1], row[3], int(row[4]), int(row[5]))
        players.append(newPlayer)


# --- Load the previous data.json (if it exists) so we can carry forward
# whether each player has EVER reached Master+ during the challenge.
# Without this, every run would only know the player's CURRENT tier,
# and someone who hit Master then dropped back to Diamond would lose the flag.
output_path = os.path.join(os.path.dirname(__file__), "data", "data.json")
previous_master_flags = {}

if os.path.exists(output_path):
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            prev_data = json.load(f)
            for pd in prev_data.get("players", []):
                previous_master_flags[pd["riotId"]] = pd.get("reachedMaster", False)
    except (json.JSONDecodeError, KeyError):
        # If the old file is missing/corrupt, just start fresh — don't crash the run
        previous_master_flags = {}


for user in players:
    username = user.Name
    # Step 1: Riot ID -> PUUID
    acc_resp = requests.get(account_base + username, headers=headers)
    if acc_resp.status_code != 200:
        print(f"{username} -> Error fetching account: {acc_resp.status_code} {acc_resp.text}")
        continue

    puuid = acc_resp.json()["puuid"]

    # Step 2: PUUID -> ranked entries
    rank_resp = requests.get(league_base + puuid, headers=headers)
    if rank_resp.status_code != 200:
        print(f"{username} -> Error fetching rank: {rank_resp.status_code} {rank_resp.text}")
        continue

    entries = rank_resp.json()
    solo_entry = next((e for e in entries if e["queueType"] == "RANKED_SOLO_5x5"), None)

    # Step 3: PUUID -> summoner data (for icon ID)
    summ_resp = requests.get(summoner_base + puuid, headers=headers)
    if summ_resp.status_code != 200:
        print(f"{username} -> Error fetching icon: {summ_resp.status_code} {summ_resp.text}")
    else:
        user.iconID = summ_resp.json()["profileIconId"]

    if solo_entry is None:
        print(f"{username} -> Unranked in Solo/Duo")
    else:
        tier = solo_entry["tier"]
        rank = solo_entry["rank"]
        lp = solo_entry["leaguePoints"]
        wins = solo_entry["wins"]
        losses = solo_entry["losses"]

        user.CurrentRankTier = tier
        user.CurrentRankDivision = rank
        user.CurrentRankLP = lp
        user.CurrentRankValue = convertRank(f"{tier} {rank} {lp}")
        user.CurrentWins = wins
        user.CurrentLosses = losses
        print(f"{user.Name}: {user.CurrentRankValue - user.StartingRank} pts, "
              f"{user.CurrentWins - user.StartingWins}W/{user.CurrentLosses - user.StartingLosses}L")

    time.sleep(1.2)


# --- Build JSON output matching the shape index.html expects ---
def player_to_dict(p):
    tier_title = p.CurrentRankTier.title() if p.CurrentRankTier else "Unranked"
    division_num = DIVISION_TO_NUM.get(p.CurrentRankDivision, 0)
    lp_gained = p.CurrentRankValue - p.StartingRank
    wins_gained = p.CurrentWins - p.StartingWins
    losses_gained = p.CurrentLosses - p.StartingLosses

    riot_id1 = p.Name.split("/")
    riot_id_escaped = riot_id1[0] + "#" + riot_id1[1]

    reached_master_now = p.CurrentRankTier.upper() in MASTER_PLUS_TIERS if p.CurrentRankTier else False
    reached_master_ever = previous_master_flags.get(riot_id_escaped, False) or reached_master_now

    return {
        "time": None,
        "riotId": riot_id_escaped,
        "profileIconId": p.iconID,
        "tier": tier_title,
        "division": division_num,
        "lp": p.CurrentRankLP,
        "lpGained": lp_gained,
        "wins": wins_gained,
        "losses": losses_gained,
        "reachedMaster": reached_master_ever,
    }


output_data = {
    "lastUpdated": datetime.datetime.utcnow().isoformat() + "Z",
    "players": [player_to_dict(p) for p in players],
}

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2)

print(f"\nResults written to: {output_path}")
