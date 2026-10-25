# -----smart fertilizer----------
# -------------------------------
# fertilizer_project.py - Backend
# -----------------------------
from flask import Flask, request, jsonify
import pandas as pd
from pathlib import Path

app = Flask(__name__)
# ------------------- Load CSV with real soil data -------------------
CSV_PATH = Path(__file__).resolve().parent / "Crop_recommendation.csv"

try:
    soil_data = pd.read_csv(CSV_PATH)
except FileNotFoundError:
    raise FileNotFoundError(f"CSV not found at {CSV_PATH}. Place crop_recommendation.csv there or change CSV_PATH.")

soil_data.columns = soil_data.columns.str.strip()
lower_cols = {c.lower(): c for c in soil_data.columns}

# Detect crop column
crop_col = next((lower_cols[c] for c in ["crop","label","crop_name","name"] if c in lower_cols), None)
if not crop_col:
    raise ValueError("Could not find crop column in CSV.")

# Optional city/location column
city_col = next((lower_cols[c] for c in ["city","location","region","place"] if c in lower_cols), None)

# Detect numeric NPK columns
def find_col_starting_with(prefixes):
    for pref in prefixes:
        if pref in lower_cols:
            return lower_cols[pref]
    for lc, orig in lower_cols.items():
        for pref in prefixes:
            if lc.startswith(pref):
                return orig
    return None

n_col = find_col_starting_with(["n","nitrogen"])
p_col = find_col_starting_with(["p","phosphorus","phosphate"])
k_col = find_col_starting_with(["k","potassium"])

for col in [n_col,p_col,k_col]:
    soil_data[col] = pd.to_numeric(soil_data[col], errors="coerce").fillna(0)

# ------------------- Ideal levels and crop sensitivity -------------------
ideal_levels = {
    "rice": {"N":120,"P":60,"K":50,"temp_range":(20,30)},
    "wheat":{"N":140,"P":70,"K":60,"temp_range":(10,25)},
    "maize":{"N":160,"P":80,"K":90,"temp_range":(18,32)},
    "cotton":{"N":100,"P":60,"K":70,"temp_range":(20,32)},
    "sugarcane":{"N":220,"P":90,"K":100,"temp_range":(22,34)},
    "potato":{"N":180,"P":100,"K":130,"temp_range":(15,22)},
    "tomato":{"N":120,"P":60,"K":60,"temp_range":(18,28)}
}

crop_sensitivity = {
    "rice":{"temp_sens":0.08,"hum_sens":0.06,"disease_sensitive":False},
    "wheat":{"temp_sens":0.10,"hum_sens":0.04,"disease_sensitive":False},
    "maize":{"temp_sens":0.09,"hum_sens":0.05,"disease_sensitive":False},
    "cotton":{"temp_sens":0.07,"hum_sens":0.05,"disease_sensitive":False},
    "sugarcane":{"temp_sens":0.05,"hum_sens":0.03,"disease_sensitive":False},
    "potato":{"temp_sens":0.12,"hum_sens":0.10,"disease_sensitive":True},
    "tomato":{"temp_sens":0.11,"hum_sens":0.12,"disease_sensitive":True}
}

