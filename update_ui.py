from pathlib import Path
import re

BASE = Path("templates")


def update_file(filename, replacements):
    path = BASE / filename
    text = path.read_text(encoding="utf-8")

    original = text

    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
        else:
            print(f"[WARNING] {filename}: pattern tapilmadi:")
            print(old[:150])

    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"[OK] {filename} yenilendi")
    else:
        print(f"[INFO] {filename}: deyisiklik olunmadi")


# ============================================================
# SEARCH
# ============================================================

search_replacements = [

(
"""    <style>
""",
"""    <style>

        /* LIVE indicator */
        .dot {
            display: inline-block;
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #a4d007;
            margin-right: 5px;
            box-shadow: 0 0 8px rgba(164,208,7,.7);
            animation: livePulse 1.8s ease-in-out infinite;
        }

        @keyframes livePulse {
            0%, 100% {
                opacity: 1;
                transform: scale(1);
                box-shadow: 0 0 7px rgba(164,208,7,.65);
            }

            50% {
                opacity: .35;
                transform: scale(.82);
                box-shadow: 0 0 3px rgba(164,208,7,.25);
            }
        }

        /* Whole game row is clickable */
        .game-row {
            cursor: pointer;
            transition: background .18s ease;
        }

        .game-row:hover {
            background: rgba(102,192,244,.06);
        }

"""
),

(
"""<tr>

    <td>
        <a href="/game/{{ game.app_id }}">
            {{ game.name }}
        </a>
    </td>
""",
"""<tr class="game-row"
    onclick="window.location.href='/game/{{ game.app_id }}'">

    <td>
        <a href="/game/{{ game.app_id }}">
            {{ game.name }}
        </a>
    </td>
"""
)

]

update_file("search.html", search_replacements)


# ============================================================
# GAME
# ============================================================

game_replacements = [

(
""".dot{
    display:inline-block;
    width:7px;
    height:7px;
    border-radius:50%;
    background:#a4d007;
    margin-right:5px;
    box-shadow:0 0 8px rgba(164,208,7,.7);
}""",
""".dot{
    display:inline-block;
    width:7px;
    height:7px;
    border-radius:50%;
    background:#a4d007;
    margin-right:5px;
    box-shadow:0 0 8px rgba(164,208,7,.7);
    animation:livePulse 1.8s ease-in-out infinite;
}

@keyframes livePulse{
    0%,100%{
        opacity:1;
        transform:scale(1);
        box-shadow:0 0 7px rgba(164,208,7,.65);
    }

    50%{
        opacity:.35;
        transform:scale(.82);
        box-shadow:0 0 3px rgba(164,208,7,.25);
    }
}"""
),

(
"""<div class="logo">""",
"""<a href="/" class="logo">"""
),

(
"""</div>
        <div class="nav-title">""",
"""</a>
        <div class="nav-title">"""
)

]

update_file("game.html", game_replacements)


# ============================================================
# DEALS
# ============================================================

deals_replacements = [

(
""".dot{
    display:inline-block;
    width:7px;
    height:7px;
    border-radius:50%;
    background:#a4d007;
    margin-right:5px;
    box-shadow:0 0 8px rgba(164,208,7,.7);
}""",
""".dot{
    display:inline-block;
    width:7px;
    height:7px;
    border-radius:50%;
    background:#a4d007;
    margin-right:5px;
    box-shadow:0 0 8px rgba(164,208,7,.7);
    animation:livePulse 1.8s ease-in-out infinite;
}

@keyframes livePulse{
    0%,100%{
        opacity:1;
        transform:scale(1);
        box-shadow:0 0 7px rgba(164,208,7,.65);
    }

    50%{
        opacity:.35;
        transform:scale(.82);
        box-shadow:0 0 3px rgba(164,208,7,.25);
    }
}"""
),

(
"""<div class="logo">""",
"""<a href="/" class="logo">"""
)

]

update_file("deals.html", deals_replacements)


print()
print("====================================")
print(" UI yenilenmesi tamamlandi")
print("====================================")
