import sqlite3
import re
from collections import Counter

DB = "steam.db"

EXCLUDE_RULES = [
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


def is_junk(name, game_type):
    if game_type in ("dlc", "hardware"):
        return True

    name = name or ""

    for pattern in EXCLUDE_RULES:
        if re.search(pattern, name, re.IGNORECASE):
            return True

    return False


def get_level(count):
    if count >= 100000:
        return "VERY_HIGH"
    elif count >= 10000:
        return "HIGH"
    elif count >= 1000:
        return "MEDIUM"
    elif count >= 100:
        return "LOW"
    else:
        return "VERY_LOW"


def get_score(count):
    if count >= 100000:
        return 100
    elif count >= 10000:
        return 80
    elif count >= 1000:
        return 60
    elif count >= 100:
        return 30
    else:
        return 10


conn = sqlite3.connect(DB)

rows = conn.execute("""
    SELECT app_id, name, type, recommendation_count
    FROM games
""").fetchall()

conn.close()

stats = Counter()
examples = {
    "VERY_HIGH": [],
    "HIGH": [],
    "MEDIUM": [],
    "LOW": [],
    "VERY_LOW": [],
    "JUNK": []
}

for app_id, name, game_type, count in rows:

    if is_junk(name, game_type):
        stats["JUNK"] += 1

        if len(examples["JUNK"]) < 20:
            examples["JUNK"].append(
                (app_id, name, count)
            )

        continue

    level = get_level(count)
    score = get_score(count)

    stats[level] += 1

    if len(examples[level]) < 20:
        examples[level].append(
            (app_id, name, count, score)
        )


print("=" * 65)
print("STEAM POPULARITY SCORE - DRY RUN")
print("=" * 65)

print(f"Total products:       {len(rows):,}")
print(f"Junk / excluded:      {stats['JUNK']:,}")
print()

print("--- POPULARITY LEVELS ---")

for level in [
    "VERY_HIGH",
    "HIGH",
    "MEDIUM",
    "LOW",
    "VERY_LOW"
]:
    print(f"{level:12} {stats[level]:,}")

print()
print("--- EXAMPLES ---")

for level in [
    "VERY_HIGH",
    "HIGH",
    "MEDIUM",
    "LOW",
    "VERY_LOW"
]:
    print(f"\n[{level}]")

    for item in examples[level]:
        app_id, name, count, score = item
        print(
            f"{app_id} | "
            f"{count:,} recommendations | "
            f"score={score} | "
            f"{name}"
        )

print("\n[JUNK EXAMPLES]")

for app_id, name, count in examples["JUNK"]:
    print(
        f"{app_id} | "
        f"{count:,} recommendations | "
        f"{name}"
    )

print()
print("=" * 65)
print("DATABASE DEYISDIRILMEDI")
print("=" * 65)
