from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import math

app = Flask(__name__)

CORS(app)


# ==========================================
# НАСТРОЙКИ
# ==========================================

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

HEADERS = {
    "User-Agent": "Kuda Telegram Mini App"
}


# ==========================================
# ГЛАВНАЯ
# ==========================================

@app.route("/")
def home():

    return jsonify({
        "status": "ok",
        "message": "Kuda backend работает 🗺️"
    })


# ==========================================
# СООТВЕТСТВИЕ ИНТЕРЕСОВ OSM
# ==========================================

def get_osm_filters(interests):

    filters = []

    for interest in interests:

        if interest in [
            "Кофе и уютные места",
            "Еда"
        ]:

            filters.append(
                'node["amenity"~"cafe|restaurant|fast_food|food_court"]'
            )

        elif interest == "Бары и вечеринки":

            filters.append(
                'node["amenity"~"bar|pub|nightclub"]'
            )

        elif interest == "Искусство":

            filters.append(
                'node["tourism"="museum"]'
            )

            filters.append(
                'node["amenity"="arts_centre"]'
            )

        elif interest == "Театр и шоу":

            filters.append(
                'node["amenity"~"theatre|arts_centre"]'
            )

        elif interest == "Музыка":

            filters.append(
                'node["amenity"~"music_venue|concert_hall"]'
            )

        elif interest == "Кино":

            filters.append(
                'node["amenity"="cinema"]'
            )

        elif interest == "Природа":

            filters.append(
                'node["leisure"~"park|garden|nature_reserve"]'
            )

        elif interest == "Красивые места":

            filters.append(
                'node["tourism"~"viewpoint|attraction"]'
            )

        elif interest == "История":

            filters.append(
                'node["historic"]'
            )

        elif interest == "Шопинг":

            filters.append(
                'node["shop"]'
            )

        elif interest == "Развлечения":

            filters.append(
                'node["leisure"~"bowling_alley|water_park|amusement_arcade"]'
            )

        elif interest == "Образование":

            filters.append(
                'node["amenity"~"library|school|college|university"]'
            )

        elif interest == "SPA и релакс":

            filters.append(
                'node["leisure"~"spa|fitness_centre"]'
            )

        elif interest == "Активности":

            filters.append(
                'node["leisure"~"sports_centre|fitness_centre|pitch"]'
            )

        elif interest == "Актуальные мероприятия":

            filters.append(
                'node["amenity"~"theatre|cinema|arts_centre|music_venue"]'
            )

        elif interest == "Что-нибудь необычное":

            filters.append(
                'node["tourism"~"attraction|viewpoint"]'
            )

    return list(set(filters))


# ==========================================
# РАССТОЯНИЕ
# ==========================================

def get_radius(distance):

    if distance == "До 15 минут":
        return 1500

    if distance == "До 30 минут":
        return 3000

    if distance == "До 60 минут":
        return 7000

    if distance == "Рядом с центром":
        return 2500

    if distance == "Весь город":
        return 10000

    return 5000


# ==========================================
# РАССТОЯНИЕ МЕЖДУ ТОЧКАМИ
# ==========================================

def calculate_distance(lat1, lon1, lat2, lon2):

    radius = 6371

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        +
        math.cos(lat1)
        *
        math.cos(lat2)
        *
        math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return radius * c


# ==========================================
# ПОИСК МЕСТ
# ==========================================

