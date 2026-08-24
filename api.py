from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import math
import time

app = Flask(__name__)
CORS(app)

# ============================================================
# НАСТРОЙКИ
# ============================================================

APP_NAME = "KudaMiniApp/1.0"

HEADERS = {
    "User-Agent": "KudaMiniApp/1.0 (Telegram Mini App)"
}

# Несколько бесплатных публичных Overpass-серверов.
# Если один недоступен — пробуем следующий.
OVERPASS_SERVERS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


# ============================================================
# ГЕОГРАФИЯ
# ============================================================

def distance_km(lat1, lon1, lat2, lon2):

    R = 6371.0

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        +
        math.cos(p1)
        * math.cos(p2)
        * math.sin(dl / 2) ** 2
    )

    return R * 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )


# ============================================================
# РАЗМЕР РАДИУСА
# ============================================================

def get_radius(distance):

    distance = str(distance or "")

    if "15" in distance:
        return 1500

    if "30" in distance:
        return 3000

    if "60" in distance:
        return 6000

    return 10000


# ============================================================
# КАТЕГОРИИ OSM
# ============================================================

def get_categories(interests):

    text = " ".join(
        str(x) for x in interests
    ).lower()

    categories = []

    if "кофе" in text:
        categories += [
            '["amenity"="cafe"]'
        ]

    if "еда" in text:
        categories += [
            '["amenity"="restaurant"]',
            '["amenity"="fast_food"]',
            '["amenity"="food_court"]'
        ]

    if "бары" in text:
        categories += [
            '["amenity"="bar"]',
            '["amenity"="pub"]',
            '["amenity"="nightclub"]'
        ]

    if "искусство" in text:
        categories += [
            '["tourism"="museum"]',
            '["tourism"="gallery"]',
            '["amenity"="arts_centre"]'
        ]

    if "театр" in text:
        categories += [
            '["amenity"="theatre"]'
        ]

    if "музыка" in text:
        categories += [
            '["amenity"="music_venue"]'
        ]

    if "кино" in text:
        categories += [
            '["amenity"="cinema"]'
        ]

    if "природа" in text:
        categories += [
            '["leisure"="park"]',
            '["leisure"="garden"]',
            '["leisure"="nature_reserve"]'
        ]

    if "красивые места" in text:
        categories += [
            '["tourism"="viewpoint"]',
            '["tourism"="attraction"]'
        ]

    if "история" in text:
        categories += [
            '["tourism"="museum"]',
            '["historic"]'
        ]

    if "шопинг" in text:
        categories += [
            '["shop"]'
        ]

    if "развлечения" in text:
        categories += [
            '["leisure"]',
            '["amenity"="bowling_alley"]',
            '["amenity"="escape_game"]'
        ]

    if "образование" in text:
        categories += [
            '["amenity"="library"]',
            '["amenity"="college"]',
            '["amenity"="university"]'
        ]

    if "spa" in text:
        categories += [
            '["leisure"="spa"]',
            '["amenity"="spa"]'
        ]

    if "активности" in text:
        categories += [
            '["leisure"="sports_centre"]',
            '["leisure"="fitness_centre"]',
            '["sport"]'
        ]

    if "что-нибудь необычное" in text:
        categories += [
            '["tourism"="attraction"]',
            '["tourism"="museum"]',
            '["amenity"="arts_centre"]',
            '["leisure"="park"]'
        ]

    if not categories:
        categories = [
            '["amenity"="cafe"]',
            '["amenity"="restaurant"]',
            '["tourism"="museum"]',
            '["leisure"="park"]'
        ]

    # Убираем дубликаты
    categories = list(dict.fromkeys(categories))

    return categories


# ============================================================
# ГОРОД → КООРДИНАТЫ
# ============================================================

def geocode_city(city):

    if not city:
        raise Exception(
            "Не указан город"
        )

    params = {
        "q": city,
        "format": "json",
        "limit": 1,
        "addressdetails": 1
    }

    response = requests.get(
        NOMINATIM_URL,
        params=params,
        headers=HEADERS,
        timeout=15
    )

    if response.status_code != 200:
        raise Exception(
            f"Ошибка геокодирования: HTTP {response.status_code}"
        )

    results = response.json()

    if not results:
        raise Exception(
            f"Город «{city}» не найден"
        )

    return (
        float(results[0]["lat"]),
        float(results[0]["lon"])
    )


# ============================================================
# ПОИСК OVERPASS
# ============================================================

def search_overpass(
    latitude,
    longitude,
    radius,
    categories
):

    parts = []

    for category in categories:

        parts.append(
            f"""
            nwr(
                around:{radius},
                {latitude},
                {longitude}
            )
            {category};
            """
        )

    query = f"""
    [out:json][timeout:20];

    (
        {"".join(parts)}
    );

    out center tags;
    """

    last_error = None

    for server in OVERPASS_SERVERS:

        try:

            response = requests.post(
                server,
                data=query.encode("utf-8"),
                headers={
                    **HEADERS,
                    "Content-Type":
                        "application/x-www-form-urlencoded"
                },
                timeout=25
            )

            if response.status_code != 200:

                last_error = (
                    f"{server}: "
                    f"HTTP {response.status_code}"
                )

                continue

            data = response.json()

            return data.get(
                "elements",
                []
            )

        except requests.exceptions.RequestException as error:

            last_error = (
                f"{server}: {error}"
            )

            continue

        except Exception as error:

            last_error = str(error)

            continue

    raise Exception(
        "Все бесплатные серверы поиска "
        "временно недоступны. "
        f"Последняя ошибка: {last_error}"
    )


