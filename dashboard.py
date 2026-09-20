from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, g
from functools import wraps
import shutil
import subprocess
import time
from flask_wtf.csrf import CSRFProtect
import sqlite3
import os
import secrets
import hashlib
import time
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from rapidfuzz.fuzz import ratio, WRatio

app = Flask(__name__)
csrf = CSRFProtect(app)
load_dotenv()
app.config['SECRET_KEY'] = os.environ['FLASK_SECRET_KEY']
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

import json

app.jinja_env.filters["fromjson"] = json.loads

DB = "steam.db"


@app.before_request
def analytics_start():
    g.analytics_start = time.perf_counter()


@app.after_request
def analytics_log(response):
    try:
        path = request.path

        # Static faylları və avatar şəkillərini traffic statistikasından çıxarırıq.
        if not path.startswith("/static/") and not path.startswith("/account/avatar/"):

            elapsed = (time.perf_counter() - getattr(
                g, "analytics_start", time.perf_counter()
            )) * 1000

            user_id = session.get("user_id")

            forwarded = request.headers.get("CF-Connecting-IP")
            ip = forwarded or request.remote_addr or ""

            ip_hash = hashlib.sha256(
                (app.config["SECRET_KEY"] + ip).encode()
            ).hexdigest()

            conn = get_db()

            conn.execute(
                """
                INSERT INTO site_visits
                (user_id, path, method, status_code, response_ms, ip_hash, user_agent)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    path,
                    request.method,
                    response.status_code,
                    round(elapsed, 2),
                    ip_hash,
                    request.headers.get("User-Agent", "")[:500]
                )
            )

            conn.commit()
            conn.close()

    except Exception:
        # Analytics problemi saytın özünü dayandırmamalıdır.
        pass

    return response



def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))

        conn = get_db()

        user = conn.execute(
            """
            SELECT is_admin
            FROM users
            WHERE id = ?
            """,
            (session["user_id"],)
        ).fetchone()

        conn.close()

        if not user or not user["is_admin"]:
            return "Forbidden", 403

        return view(*args, **kwargs)

    return wrapped_view


def get_service_status(service):
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True,
            text=True,
            timeout=3
        )
        status = result.stdout.strip()
        return status or "unknown"
    except Exception:
        return "unknown"


ADMIN_WORKERS = {
    "steam-store-worker.service": {
        "name": "Steam Store Worker",
        "description": "Steam store game collection",
    },
    "steam-detail-worker.service": {
        "name": "Steam Detail Worker",
        "description": "Game details, images and metadata",
    },
    "steam-popularity-worker.service": {
        "name": "Steam Popularity Worker",
        "description": "Popularity and relevance processing",
    },
    "epic-price-worker.service": {
        "name": "Epic Price Worker",
        "description": "Epic Games Store price collector",
    },
    "gog-price-worker.service": {
        "name": "GOG Price Worker",
        "description": "GOG price collector",
    },
    "game-match-worker.service": {
        "name": "Game Matching Worker",
        "description": "Cross-store game matching",
    },
}


def get_worker_details(service):
    if service not in ADMIN_WORKERS:
        return None

    try:
        result = subprocess.run(
            [
                "systemctl",
                "show",
                service,
                "--property=ActiveState",
                "--property=SubState",
                "--property=ActiveEnterTimestamp",
                "--property=UnitFileState",
            ],
            capture_output=True,
            text=True,
            timeout=3,
        )

        values = {}

        for line in result.stdout.splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                values[key] = value.strip()

        return {
            "service": service,
            "name": ADMIN_WORKERS[service]["name"],
            "description": ADMIN_WORKERS[service]["description"],
            "status": values.get("ActiveState", "unknown"),
            "sub_state": values.get("SubState", "unknown"),
            "active_since": values.get("ActiveEnterTimestamp", ""),
            "enabled": values.get("UnitFileState", "unknown"),
        }

    except Exception:
        return {
            "service": service,
            "name": ADMIN_WORKERS[service]["name"],
            "description": ADMIN_WORKERS[service]["description"],
            "status": "unknown",
            "sub_state": "unknown",
            "active_since": "",
            "enabled": "unknown",
        }


@app.route("/admin/workers")
@admin_required
def admin_workers():
    workers = [
        get_worker_details(service)
        for service in ADMIN_WORKERS
    ]

    return render_template(
        "admin/workers.html",
        workers=workers
    )


@app.route("/admin/workers/<service>/action", methods=["POST"])
@admin_required
def admin_worker_action(service):
    if service not in ADMIN_WORKERS:
        return "Unknown worker", 404

    action = request.form.get("action", "").strip()

    allowed_actions = {
        "start": "start",
        "stop": "stop",
        "restart": "restart",
        "enable": "enable",
        "disable": "disable",
    }

    if action not in allowed_actions:
        return "Invalid action", 400

    try:
        result = subprocess.run(
            [
                "sudo",
                "/usr/bin/systemctl",
                allowed_actions[action],
                service,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode != 0:
            error = (result.stderr or result.stdout).strip()
            return f"Worker action failed: {error}", 500

    except Exception as exc:
        return f"Worker action failed: {exc}", 500

    return redirect(url_for("admin_workers"))


@app.route("/admin/workers/<service>/logs")
@admin_required
def admin_worker_logs(service):
    if service not in ADMIN_WORKERS:
        return jsonify({"error": "Unknown worker"}), 404

    try:
        result = subprocess.run(
            [
                "sudo",
                "/usr/bin/journalctl",
                "-u",
                service,
                "-n",
                "50",
                "--no-pager",
                "-o",
                "short",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        return jsonify({
            "service": service,
            "logs": result.stdout,
        })

    except Exception as exc:
        return jsonify({
            "error": str(exc)
        }), 500




def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def smart_search_games(conn, query, limit=2000):
    """
    Final intelligent game search.

    Ranking:
    - exact / alias match
    - version matching
    - token coverage
    - fuzzy similarity
    - game/tracked/popularity bonuses
    - DLC / soundtrack / tool / addon penalties
    """

    import re
    import unicodedata

    query = " ".join((query or "").strip().split())

    if not query:
        return []

    ALIASES = {
        "gta": "grand theft auto",
        "gta5": "grand theft auto v",
        "gta 5": "grand theft auto v",
        "gta4": "grand theft auto iv",
        "gta 4": "grand theft auto iv",
        "gta3": "grand theft auto iii",
        "gta 3": "grand theft auto iii",
        "rdr": "red dead redemption",
        "rdr2": "red dead redemption 2",
        "cod": "call of duty",
        "cs": "counter strike",
        "cs2": "counter strike 2",
        "pubg": "playerunknowns battlegrounds",
        "aoe": "age of empires",
        "ac": "assassins creed",
    }

    ROMAN_TO_NUMBER = {
        "i": "1",
        "ii": "2",
        "iii": "3",
        "iv": "4",
        "v": "5",
        "vi": "6",
        "vii": "7",
        "viii": "8",
        "ix": "9",
        "x": "10",
    }

    NUMBER_TO_ROMAN = {
        "1": "i",
        "2": "ii",
        "3": "iii",
        "4": "iv",
        "5": "v",
        "6": "vi",
        "7": "vii",
        "8": "viii",
        "9": "ix",
        "10": "x",
    }

    PRODUCT_PENALTIES = {
        "dlc": 500,
        "soundtrack": 500,
        "ost": 500,
        "season pass": 450,
        "expansion": 450,
        "artbook": 450,
        "wallpaper": 450,
        "cosmetic": 400,
        "pack": 350,
        "bundle": 350,
        "collection": 300,
        "upgrade": 400,
        "add-on": 450,
        "addon": 450,
        "redmod": 400,
        "redkit": 350,
        "mod": 400,
        "tool": 400,
        "demo": 350,
        "benchmark": 300,
        "map": 300,
        "sfx": 450,
        "sound effects": 450,
        "content": 250,
    }

    def normalize(value):
        value = unicodedata.normalize("NFKD", value or "")
        value = value.lower()
        value = re.sub(r"[®™©]", "", value)

        # Compact aliases before punctuation removal.
        value = re.sub(r"\bgta\s*5\b", "grand theft auto v", value)
        value = re.sub(r"\bgta\s*4\b", "grand theft auto iv", value)
        value = re.sub(r"\bgta\s*3\b", "grand theft auto iii", value)
        value = re.sub(r"\bgta\s*v\b", "grand theft auto v", value)
        value = re.sub(r"\bgta\s*iv\b", "grand theft auto iv", value)

        value = re.sub(r"[^a-z0-9\s]", " ", value)
        tokens = value.split()

        normalized = []

        for token in tokens:
            if token in ROMAN_TO_NUMBER:
                normalized.append(ROMAN_TO_NUMBER[token])
            else:
                normalized.append(token)

        return " ".join(normalized)

    def version_tokens(value):
        """
        Extract meaningful standalone game versions.
        Examples:
        V -> 5
        IV -> 4
        2077 -> 2077
        3 -> 3
        """
        normalized = normalize(value)
        tokens = normalized.split()

        versions = set()

        for token in tokens:
            if token.isdigit():
                number = int(token)

                # Ignore very small incidental numbers except 1-10,
                # which commonly represent game sequels.
                if 1 <= number <= 10 or number >= 100:
                    versions.add(str(number))

        return versions

    def product_penalty(name):
        lowered = (name or "").lower()
        penalty = 0

        for phrase, value in PRODUCT_PENALTIES.items():
            if re.search(r"\b" + re.escape(phrase) + r"\b", lowered):
                penalty += value

        return penalty

    raw_query = query.lower()
    normalized_query = normalize(query)

    # Apply alias only to the complete query.
    alias_value = ALIASES.get(raw_query)
    if alias_value:
        normalized_query = normalize(alias_value)

    query_tokens = normalized_query.split()

    if not query_tokens:
        return []

    # ---------------------------------------------------------
    # Candidate discovery
    # ---------------------------------------------------------
    #
    # First try a strict AND search using the meaningful title
    # tokens. This prevents queries such as "rdr2" from returning
    # unrelated games containing only "dead" or "2".
    #
    # If strict search finds nothing, fall back to OR search for
    # typo-tolerance and unusual titles.
    #

    version_token_set = {
        token for token in query_tokens
        if token.isdigit()
    }

    core_tokens = [
        token
        for token in query_tokens
        if token not in version_token_set and len(token) >= 2
    ]

    # For a versioned search such as "gta 5", the franchise words
    # are the strict SQL candidate filter. Version matching itself
    # is handled by the scoring engine below.
    strict_conditions = []
    strict_params = []

    for token in core_tokens:
        strict_conditions.append("lower(name) LIKE ?")
        strict_params.append(f"%{token}%")

    # If there are no core tokens, use all useful tokens.
    if not strict_conditions:
        for token in query_tokens:
            if len(token) >= 2:
                strict_conditions.append("lower(name) LIKE ?")
                strict_params.append(f"%{token}%")

    rows = []

    if strict_conditions:
        strict_where = " AND ".join(strict_conditions)

        rows = conn.execute(
            f"""
            SELECT app_id, name, type, developer,
                   current_price, discount_percent,
                   header_image, is_free,
                   popularity_score, recommendation_count,
                   tracked
            FROM games
            WHERE {strict_where}
            LIMIT 8000
            """,
            strict_params
        ).fetchall()

    # Fallback only when strict discovery found nothing.
    if not rows:
        conditions = []
        params = []

        for token in query_tokens:
            if len(token) >= 2:
                conditions.append("lower(name) LIKE ?")
                params.append(f"%{token}%")

        conditions.append("lower(name) LIKE ?")
        params.append(f"%{raw_query}%")

        where_clause = " OR ".join(conditions)

        rows = conn.execute(
            f"""
            SELECT app_id, name, type, developer,
                   current_price, discount_percent,
                   header_image, is_free,
                   popularity_score, recommendation_count,
                   tracked
            FROM games
            WHERE {where_clause}
            LIMIT 8000
            """,
            params
        ).fetchall()

    # ---------------------------------------------------------
    # Scoring
    # ---------------------------------------------------------

    query_versions = version_tokens(normalized_query)
    query_token_set = set(query_tokens)

    EDITION_WORDS = {
        "ultimate",
        "complete",
        "definitive",
        "deluxe",
        "enhanced",
        "remastered",
        "director",
        "cut",
        "edition",
    }

    scored = []

    for game in rows:
        name = game["name"] or ""
        normalized_name = normalize(name)
        name_tokens = normalized_name.split()
        name_token_set = set(name_tokens)

        if not normalized_name:
            continue

        # -----------------------------------------------------
        # Token matching
        # -----------------------------------------------------

        matched_tokens = query_token_set & name_token_set

        if query_token_set:
            token_coverage = len(matched_tokens) / len(query_token_set)
        else:
            token_coverage = 0.0

        fuzzy_score = WRatio(normalized_query, normalized_name)

        exact = normalized_name == normalized_query
        prefix = normalized_name.startswith(normalized_query)
        contains = normalized_query in normalized_name

        score = 0.0

        if exact:
            score += 1800
        elif prefix:
            score += 1100
        elif contains:
            score += 850

        score += token_coverage * 650
        score += fuzzy_score * 2.0

        # -----------------------------------------------------
        # Version matching
        # -----------------------------------------------------

        name_versions = version_tokens(normalized_name)

        if query_versions:
            if query_versions & name_versions:
                # Exact requested version.
                score += 1200
            elif name_versions:
                # Candidate explicitly has another version.
                score -= 1800
            else:
                # Candidate belongs to the franchise but has no
                # recognizable requested version.
                score -= 700

        # -----------------------------------------------------
        # GTA-specific franchise/version matching
        # -----------------------------------------------------

        if "grand theft auto" in normalized_query:

            if "grand theft auto" in normalized_name:
                score += 500

                if query_versions:
                    if query_versions & name_versions:
                        score += 1200
                    elif name_versions:
                        score -= 2200
                    else:
                        score -= 900

        # -----------------------------------------------------
        # RDR-specific matching
        # -----------------------------------------------------

        if "red dead redemption" in normalized_query:

            if "red dead redemption" in normalized_name:
                score += 500

                if query_versions:
                    if query_versions & name_versions:
                        score += 1000
                    elif name_versions:
                        score -= 2000
                    else:
                        score -= 800

        # -----------------------------------------------------
        # Main game type
        # -----------------------------------------------------

        game_type = (game["type"] or "").lower()

        if game_type == "game":
            score += 120
        elif game_type == "dlc":
            score -= 700
        elif game_type in {"music", "mod", "hardware"}:
            score -= 600

        # -----------------------------------------------------
        # Product/content penalties
        # -----------------------------------------------------

        score -= product_penalty(name)

        lowered_name = normalized_name.lower()

        # Edition variants should not outrank the base game when
        # the user did not explicitly search for that edition.
        edition_hits = sum(
            1 for word in EDITION_WORDS
            if word in name_token_set
        )

        query_mentions_edition = bool(
            query_token_set & EDITION_WORDS
        )

        if edition_hits and not query_mentions_edition:
            score -= min(edition_hits, 2) * 120

        # -----------------------------------------------------
        # Base-game preference
        # -----------------------------------------------------

        # If the candidate looks like the exact requested title
        # plus extra words, slightly prefer the shorter/main title.
        extra_tokens = max(
            0,
            len(name_tokens) - len(query_tokens)
        )

        if not query_versions and extra_tokens > 0:
            score -= min(extra_tokens, 6) * 12

        # A recognizable sequel number is useful for generic
        # franchise searches such as "cyberpunk".
        if not query_versions and name_versions:
            score += 120

        # -----------------------------------------------------
        # Tracked / popularity
        # -----------------------------------------------------

        if game["tracked"]:
            score += 50

        popularity = float(game["popularity_score"] or 0)
        recommendations = float(game["recommendation_count"] or 0)

        score += min(popularity, 100) * 0.35
        score += min(recommendations, 1000) * 0.01

        scored.append((score, game))

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1]["name"].lower()
        )
    )

    return [game for _, game in scored[:limit]]


ALLOWED_AVATAR_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
AVATAR_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", "avatars")


@app.route("/account/avatar", methods=["POST"])
def upload_avatar():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    file = request.files.get("avatar")

    if not file or not file.filename:
        return redirect(url_for("account"))

    original_name = secure_filename(file.filename)

    if "." not in original_name:
        return "Invalid image file.", 400

    extension = original_name.rsplit(".", 1)[1].lower()

    if extension not in ALLOWED_AVATAR_EXTENSIONS:
        return "Invalid image format.", 400

    random_name = f"{secrets.token_hex(16)}.{extension}"
    os.makedirs(AVATAR_UPLOAD_DIR, mode=0o700, exist_ok=True)

    file.save(os.path.join(AVATAR_UPLOAD_DIR, random_name))

    conn = get_db()

    old_avatar = conn.execute(
        "SELECT avatar_filename FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    conn.execute(
        "UPDATE users SET avatar_filename = ? WHERE id = ?",
        (random_name, session["user_id"])
    )
    conn.commit()
    conn.close()

    if old_avatar and old_avatar["avatar_filename"]:
        old_path = os.path.join(
            AVATAR_UPLOAD_DIR,
            old_avatar["avatar_filename"]
        )
        if os.path.isfile(old_path):
            os.remove(old_path)

    return redirect(url_for("account"))


@app.route("/account/avatar/<path:filename>")
def account_avatar(filename):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    conn = get_db()

    avatar = conn.execute(
        "SELECT avatar_filename FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    conn.close()

    if not avatar or avatar["avatar_filename"] != filename:
        return "Forbidden", 403

    return send_from_directory(AVATAR_UPLOAD_DIR, filename)


@app.route("/account")
def account():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    conn = get_db()

    user = conn.execute(
        """
        SELECT id, username, email, created_at, avatar_filename
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    conn.close()

    if not user:
        session.clear()
        return redirect(url_for("login"))

    return render_template(
        "account.html",
        user=user
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    conn = get_db()

    user = conn.execute(
        """
        SELECT id, username, email, password_hash, is_admin
        FROM users
        WHERE email = ?
        """,
        (email,)
    ).fetchone()

    conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return "Invalid email or password.", 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["email"] = user["email"]
    session["is_admin"] = bool(user["is_admin"])

    return redirect(url_for("dashboard"))


@app.route("/account/change-password", methods=["GET", "POST"])
def change_password():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("change_password.html")

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not current_password or not new_password or not confirm_password:
        return "All password fields are required.", 400

    if len(new_password) < 8:
        return "New password must be at least 8 characters.", 400

    if new_password != confirm_password:
        return "New passwords do not match.", 400

    conn = get_db()

    user = conn.execute(
        """
        SELECT password_hash
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    if not user or not check_password_hash(
        user["password_hash"],
        current_password
    ):
        conn.close()
        return "Current password is incorrect.", 401

    new_password_hash = generate_password_hash(new_password)

    conn.execute(
        """
        UPDATE users
        SET password_hash = ?
        WHERE id = ?
        """,
        (new_password_hash, session["user_id"])
    )

    conn.commit()
    conn.close()

    return redirect(url_for("account"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if len(username) < 3:
        return "Username must be at least 3 characters.", 400

    if len(password) < 8:
        return "Password must be at least 8 characters.", 400

    if not email or "@" not in email:
        return "Please enter a valid email.", 400

    password_hash = generate_password_hash(password)

    conn = get_db()

    try:
        conn.execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (username, email, password_hash)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return "Username or email already exists.", 409

    conn.close()

    return redirect(url_for("login"))



@app.route("/admin")
@admin_required
def admin_dashboard():
    conn = get_db()

    total_users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    total_games = conn.execute(
        "SELECT COUNT(*) FROM games"
    ).fetchone()[0]

    total_visits = conn.execute(
        "SELECT COUNT(*) FROM site_visits"
    ).fetchone()[0]

    today_visits = conn.execute(
        """
        SELECT COUNT(*)
        FROM site_visits
        WHERE date(created_at) = date('now', 'localtime')
        """
    ).fetchone()[0]

    last_7_days = conn.execute(
        """
        SELECT COUNT(*)
        FROM site_visits
        WHERE datetime(created_at) >= datetime('now', '-7 days')
        """
    ).fetchone()[0]

    unique_visitors = conn.execute(
        """
        SELECT COUNT(DISTINCT ip_hash)
        FROM site_visits
        WHERE ip_hash IS NOT NULL
        """
    ).fetchone()[0]

    avg_response = conn.execute(
        """
        SELECT ROUND(AVG(response_ms), 1)
        FROM site_visits
        WHERE response_ms IS NOT NULL
        """
    ).fetchone()[0] or 0

    errors_4xx = conn.execute(
        """
        SELECT COUNT(*)
        FROM site_visits
        WHERE status_code >= 400 AND status_code < 500
        """
    ).fetchone()[0]

    errors_5xx = conn.execute(
        """
        SELECT COUNT(*)
        FROM site_visits
        WHERE status_code >= 500
        """
    ).fetchone()[0]

    top_pages = conn.execute(
        """
        SELECT path, COUNT(*) AS views
        FROM site_visits
        GROUP BY path
        ORDER BY views DESC
        LIMIT 10
        """
    ).fetchall()

    traffic_24h = conn.execute(
        """
        SELECT
            strftime('%Y-%m-%d %H:00', created_at) AS hour,
            COUNT(*) AS visits
        FROM site_visits
        WHERE datetime(created_at) >= datetime('now', '-24 hours')
        GROUP BY hour
        ORDER BY hour
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin/dashboard.html",
        total_users=total_users,
        total_games=total_games,
        total_visits=total_visits,
        today_visits=today_visits,
        last_7_days=last_7_days,
        unique_visitors=unique_visitors,
        avg_response=avg_response,
        errors_4xx=errors_4xx,
        errors_5xx=errors_5xx,
        top_pages=top_pages,
        traffic_24h=traffic_24h
    )


@app.route("/admin/traffic")
@admin_required
def admin_traffic():
    conn = get_db()

    total_visits = conn.execute(
        "SELECT COUNT(*) FROM site_visits"
    ).fetchone()[0]

    today_visits = conn.execute("""
        SELECT COUNT(*)
        FROM site_visits
        WHERE date(created_at) = date('now', 'localtime')
    """).fetchone()[0]

    yesterday_visits = conn.execute("""
        SELECT COUNT(*)
        FROM site_visits
        WHERE date(created_at) = date('now', 'localtime', '-1 day')
    """).fetchone()[0]

    unique_visitors = conn.execute("""
        SELECT COUNT(DISTINCT ip_hash)
        FROM site_visits
        WHERE ip_hash IS NOT NULL
    """).fetchone()[0]

    avg_response = conn.execute("""
        SELECT ROUND(AVG(response_ms), 1)
        FROM site_visits
    """).fetchone()[0] or 0

    errors_4xx = conn.execute("""
        SELECT COUNT(*)
        FROM site_visits
        WHERE status_code BETWEEN 400 AND 499
    """).fetchone()[0]

    errors_5xx = conn.execute("""
        SELECT COUNT(*)
        FROM site_visits
        WHERE status_code >= 500
    """).fetchone()[0]

    top_pages = conn.execute("""
        SELECT path, COUNT(*) AS views
        FROM site_visits
        GROUP BY path
        ORDER BY views DESC
        LIMIT 20
    """).fetchall()

    hourly = conn.execute("""
        SELECT
            strftime('%H:00', created_at) AS hour,
            COUNT(*) AS visits
        FROM site_visits
        WHERE datetime(created_at) >= datetime('now', '-24 hours')
        GROUP BY hour
        ORDER BY hour
    """).fetchall()

    methods = conn.execute("""
        SELECT method, COUNT(*) AS count
        FROM site_visits
        GROUP BY method
        ORDER BY count DESC
    """).fetchall()

    status_codes = conn.execute("""
        SELECT status_code, COUNT(*) AS count
        FROM site_visits
        GROUP BY status_code
        ORDER BY count DESC
        LIMIT 15
    """).fetchall()

    conn.close()

    return render_template(
        "admin/traffic.html",
        total_visits=total_visits,
        today_visits=today_visits,
        yesterday_visits=yesterday_visits,
        unique_visitors=unique_visitors,
        avg_response=avg_response,
        errors_4xx=errors_4xx,
        errors_5xx=errors_5xx,
        top_pages=top_pages,
        hourly=hourly,
        methods=methods,
        status_codes=status_codes
    )

@app.route("/admin/users")
@admin_required
def admin_users():
    conn = get_db()

    users = conn.execute(
        """
        SELECT
            u.id,
            u.username,
            u.email,
            u.created_at,
            u.avatar_filename,
            u.is_admin,
            COUNT(w.id) AS wishlist_count
        FROM users u
        LEFT JOIN wishlists w ON w.user_id = u.id
        GROUP BY u.id
        ORDER BY u.created_at DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin/users.html",
        users=users
    )


@app.route("/")
def dashboard():
    conn = get_db()

    total_games = conn.execute(
        "SELECT COUNT(*) FROM games"
    ).fetchone()[0]

    free_games = conn.execute(
        "SELECT COUNT(*) FROM games WHERE is_free = 1"
    ).fetchone()[0]

    on_sale = conn.execute(
        """
        SELECT COUNT(*)
        FROM games
        WHERE discount_percent > 0
        """
    ).fetchone()[0]

    biggest_discounts = conn.execute(
        """
        SELECT *
        FROM games
        WHERE discount_percent >= 50
          AND current_price > 0
          AND recommendation_count >= 1000
        ORDER BY RANDOM()
        LIMIT 6
        """
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        total_games=total_games,
        free_games=free_games,
        on_sale=on_sale,
        biggest_discounts=biggest_discounts
    )
@app.route("/deals")
def deals():
    conn = get_db()

    games = conn.execute(
        """
        SELECT *
        FROM games
        WHERE discount_percent > 0
          AND current_price > 0
        ORDER BY discount_percent DESC, current_price ASC
        LIMIT 100
        """
    ).fetchall()

    conn.close()

    return render_template(
        "deals.html",
        games=games
    )



@app.route("/api/games")
def api_games():
    page = request.args.get("page", 1, type=int)
    query = request.args.get("q", "").strip()

    limit = 50
    offset = (page - 1) * limit

    conn = get_db()

    if query:
        all_matches = smart_search_games(conn, query, limit=2000)

        total = len(all_matches)

        start = offset
        end = offset + limit
        games = all_matches[start:end]

    else:

        games = conn.execute("""
            SELECT app_id, name, type, developer,
                   current_price, discount_percent,
                   header_image, is_free
            FROM games
            WHERE tracked = 1
            ORDER BY popularity_score DESC,
                     recommendation_count DESC,
                     name
            LIMIT ? OFFSET ?
        """, (limit, offset)).fetchall()

        total = conn.execute(
            "SELECT COUNT(*) FROM games WHERE tracked = 1"
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


@app.route("/search")
def search():
    query = request.args.get("q", "").strip()

    conn = get_db()

    games = conn.execute(
        """
        SELECT *
        FROM games
        WHERE name LIKE ?
        ORDER BY name
        LIMIT 50
        """,
        (f"%{query}%",)
    ).fetchall()

    conn.close()

    return render_template(
        "search.html",
        games=games,
        query=query
    )


@app.route("/wishlist/add/<int:app_id>", methods=["POST"])
def add_wishlist(app_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    conn = get_db()

    game = conn.execute(
        "SELECT app_id FROM games WHERE app_id = ?",
        (app_id,)
    ).fetchone()

    if not game:
        conn.close()
        return "Game not found", 404

    conn.execute(
        """
        INSERT OR IGNORE INTO wishlists (user_id, app_id)
        VALUES (?, ?)
        """,
        (session["user_id"], app_id)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("game", app_id=app_id))


@app.route("/wishlist/remove/<int:app_id>", methods=["POST"])
def remove_wishlist(app_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    conn = get_db()

    conn.execute(
        """
        DELETE FROM wishlists
        WHERE user_id = ? AND app_id = ?
        """,
        (session["user_id"], app_id)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("game", app_id=app_id))



@app.route("/wishlist/target/<int:app_id>", methods=["POST"])
def set_wishlist_target(app_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    try:
        target_price = int(round(float(request.form.get("target_price", "0")) * 100))
    except (TypeError, ValueError):
        return redirect(url_for("game", app_id=app_id))

    if target_price <= 0:
        return redirect(url_for("game", app_id=app_id))

    currency = (request.form.get("currency") or "USD").upper()

    if currency not in {"USD", "EUR"}:
        currency = "USD"

    conn = get_db()

    game = conn.execute(
        "SELECT app_id FROM games WHERE app_id = ?",
        (app_id,)
    ).fetchone()

    if not game:
        conn.close()
        return "Game not found", 404

    wishlist = conn.execute(
        """
        SELECT 1
        FROM wishlists
        WHERE user_id = ? AND app_id = ?
        """,
        (session["user_id"], app_id)
    ).fetchone()

    if not wishlist:
        conn.close()
        return "Game is not in wishlist", 400

    conn.execute(
        """
        INSERT INTO wishlist_targets
            (user_id, app_id, target_price, currency, enabled, updated_at)
        VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, app_id)
        DO UPDATE SET
            target_price = excluded.target_price,
            currency = excluded.currency,
            enabled = 1,
            updated_at = CURRENT_TIMESTAMP
        """,
        (session["user_id"], app_id, target_price, currency)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("game", app_id=app_id))


@app.route("/wishlist/target/<int:app_id>/disable", methods=["POST"])
def disable_wishlist_target(app_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    conn = get_db()

    conn.execute(
        """
        UPDATE wishlist_targets
        SET enabled = 0,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND app_id = ?
        """,
        (session["user_id"], app_id)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("game", app_id=app_id))


@app.route("/wishlist")
def wishlist():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    conn = get_db()

    wishlist_games = conn.execute(
        """
        SELECT
            g.*,
            w.created_at AS wishlist_added_at
        FROM wishlists w
        JOIN games g ON g.app_id = w.app_id
        WHERE w.user_id = ?
        ORDER BY w.created_at DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "wishlist.html",
        wishlist_games=wishlist_games
    )


@app.route("/game/<int:app_id>")
def game(app_id):
    country = request.headers.get("CF-IPCountry", "US").upper()

    region_map = {
        "AZ": "AZ",
        "US": "US",
    }

    region = region_map.get(country, "US")

    conn = get_db()

    game = conn.execute(
        "SELECT * FROM games WHERE app_id = ?",
        (app_id,)
    ).fetchone()

    history = conn.execute(
        """
        SELECT price, original_price, discount_percent, recorded_at
        FROM price_history
        WHERE app_id = ?
        ORDER BY recorded_at
        """,
        (app_id,)
    ).fetchall()

    steam_price = conn.execute(
        """
        SELECT current_price,
               original_price,
               discount_percent,
               currency
        FROM steam_regional_prices
        WHERE app_id = ? AND region = ?
        """,
        (app_id, region)
    ).fetchone()

    if steam_price is None:
        steam_price = {
            "current_price": game["current_price"],
            "original_price": game["original_price"],
            "discount_percent": game["discount_percent"],
            "currency": game["currency"]
        }

    store_prices = conn.execute(
        """
        SELECT
            s.name AS store_name,
            s.slug AS store_slug,
            sg.store_url,
            sp.current_price,
            sp.original_price,
            sp.discount_percent,
            sp.currency,
            sp.available,
            sp.last_updated
        FROM store_games sg
        JOIN stores s ON s.id = sg.store_id
        LEFT JOIN store_prices sp ON sp.store_game_id = sg.id
        WHERE sg.app_id = ?

        UNION ALL

        SELECT
            s.name AS store_name,
            s.slug AS store_slug,
            sg.store_url,
            sp.current_price,
            sp.original_price,
            sp.discount_percent,
            sp.currency,
            sp.available,
            sp.last_updated
        FROM game_matches gm
        JOIN store_games sg ON sg.id = gm.store_game_id
        JOIN stores s ON s.id = sg.store_id
        LEFT JOIN store_prices sp ON sp.store_game_id = sg.id
        WHERE gm.canonical_app_id = ?

        """,
        (app_id, app_id)
    ).fetchall()

    # En ucuz real qiymeti tap
    available_prices = [
        row["current_price"]
        for row in store_prices
        if row["available"]
        and row["current_price"] is not None
    ]

    best_price = min(available_prices) if available_prices else None

    wishlist_added = False
    wishlist_target = None

    if session.get("user_id"):
        wishlist_added = conn.execute(
            """
            SELECT 1
            FROM wishlists
            WHERE user_id = ? AND app_id = ?
            """,
            (session["user_id"], app_id)
        ).fetchone() is not None

        wishlist_target = conn.execute(
            """
            SELECT target_price, currency, enabled
            FROM wishlist_targets
            WHERE user_id = ? AND app_id = ?
            """,
            (session["user_id"], app_id)
        ).fetchone()

    conn.close()

    if not game:
        return "Game not found", 404

    return render_template(
        "game.html",
        game=game,
        history=history,
        store_prices=store_prices,
        best_price=best_price,
        wishlist_added=wishlist_added,
        wishlist_target=wishlist_target,
        steam_price=steam_price
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )
