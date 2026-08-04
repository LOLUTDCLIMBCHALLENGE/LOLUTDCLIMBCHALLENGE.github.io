import requests
import time
import csv
import os

# api key and headers for Riot API requests
# API KEY THING
headers = {"X-Riot-Token": api_key}

# base urls for Riot API endpoints
account_base = "https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/"
league_base = "https://na1.api.riotgames.com/lol/league/v4/entries/by-puuid/"
summoner_base = "https://na1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/"
players = []

# Riot returns tier as ALLCAPS ("EMERALD") and division as roman numerals ("IV").
# The JS output wants Title Case tiers and numeric divisions.
DIVISION_TO_NUM = {"I": 1, "II": 2, "III": 3, "IV": 4}


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
    Name = ""
    StartingRank = 0
    StartingWins = 0
    StartingLosses = 0
    CurrentRankValue = 0
    CurrentRankTier = ""
    CurrentRankDivision = ""
    CurrentRankLP = 0
    CurrentWins = 0
    CurrentLosses = 0
    iconID = 29

    def __init__(self, name, StartingRank, StartingWins, StartingLosses):
        self.Name = name
        self.StartingRank = int(StartingRank)
        self.StartingWins = int(StartingWins)
        self.StartingLosses = int(StartingLosses)


csv_path = r"C:\Users\tcfal\Desktop\fALSE\startingData.csv"

with open(csv_path, newline="", encoding="utf-8") as f:
    reader = csv.reader(f)
    for row in reader:
        newPlayer = player(row[1], row[3], int(row[4]), int(row[5]))
        players.append(newPlayer)


for user in players:
    username = user.Name
    # Step 1: Riot ID -> PUUID
    acc_resp = requests.get(account_base + username, headers=headers)
    # if request fails, print error
    if acc_resp.status_code != 200:
        print(f"{username} -> Error fetching account: {acc_resp.status_code} {acc_resp.text}")
        continue

    puuid = acc_resp.json()["puuid"]
    time.sleep(1.2)

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

    #time.sleep(1.2)

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
        print(f"{user.Name} Current Rank: {user.CurrentRankValue}")
        print(f"{user.Name} Starting Rank: {user.StartingRank}")
        user.CurrentWins = wins
        user.CurrentLosses = losses
        print(f"{user.Name} LP Change: {user.CurrentRankValue - user.StartingRank} — {user.CurrentWins - user.StartingWins}W/{user.CurrentLosses - user.StartingLosses}L")
        print(f"{user.Name} Icon ID: {user.iconID}")
        print()

    time.sleep(1.2)


# --- Write results to a .txt file as JS-style object literals ---
def format_player_js(p):
    """
    Builds one line like:
    { time: null, riotId: "Eyren#Eyren", profileIconId: 4568, tier: "Emerald",
      division: 4, lp: 95, lpGained: 40, wins: 3, losses: 1 },
    """
    tier_title = p.CurrentRankTier.title() if p.CurrentRankTier else "Unranked"
    division_num = DIVISION_TO_NUM.get(p.CurrentRankDivision, 0)
    lp_gained = p.CurrentRankValue - p.StartingRank
    wins_gained = p.CurrentWins - p.StartingWins
    losses_gained = p.CurrentLosses - p.StartingLosses

    riot_id1 = p.Name.split("/")
    riot_id_escaped = riot_id1[0]+"#"+riot_id1[1]

    return (
        "{ time: null, "
        f'riotId: "{riot_id_escaped}", '
        f"profileIconId: {p.iconID}, "
        f'tier: "{tier_title}", '
        f"division: {division_num}, "
        f"lp: {p.CurrentRankLP}, "
        f"lpGained: {lp_gained}, "
        f"wins: {wins_gained}, "
        f"losses: {losses_gained} }},"
    )


output_path = os.path.abspath("CurrentData.txt")

with open(output_path, "a", newline="", encoding="utf-8") as f:
    for p in players:
        f.write(format_player_js(p) + "\n")

print(f"\n Results written to: {output_path}")
