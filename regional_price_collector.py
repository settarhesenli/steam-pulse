import sqlite3
import requests
import time
from datetime import datetime

DB_NAME = "steam.db"

REGIONS = {
    "AZ": "az",
    "US": "us",
}

DELAY = 1.0


def get_connection():
    return sqlite3.connect(DB_NAME)


def get_games():
    conn = get_connection()

    rows = conn.execute("""
        SELECT app_id
        FROM games
        WHERE detailed_fetched = 1
        ORDER BY app_id
    """).fetchall()

    conn.close()

    return [row[0] for row in rows]


def fetch_price(app_id, cc):
    response = requests.get(
        "https://store.steampowered.com/api/appdetails",
        params={
            "appids": app_id,
            "cc": cc,
            "l": "english"
        },
        headers={
            "User-Agent": "SteamPriceTracker/1.0"
        },
        timeout=(10, 30)
    )

    response.raise_for_status()

    result = response.json()
    item = result.get(str(app_id))

    if not item or not item.get("success"):
        return None

    game = item.get("data", {})
    price = game.get("price_overview")

    if not price:
        return None

    return {
        "currency": price.get("currency"),
        "current_price": price.get("final"),
        "original_price": price.get("initial"),
        "discount_percent": price.get(
            "discount_percent",
            0
        )
    }


def save_price(app_id, region, price):
    conn = get_connection()

    conn.execute("""
        INSERT INTO steam_regional_prices (
            app_id,
            region,
            currency,
            current_price,
            original_price,
            discount_percent,
            last_updated
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(app_id, region)
        DO UPDATE SET
            currency = excluded.currency,
            current_price = excluded.current_price,
            original_price = excluded.original_price,
            discount_percent = excluded.discount_percent,
            last_updated = excluded.last_updated
    """, (
        app_id,
        region,
        price["currency"],
        price["current_price"],
        price["original_price"],
        price["discount_percent"],
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def main():
    games = get_games()

    print("=" * 60)
    print("🌍 STEAM REGIONAL PRICE COLLECTOR")
    print("=" * 60)
    print(f"Games: {len(games)}")
    print("Regions: AZ, US")
    print("=" * 60)

    for index, app_id in enumerate(games, 1):

        print(f"\n[{index}/{len(games)}] App ID: {app_id}")

        for region, cc in REGIONS.items():

            try:
                price = fetch_price(app_id, cc)

                if price is None:
                    print(f"  {region}: NO PRICE")
                    continue

                save_price(
                    app_id,
                    region,
                    price
                )

                print(
                    f"  {region}: "
                    f"{price['current_price'] / 100:.2f} "
                    f"{price['currency']} "
                    f"(-{price['discount_percent']}%)"
                )

                time.sleep(DELAY)

            except Exception as e:
                print(
                    f"  {region}: ERROR - {e}"
                )


if __name__ == "__main__":
    main()
