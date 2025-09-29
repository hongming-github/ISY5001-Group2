import streamlit as st
import requests
from datetime import datetime, timezone

BACKEND = "http://fastapi:8000"

st.set_page_config(page_title="Intelligent Care and Resource Matching Platform", page_icon="🩺", layout="centered")
st.title("Intelligent Care and Resource Matching Platform")

tab_form, tab_chat = st.tabs(["📋 Vital Signs Entry", "💬 Chatbot"])

with tab_form:
    device_id = st.text_input("Device ID")
    blood_pressure = st.text_input("Blood Pressure (format: systolic/diastolic)", placeholder="120/80")
    heart_rate = st.number_input("Heart Rate (bpm)", min_value=0, step=1)
    blood_glucose = st.number_input("Blood Glucose (mg/dL)", min_value=0, step=1)
    blood_oxygen = st.number_input("Blood Oxygen (%)", min_value=0, max_value=100, step=1)

    # Timestamp choice
    ts_option = st.radio("Timestamp option:", ("Use current time", "Enter manually"))
    if ts_option == "Enter manually":
        timestamp = st.text_input("Enter timestamp (YYYY-MM-DD HH:MM:SS or ISO 8601)")
    else:
        timestamp = datetime.now(timezone.utc).isoformat()

    # Submit to /submit
    if st.button("Submit Readings"):
        payload = {
            "device_id": device_id,
            "blood_pressure": blood_pressure,
            "heart_rate": int(heart_rate),
            "blood_glucose": int(blood_glucose),
            "blood_oxygen": int(blood_oxygen),
            "timestamp": timestamp or None
        }
        try:
            resp = requests.post(f"{BACKEND}/submit", json=payload, timeout=10)
            if resp.ok:
                st.success(f"Processed: {resp.json()}")
            else:
                st.error(f"Backend error: {resp.status_code} - {resp.text}")
        except Exception as e:
            st.error(f"Request failed: {e}")

with tab_chat:
    st.caption("Ask about your readings or say *recommend activities*.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Show chat history
    for turn in st.session_state.chat_history:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

    # Input prompt
    prompt = st.chat_input("Type your message…")
    if prompt:
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        # Placeholder context, this can be anything relevant
        ctx = {
            "device_id": device_id,
            "blood_pressure": blood_pressure,
            "heart_rate": int(heart_rate) if heart_rate else 0,
            "blood_glucose": int(blood_glucose) if blood_glucose else 0,
            "blood_oxygen": int(blood_oxygen) if blood_oxygen else 0,
            "timestamp": timestamp or None,
        }

        payload = {
            "history": st.session_state.chat_history[:-1],
            "message": prompt,
            "context_vitals": ctx
        }

        try:
            resp = requests.post(f"{BACKEND}/chat", json=payload, timeout=10)
            reply = resp.json().get("reply", "") if resp.ok else f"Error: {resp.text}"
        except Exception as e:
            reply = f"Request failed: {e}"

        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)
