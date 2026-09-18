import sqlite3

DB_NAME = "steam.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def init_database():

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            app_id INTEGER PRIMARY KEY,
            name TEXT,
            type TEXT,
            is_free INTEGER,

            developer TEXT,
            publisher TEXT,

            release_date TEXT,

            current_price INTEGER,
            original_price INTEGER,
            discount_percent INTEGER,
            currency TEXT,

            short_description TEXT,
            header_image TEXT,
            steam_url TEXT,

            detailed_fetched INTEGER DEFAULT 0,
            last_updated TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            app_id INTEGER,

            price INTEGER,
            original_price INTEGER,
            discount_percent INTEGER,
            currency TEXT,

            recorded_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scraper_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":

    init_database()

    print("Database initialized successfully.")
