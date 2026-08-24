from flask import Flask, request, jsonify

app = Flask(__name__)


@app.route("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "Kuda backend работает 🗺️"
    })


@app.route("/route", methods=["POST"])
def create_route():

    data = request.get_json()

    if not data:
        return jsonify({
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
