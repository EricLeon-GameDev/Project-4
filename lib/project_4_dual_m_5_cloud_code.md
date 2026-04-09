# Project 4 Code Pack

Below is a minimal full implementation based directly on the assignment.

---

## 1) `platformio.ini`

```ini
[env:m5stack-core2]
platform = espressif32
board = m5stack-core2
framework = arduino
monitor_speed = 115200

lib_deps =
  m5stack/M5Core2 @ ^0.1.9
  bblanchon/ArduinoJson @ ^7.0.4
  adafruit/Adafruit SHT4x Library @ ^1.0.5
  adafruit/Adafruit VCNL4040 @ ^1.0.3
```

---

## 2) `src/secrets.h`

```cpp
#pragma once

// ---------- WIFI ----------
static const char* WIFI_SSID = "YOUR_WIFI_NAME";
static const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";

// ---------- CLOUD RUN URLS ----------
static const char* UPLOAD_URL = "https://YOUR-UPLOAD-SERVICE.run.app/upload";
static const char* AVERAGE_URL = "https://YOUR-AVERAGE-SERVICE.run.app/average";

// ---------- DEVICE USER ----------
// Change this to a different hardcoded value on the second M5.
static const char* USER_ID = "DanGrissom";   // other device: "JonDoe"
```

---

## 3) `src/main.cpp`

