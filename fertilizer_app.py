# ----------------------------
# FRONTEND: app.py (Streamlit)
# ----------------------------
# fertilizer_app.py
# -------------------------------
import streamlit as st
import requests
import os
from dotenv import load_dotenv
from fertilizer_project import get_recommendation

load_dotenv()

st.set_page_config(page_title="Smart Fertilizer Dosage AI", page_icon="🌾", layout="wide")
st.title("🌾 Smart Fertilizer Recommender (Weather Based)")

# ---------------- Input Section ----------------
with st.container():
    st.markdown("""
    <div style="
        background-color:#F0FFF0;
        padding: 20px;
        border-radius: 15px;
        border: 1px solid #C9E4C5;
        margin-bottom: 20px;">
        <h3>🌱 Input Details</h3>
    </div>
    """, unsafe_allow_html=True)

crop = st.selectbox("Select Crop", ["rice","wheat","maize","cotton","sugarcane","potato","tomato"])
city = st.text_input("Enter City (e.g., BELAGAVI,IN)")

if st.button("Get Fertilizer Recommendation"):
    try:
        API_KEY = os.getenv("WEATHER_API_KEY")

        weather_url = f"http://api.weatherapi.com/v1/current.json?key={API_KEY}&q={city}"
        weather_data = requests.get(weather_url).json()

        if "error" in weather_data:
            st.error("❌ City not found or API error!")
        else:
            temp = weather_data["current"]["temp_c"]
            humidity = weather_data["current"]["humidity"]
            condition = weather_data["current"]["condition"]["text"]

            # Two-column layout
            col_weather, col_fertilizer = st.columns(2)

            # Weather card
            with col_weather:
                st.markdown(f"""
                <div style="
                    background-color:#E0F7FA;
                    padding:20px;
                    border-radius:15px;
                    border:1px solid #B2EBF2;
                    text-align:center;">
                    <h3>🌤 Live Weather</h3>
                    <p>🌡 Temperature: <b>{temp} °C</b></p>
                    <p>💧 Humidity: <b>{humidity} %</b></p>
                    <p>🌥 Condition: <b>{condition}</b></p>
                </div>
                """, unsafe_allow_html=True)

            # Backend request
            data, status = get_recommendation(crop, temp, humidity, city)

            if status == 200:

                # Fertilizer Card
                with col_fertilizer:
                    st.markdown(f"""
                    <div style="
                        background-color:#FFF3E0;
                        padding:20px;
                        border-radius:15px;
                        border:1px solid #FFE0B2;
                        text-align:center;">
                        <h3>🌱 Soil & Fertilizer</h3>
                        <p>Soil N: <b>{data['soil_N']} kg/acre</b></p>
                        <p>Soil P: <b>{data['soil_P']} kg/acre</b></p>
                        <p>Soil K: <b>{data['soil_K']} kg/acre</b></p>
                        <hr>
                        <h4>✅ Recommended Dosage</h4>
                        <p>N: <b>{data['N_final']} kg/acre</b></p>
                        <p>P: <b>{data['P_final']} kg/acre</b></p>
                        <p>K: <b>{data['K_final']} kg/acre</b></p>
                    </div>
                    """, unsafe_allow_html=True)

                    # Progress bars
                    st.subheader("💡 Fertilizer Dosage Progress")
                    st.progress(min(1.0, data['N_final']/(data['N_final']+data['soil_N'])))
                    st.text(f"N: {data['N_final']} / Total: {data['N_final'] + data['soil_N']}")
                    st.progress(min(1.0, data['P_final']/(data['P_final']+data['soil_P'])))
                    st.text(f"P: {data['P_final']} / Total: {data['P_final'] + data['soil_P']}")
                    st.progress(min(1.0, data['K_final']/(data['K_final']+data['soil_K'])))
                    st.text(f"K: {data['K_final']} / Total: {data['K_final'] + data['soil_K']}")

                # Advice cards
                st.subheader("🧠 Weather & Crop Advice")
                for item in data["advice"]:
                    st.markdown(f"<div style='background-color:#E8F5E9;padding:10px;margin:5px;border-radius:10px;border:1px solid #A5D6A7;'>{item}</div>", unsafe_allow_html=True)

            else:
                st.error("❌ Recommendation error: " + str(data))

    except Exception as e:
        st.error(f"⚠ Unable to fetch data or connect to backend.\nError: {e}")
