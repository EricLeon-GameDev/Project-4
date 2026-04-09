from flask import Flask, request, jsonify
from google.cloud import firestore
from datetime import datetime, timezone

app = Flask(__name__)
db = firestore.Client()
COLLECTION_NAME = "sensorUploads"

REQUIRED_FIELDS = [
    "userId",
    "timestampEpoch",
    "temp",
    "rHum",
    "prox",
    "lux",
    "ax",
    "ay",
    "az",
]

@app.get("/")
def home():
    return jsonify({"message": "Upload function alive"}), 200

@app.post("/upload")
def upload_sensor_data():
    data = request.get_json(silent=True) or {}

    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        return jsonify({
            "success": False,
            "message": f"Missing fields: {', '.join(missing)}"
        }), 400

    try:
        timestamp_epoch = int(data["timestampEpoch"])
        utc_dt = datetime.fromtimestamp(timestamp_epoch, tz=timezone.utc)

        doc = {
            "userId": str(data["userId"]),
            "timestampEpoch": timestamp_epoch,
            "timestampIso": utc_dt.isoformat(),
            "temp": float(data["temp"]),
            "rHum": float(data["rHum"]),
            "prox": float(data["prox"]),
            "lux": float(data["lux"]),
            "ax": float(data["ax"]),
            "ay": float(data["ay"]),
            "az": float(data["az"]),
            "createdAt": firestore.SERVER_TIMESTAMP,
        }

        db.collection(COLLECTION_NAME).add(doc)

        return jsonify({
            "success": True,
            "message": "Upload stored"
        }), 200

    except Exception as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
