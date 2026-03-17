import serial
import csv
from datetime import datetime

ser = serial.Serial("COM4", 9600, timeout=1)

prev_temp = None
prev_time = None

# ===== NGƯỠNG CẢNH BÁO =====
TEMP_THRESHOLD = 60      # °C 
TEMP_DELTA     = 5       # °C 
MQ2_THRESHOLD  = 300     # ADC Value

def get_fire_level(mq2, temp, now):
    global prev_temp, prev_time

    # 🔴 LEVEL 3 FIRE !!!
    if mq2 >= MQ2_THRESHOLD and temp >= TEMP_THRESHOLD:
        return 3

    # 🟠 LEVEL 2 — HIGH RISING TEMPERATURE
    if prev_temp is not None and prev_time is not None:
        dt = (now - prev_time).total_seconds()
        if dt > 0 and (temp - prev_temp) >= TEMP_DELTA and dt <= 10:
            return 2

    if temp >= TEMP_THRESHOLD:
        return 2

    # 🟡 LEVEL 1 — HIGH GAS VALUE
    if mq2 >= MQ2_THRESHOLD:
        return 1

    # 🟢 LEVEL 0 - NORMAL CONDITION
    return 0


print("Record data from Arduino...")

while True:
    line = ser.readline().decode(errors="ignore").strip()

    if line and "Date" not in line:
        parts = line.split(",")

        if len(parts) == 5:
            try:
                now  = datetime.now()
                temp = float(parts[2])
                hum  = float(parts[3])
                mq2  = int(parts[4])

                level = get_fire_level(mq2, temp, now)

                # Synchronize level 3 to level 2 for ML model consistency
                if level == 3:
                    level = 2

                # Record file
                with open("data.csv", "a", newline="") as f:
                    writer = csv.writer(f)

                    # Write header if file is new
                    if f.tell() == 0:
                        writer.writerow(["Timestamp", "Temp", "Hum", "MQ2", "FireLevel"])

                    writer.writerow([now, temp, hum, mq2, level])

                print(now, "| Temp:", temp, "| Hum:", hum, "| MQ2:", mq2, "| Level:", level)

                prev_temp = temp
                prev_time = now

            except Exception as e:
                print("Data Error:", e)
