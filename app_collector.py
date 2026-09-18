import requests
import sqlite3
import time
from datetime import datetime

DB_NAME = "steam.db"

STEAM_API = "https://api.steampowered.com/IStoreService/GetAppList/v1/"


def get_connection():
    return sqlite3.connect(DB_NAME)


def get_apps(last_appid=0):

    params = {
        "max_results": 50000,
        "last_appid": last_appid
    }

    response = requests.get(
        STEAM_API,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


def save_apps(apps):

    conn = get_connection()
    cursor = conn.cursor()

    for app in apps:

        app_id = app.get("appid")
        name = app.get("name")

        if not app_id or not name:
            continue

        cursor.execute("""
            INSERT INTO games (app_id, name)
            VALUES (?, ?)
            ON CONFLICT(app_id)
            DO UPDATE SET name = excluded.name
        """, (app_id, name))

    conn.commit()
    conn.close()


def get_last_appid():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT value
        FROM scraper_state
        WHERE key = 'last_appid'
    """)

    result = cursor.fetchone()

    conn.close()

    if result:
        return int(result[0])

    return 0


def save_last_appid(app_id):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO scraper_state (key, value)
        VALUES ('last_appid', ?)
        ON CONFLICT(key)
        DO UPDATE SET value = excluded.value
    """, (str(app_id),))

    conn.commit()
    conn.close()


def main():

    print("=" * 60)
    print("🎮 STEAM APP COLLECTOR")
    print("=" * 60)

    last_appid = get_last_appid()

    print(f"Starting from App ID: {last_appid}")

    while True:

        try:

            data = get_apps(last_appid)

            apps = data.get("response", {}).get("apps", [])

            if not apps:
                print("No more apps found.")
                break

            print(f"Received {len(apps)} apps")

            save_apps(apps)

            last_appid = apps[-1]["appid"]

            save_last_appid(last_appid)

            print(f"Last App ID: {last_appid}")
            print(
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            print("-" * 60)

            time.sleep(1)

        except Exception as e:

            print(f"ERROR: {e}")

            print("Retrying in 30 seconds...")

            time.sleep(30)


if __name__ == "__main__":
    main()
