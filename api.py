from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import math
import time
app = Flask(__name__)
CORS(app)
# ==========================================
# OVERPASS SERVERS
# ==========================================
OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
# ==========================================
# ГЕОГРАФИЯ
# ==========================================
def distance_km(lat1, lon1, lat2, lon2):
    R = 6371
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
# ==========================================
# КАТЕГОРИИ
# ==========================================
def get_categories(interests):
    categories = []
    text = " ".join(interests).lower()
    if "кофе" in text:
        categories += [
            '["amenity"="cafe"]'
        ]
    if "еда" in text:
        categories += [
            '["amenity"="restaurant"]',
            '["amenity"="fast_food"]'
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
            '["tourism"="gallery"]'
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
            '["leisure"="garden"]'
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
            '["amenity"="bowling_alley"]'
        ]
    if "образование" in text:
        categories += [
            '["amenity"="library"]',
            '["amenity"="college"]',
            '["amenity"="university"]'
        ]
    if "spa" in text.lower():
        categories += [
            '["leisure"="spa"]',
            '["amenity"="spa"]'
        ]
    if "активности" in text:
        categories += [
            '["leisure"="sports_centre"]',
            '["leisure"="fitness_centre"]'
        ]
    if not categories:
        categories = [
            '["amenity"="cafe"]',
            '["amenity"="restaurant"]',
            '["tourism"="museum"]',
            '["leisure"="park"]'
        ]
    return categories
# ==========================================
# ПОИСК ЧЕРЕЗ OVERPASS
# ==========================================
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
    [out:json][timeout:25];
    (
        {"".join(parts)}
    );
    out center tags;
    """
    headers = {
        "User-Agent": "KudaMiniApp/1.0"
    }
    last_error = None
    for server in OVERPASS_SERVERS:
        try:
            response = requests.post(
                server,
                data=query.encode("utf-8"),
                headers=headers,
                timeout=30
            )
            if response.status_code != 200:
                last_error = (
                    f"HTTP {response.status_code}"
                )
                continue
            data = response.json()
            return data.get(
                "elements",
                []
            )
        except Exception as error:
            last_error = str(error)
            continue
    raise Exception(
        "Не удалось связаться с серверами поиска мест. "
        + str(last_error)
    )
# ==========================================
# НОРМАЛИЗАЦИЯ МЕСТ
# ==========================================
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
        distance = distance_km(
            user_lat,
            user_lon,
            float(lat),
            float(lon)
        )
        category = (
            tags.get("amenity")
            or tags.get("tourism")
            or tags.get("leisure")
            or tags.get("shop")
            or tags.get("historic")
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
                address_parts.append(value)
        address = ", ".join(
            address_parts
        )
        places.append({
            "name": name,
            "category": category,
            "latitude": float(lat),
            "longitude": float(lon),
            "distance_km": round(
                distance,
                2
            ),
            "address": address
        })
    places.sort(
        key=lambda x:
            x["distance_km"]
    )
    # убираем дубликаты по названию
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
# ==========================================
# ГЛАВНАЯ
# ==========================================
@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message":
            "Kuda backend работает 🗺️",
        "search":
            "OpenStreetMap"
    })
# ==========================================
# ROUTE
# ==========================================
@app.route(
    "/route",
    methods=["POST"]
)
def create_route():
    data = request.get_json()
    if not data:
        return jsonify({
            "error":
                "Нет данных"
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
    if not latitude or not longitude:
        return jsonify({
            "error":
                "Не получена геолокация. "
                "Для поиска реальных мест "
                "сейчас нужна геолокация."
        }), 400
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
    # --------------------------------------
    # РАДИУС
    # --------------------------------------
    distance = data.get(
        "distance",
        ""
    )
    if "15" in distance:
        radius = 1500
    elif "30" in distance:
        radius = 3000
    elif "60" in distance:
        radius = 6000
    else:
        radius = 10000
    # --------------------------------------
    # КАТЕГОРИИ
    # --------------------------------------
    categories = get_categories(
        interests
    )
    # --------------------------------------
    # ПОИСК
    # --------------------------------------
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
                "Не удалось найти реальные места.",
            "details":
                str(error)
        }), 503
    return jsonify({
        "status":
            "success",
        "places":
            places,
        "count":
            len(places)
    })
# ==========================================
# START
# ==========================================
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=8000
    )
