import requests
import sqlite3
import json
import time
from datetime import datetime


DB_NAME = "steam.db"

API_URL = (
    "https://store.steampowered.com/api/appdetails"
)

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


def get_next_game():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT app_id
        FROM games
        WHERE detailed_fetched = 0
        ORDER BY app_id
        LIMIT 1
    """)

    result = cursor.fetchone()

    conn.close()

    return result[0] if result else None


def get_game_details(app_id):

    response = session.get(
        API_URL,
        params={
            "appids": app_id,
            "l": "english",
            "cc": "us"
        },
        timeout=(10, 30)
    )

    response.raise_for_status()

    result = response.json()

    game_data = result.get(str(app_id))

    if not game_data:
        return None

    if not game_data.get("success"):
        return None

    return game_data.get("data")


def save_game(game):

    conn = get_connection()
    cursor = conn.cursor()

    app_id = game.get("steam_appid")

    name = game.get("name")

    game_type = game.get("type")

    is_free = int(
        bool(game.get("is_free"))
    )

    developers = game.get(
        "developers",
        []
    )

    publishers = game.get(
        "publishers",
        []
    )

    developer = ", ".join(
        developers
    )

    publisher = ", ".join(
        publishers
    )

    release_date = (
        game.get("release_date", {})
        .get("date")
    )

    price_data = game.get(
        "price_overview"
    )

    current_price = None
    original_price = None
    discount_percent = 0
    currency = None

    if price_data:

        current_price = price_data.get(
            "final"
        )

        original_price = price_data.get(
            "initial"
        )

        discount_percent = price_data.get(
            "discount_percent",
            0
        )

        currency = price_data.get(
            "currency"
        )

    # Images and additional Steam metadata
    background_image = (
        game.get("background")
        or game.get("background_raw")
    )

    screenshots = [
        s.get("path_full")
        for s in game.get("screenshots", [])
        if s.get("path_full")
    ]

    genres = [
        g.get("description")
        for g in game.get("genres", [])
        if g.get("description")
    ]

    categories = [
        c.get("description")
        for c in game.get("categories", [])
        if c.get("description")
    ]

    now = datetime.now().isoformat()

    cursor.execute("""
        UPDATE games

        SET
            name = ?,
            type = ?,
            is_free = ?,

            developer = ?,
            publisher = ?,

            release_date = ?,

            current_price = ?,
            original_price = ?,
            discount_percent = ?,
            currency = ?,

            short_description = ?,
            header_image = ?,
            background_image = ?,
            screenshots = ?,
            genres = ?,
            categories = ?,

            detailed_fetched = 1,
            last_updated = ?

        WHERE app_id = ?
    """, (

        name,
        game_type,
        is_free,

        developer,
        publisher,

        release_date,

        current_price,
        original_price,
        discount_percent,
        currency,

        game.get("short_description"),
        game.get("header_image"),
        background_image,
        json.dumps(screenshots),
        json.dumps(genres),
        json.dumps(categories),

        now,

        app_id
    ))

    # Price history
    if current_price is not None:

        cursor.execute("""
            SELECT price,
                   original_price,
                   discount_percent
            FROM price_history

            WHERE app_id = ?

            ORDER BY id DESC

            LIMIT 1
        """, (app_id,))

        previous = cursor.fetchone()

        changed = (
            previous is None
            or previous[0] != current_price
            or previous[1] != original_price
            or previous[2] != discount_percent
        )

        if changed:

            cursor.execute("""
                INSERT INTO price_history (
                    app_id,
                    price,
                    original_price,
                    discount_percent,
                    currency,
                    recorded_at
                )

                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                app_id,
                current_price,
                original_price,
                discount_percent,
                currency,
                now
            ))

    conn.commit()
    conn.close()


def main():

    print("=" * 60)
    print("🎮 STEAM DETAIL SCRAPER")
    print("=" * 60)

    while True:

        app_id = get_next_game()

        if app_id is None:

            print(
                "No unprocessed games."
            )

            print(
                "Waiting 10 minutes..."
            )

            time.sleep(600)

            continue

        print(
            f"\nFetching App ID: {app_id}"
        )

        try:

            game = get_game_details(
                app_id
            )

            if game is None:

                print(
                    "No details available."
                )

                # Don't retry forever
                conn = get_connection()

                conn.execute("""
                    UPDATE games

                    SET detailed_fetched = 1

                    WHERE app_id = ?
                """, (app_id,))

                conn.commit()
                conn.close()

                continue

            save_game(game)

            print(
                f"✓ {game.get('name')}"
            )

            price = game.get(
                "price_overview"
            )

            if price:

                print(
                    f"  Price: "
                    f"{price.get('final', 0) / 100:.2f} "
                    f"{price.get('currency')}"
                )

                print(
                    f"  Discount: "
                    f"{price.get('discount_percent', 0)}%"
                )

            elif game.get("is_free"):

                print(
                    "  Price: FREE"
                )

            print(
                f"  Time: "
                f"{datetime.now().strftime('%H:%M:%S')}"
            )

            time.sleep(0.5)

        except requests.exceptions.Timeout:

            print(
                "⚠️ Timeout. Retrying..."
            )

            time.sleep(30)

        except requests.exceptions.RequestException as e:

            print(
                f"⚠️ Network error: {e}"
            )

            time.sleep(60)

        except KeyboardInterrupt:

            print(
                "\n🛑 Detail scraper stopped."
            )

            break

        except Exception as e:

            print(
                f"⚠️ Error: {e}"
            )

            time.sleep(30)


if __name__ == "__main__":
    main()
