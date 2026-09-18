import sqlite3
import urllib.request
import json
import time

DB = "steam.db"
API = "https://catalog.gog.com/v1/catalog"
LIMIT = 100
DELAY = 300


def fetch_gog(conn):
    row = conn.execute("""
        SELECT value
        FROM scraper_state
        WHERE key='gog_catalog_page'
    """).fetchone()

    page = int(row[0]) if row else 1

    while True:
        url = f"{API}?limit={LIMIT}&page={page}&order=desc:trending"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "SteamPriceTracker/1.0"}
        )

        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)

        products = data.get("products", [])

        if not products:
            print("GOG catalog finished.")
            conn.execute("""
                UPDATE scraper_state
                SET value='1'
                WHERE key='gog_catalog_page'
            """)
            conn.commit()
            break

        total_pages = data.get("pages")

        print(
            f"GOG page {page}/{total_pages or '?'} | "
            f"products: {len(products)}"
        )

        yield page, products

        page += 1

        conn.execute("""
            INSERT INTO scraper_state (key, value)
            VALUES ('gog_catalog_page', ?)
            ON CONFLICT(key)
            DO UPDATE SET value=excluded.value
        """, (str(page),))
        conn.commit()

        if total_pages and page > total_pages:
            conn.execute("""
                UPDATE scraper_state
                SET value='1'
                WHERE key='gog_catalog_page'
            """)
            conn.commit()
            print("GOG full catalog cycle completed.")
            break


def cents(value):
    if value is None:
        return None
    try:
        return int(round(float(value) * 100))
    except:
        return None


def main():
    conn = sqlite3.connect(DB)

    gog_store_id = conn.execute(
        "SELECT id FROM stores WHERE slug='gog'"
    ).fetchone()[0]

    print("=" * 60)
    print("GOG COLLECTOR")
    print("=" * 60)

    added = 0
    updated = 0
    total = 0

    for page, products in fetch_gog(conn):

        for product in products:
            name = product.get("title")
            external_id = str(product.get("id"))
            slug = product.get("slug")

            if not name or not slug:
                continue

            price_data = product.get("price") or {}
            final_money = price_data.get("finalMoney") or {}
            base_money = price_data.get("baseMoney") or {}

            current_price = cents(final_money.get("amount"))
            original_price = cents(base_money.get("amount"))

            currency = (
                final_money.get("currency")
                or base_money.get("currency")
                or "USD"
            )

            if original_price and current_price is not None:
                discount = round(
                    (1 - current_price / original_price) * 100
                )
            else:
                discount = 0

            url = f"https://www.gog.com/en/game/{slug}"

            game = conn.execute("""
                SELECT app_id
                FROM games
                WHERE lower(name)=lower(?)
                LIMIT 1
            """, (name,)).fetchone()

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
                """, (name,))

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
            """, (app_id, gog_store_id, external_id, url))

            store_game_id = conn.execute("""
                SELECT id
                FROM store_games
                WHERE app_id=? AND store_id=?
            """, (app_id, gog_store_id)).fetchone()[0]

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

            if old is None:
                added += 1
            else:
                updated += 1

            total += 1

        conn.commit()
        print(f"DB updated | processed: {total}")

    conn.close()

    print()
    print("Added:", added)
    print("Updated:", updated)
    print("Total processed:", total)
    print("=" * 60)


if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            print("ERROR:", e)

        print(f"Next check in {DELAY} seconds...")
        time.sleep(DELAY)
