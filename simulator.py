# simulator.py
"""
A simulator script to mimic an IoT fermentation monitoring device.

This script generates realistic sensor data payloads and sends them via HTTP POST
requests to a specified target server endpoint. It is designed to test the
`app.py` Flask application.

The target URL and the unit ID can be configured via environment variables:
- TARGET: The full URL of the data endpoint (e.g., 'http://127.0.0.1:5000/data').
- UNIT: The unique identifier for the simulated unit (e.g., 'FERM-001').
"""
import time
import requests
import random
import datetime
import os

# The target URL for the POST request. Defaults to the local Flask app's /data endpoint.
TARGET = os.environ.get('TARGET', 'http://127.0.0.1:5000/data')
# The unique ID for this simulated device.
UNIT = os.environ.get('UNIT', 'FERM-001')

def gen_reading():
    """
    Generates a single, simulated sensor reading payload.

    The function creates a data structure that mimics the JSON payload from a real
    IoT device. It includes a chance for a "spike" event, which simulates
    conditions similar to a fire (high temperature, high VOC, and a chance of
    flame detection) to test the alerting logic on the server.

    Returns:
        dict: A dictionary containing the simulated sensor data.
    """
    # Get the current time in UTC ISO 8601 format, as expected by the server.
    t = datetime.datetime.utcnow().isoformat() + 'Z'
    
    # --- Simulate a potential fire/spike event ---
    # There is a 4% chance of a "spike" event occurring in any given reading.
    spike = random.random() < 0.04
    
    # --- Generate sensor values based on whether a spike is happening ---
    # Normal temperature is between 25-33 C. A spike adds a significant increase.
    base_temp = random.uniform(25, 33)
    temp = base_temp + (random.uniform(15, 30) if spike else random.uniform(-1, 2))
    
    # Normal VOC index is low. A spike simulates a large increase (e.g., from smoke).
    voc = random.uniform(10, 80) if not spike else random.uniform(130, 300)
    
    # Flame is only detected during a spike, and even then, not always (60% chance).
    flame = spike and random.random() < 0.6
    
    # --- Construct the final JSON payload ---
    payload = {
      "unit_id": UNIT,
      "timestamp": t,
      "sensors": {
        "temperature_c": round(temp, 2),
        "humidity_pct": round(random.uniform(15, 80), 1),
        "pressure_hpa": round(random.uniform(1004, 1012), 1),
        "voc_index": round(voc, 1),
        "flame_detected": flame,
        "sound_db": round(random.uniform(35, 60), 1),
        "light_lux": int(random.uniform(10, 900))
      },
      "power": {
        "battery_v": round(random.uniform(3.5, 4.08), 2) # Simulates a LiPo battery voltage.
      }
    }
    return payload

if __name__ == '__main__':
    """
    Main execution loop.
    This loop runs continuously, generating a new reading and posting it to the
    target server every 30 seconds.
    """
    print(f"Simulator posting to '{TARGET}' for unit '{UNIT}'")
    while True:
        # Generate a new payload.
        p = gen_reading()
        try:
            # Send the payload as JSON in a POST request.
            # A 5-second timeout is set to prevent the script from hanging indefinitely.
            r = requests.post(TARGET, json=p, timeout=5)
            # Print a confirmation with key data and the server's response code.
            print(f"sent {p['timestamp']} flame={p['sensors']['flame_detected']}, resp {r.status_code}")
        except Exception as e:
            # If the request fails (e.g., server is down, network error), print the error.
            print(f"failed to send data: {e}")
        
        # Wait for 30 seconds before generating and sending the next reading.
        time.sleep(30)