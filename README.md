# FERM — IoT Fermentation Monitoring

FERM is an IoT monitoring prototype for collecting environmental and device-status readings from sensor units, storing historical data, and generating alerts when readings may indicate abnormal or potentially hazardous conditions.

The repository contains a Flask backend, an SQLite database, a sensor-data simulator, a frontend/platform directory, and an Arduino sensor sketch.

## Features

- Receive sensor readings from monitoring units through an HTTP API.
- Store raw readings, alerts, and the latest status of each unit in SQLite.
- Retrieve historical readings, recent alerts, and registered unit information.
- Generate alerts for flame detection, high temperature, high fire risk, and sudden VOC increases.
- Simulate an IoT unit to test the backend without connecting physical hardware.
- Include an Arduino sketch for the sensor-side implementation.

## Repository Structure

```text
ferm/
├── hardware/
│   └── ferm_sensors/
│       └── ferm_sensors_test02.ino   # Arduino sensor sketch
├── platform/                         # Frontend/platform files
├── app.py                            # Flask API and web entry point
├── ferm.db                           # SQLite database
└── simulator.py                      # Simulated sensor-data publisher
```

## System Overview

```text
       FERM sensor device                         Python simulator
               |                                          |
               | USB connection stays active              | HTTP POST
               | during device operation                  |
               v                                          v
        Local computer / development environment ---> Flask backend
          |  Arduino IDE (firmware)                       app.py
          |  Frontend: npm run dev                           |
          |                                                 |
          +---------------- Frontend <--- JSON API ---------+
                                                            |
                                              +-------------+-------------+
                                              |                           |
                                              v                           v
                                        SQLite database              Alert rules
                                           ferm.db
```

During normal operation, the FERM device stays connected to the computer over USB. USB is used both when programming the Arduino firmware and while the device is connected for live sensor-data operation. The local development stack consists of the USB-connected device, the Flask API, and the frontend development server started with `npm run dev`. The Flask backend accepts structured sensor readings through `POST /data`, stores them, updates the unit's last-seen time and battery voltage, evaluates alert rules, and exposes the data through its GET endpoints.

## Requirements

- Python 3 (the repository does not specify a tested minimum version)
- Flask
- Requests (only required to run the simulator)
- A modern web browser if using the frontend

SQLite is provided by Python's standard library; no separate database server is required.

## Getting Started

There are two ways to run the project:

- **Physical device (normal workflow):** connect the FERM unit to the computer over USB, upload/run its Arduino sketch, keep the USB connection in place for live operation, then start the Flask backend and frontend development server.
- **Simulator (development/testing only):** run `simulator.py` to send sample readings to Flask without relying on live sensor readings from the physical unit.

### 1. Clone the repository

```bash
git clone https://github.com/oreh-coder/ferm.git
cd ferm
```

### 2. Install Python dependencies

```bash
python -m pip install Flask requests
```

### 3. Connect and start the physical FERM device

1. Install the **Arduino IDE** on the computer that will operate the device.
2. Connect the FERM unit to the computer using a **USB data cable**. Keep this USB connection in place during normal operation; it is not only for uploading the firmware.
3. Open the Arduino sketch:

   ```text
   hardware/ferm_sensors/ferm_sensors_test02.ino
   ```

4. In Arduino IDE, select the board that matches the hardware and the serial/COM port assigned to the connected device. Install any libraries required by the sketch and configure any board-specific settings it requires.
5. Verify/compile the sketch, then click **Upload**. Wait for Arduino IDE to report that the upload has completed.
6. Leave the device connected over USB while running the local application so the live-device connection remains available.

> **Hardware-specific settings:** The repository does not document a verified board model, USB driver, library list, or pin mapping. Select these according to the actual board and the requirements shown by the Arduino sketch; do not assume that a different board or COM port will work.

### 4. Start the Flask backend

Open a terminal at the repository root (the directory containing `app.py`) and run:

```bash
python app.py
```

The Flask API runs locally at:

```text
http://127.0.0.1:5000
```

Keep this terminal running. The backend receives structured sensor readings through `POST /data`, stores them in `ferm.db`, updates unit status, and evaluates alert rules. The frontend communicates with this backend to retrieve readings, alerts, and unit status.

> **Data transport note:** In the current `app.py` source, Flask exposes an HTTP `POST /data` endpoint; it does not itself open a USB COM/Serial port. The USB connection is part of the physical-device operating setup, but the exact component that bridges USB sensor output into the Flask HTTP endpoint should be confirmed from the device/frontend code before documenting it as a direct Serial-to-Flask connection.

### 5. Start the frontend development server

Open a **second terminal** in VS Code or Antigravity. Change to the frontend project directory:

```bash
cd platform
```

Install the frontend dependencies:

```bash
npm install
```

Start the frontend development server:

```bash
npm run dev
```

Keep this terminal running as well. Open the local URL printed by the development server (often a `localhost` URL). Use this frontend URL for the dashboard while developing; the Flask backend remains available separately at `http://127.0.0.1:5000`.

> **Important:** Running `npm run dev` starts the frontend only; it does not start Flask or upload firmware to the hardware. For the physical-device workflow, keep the USB-connected FERM device, Flask backend, and frontend development server running together. The exact frontend port is determined by the project's npm/Vite configuration and will be printed in the terminal.

### 5.1. Check the data flow

- Confirm that the FERM device is connected and its firmware has been uploaded successfully.
- Confirm that the Flask terminal is running without errors.
- Confirm that the frontend development server is running and open the URL it prints.
- The dashboard can display live readings only when sensor data is reaching the backend. If no readings appear, check the USB/device connection and the data-ingestion path to `POST /data`.

