from flask import Flask, render_template, jsonify
import math
import pandas as pd
import os
from datetime import datetime, timedelta

app = Flask(__name__, template_folder="web")

W = {
   0 : [-0.4120684, 0.06040325, 1.76010941, -0.86836612, 0.12175123, 0.0312855],
   1 : [1.17790963, 0.39454, -0.93737114, 0.73343799, -0.06395781, -0.04636267],
   2 : [-0.76584123, -0.45494325, -0.82273827, 0.13492813, -0.05779342, 0.01507717]
}
B = {
   0 : -4.47485050194445,
   1 : -55.17857101109831,
   2 : 59.6534215130192
}

def softmax(scores):
    exps = [math.exp(s) for s in scores]
    s = sum(exps)
    return [e/s for e in exps]

def predict_fire_level(features):
    scores = []
    for cls in [0, 1, 2]:
        score = sum(w*f for w, f in zip(W[cls], features)) + B[cls]
        scores.append(score)
    probs = softmax(scores)
    return probs.index(max(probs)), probs

def fire_level_msg(level):
    if level == 2:
        return "🚨 FIRE DETECTED!!!"
    elif level == 1:
        return "⚠️ TEMPERATURE RISE DETECTED"
    else:
        return "🟢 NORMAL CONDITION"

def gas_ratio(adc_value):
    RL = 5.0
    r0 = 1.20
    if adc_value < 1:
        adc_value = 1
    rs = RL * (1023.0 / adc_value - 1.0)
    return rs / r0

def cleanup_old_data(file_path="data.csv", days=2):
    if not os.path.exists(file_path):
        return
    df = pd.read_csv(file_path)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
    cutoff = datetime.now() - timedelta(days=days)
    df = df[df["Timestamp"] >= cutoff]
    df.to_csv(file_path, index=False)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def data():
    try:
        cleanup_old_data()
        df = pd.read_csv("data.csv")
        df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
        df = df[df["Timestamp"] >= datetime.now() - timedelta(days=2)]
        df = df.sort_values("Timestamp").reset_index(drop=True)

        if df.empty:
            return jsonify({"temps": [], "hums": [], "gas": [], "logs": [], "current_level": 0})

        df["GasRatio"] = df["MQ2"].apply(gas_ratio)
        df["dTemp"] = df["Temp"].diff().fillna(0)
        df["dHum"]  = df["Hum"].diff().fillna(0)
        df["dGas"]  = df["GasRatio"].diff().fillna(0)

        Time = df["Timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S").tolist()
        temps = df["Temp"].tolist()
        hums  = df["Hum"].tolist()
        gas   = df["MQ2"].tolist()

        logs = []
        last_level = -1
        confirm_warn = 0
        confirm_fire = 0
        current_level = 0

        for i in range(len(df)):
            time_str = Time[i]
            temp = temps[i]
            hum = hums[i]
            gas_val = gas_ratio(gas[i])
            dtemp = df["dTemp"].iloc[i]
            dhum  = df["dHum"].iloc[i]
            dgas  = df["dGas"].iloc[i]

            features = [temp, hum, gas_val, dtemp, dhum, dgas]
            _, probs = predict_fire_level(features)

            fire_prob = probs[2]
            warn_prob = probs[1]

            # OPTIMIZED DECISION LOGIC
            
            if temp < 35:
                level = 1 if warn_prob >= 0.75 else 0
            else:
                if fire_prob >= 0.75:
                    confirm_fire += 1
                else:
                    confirm_fire = 0

                if warn_prob >= 0.65:
                    confirm_warn += 1
                else:
                    confirm_warn = 0

                if confirm_fire >= 3:
                    level = 2
                elif confirm_warn >= 2:
                    level = 1
                else:
                    level = 0

            current_level = level
            
            msg = f"{time_str} | Temperature: {temp}°C | Humidity: {hum}% | Gas Ratio: {gas_val:.2f}"
            logs.append({"text": msg, "level": level})

            if level != last_level:
                logs.append({
                    "text": f"{fire_level_msg(level)} (Confidence: {fire_prob*100:.1f}%)",
                    "level": level
                })
                last_level = level

        return jsonify({
            "temps": temps,
            "hums": hums,
            "gas": gas,
            "logs": logs,
            "current_level": current_level
        })

    except Exception as e:
        print("Data Reading Error !!!", e)
        return jsonify({"temps": [], "hums": [], "gas": [], "logs": [], "current_level": 0})

if __name__ == "__main__":
    app.run(debug=True)
