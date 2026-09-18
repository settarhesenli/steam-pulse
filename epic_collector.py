import sqlite3
import json
import urllib.request
import time
from datetime import datetime

DB = "steam.db"

URL = (
    "https://store-site-backend-static.ak.epicgames.com/"
    "freeGamesPromotions?locale=en-US&country=US&allowCountries=US"
)

DELAY = 60


def fetch_epic():
    req = urllib.request.Request(
        URL,
        headers={"User-Agent": "SteamPriceTracker/1.0"}
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def cents(value):
    if value is None:
        return None
    return int(value)


def main():
    conn = sqlite3.connect(DB)

    stores = conn.execute(
        "SELECT id FROM stores WHERE slug='epic'"
    ).fetchone()

    if not stores:
        print("Epic store tapilmadi.")
        conn.close()
        return

    epic_store_id = stores[0]

    data = fetch_epic()
    items = data["data"]["Catalog"]["searchStore"]["elements"]

    print("=" * 60)
    print("EPIC GAMES COLLECTOR")
    print("=" * 60)
    print("Items:", len(items))

    added = 0
    updated = 0

    for item in items:
        title = item.get("title")
        external_id = item.get("id")

        if not title or not external_id:
            continue

        price_data = item.get("price", {}).get("totalPrice", {})

        current_price = cents(price_data.get("discountPrice"))
        original_price = cents(price_data.get("originalPrice"))
        currency = price_data.get("currencyCode")

        if original_price and current_price is not None:
            discount = round(
                (1 - current_price / original_price) * 100
            )
        else:
            discount = 0

        url = f"https://store.epicgames.com/en-US/p/{external_id}"

        game = conn.execute(
            "SELECT app_id FROM games WHERE lower(name)=lower(?) LIMIT 1",
            (title,)
        ).fetchone()

        if game:
            app_id = game[0]
        else:
            conn.execute("""
                INSERT INTO games (
                    name,
                    type,
                    tracked,
                    popularity_score,
                    relevance_score
                )
                VALUES (?, 'game', 0, 0, 0)
            """, (title,))
            app_id = conn.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]

        conn.execute("""
            INSERT INTO store_games (
                app_id,
                store_id,
                external_id,
                store_url,
                last_checked
            )
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(app_id, store_id)
            DO UPDATE SET
                external_id=excluded.external_id,
                store_url=excluded.store_url,
                last_checked=excluded.last_checked
        """, (app_id, epic_store_id, external_id, url))

        store_game_id = conn.execute("""
            SELECT id
            FROM store_games
            WHERE app_id=? AND store_id=?
        """, (app_id, epic_store_id)).fetchone()[0]

        old = conn.execute("""
            SELECT current_price
            FROM store_prices
            WHERE store_game_id=?
        """, (store_game_id,)).fetchone()

        conn.execute("""
            INSERT INTO store_prices (
                store_game_id,
                current_price,
                original_price,
                discount_percent,
                currency,
                available,
                last_updated
            )
            VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(store_game_id)
            DO UPDATE SET
                current_price=excluded.current_price,
                original_price=excluded.original_price,
                discount_percent=excluded.discount_percent,
                currency=excluded.currency,
                available=1,
                last_updated=CURRENT_TIMESTAMP
        """, (
            store_game_id,
            current_price,
            original_price,
            discount,
            currency
        ))

        if old is None or old[0] != current_price:
            conn.execute("""
                INSERT INTO store_price_history (
                    store_game_id,
                    price,
                    original_price,
                    discount_percent,
                    currency
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                store_game_id,
                current_price,
                original_price,
                discount,
                currency
            ))

        conn.commit()

        if old is None:
            added += 1
        else:
            updated += 1

        print(
            f"{title} | "
            f"{current_price} {currency} | "
            f"-{discount}%"
        )

    conn.close()

    print()
    print("Added:", added)
    print("Updated:", updated)
    print("=" * 60)


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print("ERROR:", e)

        print(f"Next check in {DELAY} seconds...")
        time.sleep(DELAY)
