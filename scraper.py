import requests
from datetime import datetime


def get_game(app_id):
    url = f"https://store.steampowered.com/api/appdetails?appids={app_id}"

    response = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        },
        timeout=10
    )

    if response.status_code != 200:
        print(f"HTTP Error: {response.status_code}")
        return None

    result = response.json()

    if not result.get(str(app_id), {}).get("success"):
        print("Game məlumatı tapılmadı.")
        return None

    return result[str(app_id)]["data"]


def show_game(game):

    print("\n" + "=" * 60)
    print("🎮 STEAM GAME INFORMATION")
    print("=" * 60)

    print(f"Name:           {game.get('name')}")
    print(f"App ID:         {game.get('steam_appid')}")
    print(f"Type:           {game.get('type')}")

    print("\n📅 RELEASE")
    print("-" * 60)
    print(f"Release date:   {game.get('release_date', {}).get('date')}")
    print(f"Coming soon:    {game.get('release_date', {}).get('coming_soon')}")

    print("\n🏢 COMPANY")
    print("-" * 60)

    developers = game.get("developers", [])
    publishers = game.get("publishers", [])

    print(f"Developer:      {', '.join(developers)}")
    print(f"Publisher:      {', '.join(publishers)}")

    print("\n🎭 GENRES")
    print("-" * 60)

    genres = game.get("genres", [])

    for genre in genres:
        print(f"- {genre.get('description')}")

    print("\n🏷️ CATEGORIES")
    print("-" * 60)

    categories = game.get("categories", [])

    for category in categories:
        print(f"- {category.get('description')}")

    print("\n💰 PRICE")
    print("-" * 60)

    price = game.get("price_overview")

    if price:

        initial = price.get("initial", 0) / 100
        final = price.get("final", 0) / 100
        discount = price.get("discount_percent", 0)
        currency = price.get("currency")

        print(f"Original price: {initial:.2f} {currency}")
        print(f"Current price:  {final:.2f} {currency}")
        print(f"Discount:       {discount}%")

    else:

        if game.get("is_free"):
            print("FREE TO PLAY")

        else:
            print("Price information unavailable.")

    print("\n⭐ REVIEWS")
    print("-" * 60)

    print(f"Reviews:        {game.get('recommendations', {}).get('total', 0):,}")

    print("\n📝 DESCRIPTION")
    print("-" * 60)

    description = game.get("short_description")

    if description:
        print(description)

    print("\n🌐 LINKS")
    print("-" * 60)

    print(f"Steam:          https://store.steampowered.com/app/{game.get('steam_appid')}/")

    print("\n🖼️ MEDIA")
    print("-" * 60)

    print(f"Header image:   {game.get('header_image')}")

    screenshots = game.get("screenshots", [])

    print(f"Screenshots:    {len(screenshots)}")

    movies = game.get("movies", [])

    print(f"Videos:         {len(movies)}")

    print("\n⏱️ SCRAPED")
    print("-" * 60)

    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    print("=" * 60)


def main():

    # Cyberpunk 2077
    app_id = 1091500

    print(f"Fetching Steam App ID: {app_id}...")

    game = get_game(app_id)

    if game:
        show_game(game)


if __name__ == "__main__":
    main()
