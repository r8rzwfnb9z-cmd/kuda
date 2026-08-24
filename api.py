from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)

CORS(app)


@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "Kuda backend работает 🗺️"
    })


@app.route("/route", methods=["POST"])
def create_route():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "status": "error",
            "error": "Нет данных"
        }), 400

    return jsonify({

        "status": "success",

        "message": "Запрос получен 🗺️",

        "request": {

            "city": data.get("city"),

            "latitude": data.get("latitude"),

            "longitude": data.get("longitude"),

            "moods": data.get("moods", []),

            "company": data.get("company"),

            "budget": data.get("budget"),

            "time": data.get("time"),

            "interests": data.get("interests", []),

            "distance": data.get("distance")

        }

    })


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=8000
    )
