from flask import Flask, request, jsonify
from google.cloud import firestore
from datetime import datetime, timezone

app = Flask(__name__)
db = firestore.Client()
COLLECTION_NAME = "sensorUploads"
ALLOWED_TYPES = {"temp", "rHum", "prox", "lux", "ax", "ay", "az"}
UNIT_MAP = {
    "temp": "F",
    "rHum": "%",
    "prox": "count",
    "lux": "lux",
    "ax": "g",
    "ay": "g",
    "az": "g",
}


def format_epoch(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


@app.get("/")
def home():
    return jsonify({"message": "Average function alive"}), 200


@app.get("/average")
def average_data():
    user_id = request.args.get("userId", "")
    time_duration = request.args.get("timeDuration", "")
    data_type = request.args.get("dataType", "")

    if not user_id or not time_duration or not data_type:
        return jsonify({
            "success": False,
            "message": "Missing userId, timeDuration, or dataType"
        }), 400

    if data_type not in ALLOWED_TYPES:
        return jsonify({
            "success": False,
            "message": f"Unsupported dataType: {data_type}"
        }), 400

    try:
        time_duration = int(time_duration)
    except ValueError:
        return jsonify({
            "success": False,
            "message": "timeDuration must be an integer"
        }), 400

    try:
        now_epoch = int(datetime.now(timezone.utc).timestamp())
        min_epoch = now_epoch - time_duration

        query = db.collection(COLLECTION_NAME).where("timestampEpoch", ">=", min_epoch)
        if user_id != "All":
            query = query.where("userId", "==", user_id)

        docs = list(query.stream())

        rows = []
        for doc in docs:
            row = doc.to_dict()
            if data_type in row and isinstance(row[data_type], (int, float)):
                rows.append(row)

        if not rows:
            return jsonify({
                "success": False,
                "message": "No matching data found",
                "dataType": data_type,
                "averageValue": 0,
                "units": UNIT_MAP.get(data_type, ""),
                "minTimestampText": "N/A",
                "maxTimestampText": "N/A",
                "elapsedSeconds": 0,
                "dataPointCount": 0,
                "dataRate": 0.0,
            }), 200

        values = [float(row[data_type]) for row in rows]
        timestamps = [int(row["timestampEpoch"]) for row in rows]

        average_value = sum(values) / len(values)
        min_timestamp = min(timestamps)
        max_timestamp = max(timestamps)
        elapsed_seconds = max(0, max_timestamp - min_timestamp)
        data_point_count = len(values)
        data_rate = (data_point_count / elapsed_seconds) if elapsed_seconds > 0 else float(data_point_count)

        return jsonify({
            "success": True,
            "message": "Average computed",
            "dataType": data_type,
            "averageValue": round(average_value, 4),
            "units": UNIT_MAP.get(data_type, ""),
            "minTimestamp": min_timestamp,
            "maxTimestamp": max_timestamp,
            "minTimestampText": format_epoch(min_timestamp),
            "maxTimestampText": format_epoch(max_timestamp),
            "elapsedSeconds": elapsed_seconds,
            "dataPointCount": data_point_count,
            "dataRate": round(data_rate, 4),
        }), 200

    except Exception as exc:
        return jsonify({
            "success": False,
            "message": str(exc)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
