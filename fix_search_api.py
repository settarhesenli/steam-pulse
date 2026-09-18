from pathlib import Path

path = Path("dashboard.py")
text = path.read_text(encoding="utf-8")

old = '''@app.route("/api/games")
def api_games():
    page = request.args.get("page", 1, type=int)
    limit = 50
    offset = (page - 1) * limit

    conn = get_db()

    games = conn.execute("""
        SELECT app_id, name, type, developer,
               current_price, discount_percent,
               header_image, is_free
        FROM games
        ORDER BY name
        LIMIT ? OFFSET ?
    """, (limit, offset)).fetchall()

    total = conn.execute(
        "SELECT COUNT(*) FROM games"
    ).fetchone()[0]

    conn.close()
'''

new = '''@app.route("/api/games")
def api_games():
    page = request.args.get("page", 1, type=int)
    query = request.args.get("q", "").strip()

    limit = 50
    offset = (page - 1) * limit

    conn = get_db()

    if query:
        search_pattern = f"%{query}%"

        games = conn.execute("""
            SELECT app_id, name, type, developer,
                   current_price, discount_percent,
                   header_image, is_free
            FROM games
            WHERE name LIKE ? COLLATE NOCASE
            ORDER BY name
            LIMIT ? OFFSET ?
        """, (search_pattern, limit, offset)).fetchall()

        total = conn.execute("""
            SELECT COUNT(*)
            FROM games
            WHERE name LIKE ? COLLATE NOCASE
        """, (search_pattern,)).fetchone()[0]

    else:

        games = conn.execute("""
            SELECT app_id, name, type, developer,
                   current_price, discount_percent,
                   header_image, is_free
            FROM games
            ORDER BY name
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()

        total = conn.execute(
            "SELECT COUNT(*) FROM games"
        ).fetchone()[0]

    conn.close()
'''

if old not in text:
    print("ERROR: kohne API kodu tapilmadi.")
    print("dashboard.py backup-dan yoxlamaq lazim olacaq.")
else:
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print("Search API duzeldildi.")