# ============================================================
# НОРМАЛИЗАЦИЯ
# ============================================================

def normalize_places(
    elements,
    user_lat,
    user_lon
):

    places = []

    for element in elements:

        tags = element.get(
            "tags",
            {}
        )

        name = tags.get(
            "name"
        )

        if not name:
            continue

        lat = element.get(
            "lat"
        )

        lon = element.get(
            "lon"
        )

        center = element.get(
            "center",
            {}
        )

        if lat is None:
            lat = center.get(
                "lat"
            )

        if lon is None:
            lon = center.get(
                "lon"
            )

        if lat is None or lon is None:
            continue

        try:

            lat = float(lat)
            lon = float(lon)

        except:

            continue

        distance = distance_km(
            user_lat,
            user_lon,
            lat,
            lon
        )

        category = (
            tags.get("amenity")
            or tags.get("tourism")
            or tags.get("leisure")
            or tags.get("shop")
            or tags.get("historic")
            or tags.get("sport")
            or "place"
        )

        address_parts = []

        for key in [
            "addr:street",
            "addr:housenumber",
            "addr:city"
        ]:

            value = tags.get(key)

            if value:
                address_parts.append(
                    value
                )

        address = ", ".join(
            address_parts
        )

        places.append({

            "name": name,

            "category": category,

            "latitude": lat,

            "longitude": lon,

            "distance_km": round(
                distance,
                2
            ),

            "address": address

        })

    # Ближайшие сначала

    places.sort(
        key=lambda x:
            x["distance_km"]
    )

    # Удаляем дубликаты

    unique = []

    seen = set()

    for place in places:

        key = (
            place["name"].lower(),
            round(
                place["latitude"],
                4
            ),
            round(
                place["longitude"],
                4
            )
        )

        if key in seen:
            continue

        seen.add(key)

        unique.append(place)

    return unique[:20]


# ============================================================
# ГЛАВНАЯ
# ============================================================

@app.route("/")
def home():

    return jsonify({

        "status":
            "ok",

        "message":
            "Kuda backend работает 🗺️",

        "search":
            "OpenStreetMap",

        "version":
            "2.0"

    })


# ============================================================
# ПРОВЕРКА
# ============================================================

@app.route(
    "/health"
)
def health():

    return jsonify({

        "status":
            "ok",

        "service":
            "kuda-backend"

    })


# ============================================================
# ROUTE
# ============================================================

@app.route(
    "/route",
    methods=["POST"]
)
def create_route():

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({

            "error":
                "Не получены данные"

        }), 400

    # --------------------------------------------------------
    # Получаем координаты
    # --------------------------------------------------------

    latitude = data.get(
        "latitude"
    )

    longitude = data.get(
        "longitude"
    )

    city = str(
        data.get(
            "city",
            ""
        )
    ).strip()

    # --------------------------------------------------------
    # Если геолокации нет — ищем город
    # --------------------------------------------------------

    if latitude is None or longitude is None:

        if not city:

            return jsonify({

                "error":
                    "Не указана геолокация "
                    "или город."

            }), 400

        try:

            latitude, longitude = (
                geocode_city(city)
            )

        except Exception as error:

            return jsonify({

                "error":
                    "Не удалось определить "
                    "координаты города.",

                "details":
                    str(error)

            }), 503

    # --------------------------------------------------------
    # Проверяем координаты
    # --------------------------------------------------------

    try:

        latitude = float(
            latitude
        )

        longitude = float(
            longitude
        )

    except:

        return jsonify({

            "error":
                "Некорректные координаты"

        }), 400

    # --------------------------------------------------------
    # Интересы
    # --------------------------------------------------------

    interests = data.get(
        "interests",
        []
    )

    if not isinstance(
        interests,
        list
    ):

        interests = []

    # --------------------------------------------------------
    # Радиус
    # --------------------------------------------------------

    radius = get_radius(
        data.get(
            "distance",
            ""
        )
    )

    # --------------------------------------------------------
    # Категории
    # --------------------------------------------------------

    categories = get_categories(
        interests
    )

    # --------------------------------------------------------
    # Поиск
    # --------------------------------------------------------

    try:

        elements = search_overpass(
            latitude,
            longitude,
            radius,
            categories
        )

        places = normalize_places(
            elements,
            latitude,
            longitude
        )

    except Exception as error:

        return jsonify({

            "error":
                "Не удалось найти "
                "реальные места.",

            "details":
                str(error)

        }), 503

    # --------------------------------------------------------
    # Ответ
    # --------------------------------------------------------

    return jsonify({

        "status":
            "success",

        "places":
            places,

        "count":
            len(places),

        "center": {

            "latitude":
                latitude,

            "longitude":
                longitude

        }

    })


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8000
    )