# ------------------- Adjustment logic -------------------
def adjust_fertilizer(N_need, P_need, K_need, crop, temperature, humidity):
    advice = []
    crop_key = crop.lower()
    sens = crop_sensitivity.get(crop_key, {"temp_sens":0.08,"hum_sens":0.05,"disease_sensitive":False})
    temp_s = sens["temp_sens"]
    hum_s = sens["hum_sens"]
    disease_sensitive = sens["disease_sensitive"]

    Nf, Pf, Kf = N_need, P_need, K_need
    ideal = ideal_levels.get(crop_key)
    t_min, t_max = ideal["temp_range"] if ideal else (18,30)

    # Temperature adjustment
    if temperature < t_min:
        Nf *= 1 + 0.1 * temp_s * 10
        Pf *= 1 + 0.08 * temp_s * 10
        advice.append(f"🌡 Temp {temperature}°C low → increase N by {round(Nf-N_need,2)} kg/acre, P by {round(Pf-P_need,2)} kg/acre.")
    elif temperature > t_max:
        Nf *= 1 - 0.15 * temp_s * 10
        Kf *= 1 + 0.12 * temp_s * 10
        advice.append(f"🌡 Temp {temperature}°C high → reduce N by {round(abs(Nf-N_need),2)} kg/acre, increase K by {round(Kf-K_need,2)} kg/acre.")
    else:
        advice.append(f"🌡 Temp {temperature}°C within optimal range → no major NPK adjustment.")

    # Humidity adjustment
    if humidity > 80:
        Nf *= 1 + 0.1 * hum_s * 10
        advice.append(f"💧 Humidity {humidity}% high → increase N by {round(Nf-N_need,2)} kg/acre; monitor for disease.")
        if disease_sensitive:
            advice.append("⚠ Disease-prone crop → consider scouting/fungicide.")
    elif humidity < 30:
        Nf *= 1 - 0.05 * hum_s * 10
        advice.append(f"💨 Humidity {humidity}% low → reduce N by {round(abs(Nf-N_need),2)} kg/acre; ensure irrigation.")
    else:
        advice.append(f"💧 Humidity {humidity}% moderate → no major NPK adjustment.")

    # Crop tips
    crop_tips = {
        "rice":["Split N application: basal + tillering + panicle initiation.","Use urea for N supply."],
        "wheat":["Apply part N at sowing, remainder at tillering.","Ensure soil moisture."],
        "maize":["Place part N near seed, split remaining at V6 stage."],
        "potato":["Avoid excess N near harvest.","Balance K for tuber quality."],
        "tomato":["Balanced N and K.","Avoid excess N during fruiting."]
    }
    if crop_key in crop_tips:
        for tip in crop_tips[crop_key]:
            advice.append(f"📌 {crop.title()} tip: {tip}")

    return round(Nf,2), round(Pf,2), round(Kf,2), advice

# ------------------- API Endpoint -------------------
def get_recommendation(crop, temperature, humidity, city):
    with app.test_request_context(
        "/recommend",
        method="POST",
        json={
            "crop": crop,
            "temperature": temperature,
            "humidity": humidity,
            "city": city
        }
    ):
        response, status = recommend()
        return response.get_json(), status
@app.route("/recommend", methods=["POST"])
def recommend():
    data = request.get_json() or {}
    crop = str(data.get("crop","")).strip().lower()
    city = data.get("city",None)
    temperature = float(data.get("temperature",25))
    humidity = float(data.get("humidity",50))

    if not crop:
        return jsonify({"error":"Provide crop"}), 400

    # Select soil row
    soil_row = pd.DataFrame()
    if city and city_col:
        soil_row = soil_data[(soil_data[city_col].astype(str).str.lower()==city.lower()) &
                             (soil_data[crop_col].astype(str).str.lower()==crop)]
    if soil_row.empty:
        soil_row = soil_data[soil_data[crop_col].astype(str).str.lower()==crop]
    if soil_row.empty:
        return jsonify({"error":"Crop not found"}), 400

    soil_N = float(soil_row[n_col].values[0])
    soil_P = float(soil_row[p_col].values[0])
    soil_K = float(soil_row[k_col].values[0])

    # Base need
    ideal = ideal_levels.get(crop)
    N_need = max(0, ideal["N"] - soil_N)
    P_need = max(0, ideal["P"] - soil_P)
    K_need = max(0, ideal["K"] - soil_K)

    N_final, P_final, K_final, advice = adjust_fertilizer(N_need,P_need,K_need,crop,temperature,humidity)

    result = {
        "crop": crop,
        "city_used": city if (city and city_col) else None,
        "soil_N": soil_N,
        "soil_P": soil_P,
        "soil_K": soil_K,
        "base_need_N": N_need,
        "base_need_P": P_need,
        "base_need_K": K_need,
        "N_final": N_final,
        "P_final": P_final,
        "K_final": K_final,
        "temperature": temperature,
        "humidity": humidity,
        "advice": advice
    }
    return jsonify(result), 200

if __name__ == "__main__":
    app.run(debug=True)