```cpp
#include <M5Core2.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_SHT4x.h>
#include <Adafruit_VCNL4040.h>
#include <time.h>
#include "secrets.h"

Adafruit_SHT4x sht4 = Adafruit_SHT4x();
Adafruit_VCNL4040 vcnl4040 = Adafruit_VCNL4040();

static const unsigned long SCREEN1_REFRESH_MS = 5000;
static const char* NTP_SERVER = "pool.ntp.org";
static const long GMT_OFFSET_SEC = 0;
static const int DAYLIGHT_OFFSET_SEC = 0;

enum ScreenState {
  SCREEN_UPLOAD = 0,
  SCREEN_FETCH = 1,
  SCREEN_RESULTS = 2
};

ScreenState currentScreen = SCREEN_UPLOAD;

struct SensorSnapshot {
  float tempF = 0.0f;
  float rHum = 0.0f;
  uint16_t prox = 0;
  float lux = 0.0f;
  float ax = 0.0f;
  float ay = 0.0f;
  float az = 0.0f;
  time_t utcEpoch = 0;
  String utcText = "Not Synced";
};

struct AverageResult {
  bool success = false;
  String dataType = "";
  float averageValue = 0.0f;
  String units = "";
  String minTime = "N/A";
  String maxTime = "N/A";
  long elapsedSeconds = 0;
  int dataPointCount = 0;
  float dataRate = 0.0f;
  String errorMessage = "";
};

SensorSnapshot latest;
AverageResult avgResult;
String uploadStatus = "No upload yet";
unsigned long lastUploadRefresh = 0;

const char* userOptions[] = {"DanGrissom", "JonDoe", "All"};
const int USER_OPTION_COUNT = 3;
int selectedUser = 0;

const int durationOptions[] = {5, 30, 120};
const int DURATION_OPTION_COUNT = 3;
int selectedDuration = 0;

const char* dataTypeOptions[] = {"temp", "rHum", "ax"};
const int DATA_TYPE_OPTION_COUNT = 3;
int selectedDataType = 0;

// 0=user, 1=duration, 2=dataType, 3=get average
int activeFetchField = 0;

void connectWifi();
void syncTimeUtc();
String formatUtcTime(time_t epoch);
bool readSensors(SensorSnapshot &snap);
bool uploadSnapshot(const SensorSnapshot &snap);
bool fetchAverage(AverageResult &result);
void drawUploadScreen();
void drawFetchScreen();
void drawResultsScreen();
void drawHeader(const String &title);
void handleButtons();
void nextScreen();
void prevScreen();

void setup() {
  M5.begin();
  M5.IMU.Init();
  Wire.begin();

  Serial.begin(115200);
  M5.Lcd.setRotation(1);
  M5.Lcd.setTextSize(2);
  M5.Lcd.fillScreen(BLACK);

  drawHeader("Project 4 Booting...");
  M5.Lcd.setCursor(10, 50);
  M5.Lcd.println("Starting sensors...");

  bool shtOk = sht4.begin();
  bool vcnlOk = vcnl4040.begin();

  M5.Lcd.printf("SHT40: %s\n", shtOk ? "OK" : "FAIL");
  M5.Lcd.printf("VCNL4040: %s\n", vcnlOk ? "OK" : "FAIL");

  connectWifi();
  syncTimeUtc();
  readSensors(latest);
  drawUploadScreen();
}

void loop() {
  M5.update();
  handleButtons();

  if (currentScreen == SCREEN_UPLOAD) {
    unsigned long now = millis();
    if (now - lastUploadRefresh >= SCREEN1_REFRESH_MS) {
      lastUploadRefresh = now;
      readSensors(latest);
      bool ok = uploadSnapshot(latest);
      uploadStatus = ok ? "Upload OK" : "Upload FAIL";
      drawUploadScreen();
    }
  }
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  drawHeader("Connecting WiFi");
  M5.Lcd.setCursor(10, 50);
  M5.Lcd.printf("SSID: %s\n", WIFI_SSID);

  int dots = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    M5.Lcd.print(".");
    dots++;
    if (dots % 20 == 0) {
      M5.Lcd.println();
    }
  }

  M5.Lcd.println("\nConnected!");
  M5.Lcd.println(WiFi.localIP());
  delay(1000);
}

void syncTimeUtc() {
  configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);

  struct tm timeinfo;
  drawHeader("Syncing UTC Time");
  M5.Lcd.setCursor(10, 50);

  int tries = 0;
  while (!getLocalTime(&timeinfo) && tries < 20) {
    M5.Lcd.println("Waiting for NTP...");
    delay(500);
    tries++;
  }

  if (getLocalTime(&timeinfo)) {
    time_t now;
    time(&now);
    M5.Lcd.println("UTC synced!");
    M5.Lcd.println(formatUtcTime(now));
  } else {
    M5.Lcd.println("Time sync failed");
  }
  delay(1000);
}

String formatUtcTime(time_t epoch) {
  struct tm *utc = gmtime(&epoch);
  if (!utc) return "Invalid UTC";

  char buffer[40];
  strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M:%S UTC", utc);
  return String(buffer);
}

bool readSensors(SensorSnapshot &snap) {
  sensors_event_t humidity, temp;
  if (sht4.getEvent(&humidity, &temp)) {
    snap.rHum = humidity.relative_humidity;
    snap.tempF = (temp.temperature * 9.0f / 5.0f) + 32.0f;
  }

  snap.prox = vcnl4040.getProximity();
  snap.lux = vcnl4040.getLux();

  M5.IMU.getAccelData(&snap.ax, &snap.ay, &snap.az);

  time(&snap.utcEpoch);
  snap.utcText = formatUtcTime(snap.utcEpoch);
  return true;
}

bool uploadSnapshot(const SensorSnapshot &snap) {
  if (WiFi.status() != WL_CONNECTED) {
    return false;
  }

  HTTPClient http;
  http.begin(UPLOAD_URL);
  http.addHeader("Content-Type", "application/json");

  JsonDocument doc;
  doc["userId"] = USER_ID;
  doc["timestampEpoch"] = (long)snap.utcEpoch;
  doc["temp"] = snap.tempF;
  doc["rHum"] = snap.rHum;
  doc["prox"] = snap.prox;
  doc["lux"] = snap.lux;
  doc["ax"] = snap.ax;
  doc["ay"] = snap.ay;
  doc["az"] = snap.az;

  String body;
  serializeJson(doc, body);
  Serial.println("UPLOAD BODY:");
  Serial.println(body);

  int httpCode = http.POST(body);
  String response = http.getString();
  Serial.printf("UPLOAD HTTP %d\n", httpCode);
  Serial.println(response);
  http.end();

  return httpCode >= 200 && httpCode < 300;
}

bool fetchAverage(AverageResult &result) {
  result = AverageResult();

  if (WiFi.status() != WL_CONNECTED) {
    result.errorMessage = "WiFi disconnected";
    return false;
  }

  String url = String(AVERAGE_URL)
    + "?userId=" + userOptions[selectedUser]
    + "&timeDuration=" + String(durationOptions[selectedDuration])
    + "&dataType=" + dataTypeOptions[selectedDataType];

  HTTPClient http;
  http.begin(url);
  int httpCode = http.GET();
  String response = http.getString();
  Serial.printf("AVERAGE HTTP %d\n", httpCode);
  Serial.println(response);

  if (!(httpCode >= 200 && httpCode < 300)) {
    result.errorMessage = "HTTP error: " + String(httpCode);
    http.end();
    return false;
  }

  JsonDocument doc;
  DeserializationError err = deserializeJson(doc, response);
  http.end();

  if (err) {
    result.errorMessage = "JSON parse failed";
    return false;
  }

  result.success = doc["success"] | false;
  result.dataType = String((const char*)doc["dataType"]);
  result.averageValue = doc["averageValue"] | 0.0;
  result.units = String((const char*)doc["units"]);
  result.minTime = String((const char*)doc["minTimestampText"]);
  result.maxTime = String((const char*)doc["maxTimestampText"]);
  result.elapsedSeconds = doc["elapsedSeconds"] | 0;
  result.dataPointCount = doc["dataPointCount"] | 0;
  result.dataRate = doc["dataRate"] | 0.0;
  result.errorMessage = String((const char*)doc["message"]);

  return result.success;
}

void drawHeader(const String &title) {
  M5.Lcd.fillScreen(BLACK);
  M5.Lcd.setTextColor(WHITE, BLACK);
  M5.Lcd.setCursor(10, 10);
  M5.Lcd.setTextSize(2);
  M5.Lcd.println(title);
  M5.Lcd.drawLine(0, 35, 320, 35, WHITE);
}

void drawUploadScreen() {
  drawHeader("Screen 1: Upload");
  M5.Lcd.setCursor(10, 45);
  M5.Lcd.printf("User: %s\n", USER_ID);
  M5.Lcd.printf("UTC: %s\n", latest.utcText.c_str());
  M5.Lcd.println();
  M5.Lcd.printf("Temp: %.2f F\n", latest.tempF);
  M5.Lcd.printf("rHum: %.2f %%\n", latest.rHum);
  M5.Lcd.printf("Prox: %u\n", latest.prox);
  M5.Lcd.printf("Lux:  %.2f\n", latest.lux);
  M5.Lcd.printf("ax: %.3f\n", latest.ax);
  M5.Lcd.printf("ay: %.3f\n", latest.ay);
  M5.Lcd.printf("az: %.3f\n", latest.az);
  M5.Lcd.println();
  M5.Lcd.printf("Status: %s\n", uploadStatus.c_str());
  M5.Lcd.println("A=Prev  B=Next Screen  C=Manual Refresh");
}

void drawFetchScreen() {
  drawHeader("Screen 2: Fetch Params");
  M5.Lcd.setCursor(10, 45);

  M5.Lcd.printf("%s User: %s\n", activeFetchField == 0 ? ">" : " ", userOptions[selectedUser]);
  M5.Lcd.printf("%s Time: %ds\n", activeFetchField == 1 ? ">" : " ", durationOptions[selectedDuration]);
  M5.Lcd.printf("%s Type: %s\n", activeFetchField == 2 ? ">" : " ", dataTypeOptions[selectedDataType]);
  M5.Lcd.printf("%s Get Average\n", activeFetchField == 3 ? ">" : " ");

  M5.Lcd.println();
  M5.Lcd.println("A = move field");
  M5.Lcd.println("B = change option");
  M5.Lcd.println("C = run / next");
}

void drawResultsScreen() {
  drawHeader("Screen 3: Results");
  M5.Lcd.setCursor(10, 45);

  if (!avgResult.success) {
    M5.Lcd.println("Average request failed");
    M5.Lcd.printf("Reason: %s\n", avgResult.errorMessage.c_str());
    M5.Lcd.println();
    M5.Lcd.println("A=Prev  B=Fetch Screen  C=Retry");
    return;
  }

  M5.Lcd.printf("Type: %s\n", avgResult.dataType.c_str());
  M5.Lcd.printf("Average: %.3f %s\n", avgResult.averageValue, avgResult.units.c_str());
  M5.Lcd.printf("From: %s\n", avgResult.minTime.c_str());
  M5.Lcd.printf("To:   %s\n", avgResult.maxTime.c_str());
  M5.Lcd.printf("Elapsed: %ld s\n", avgResult.elapsedSeconds);
  M5.Lcd.printf("Points: %d\n", avgResult.dataPointCount);
  M5.Lcd.printf("Rate: %.3f pts/s\n", avgResult.dataRate);
  M5.Lcd.println();
  M5.Lcd.println("A=Prev  B=Fetch Screen  C=Retry");
}

void nextScreen() {
  if (currentScreen == SCREEN_UPLOAD) currentScreen = SCREEN_FETCH;
  else if (currentScreen == SCREEN_FETCH) currentScreen = SCREEN_RESULTS;
  else currentScreen = SCREEN_UPLOAD;

  if (currentScreen == SCREEN_UPLOAD) drawUploadScreen();
  else if (currentScreen == SCREEN_FETCH) drawFetchScreen();
  else drawResultsScreen();
}

void prevScreen() {
  if (currentScreen == SCREEN_UPLOAD) currentScreen = SCREEN_RESULTS;
  else if (currentScreen == SCREEN_FETCH) currentScreen = SCREEN_UPLOAD;
  else currentScreen = SCREEN_FETCH;

  if (currentScreen == SCREEN_UPLOAD) drawUploadScreen();
  else if (currentScreen == SCREEN_FETCH) drawFetchScreen();
  else drawResultsScreen();
}

void handleButtons() {
  if (M5.BtnA.wasPressed()) {
    if (currentScreen == SCREEN_FETCH) {
      activeFetchField = (activeFetchField + 3) % 4;
      drawFetchScreen();
    } else {
      prevScreen();
    }
  }

  if (M5.BtnB.wasPressed()) {
    if (currentScreen == SCREEN_UPLOAD) {
      currentScreen = SCREEN_FETCH;
      drawFetchScreen();
    } else if (currentScreen == SCREEN_FETCH) {
      switch (activeFetchField) {
        case 0:
          selectedUser = (selectedUser + 1) % USER_OPTION_COUNT;
          break;
        case 1:
          selectedDuration = (selectedDuration + 1) % DURATION_OPTION_COUNT;
          break;
        case 2:
          selectedDataType = (selectedDataType + 1) % DATA_TYPE_OPTION_COUNT;
          break;
        case 3:
          // no-op, C actually runs the request
          break;
      }
      drawFetchScreen();
    } else if (currentScreen == SCREEN_RESULTS) {
      currentScreen = SCREEN_FETCH;
      drawFetchScreen();
    }
  }

  if (M5.BtnC.wasPressed()) {
    if (currentScreen == SCREEN_UPLOAD) {
      readSensors(latest);
      bool ok = uploadSnapshot(latest);
      uploadStatus = ok ? "Upload OK" : "Upload FAIL";
      drawUploadScreen();
    } else if (currentScreen == SCREEN_FETCH) {
      if (activeFetchField == 3) {
        fetchAverage(avgResult);
        currentScreen = SCREEN_RESULTS;
        drawResultsScreen();
      } else {
        activeFetchField = (activeFetchField + 1) % 4;
        drawFetchScreen();
      }
    } else if (currentScreen == SCREEN_RESULTS) {
      fetchAverage(avgResult);
      drawResultsScreen();
    }
  }
}
```

