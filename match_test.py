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
    r"\bsupporter\s+pack\b",
    r"\badd[- ]on\b",
    r"\baddon\b",
    r"\bupgrade\b",
    r"\bbundle\b",
]

def is_excluded(name):
    name = name or ""
    return any(
        re.search(pattern, name, re.IGNORECASE)
        for pattern in EXCLUDE_PATTERNS
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
    SELECT g.app_id, g.name, s.name AS store
    FROM store_games sg
    JOIN games g ON g.app_id = sg.app_id
    JOIN stores s ON s.id = sg.store_id
    WHERE s.slug IN ('steam', 'gog')
    ORDER BY g.name
""").fetchall()

groups = {}

for row in rows:
    if is_excluded(row["name"]):
        continue

    key = normalize(row["name"])

    if key:
        groups.setdefault(key, []).append(row)

matched = 0
steam_gog = 0

for key, items in groups.items():

    stores = {x["store"] for x in items}

    if "Steam" in stores and "GOG" in stores:

        matched += 1
        steam_gog += 1

        if matched <= 30:
            print()
            print("MATCH:", key)

            for x in items:
                print(f"  {x['store']}: {x['name']}")

conn.close()

print()
print("======================================")
print("MATCHING TEST")
print("======================================")
print("Total matches:", matched)
print("Steam <-> GOG:", steam_gog)
print("======================================")
