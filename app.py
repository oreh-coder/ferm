# app.py
"""
A simple Flask web application for receiving, storing, and serving sensor data.

This application provides a backend for an IoT device monitoring system. It exposes
endpoints to:
- Receive sensor data payloads (POST /data).
- Query historical sensor readings (GET /data).
- View triggered alerts (GET /alerts).
- List all monitored units and their last known status (GET /units).

It uses SQLite for data storage and includes a background thread that periodically
cleans up old data to manage database size.
"""
from flask import Flask, request, jsonify, send_from_directory
import sqlite3
import datetime
import os
import json
import threading
import time

# --- Globals & Configuration ---

# Database file name
DB = 'ferm.db'
# Initialize the Flask application
app = Flask(__name__, static_folder='frontend', static_url_path='/')

# --- Database Utilities ---

def init_db():
    """
    Initializes the database and creates the necessary tables if they don't exist.
    Tables created:
    - readings: Stores raw sensor data payloads.
    - alerts: Stores alerts generated based on sensor data rules.
    - units: Stores the last known status of each monitoring unit.
    """
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Table for storing every reading from every unit
    c.execute('''CREATE TABLE IF NOT EXISTS readings
                (id INTEGER PRIMARY KEY, unit_id TEXT, timestamp TEXT, payload TEXT)''')
    # Table for storing generated alerts
    c.execute('''CREATE TABLE IF NOT EXISTS alerts
                (id INTEGER PRIMARY KEY, unit_id TEXT, timestamp TEXT, alert_type TEXT, details TEXT)''')
    # Table for tracking the status of each unit (last seen, battery, etc.)
    c.execute('''CREATE TABLE IF NOT EXISTS units
                (unit_id TEXT PRIMARY KEY, last_seen TEXT, battery_v REAL)''')
    conn.commit()
    conn.close()

def record_alert(unit_id, alert_type, details):
    """
    Inserts a new alert into the alerts table.

    Args:
        unit_id (str): The ID of the unit that triggered the alert.
        alert_type (str): The type of alert (e.g., 'HIGH_TEMP').
        details (str): Specific details about the alert (e.g., temperature value).
    """
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # Use UTC time for consistency
    timestamp = datetime.datetime.utcnow().isoformat() + 'Z'
    c.execute('INSERT INTO alerts (unit_id, timestamp, alert_type, details) VALUES (?,?,?,?)',
              (unit_id, timestamp, alert_type, details))
    conn.commit()
    conn.close()

def update_unit_status(unit_id, battery_v=None):
    """
    Updates the last_seen time and battery voltage for a specific unit.
    Uses 'INSERT OR REPLACE' to either create a new entry or update an existing one.

    Args:
        unit_id (str): The unique identifier for the unit.
        battery_v (float, optional): The last reported battery voltage. Defaults to None.
    """
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    # 'INSERT OR REPLACE' is a convenient way to add a new unit or update its status
    c.execute('INSERT OR REPLACE INTO units (unit_id, last_seen, battery_v) VALUES (?,?,?)',
              (unit_id, now, battery_v if battery_v is not None else None))
    conn.commit()
    conn.close()

# --- API Endpoints ---

@app.route('/data', methods=['POST'])
def post_data():
    """
    API endpoint to receive and process sensor data from a monitoring unit.
    It saves the reading, updates the unit's status, and evaluates alert rules.

    Returns:
        JSON: A status message and HTTP status code. 400 for bad payload, 201 for success.
    """
    data = request.get_json()
    if not data or 'unit_id' not in data or 'timestamp' not in data:
        return jsonify({'error': 'bad payload'}), 400

    # Save the raw reading to the database
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('INSERT INTO readings (unit_id,timestamp,payload) VALUES (?,?,?)',
              (data['unit_id'], data['timestamp'], json.dumps(data)))
    conn.commit()
    conn.close()

    # Update the unit's last seen time and battery voltage
    battery_v = None
    if isinstance(data.get('power'), dict):
        battery_v = data['power'].get('battery_v')
    update_unit_status(data['unit_id'], battery_v)

    # --- Evaluate Alert Rules ---
    sensors = data.get('sensors', {})
    temp = sensors.get('temperature_c')
    hum = sensors.get('humidity_pct')
    voc = sensors.get('voc_index')
    flame = sensors.get('flame_detected')

    # Rule: Flame detected
    if flame:
        record_alert(data['unit_id'], 'FLAME_DETECTED', 'flame boolean true')

    # Rules: Temperature-based
    if temp is not None:
        try:
            # High temperature alert
            if float(temp) >= 55.0:
                record_alert(data['unit_id'], 'HIGH_TEMP', f'{temp} C')
            # High fire risk alert (high temp and low humidity)
            if float(temp) >= 40.0 and (hum is not None and float(hum) <= 20.0):
                record_alert(data['unit_id'], 'HIGH_FIRE_RISK', f'{temp}C & {hum}%')
        except (ValueError, TypeError):
            # Ignore if temperature is not a valid number
            pass

    # Rule: Volatile Organic Compound (VOC) sudden jump check
    # This is a naive approach that compares the current VOC index to the previous one.
    if voc is not None:
        try:
            conn = sqlite3.connect(DB)
            c = conn.cursor()
            # Get the last few readings to find the previous VOC value
            c.execute('SELECT payload FROM readings WHERE unit_id=? ORDER BY timestamp DESC LIMIT 6', (data['unit_id'],))
            rows = c.fetchall()
            conn.close()

            # Parse the payloads to extract VOC values
            vocs = []
            for r in rows:
                try:
                    p = json.loads(r[0])
                    s = p.get('sensors', {})
                    if 'voc_index' in s:
                        vocs.append(float(s['voc_index']))
                except (json.JSONDecodeError, ValueError, TypeError):
                    pass # Ignore malformed payloads or non-numeric values
            
            # Check for a significant jump (more than 40%)
            if len(vocs) >= 2:
                # vocs[0] is the current reading, vocs[1] is the previous
                prev = vocs[1] 
                if prev > 0 and (float(voc) - prev) / prev > 0.4:
                    record_alert(data['unit_id'], 'POSSIBLE_SMOKE', f'voc jump {prev}->{voc}')
        except Exception as e:
            # Log any errors during the VOC check to the console
            print('voc check err', e)

    return jsonify({'status': 'ok'}), 201