---

## 4) Cloud Function 1 — Upload Service

### `upload_function/requirements.txt`

```txt
flask==3.0.3
google-cloud-firestore==2.16.0
gunicorn==22.0.0
```

### `upload_function/main.py`

```python
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
```

### `upload_function/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD exec gunicorn --bind :8080 --workers 1 --threads 8 --timeout 0 main:app
```

---

## 5) Cloud Function 2 — Averaging Service

### `average_function/requirements.txt`

```txt
flask==3.0.3
google-cloud-firestore==2.16.0
gunicorn==22.0.0
```

### `average_function/main.py`

```python
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
```

### `average_function/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD exec gunicorn --bind :8080 --workers 1 --threads 8 --timeout 0 main:app
```

---

## 6) Firestore document shape

Each upload inserts one flat document into collection `sensorUploads`:

```json
{
  "userId": "DanGrissom",
  "timestampEpoch": 1744651232,
  "timestampIso": "2025-04-14T20:20:32+00:00",
  "temp": 72.1,
  "rHum": 41.3,
  "prox": 8,
  "lux": 215.6,
  "ax": 0.03,
  "ay": -0.01,
  "az": 0.98,
  "createdAt": "server timestamp"
}
```

---

## 7) What to change before running

1. Put your Wi-Fi name/password into `secrets.h`
2. Deploy both cloud services and paste their URLs into `secrets.h`
3. Change `USER_ID` on the second M5 to the second hardcoded user
4. Confirm your sensor libraries match your exact hardware wiring
5. In Google Cloud, enable Firestore and authenticate Cloud Run with a service account that can read/write Firestore

---

## 8) Deploy commands (example)

### Upload function

```bash
gcloud run deploy project4-upload \
  --source . \
  --region us-west1 \
  --allow-unauthenticated
```

### Average function

```bash
gcloud run deploy project4-average \
  --source . \
  --region us-west1 \
  --allow-unauthenticated
```

---

## 9) Notes

- This implementation is intentionally minimal and rubric-focused.
- Screen 1 updates every 5 seconds and uploads every 5 seconds.
- Screen 2 contains userId, timeDuration, dataType, and Get Average.
- Screen 3 displays the returned average data and required stats.
- The assignment allows limiting average selections to 3 data types, so this uses `temp`, `rHum`, and `ax` on the M5 UI.
- All live values still appear on Screen 1.
```

