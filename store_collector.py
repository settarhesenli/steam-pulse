import requests
from bs4 import BeautifulSoup
import re
import time
import sqlite3
from datetime import datetime


DB_NAME = "steam.db"

BASE_URL = "https://store.steampowered.com/search/"

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 "
        "(X11; Linux x86_64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/140.0 Safari/537.36"
    )
})


def get_connection():
    return sqlite3.connect(DB_NAME)


def get_state(key, default=0):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT value FROM scraper_state WHERE key = ?",
        (key,)
    )

    result = cursor.fetchone()

    conn.close()

    if result:
        return int(result[0])

    return default


def save_state(key, value):

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO scraper_state (key, value)
        VALUES (?, ?)

        ON CONFLICT(key)
        DO UPDATE SET
            value = excluded.value
    """, (key, str(value)))

    conn.commit()
    conn.close()


def scrape_page(start):

    params = {
        "start": start,
        "count": 50,
        "ndl": 1
    }

    response = session.get(
        BASE_URL,
        params=params,
        timeout=(10, 30)
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    games = []

    for item in soup.select(
        "a.search_result_row"
    ):

        url = item.get("href", "")

        match = re.search(
            r"/app/(\d+)/",
            url
        )

        if not match:
            continue

        app_id = int(match.group(1))

        name_element = item.select_one(
            ".title"
        )

        if not name_element:
            continue

        name = name_element.get_text(
            strip=True
        )

        date_element = item.select_one(
            ".search_released"
        )

        release_date = None

        if date_element:
            release_date = date_element.get_text(
                strip=True
            )

        image_element = item.select_one(
            "img"
        )

        image = None

        if image_element:
            image = image_element.get(
                "src"
            )

        games.append({
            "app_id": app_id,
            "name": name,
            "url": url,
            "release_date": release_date,
            "image": image
        })

    return games


def save_games(games):

    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat()

    for game in games:

        cursor.execute("""
            INSERT INTO games (
                app_id,
                name,
                release_date,
                header_image,
                steam_url,
                last_updated
            )

            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT(app_id)
            DO UPDATE SET

                name = excluded.name,

                release_date =
                    excluded.release_date,

                header_image =
                    excluded.header_image,

                steam_url =
                    excluded.steam_url,

                last_updated =
                    excluded.last_updated
        """, (
            game["app_id"],
            game["name"],
            game["release_date"],
            game["image"],
            game["url"],
            now
        ))

    conn.commit()
    conn.close()


def main():

    print("=" * 60)
    print("🕷️ STEAM STORE COLLECTOR")
    print("=" * 60)

    start = get_state(
        "store_search_start",
        0
    )

    print(
        f"Resuming from: {start}"
    )

    while True:

        print(
            f"\nFetching: {start} → {start + 50}"
        )

        try:

            games = scrape_page(start)

            if not games:

                print(
                    "No games found."
                )

                print(
                    "Restarting scan in 1 hour..."
                )

                time.sleep(3600)

                start = 0

                save_state(
                    "store_search_start",
                    start
                )

                continue

            save_games(games)

            start += 50

            save_state(
                "store_search_start",
                start
            )

            print(
                f"Collected: {len(games)} games"
            )

            print(
                f"Next position: {start}"
            )

            print(
                "Time:",
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            )

            time.sleep(3)

        except requests.exceptions.Timeout:

            print(
                "⚠️ Request timeout."
            )

            print(
                "Retrying in 30 seconds..."
            )

            time.sleep(30)

        except requests.exceptions.RequestException as e:

            print(
                f"⚠️ Network error: {e}"
            )

            print(
                "Retrying in 60 seconds..."
            )

            time.sleep(60)

        except KeyboardInterrupt:

            print(
                "\n🛑 Collector stopped."
            )

            print(
                f"Progress saved at: {start}"
            )

            break

        except Exception as e:

            print(
                f"⚠️ Unexpected error: {e}"
            )

            print(
                "Retrying in 60 seconds..."
            )

            time.sleep(60)


if __name__ == "__main__":
    main()
