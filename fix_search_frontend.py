from pathlib import Path

path = Path("templates/search.html")
text = path.read_text(encoding="utf-8")

old = '''let page = 1;
let loading = false;
let hasMore = true;

const gamesContainer = document.getElementById("games");
'''

new = '''let page = 1;
let loading = false;
let hasMore = true;

const searchQuery = {{ query|tojson }};

const gamesContainer = document.getElementById("games");
'''

if old not in text:
    print("ERROR: frontend pattern tapilmadi.")
else:
    text = text.replace(old, new)

old2 = '''const response =
            await fetch(
                "/api/games?page=" + page
            );'''

new2 = '''const params = new URLSearchParams();

        params.set("page", page);

        if (searchQuery) {
            params.set("q", searchQuery);
        }

        const response =
            await fetch(
                "/api/games?" + params.toString()
            );'''

if old2 not in text:
    print("ERROR: fetch pattern tapilmadi.")
else:
    text = text.replace(old2, new2)

path.write_text(text, encoding="utf-8")

print("Search frontend duzeldildi.")
