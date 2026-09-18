from pathlib import Path

path = Path("templates/search.html")

html = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>All Games — Steam Pulse</title>

<style>

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: #071018;
    color: #e8f0f6;
    font-family: Arial, Helvetica, sans-serif;
}

.container {
    max-width: 1450px;
    margin: auto;
    padding: 35px;
}

.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 25px;
}

.logo {
    color: #66c0f4;
    font-size: 20px;
    font-weight: 900;
    text-decoration: none;
}

.logo span {
    color: white;
}

.back {
    color: #66c0f4;
    text-decoration: none;
    font-size: 13px;
}

h1 {
    font-size: 38px;
    margin: 0;
}

.subtitle {
    color: #72879a;
    margin-top: 8px;
    font-size: 13px;
}

.search-box {
    display: flex;
    gap: 10px;
    margin: 25px 0;
}

.search-box input {
    flex: 1;
    max-width: 500px;
    background: #111e2b;
    border: 1px solid #25394a;
    border-radius: 8px;
    padding: 13px 15px;
    color: white;
    outline: none;
}

.search-box button {
    background: #66c0f4;
    border: none;
    border-radius: 8px;
    padding: 0 22px;
    cursor: pointer;
    font-weight: bold;
}

.games {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
}

.game {
    background: #0d1924;
    border: 1px solid #1d3040;
    border-radius: 11px;
    overflow: hidden;
    cursor: pointer;
    transition: .22s;
}

.game:hover {
    transform: translateY(-4px);
    border-color: #36546a;
    box-shadow: 0 18px 40px rgba(0,0,0,.28);
}

.image {
    height: 150px;
    background: #101a24;
    overflow: hidden;
}

.image img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
    transition: .3s;
}

.game:hover .image img {
    transform: scale(1.05);
}

.info {
    padding: 15px;
}

.name {
    font-size: 15px;
    font-weight: bold;
    line-height: 1.3;
    height: 39px;
    overflow: hidden;
}

.developer {
    color: #667b8d;
    font-size: 10px;
    margin-top: 7px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.bottom {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 14px;
}

.price {
    font-size: 16px;
    font-weight: 900;
}

.discount {
    color: #a4d007;
    font-weight: bold;
    font-size: 12px;
}

.loading {
    text-align: center;
    padding: 35px;
    color: #71879a;
    display: none;
}

.spinner {
    width: 24px;
    height: 24px;
    border: 3px solid #243747;
    border-top-color: #66c0f4;
    border-radius: 50%;
    margin: auto;
    animation: spin .8s linear infinite;
}

@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}

.end {
    text-align: center;
    padding: 35px;
    color: #536b7e;
    display: none;
}

@media (max-width: 1100px) {
    .games {
        grid-template-columns: repeat(3, 1fr);
    }
}

@media (max-width: 750px) {
    .games {
        grid-template-columns: repeat(2, 1fr);
    }

    .container {
        padding: 20px;
    }
}

@media (max-width: 500px) {
    .games {
        grid-template-columns: 1fr;
    }
}

</style>
</head>

<body>

<div class="container">

    <div class="header">

        <a href="/" class="logo">
            STEAM <span>PULSE</span>
        </a>

        <a href="/" class="back">
            ← Dashboard
        </a>

    </div>

    <h1>All Games</h1>

    <div class="subtitle">
        Browse the Steam game database
    </div>

    <form class="search-box" action="/search" method="get">

        <input
            type="text"
            name="q"
            value="{{ query }}"
            placeholder="Search games..."
        >

        <button type="submit">
            Search
        </button>

    </form>

    <div id="games" class="games"></div>

    <div id="loading" class="loading">

        <div class="spinner"></div>

        <div style="margin-top:10px;">
            Loading more games...
        </div>

    </div>

    <div id="end" class="end">
        All games loaded.
    </div>

</div>


<script>

let page = 1;
let loading = false;
let hasMore = true;

const gamesContainer = document.getElementById("games");
const loadingElement = document.getElementById("loading");
const endElement = document.getElementById("end");


function createGame(game) {

    const card = document.createElement("div");

    card.className = "game";

    card.onclick = function() {
        window.location.href = "/game/" + game.app_id;
    };


    let price = "FREE";

    if (!game.is_free && game.current_price) {

        price =
            "$" +
            (game.current_price / 100).toFixed(2);

    }


    let discount = "";

    if (game.discount_percent) {

        discount =
            "-" +
            game.discount_percent +
            "%";

    }


    const image =
        game.header_image ||
        "";


    card.innerHTML = `

        <div class="image">

            ${
                image
                ? `<img src="${image}" loading="lazy">`
                : ""
            }

        </div>

        <div class="info">

            <div class="name">
                ${escapeHtml(game.name || "Unknown")}
            </div>

            <div class="developer">
                ${escapeHtml(game.developer || "-")}
            </div>

            <div class="bottom">

                <div class="price">
                    ${price}
                </div>

                <div class="discount">
                    ${discount}
                </div>

            </div>

        </div>
    `;


    return card;
}


function escapeHtml(value) {

    const div = document.createElement("div");

    div.textContent = value;

    return div.innerHTML;
}


async function loadGames() {

    if (loading || !hasMore) {
        return;
    }


    loading = true;

    loadingElement.style.display = "block";


    try {

        const response =
            await fetch(
                "/api/games?page=" + page
            );


        if (!response.ok) {
            throw new Error("API error");
        }


        const data =
            await response.json();


        data.games.forEach(function(game) {

            gamesContainer.appendChild(
                createGame(game)
            );

        });


        hasMore = data.has_more;

        page++;


        if (!hasMore) {

            endElement.style.display = "block";

        }

    } catch (error) {

        console.error(error);

    } finally {

        loading = false;

        loadingElement.style.display = "none";

    }

}


/*
    Scroll monitor

    Səhifənin aşağı hissəsinə
    təxminən 500px qalmış
    növbəti oyunları yükləyir.
*/

window.addEventListener("scroll", function() {

    if (
        window.innerHeight +
        window.scrollY >=
        document.body.offsetHeight - 500
    ) {

        loadGames();

    }

});


/*
    İlk 50 oyun
*/

loadGames();

</script>

</body>
</html>
'''

path.write_text(html, encoding="utf-8")

print("search.html infinite scroll versiyasina kecirildi.")