@app.route('/data', methods=['GET'])
def get_data():
    """
    API endpoint to retrieve historical sensor readings.

    Query Params:
        unit_id (str, optional): Filter readings for a specific unit.
        limit (int, optional): The maximum number of readings to return. Defaults to 200.

    Returns:
        JSON: A list of reading objects.
    """
    unit = request.args.get('unit_id')
    limit = int(request.args.get('limit', 200))
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    if unit:
        c.execute('SELECT id,timestamp,payload FROM readings WHERE unit_id=? ORDER BY timestamp DESC LIMIT ?', (unit, limit))
    else:
        c.execute('SELECT id,timestamp,payload FROM readings ORDER BY timestamp DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    
    # Return parsed JSON payloads for easier consumption by the frontend
    out = []
    for r in rows:
        try:
            payload = json.loads(r[2])
        except json.JSONDecodeError:
            payload = r[2] # Return as string if not valid JSON
        out.append({'id': r[0], 'timestamp': r[1], 'payload': payload})
    return jsonify(out)

@app.route('/alerts', methods=['GET'])
def get_alerts():
    """
    API endpoint to retrieve the most recent alerts.

    Returns:
        JSON: A list of alert objects, sorted by most recent first.
    """
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT id, unit_id, timestamp, alert_type, details FROM alerts ORDER BY timestamp DESC LIMIT 200')
    rows = c.fetchall()
    conn.close()
    # Convert list of tuples to a list of dictionaries for JSON serialization
    return jsonify([dict(id=r[0], unit_id=r[1], timestamp=r[2], alert_type=r[3], details=r[4]) for r in rows])

@app.route('/units', methods=['GET'])
def get_units():
    """
    API endpoint to retrieve a list of all known units and their status.

    Returns:
        JSON: A list of unit objects, each containing its ID, last seen time, and battery voltage.
    """
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('SELECT unit_id, last_seen, battery_v FROM units')
    rows = c.fetchall()
    conn.close()
    # Convert list of tuples to a list of dictionaries
    return jsonify([dict(unit_id=r[0], last_seen=r[1], battery_v=r[2]) for r in rows])

# --- Frontend Serving ---

@app.route('/')
def index():
    """Serves the main index.html file for the frontend."""
    return send_from_directory('frontend', 'index.html')

# --- Background Cleanup Task ---

def clean_old_data(days_to_keep=7):
    """
    Deletes readings and alerts older than a specified number of days from the database.
    This is essential to prevent the database from growing indefinitely.

    Args:
        days_to_keep (int): The number of days of data to retain.
    """
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days_to_keep)
    cutoff_str = cutoff.isoformat() + 'Z'
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # Delete old readings
    c.execute("DELETE FROM readings WHERE timestamp < ?", (cutoff_str,))
    # Delete old alerts
    c.execute("DELETE FROM alerts WHERE timestamp < ?", (cutoff_str,))
    
    conn.commit()
    conn.close()
    print(f"[CLEANUP] Deleted data older than {cutoff_str}")

def run_cleanup_loop():
    """
    A target function for a background thread that runs the cleanup task periodically.
    """
    while True:
        # Number of days to store data can be adjusted here
        clean_old_data(days_to_keep=1) 
        # Wait for 1 hour (3600 seconds) before running the cleanup again
        time.sleep(3600)

# --- Main Execution ---

if __name__ == '__main__':
    # Ensure the database is initialized on startup
    init_db()

    # Create and start the background cleanup thread
    # The 'daemon=True' ensures the thread will exit when the main app exits.
    cleanup_thread = threading.Thread(target=run_cleanup_loop, daemon=True)
    cleanup_thread.start()

    # Start the Flask development server
    app.run(debug=True, port=5000)

""" 
Things to update: 
1. Warning alerts for some indexes that may indicate fire risk (e.g., high temperature, low humidity, sudden VOC increase).
2. A graph timeline existed in the frontend (UTC +7 like Vietnam time).
3. Decoration for the frontend to make it more user-friendly.
"""