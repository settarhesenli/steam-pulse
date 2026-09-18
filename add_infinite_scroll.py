from pathlib import Path

path = Path("dashboard.py")
text = path.read_text(encoding="utf-8")

# Flask importuna jsonify əlavə et
text = text.replace(
    "from flask import Flask, render_template, request",
    "from flask import Flask, render_template, request, jsonify"
)

# Search route-dan əvvəl yeni API əlavə edirik
marker = '@app.route("/search")'

api_code = r'''
@app.route("/api/games")
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

    result = []

    for game in games:
        result.append({
            "app_id": game["app_id"],
            "name": game["name"],
            "type": game["type"],
            "developer": game["developer"],
            "current_price": game["current_price"],
            "discount_percent": game["discount_percent"],
            "header_image": game["header_image"],
            "is_free": game["is_free"]
        })

    return jsonify({
        "games": result,
        "page": page,
        "has_more": offset + len(games) < total
    })


'''

if '@app.route("/api/games")' not in text:
    text = text.replace(marker, api_code + marker)

path.write_text(text, encoding="utf-8")

print("Backend infinite scroll API elave edildi.")
