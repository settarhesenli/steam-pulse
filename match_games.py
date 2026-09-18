
import sqlite3
import re
import unicodedata

DB = "steam.db"

EXCLUDE_PATTERNS = [
    r"\bdlc\b",
    r"\bsoundtrack\b",
    r"\bseason\s+pass\b",
    r"\bexpansion\b",
    r"\bcharacter\s+pack\b",
    r"\bweapon\s+pack\b",
    r"\bcontent\s+pack\b",
    r"\bstory\s+pack\b",
    r"\bspecies\s+pack\b",
    r"\bmusic\s+pack\b",
    r"\bcosmetic\s+pack\b",
    r"\bmini\s+pack\b",
    r"\bsupporter\s+pack\b",
    r"\badd[- ]on\b",
    r"\baddon\b",
    r"\bupgrade\b",
    r"\bbundle\b",
    r"\bcollection\b",
]

def is_excluded(name):
    return any(
        re.search(p, name or "", re.IGNORECASE)
        for p in EXCLUDE_PATTERNS
    )

def normalize(name):
    name = unicodedata.normalize("NFKD", name or "")
    name = name.lower()
    name = re.sub(r"[®™©]", "", name)

    name = re.sub(
        r"\b(complete|goty|game of the year|deluxe|ultimate|"
        r"definitive|enhanced|remastered|standard|edition|"
        r"collection)\b",
        " ",
        name
    )

    name = re.sub(r"[^a-z0-9]+", " ", name)
    return re.sub(r"\s+", " ", name).strip()


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

rows = conn.execute("""
    SELECT
        sg.id AS store_game_id,
        sg.app_id,
        g.name,
        g.type,
        s.slug AS store_slug
    FROM store_games sg
    JOIN games g ON g.app_id = sg.app_id
    JOIN stores s ON s.id = sg.store_id
    WHERE s.slug IN ('steam', 'gog')
      AND (
          s.slug = 'gog'
          OR g.tracked = 1
      )
""").fetchall()

steam = {}
gog = {}

for row in rows:

    if is_excluded(row["name"]):
        continue

    key = normalize(row["name"])

    if not key:
        continue

    if row["store_slug"] == "steam":
        steam.setdefault(key, []).append(row)

    elif row["store_slug"] == "gog":
        gog.setdefault(key, []).append(row)


matches = []

for key in steam.keys() & gog.keys():

    steam_items = steam[key]
    gog_items = gog[key]

    # Yalnız bir Steam məhsulu varsa avtomatik match təhlükəsizdir.
    if len(steam_items) != 1:
        continue

    steam_item = steam_items[0]

    for gog_item in gog_items:

        matches.append({
            "name": key,
            "steam_app_id": steam_item["app_id"],
            "steam_name": steam_item["name"],
            "gog_store_game_id": gog_item["store_game_id"],
            "gog_name": gog_item["name"],
            "confidence": 1.0
        })


print()
print("======================================")
print("MATCH DRY-RUN")
print("======================================")
print("Steam candidates:", len(steam))
print("GOG candidates:", len(gog))
print("Safe matches:", len(matches))
print("======================================")

print()


def classify_match(steam_name, gog_name):
    raw_s = unicodedata.normalize("NFKD", steam_name or "").lower()
    raw_g = unicodedata.normalize("NFKD", gog_name or "").lower()

    raw_s = re.sub(r"[®™©]", "", raw_s)
    raw_g = re.sub(r"[®™©]", "", raw_g)

    if raw_s == raw_g:
        return "exact", 1.00

    edition_words = [
        "complete",
        "goty",
        "game of the year",
        "deluxe",
        "ultimate",
        "definitive",
        "enhanced",
        "standard",
        "edition",
    ]

    s = raw_s
    g = raw_g

    for word in edition_words:
        s = re.sub(r"\b" + re.escape(word) + r"\b", " ", s)
        g = re.sub(r"\b" + re.escape(word) + r"\b", " ", g)

    s = re.sub(r"\s+", " ", s).strip()
    g = re.sub(r"\s+", " ", g).strip()

    # Edition-only difference
    if s == g:
        return "edition", 0.98

    # Remastered / Enhanced kimi real versiya ferqlerini
    # avtomatik match etmirik.
    return "review", 0.00


exact_count = 0
edition_count = 0
review_count = 0

for m in matches:
    method, confidence = classify_match(
        m["steam_name"],
        m["gog_name"]
    )

    m["match_method"] = method
    m["confidence"] = confidence

    if method == "exact":
        exact_count += 1
    elif method == "edition":
        edition_count += 1
    else:
        review_count += 1

print()
print("======================================")
print("MATCH CLASSIFICATION")
print("======================================")
print("Exact:", exact_count)
print("Edition:", edition_count)
print("Review:", review_count)
print("Total:", len(matches))
print("======================================")

print()
print("SUSPICIOUS MATCHES")
print("--------------------------------------")

suspicious = 0

for m in matches:
    steam = m["steam_name"].lower()
    gog = m["gog_name"].lower()

    if steam != gog:
        print(f'{m["steam_name"]}  <->  {m["gog_name"]}')
        suspicious += 1

        if suspicious >= 50:
            break

print("Suspicious shown:", suspicious)

print("FIRST 30 MATCHES")
print("--------------------------------------")

for m in matches[:30]:
    print(
        f'{m["steam_name"]}  <->  {m["gog_name"]}'
    )

# Exact + Edition match-ləri DB-yə yaz
inserted = 0
skipped = 0

conn2 = sqlite3.connect(DB)

for m in matches:
    method, confidence = classify_match(
        m["steam_name"],
        m["gog_name"]
    )

    if method not in ("exact", "edition"):
        continue

    try:
        conn2.execute("""
            INSERT OR IGNORE INTO game_matches
            (canonical_app_id, store_game_id, match_method, confidence)
            VALUES (?, ?, ?, ?)
        """, (
            m["steam_app_id"],
            m["gog_store_game_id"],
            method,
            confidence
        ))

        if conn2.total_changes:
            inserted += 1
        else:
            skipped += 1

    except sqlite3.Error:
        skipped += 1

conn2.commit()
conn2.close()

print()
print("======================================")
print("MATCH DATABASE UPDATE")
print("======================================")
print("Inserted:", inserted)
print("Skipped:", skipped)
print("======================================")

conn.close()
