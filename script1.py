import asyncio, coc, json, os
from datetime import datetime, timedelta, timezone


datetime.now(timezone.utc)
today = datetime.now(timezone.utc).date().isoformat()

report = {"timestamp": datetime.now(timezone.utc).isoformat(), "members": {}}


EMAIL = "maximushorstkarlkurt@gmail.com"
APITOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiIsImtpZCI6IjI4YTMxOGY3LTAwMDAtYTFlYi03ZmExLTJjNzQzM2M2Y2NhNSJ9.eyJpc3MiOiJzdXBlcmNlbGwiLCJhdWQiOiJzdXBlcmNlbGw6Z2FtZWFwaSIsImp0aSI6ImUyYjQ2YmZiLWM5NGMtNDJjNS05NmI0LTY2NjA2NDM5MjhjNiIsImlhdCI6MTc1MTU0OTE5OSwic3ViIjoiZGV2ZWxvcGVyLzI0NDA4M2E1LWY4ZjEtMWUwYy05MmU4LTQxYzBjODEyZmU5ZiIsInNjb3BlcyI6WyJjbGFzaCJdLCJsaW1pdHMiOlt7InRpZXIiOiJkZXZlbG9wZXIvc2lsdmVyIiwidHlwZSI6InRocm90dGxpbmcifSx7ImNpZHJzIjpbIjkzLjIzOC43NS40NSJdLCJ0eXBlIjoiY2xpZW50In1dfQ.pwSYwLycrg3-2fPvcemgylLNjbNDI4-heCetNjeSmsGGSFK8OoNlV_B-YPpjFTMwJSNo-tGDVqVdNpqqTqoqhw"

ACTIVE_THRESHOLD = timedelta(days=3)
DATA_DIR = "clan_snapshots"
os.makedirs(DATA_DIR, exist_ok=True)

async def collect_war_data(client, clan):
    missed_attacks = {}
    total_attacks = 0
    war_attacks_per_player = {}

    try:
        war = await client.get_current_war(clan.tag)
        if war.state != "notInWar":
            for member in war.members:
                tag = member.tag
                attacks_used = len(member.attacks) if member.attacks else 0
                expected = war.attacks_per_member
                total_attacks += attacks_used
                war_attacks_per_player[tag] = attacks_used
                if attacks_used < expected:
                    missed_attacks[tag] = expected - attacks_used
    except (coc.PrivateWarLog, coc.NotFound):
        pass

    try:
        league_group = await client.get_league_group(clan.tag)
        if league_group.state != "notInWar":
            for round in league_group.rounds:
                for war_tag in round:
                    try:
                        war = await client.get_league_war(war_tag)
                        for member in war.members:
                            tag = member.tag
                            attacks_used = len(member.attacks) if member.attacks else 0
                            war_attacks_per_player[tag] = war_attacks_per_player.get(tag, 0) + attacks_used
                            if attacks_used < war.attacks_per_member:
                                missed_attacks[tag] = missed_attacks.get(tag, 0) + (war.attacks_per_member - attacks_used)
                    except coc.NotFound:
                        continue
    except coc.NotFound:
        pass

    return war_attacks_per_player, missed_attacks

async def collect_data(client, clan_tag):
    clan = await client.get_clan(clan_tag)
    war_attacks, missed = await collect_war_data(client, clan)

    report = {"timestamp": datetime.now(timezone.utc).isoformat(), "members": {}}
    for mem in clan.members:
        tag = mem.tag

        report["members"][tag] = {
            "name": mem.name,
            "tag": mem.tag,
            "town_hall": mem.town_hall,
            "exp_level": mem.exp_level,
            "trophies": mem.trophies,
            "donations": mem.donations,
            "role": str(mem.role),
            "clan_rank": mem.clan_rank,
            "clan_previous_rank": mem.clan_previous_rank,
            "war_attacks": war_attacks.get(tag, 0),  # add war attacks count, default 0
            # If you have war stars, add here similarly, else set to 0
            "war_stars": 0
        }
    return report, missed


def update_timeline(data):
    today = datetime.utcnow().date().isoformat()
    timeline_path = os.path.join(DATA_DIR, "timeline.json")

    if os.path.exists(timeline_path):
        with open(timeline_path, "r") as f:
            timeline_data = json.load(f)
    else:
        timeline_data = {}


    for tag, stats in data["members"].items():

        if tag not in timeline_data:
            timeline_data[tag] = {
                "name": stats["name"],
                "timeline": []
            }
        timeline_data[tag]["timeline"].append({
            "date": today,
            "donations": stats.get("donations", 0),
            "trophies": stats.get("trophies", 0),
            "war_attacks": stats.get("war_attacks", 0),
            "war_stars": stats.get("war_stars", 0)
        })


    with open(timeline_path, "w") as f:
        json.dump(timeline_data, f, indent=2)

async def main():
    async with coc.Client() as client:
        print("Logging in to Clash of Clans API...")
        await client.login("maximushorstkarlkurt@gmail.com", "0ZgN$X3$1jn%AJrngDvV")
        print("Logged in successfully.")
        data, missed = await collect_data(client, "#2JP2JRP92")  # replace with your clan tag
        print(f"Collected data for {len(data['members'])} members.")

        now = datetime.fromisoformat(data["timestamp"])
        promo = []
        inactive = []

        update_timeline(data)

        for tag, m in data["members"].items():
            active = m["donations"] > 0 or m["war_attacks"] > 0
            if not active:
                last_active = now - timedelta(days=1)
            else:
                last_active = now

            m.update({
                "inactive": (now - last_active) > ACTIVE_THRESHOLD,
                "progress_bar": f"{m['trophies']}/5000"
            })

            if m["inactive"]:
                inactive.append(m["name"])
            if m["donations"] > 500 or m["war_stars"] > 3:
                promo.append(m["name"])
            if tag in missed:
                m["missed_attacks"] = missed[tag]

        # Save final report
        with open("clan_report.json", "w") as f:
            json.dump({
                "data": data,
                "promote": promo,
                "inactive": inactive,
                "timestamp": now.isoformat()
            }, f, indent=2)

        # Optional: save today's snapshot
        today_path = os.path.join(DATA_DIR, f"{now.date().isoformat()}.json")
        with open(today_path, "w") as f:
            json.dump(data, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())


import subprocess

# After your main script work:
subprocess.run(["git", "add", "."])
subprocess.run(["git", "commit", "-m", "Auto commit from scheduled script"])
subprocess.run(["git", "push"])
