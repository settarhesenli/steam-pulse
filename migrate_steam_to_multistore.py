import sqlite3

DB = "steam.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

conn.execute("PRAGMA foreign_keys = ON")

print("Steam migration baslayir...")

# Steam store ID
steam_store = conn.execute("""
    SELECT id
    FROM stores
    WHERE slug = 'steam'
""").fetchone()

if not steam_store:
    raise RuntimeError("Steam store tapilmadi.")

steam_store_id = steam_store["id"]

# ---------------------------------------------------------
# 1. games -> store_games
# ---------------------------------------------------------

games = conn.execute("""
    SELECT
        app_id,
        name,
        steam_url
    FROM games
""").fetchall()

inserted_games = 0

for game in games:

    cursor = conn.execute("""
        INSERT OR IGNORE INTO store_games (
            app_id,
            store_id,
            external_id,
            store_url,
            last_checked
        )
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
    """, (
        game["app_id"],
        steam_store_id,
        str(game["app_id"]),
        game["steam_url"]
    ))

    inserted_games += cursor.rowcount

conn.commit()

print(f"Store games elave edildi: {inserted_games}")


# ---------------------------------------------------------
# 2. Current prices
# ---------------------------------------------------------

rows = conn.execute("""
    SELECT
        app_id,
        current_price,
        original_price,
        discount_percent,
        currency,
        last_updated
    FROM games
""").fetchall()

updated_prices = 0

for game in rows:

    store_game = conn.execute("""
        SELECT id
        FROM store_games
        WHERE app_id = ?
          AND store_id = ?
    """, (
        game["app_id"],
        steam_store_id
    )).fetchone()

    if not store_game:
        continue

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
        VALUES (?, ?, ?, ?, ?, 1, ?)

        ON CONFLICT(store_game_id)
        DO UPDATE SET
            current_price = excluded.current_price,
            original_price = excluded.original_price,
            discount_percent = excluded.discount_percent,
            currency = excluded.currency,
            available = 1,
            last_updated = excluded.last_updated
    """, (
        store_game["id"],
        game["current_price"],
        game["original_price"],
        game["discount_percent"],
        game["currency"],
        game["last_updated"]
    ))

    updated_prices += 1

conn.commit()

print(f"Current prices: {updated_prices}")


# ---------------------------------------------------------
# 3. Existing price history
# ---------------------------------------------------------

history = conn.execute("""
    SELECT
        ph.app_id,
        ph.price,
        ph.original_price,
        ph.discount_percent,
        ph.currency,
        ph.recorded_at
    FROM price_history ph
    ORDER BY ph.id
""").fetchall()

inserted_history = 0

for item in history:

    store_game = conn.execute("""
        SELECT id
        FROM store_games
        WHERE app_id = ?
          AND store_id = ?
    """, (
        item["app_id"],
        steam_store_id
    )).fetchone()

    if not store_game:
        continue

    # Eyni migration tekrar isledende duplicate yaratmasin
    exists = conn.execute("""
        SELECT 1
        FROM store_price_history
        WHERE store_game_id = ?
          AND price IS ?
          AND original_price IS ?
          AND discount_percent IS ?
          AND currency IS ?
          AND recorded_at = ?
        LIMIT 1
    """, (
        store_game["id"],
        item["price"],
        item["original_price"],
        item["discount_percent"],
        item["currency"],
        item["recorded_at"]
    )).fetchone()

    if exists:
        continue

    conn.execute("""
        INSERT INTO store_price_history (
            store_game_id,
            price,
            original_price,
            discount_percent,
            currency,
            recorded_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        store_game["id"],
        item["price"],
        item["original_price"],
        item["discount_percent"],
        item["currency"],
        item["recorded_at"]
    ))

    inserted_history += 1

conn.commit()


# ---------------------------------------------------------
# 4. Verification
# ---------------------------------------------------------

total_games = conn.execute("""
    SELECT COUNT(*)
    FROM games
""").fetchone()[0]

steam_games = conn.execute("""
    SELECT COUNT(*)
    FROM store_games
    WHERE store_id = ?
""", (steam_store_id,)).fetchone()[0]

steam_prices = conn.execute("""
    SELECT COUNT(*)
    FROM store_prices sp
    JOIN store_games sg
        ON sg.id = sp.store_game_id
    WHERE sg.store_id = ?
""", (steam_store_id,)).fetchone()[0]

steam_history = conn.execute("""
    SELECT COUNT(*)
    FROM store_price_history sph
    JOIN store_games sg
        ON sg.id = sph.store_game_id
    WHERE sg.store_id = ?
""", (steam_store_id,)).fetchone()[0]


print()
print("======================================")
print("PHASE 1 - STEAM MIGRATION")
print("======================================")
print(f"Games:          {total_games}")
print(f"Steam mappings: {steam_games}")
print(f"Current prices: {steam_prices}")
print(f"Price history:  {steam_history}")
print("======================================")

if total_games == steam_games:
    print("OK: Butun Steam oyunlari map olundu.")
else:
    print("WARNING: Bazi oyunlar map olunmayib.")

conn.close()