### 6. Run the sensor simulator (optional)

Open a second terminal in the repository directory and run:

```bash
python simulator.py
```

By default, the simulator sends data to `http://127.0.0.1:5000/data` using the unit ID `FERM-001`. It generates a reading every 30 seconds and occasionally creates a simulated spike event so that the backend's alert rules can be tested.

You can override the target endpoint and unit ID with environment variables.

**macOS / Linux**

```bash
TARGET="http://127.0.0.1:5000/data" UNIT="FERM-002" python simulator.py
```

**Windows PowerShell**

```powershell
$env:TARGET = "http://127.0.0.1:5000/data"
$env:UNIT = "FERM-002"
python simulator.py
```

Stop the simulator with `Ctrl+C`.

## Sensor Data Format

The backend expects a JSON object containing at least `unit_id` and `timestamp`. The simulator currently sends a payload with the following structure:

```json
{
  "unit_id": "FERM-001",
  "timestamp": "2026-11-04T09:00:00Z",
  "sensors": {
    "temperature_c": 29.5,
    "humidity_pct": 55.0,
    "pressure_hpa": 1008.0,
    "voc_index": 42.0,
    "flame_detected": false,
    "sound_db": 45.0,
    "light_lux": 320
  },
  "power": {
    "battery_v": 3.85
  }
}
```

The timestamp above is an example. Devices should send timestamps in UTC ISO 8601 format, consistent with the simulator.

## API Reference

The backend exposes the following endpoints on `http://127.0.0.1:5000`.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/data` | Receive a sensor reading, store it, update unit status, and evaluate alert rules. |
| `GET` | `/data` | Retrieve recent sensor readings. |
| `GET` | `/alerts` | Retrieve up to 200 recent alerts. |
| `GET` | `/units` | Retrieve known units and their latest status. |
| `GET` | `/` | Flask's configured static entry point (`frontend/index.html`); during frontend development, use the URL printed by `npm run dev`. |

### Submit a reading

```bash
curl -X POST http://127.0.0.1:5000/data \
  -H "Content-Type: application/json" \
  -d '{
    "unit_id": "FERM-001",
    "timestamp": "2026-11-04T09:00:00Z",
    "sensors": {
      "temperature_c": 29.5,
      "humidity_pct": 55.0,
      "voc_index": 42.0,
      "flame_detected": false
    },
    "power": {"battery_v": 3.85}
  }'
```

A successful submission returns HTTP `201` with:

```json
{"status": "ok"}
```

### Retrieve readings

```text
GET /data
GET /data?unit_id=FERM-001
GET /data?unit_id=FERM-001&limit=100
```

The optional `unit_id` parameter filters readings by device. The optional `limit` parameter controls the maximum number of readings returned and defaults to `200`.

### Retrieve alerts and units

```text
GET /alerts
GET /units
```

`/alerts` returns up to the latest 200 alerts. `/units` returns each known unit's ID, last-seen timestamp, and battery voltage.

## Alert Rules

The current backend evaluates these conditions when a reading is received:

| Alert type | Trigger condition |
|---|---|
| `FLAME_DETECTED` | `flame_detected` is `true`. |
| `HIGH_TEMP` | Temperature is at least `55 °C`. |
| `HIGH_FIRE_RISK` | Temperature is at least `40 °C` and humidity is at most `20%`. |
| `POSSIBLE_SMOKE` | The current VOC index is more than 40% higher than the previous available VOC reading for the same unit. |

These are prototype rules and thresholds, not a certified fire-detection or safety system. They should be validated and calibrated for the actual hardware and deployment environment before operational use.

## Database

The SQLite database contains three tables:

- `readings`: raw sensor payloads, unit IDs, and timestamps.
- `alerts`: generated alert type, details, unit ID, and timestamp.
- `units`: the latest known status for each unit, including last-seen time and battery voltage.

The backend runs a cleanup task in a background thread. In the current implementation, it deletes readings and alerts older than **one day**, and repeats the cleanup every hour. Unit records are not deleted by this cleanup routine.

## Hardware

The Arduino sketch is located at `hardware/ferm_sensors/ferm_sensors_test02.ino`. Connect the FERM unit over USB, select the correct board and serial port in Arduino IDE, upload the sketch, and leave the device connected during operation. The local application is then started in two terminals: `python app.py` for the Flask backend and `npm run dev` from `platform/` for the frontend. See [Connect and start the physical FERM device](#3-connect-and-start-the-physical-ferm-device), [Start the Flask backend](#4-start-the-flask-backend), and [Start the frontend development server](#5-start-the-frontend-development-server) for the full sequence.

The repository does not currently specify a complete bill of materials or a verified board/USB-driver/library version matrix. The exact board, port, libraries, and pin assignments must match the physical hardware and sketch.

## Development Notes

- `app.py` currently starts Flask with `debug=True`; this is intended for local development, not direct production deployment.
- The backend uses SQLite and has no authentication layer in the current implementation. Do not expose it directly to an untrusted network without adding appropriate security controls.
- The simulator is an optional development/testing path and requires the backend to be running before it can submit readings. It does not replace the Arduino upload-and-connect steps when using the physical FERM unit.
- The checked-in `ferm.db` is the repository's database file. Back up any data you need before resetting or replacing it.

## License

No license file is currently listed in the repository. Unless a license is added, the code should not be assumed to be available for unrestricted reuse, modification, or redistribution.
