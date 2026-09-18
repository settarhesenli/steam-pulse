import sqlite3

DB = "steam.db"

conn = sqlite3.connect(DB)
conn.execute("PRAGMA foreign_keys = ON")

conn.executescript("""
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE,
    base_url TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS store_games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id INTEGER NOT NULL,
    store_id INTEGER NOT NULL,
    external_id TEXT,
    store_url TEXT,
    last_checked TEXT,

    UNIQUE(app_id, store_id),

    FOREIGN KEY(app_id)
        REFERENCES games(app_id)
        ON DELETE CASCADE,

    FOREIGN KEY(store_id)
        REFERENCES stores(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS store_prices (
    store_game_id INTEGER PRIMARY KEY,
    current_price INTEGER,
    original_price INTEGER,
    discount_percent INTEGER,
    currency TEXT,
    available INTEGER NOT NULL DEFAULT 1,
    last_updated TEXT,

    FOREIGN KEY(store_game_id)
        REFERENCES store_games(id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS store_price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_game_id INTEGER NOT NULL,
    price INTEGER,
    original_price INTEGER,
    discount_percent INTEGER,
    currency TEXT,
    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(store_game_id)
        REFERENCES store_games(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_store_games_app
ON store_games(app_id);

CREATE INDEX IF NOT EXISTS idx_store_games_store
ON store_games(store_id);

CREATE INDEX IF NOT EXISTS idx_price_history_game
ON store_price_history(store_game_id);

INSERT OR IGNORE INTO stores
    (name, slug, base_url)
VALUES
    ('Steam', 'steam', 'https://store.steampowered.com');

INSERT OR IGNORE INTO stores
    (name, slug, base_url)
VALUES
    ('Epic Games Store', 'epic', 'https://store.epicgames.com');

INSERT OR IGNORE INTO stores
    (name, slug, base_url)
VALUES
    ('GOG', 'gog', 'https://www.gog.com');
""")

conn.commit()

print("\nMulti-store database hazır.\n")

print("Stores:")
for row in conn.execute(
    "SELECT id, name, slug FROM stores ORDER BY id"
):
    print(row)

print("\nNew tables:")
for row in conn.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
      AND name IN (
          'stores',
          'store_games',
          'store_prices',
          'store_price_history'
      )
    ORDER BY name
"""):
    print("-", row[0])

conn.close()