def search_places(
    latitude,
    longitude,
    interests,
    distance
):

    filters = get_osm_filters(interests)

    if not filters:

        filters = [
            'node["tourism"]',
            'node["amenity"]',
            'node["leisure"]'
        ]


    radius = get_radius(distance)


    filter_text = "\n".join(
        [
            f"  {item}(around:{radius},{latitude},{longitude});"
            for item in filters
        ]
    )


    query = f"""
    [out:json][timeout:25];

    (
    {filter_text}
    );

    out center tags;
    """


    response = requests.post(
        OVERPASS_URL,
        data=query,
        headers=HEADERS,
        timeout=35
    )


    response.raise_for_status()


    data = response.json()


    places = []


    for element in data.get("elements", []):

        tags = element.get("tags", {})


        name = tags.get("name")

        if not name:
            continue


        lat = element.get("lat")

        lon = element.get("lon")


        if lat is None or lon is None:

            center = element.get("center", {})

            lat = center.get("lat")

            lon = center.get("lon")


        if lat is None or lon is None:
            continue


        distance_km = calculate_distance(
            latitude,
            longitude,
            float(lat),
            float(lon)
        )


        category = (
            tags.get("amenity")
            or
            tags.get("tourism")
            or
            tags.get("leisure")
            or
            tags.get("shop")
            or
            tags.get("historic")
            or
            "место"
        )


        address_parts = []


        for key in [
            "addr:street",
            "addr:housenumber",
            "addr:city"
        ]:

            if tags.get(key):

                address_parts.append(
                    tags.get(key)
                )


        address = ", ".join(
            address_parts
        )


        places.append({

            "name": name,

            "category": category,

            "latitude": float(lat),

            "longitude": float(lon),

            "distance_km":
                round(distance_km, 2),

            "address":
                address,

            "website":
                tags.get("website", ""),

            "phone":
                tags.get("phone", "")

        })


    # --------------------------------------
    # УБИРАЕМ ДУБЛИКАТЫ
    # --------------------------------------

    unique = {}

    for place in places:

        key = (
            place["name"].lower(),
            round(place["latitude"], 4),
            round(place["longitude"], 4)
        )

        unique[key] = place


    places = list(
        unique.values()
    )


    # --------------------------------------
    # СНАЧАЛА БЛИЖАЙШИЕ
    # --------------------------------------

    places.sort(
        key=lambda x: x["distance_km"]
    )


    # --------------------------------------
    # МАКСИМУМ 30 МЕСТ
    # --------------------------------------

    return places[:30]


# ==========================================
# ROUTE
# ==========================================

@app.route(
    "/route",
    methods=["POST"]
)
def create_route():

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "status": "error",
                "error": "Нет данных"
            }), 400


        latitude = data.get(
            "latitude"
        )

        longitude = data.get(
            "longitude"
        )


        interests = data.get(
            "interests",
            []
        )


        distance = data.get(
            "distance",
            ""
        )


        # ==================================
        # ЕСЛИ ГЕОЛОКАЦИЯ ЕСТЬ
        # ==================================

        if latitude and longitude:

            places = search_places(

                float(latitude),

                float(longitude),

                interests,

                distance

            )


            return jsonify({

                "status": "success",

                "message":
                    "Реальные места найдены 🗺️",

                "places":
                    places,

                "count":
                    len(places),

                "request": {

                    "city":
                        data.get("city"),

                    "latitude":
                        latitude,

                    "longitude":
                        longitude,

                    "moods":
                        data.get("moods", []),

                    "company":
                        data.get("company"),

                    "budget":
                        data.get("budget"),

                    "time":
                        data.get("time"),

                    "interests":
                        interests,

                    "distance":
                        distance

                }

            })


        # ==================================
        # ЕСЛИ ТОЛЬКО ГОРОД
        # ==================================

        return jsonify({

            "status": "success",

            "message":
                "Анкета получена, но для поиска мест нужны координаты 📍",

            "places": [],

            "count": 0,

            "request": {

                "city":
                    data.get("city"),

                "latitude":
                    latitude,

                "longitude":
                    longitude,

                "moods":
                    data.get("moods", []),

                "company":
                    data.get("company"),

                "budget":
                    data.get("budget"),

                "time":
                    data.get("time"),

                "interests":
                    interests,

                "distance":
                    distance

            }

        })


    except Exception as error:

        print(
            "ERROR:",
            str(error)
        )

        return jsonify({

            "status":
                "error",

            "error":
                str(error)

        }), 500


# ==========================================
# ЗАПУСК
# ==========================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=8000

    )
