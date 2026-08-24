from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


@app.route("/")
def home():

    return jsonify({
        "status": "ok",
        "message": "Kuda backend работает 🗺️"
    })


def search_places(latitude, longitude, radius=3000):

    query = f"""
    [out:json][timeout:25];

    (
      node(around:{radius},{latitude},{longitude})["amenity"];
      way(around:{radius},{latitude},{longitude})["amenity"];

      node(around:{radius},{latitude},{longitude})["tourism"];
      way(around:{radius},{latitude},{longitude})["tourism"];

      node(around:{radius},{latitude},{longitude})["leisure"];
      way(around:{radius},{latitude},{longitude})["leisure"];

      node(around:{radius},{latitude},{longitude})["shop"];
      way(around:{radius},{latitude},{longitude})["shop"];
    );

    out center tags;
    """

    response = requests.post(
        OVERPASS_URL,
        data=query,
        headers={
            "User-Agent": "KudaMiniApp/1.0"
        },
        timeout=30
    )

    response.raise_for_status()

    return response.json()


def convert_places(data):

    places = []

    for element in data.get("elements", []):

        tags = element.get("tags", {})

        name = tags.get("name")

        if not name:
            continue

        latitude = element.get("lat")
        longitude = element.get("lon")

        if latitude is None:
            center = element.get("center", {})

            latitude = center.get("lat")
            longitude = center.get("lon")

        if latitude is None or longitude is None:
            continue

        place_type = (
            tags.get("amenity")
            or tags.get("tourism")
            or tags.get("leisure")
            or tags.get("shop")
            or "place"
        )

        places.append({

            "name": name,

            "type": place_type,

            "latitude": latitude,

            "longitude": longitude,

            "address":
                tags.get("addr:street", "")

        })

    return places


@app.route("/route", methods=["POST"])
def create_route():

    data = request.get_json()

    if not data:

        return jsonify({
            "status": "error",
            "message": "Нет данных"
        }), 400


    latitude = data.get("latitude")
    longitude = data.get("longitude")

    city = data.get("city")

    interests = data.get(
        "interests",
        []
    )

    distance = data.get(
        "distance"
    )


    # Если пользователь использовал геолокацию

    if latitude and longitude:

        try:

            places_data = search_places(
                latitude,
                longitude
            )

            places = convert_places(
                places_data
            )

        except Exception as error:

            return jsonify({

                "status": "error",

                "message":
                    "Не удалось получить места",

                "details":
                    str(error)

            }), 500


    else:

        places = []


    # Простая фильтрация по интересам

    filtered_places = []

    interest_text = " ".join(
        interests
    ).lower()


    for place in places:

        place_text = (
            place["name"]
            + " "
            + place["type"]
        ).lower()


        if not interest_text:

            filtered_places.append(
                place
            )

            continue


        keywords = {

            "кофе":
                ["cafe", "coffee"],

            "еда":
                [
                    "restaurant",
                    "fast_food",
                    "food_court",
                    "cafe"
                ],

            "бары":
                ["bar", "pub"],

            "искусство":
                [
                    "arts_centre",
                    "gallery",
                    "museum"
                ],

            "театр":
                ["theatre"],

            "музыка":
                ["music_venue"],

            "кино":
                ["cinema"],

            "природа":
                [
                    "park",
                    "garden",
                    "nature_reserve"
                ],

            "шопинг":
                [
                    "shop",
                    "mall",
                    "clothes"
                ],

            "развлечения":
                [
                    "leisure",
                    "amusement"
                ],

            "spa":
                ["spa"],

            "активности":
                [
                    "sports_centre",
                    "fitness_centre"
                ],

            "история":
                [
                    "museum",
                    "monument",
                    "castle"
                ]

        }


        matched = False


        for keyword, types in keywords.items():

            if keyword in interest_text:

                for place_type in types:

                    if (
                        place_type
                        in place["type"].lower()
                        or place_type
                        in place_text
                    ):

                        matched = True

                        break


            if matched:
                break


        if matched:

            filtered_places.append(
                place
            )


    # Если фильтр оказался слишком строгим,
    # показываем обычные места

    if len(filtered_places) < 3:

        filtered_places = places


    # Ограничиваем количество

    filtered_places =
        filtered_places[:20]


    return jsonify({

        "status":
            "success",

        "message":
            "Места найдены 🗺️",

        "request": {

            "city":
                city,

            "latitude":
                latitude,

            "longitude":
                longitude,

            "moods":
                data.get(
                    "moods",
                    []
                ),

            "company":
                data.get(
                    "company"
                ),

            "budget":
                data.get(
                    "budget"
                ),

            "time":
                data.get(
                    "time"
                ),

            "interests":
                interests,

            "distance":
                distance

        },

        "places":
            filtered_places

    })


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8000
    )
