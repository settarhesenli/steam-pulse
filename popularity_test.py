import sqlite3
import json
import urllib.request
import time

DB = "steam.db"
BATCH_SIZE = 100
DELAY = 1.0

def get_connection():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_appdetails(app_id):
    url = (
        f"https://store.steampowered.com/api/appdetails"
        f"?appids={app_id}&cc=us&l=en"
    )

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SteamPriceTracker/1.0"
        }
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)

conn = get_connection()

games = conn.execute("""
    SELECT app_id, name
    FROM games
    WHERE tracked = 0
      AND type = 'game'
      AND recommendation_count = 0
    ORDER BY app_id
    LIMIT ?
""", (BATCH_SIZE,)).fetchall()

print("=" * 60)
print("STEAM POPULARITY TEST")
print("=" * 60)
print("Games selected:", len(games))
print()

success = 0
failed = 0

for index, game in enumerate(games, 1):

    app_id = game["app_id"]
    name = game["name"]

    try:
        data = fetch_appdetails(app_id)

        item = data.get(str(app_id), {})

        if not item.get("success"):
            print(f"[{index}/{len(games)}] SKIP | {app_id} | {name}")
            failed += 1
            time.sleep(DELAY)
            continue

        details = item.get("data", {})

        recommendations = details.get("recommendations") or {}
        count = recommendations.get("total", 0)

        conn.execute("""
            UPDATE games
            SET recommendation_count = ?
            WHERE app_id = ?
        """, (count, app_id))

        conn.commit()

        print(
            f"[{index}/{len(games)}] "
            f"{app_id} | {name} | recommendations={count:,}"
        )

        success += 1

    except Exception as e:
        print(
            f"[{index}/{len(games)}] ERROR | "
            f"{app_id} | {name} | {e}"
        )
        failed += 1

    time.sleep(DELAY)

conn.close()

print()
print("=" * 60)
print("TEST FINISHED")
print("=" * 60)
print("Success:", success)
print("Failed:", failed)
print("=" * 60)
