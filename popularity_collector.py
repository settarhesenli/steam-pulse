import sqlite3
import json
import urllib.request
import time
import re

DB = "steam.db"

BATCH_SIZE = 100
DELAY = 1.0
EMPTY_WAIT = 3600  # hamısı bitəndə 1 saat gözlə

EXCLUDE_RULES = [
    r"\bdlc\b",
    r"\bsoundtrack\b",
    r"\bseason\s+pass\b",
    r"\bexpansion\b",
    r"\bcharacter\s+pack\b",
    r"\bweapon\s+pack\b",
    r"\bcontent\s+pack\b",
    r"\bsupporter\s+pack\b",
    r"\badd[- ]on\b",
    r"\baddon\b",
    r"\bupgrade\b",
    r"\bbundle\b",
]


def is_excluded(name):
    name = name or ""
    return any(
        re.search(pattern, name, re.IGNORECASE)
        for pattern in EXCLUDE_RULES
    )


def fetch_recommendations(app_id):
    url = (
        f"https://store.steampowered.com/api/appdetails"
        f"?appids={app_id}&cc=us&l=en"
    )

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "SteamPriceTracker/1.0"}
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.load(response)

    item = data.get(str(app_id), {})

    if not item.get("success"):
        return None

    game = item.get("data", {})
    recommendations = game.get("recommendations") or {}

    return recommendations.get("total", 0)


while True:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT app_id, name, type
        FROM games
        WHERE popularity_checked = 0
          AND filter_reason IS NULL
          AND (
              type = 'game'
              OR type IS NULL
          )
        ORDER BY app_id
        LIMIT ?
    """, (BATCH_SIZE,)).fetchall()

    if not rows:
        conn.close()

        print("No pending games.")
        print(f"Sleeping {EMPTY_WAIT} seconds...")
        time.sleep(EMPTY_WAIT)
        continue

    print("=" * 60)
    print("STEAM POPULARITY COLLECTOR")
    print("=" * 60)
    print("Selected:", len(rows))
    print()

    success = 0
    failed = 0

    for index, row in enumerate(rows, 1):
        app_id = row["app_id"]
        name = row["name"]

        try:
            count = fetch_recommendations(app_id)

            if count is None:
                conn.execute("""
                    UPDATE games
                    SET recommendation_count = 0,
                        popularity_checked = 1
                    WHERE app_id = ?
                """, (app_id,))

                conn.commit()

                print(
                    f"[{index}/{len(rows)}] "
                    f"NO DATA | {app_id} | {name}"
                )
                failed += 1

            else:
                conn.execute("""
                    UPDATE games
                    SET recommendation_count = ?,
                        popularity_checked = 1
                    WHERE app_id = ?
                """, (count, app_id))

                conn.commit()

                print(
                    f"[{index}/{len(rows)}] "
                    f"{app_id} | {name} | "
                    f"recommendations={count:,}"
                )

                success += 1

        except Exception as e:
            print(
                f"[{index}/{len(rows)}] "
                f"ERROR | {app_id} | {name} | {e}"
            )
            failed += 1

        time.sleep(DELAY)

    conn.close()

    print()
    print("=" * 60)
    print("BATCH FINISHED")
    print("Success:", success)
    print("Failed:", failed)
    print("Next batch starting...")
    print("=" * 60)
    print()

    time.sleep(2)
