import streamlit as st
import requests
from datetime import datetime, timezone
import uuid

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
    st.caption("Ask about *health-related questions* or say *recommend activities*.")

    # Inject custom CSS for chat bubbles + typing animation
    st.markdown(
        """
        <style>
        .user-bubble {
            background-color: #f1f0f0;
            padding: 10px 15px;
            border-radius: 15px;
            margin: 10px 5px;
            text-align: right;
            max-width: 70%;
            float: right;
            clear: both;
        }
        .bot-bubble {
            background-color: #e6f4ea;
            padding: 10px 15px;
            border-radius: 15px;
            margin: 10px 5px;
            text-align: left;
            max-width: 70%;
            float: left;
            clear: both;
        }
        .retrieved-context {
            font-size: 0.9em;
            color: #555;
            background-color: #f9f9f9;
            border-left: 4px solid #ccc;
            padding: 10px;
            margin: 10px 5px;
            clear: both;
        }
        /* Typing dots animation */
        .typing {
            display: inline-block;
        }
        .typing span {
            display: inline-block;
            width: 6px;
            height: 6px;
            margin: 0 2px;
            background: #555;
            border-radius: 50%;
            animation: blink 1.4s infinite both;
        }
        .typing span:nth-child(2) {
            animation-delay: 0.2s;
        }
        .typing span:nth-child(3) {
            animation-delay: 0.4s;
        }
        @keyframes blink {
            0% { opacity: 0.2; }
            20% { opacity: 1; }
            100% { opacity: 0.2; }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Render chat history
    for turn in st.session_state.chat_history:
        if turn["role"] == "user":
            st.markdown(f"<div class='user-bubble'>{turn['content']}</div>", unsafe_allow_html=True)
        elif turn["role"] == "assistant":
            st.markdown(f"<div class='bot-bubble'>{turn['content']}</div>", unsafe_allow_html=True)
            if "retrieved" in turn and turn["retrieved"]:
                retrieved_list = turn["retrieved"] or []
                st.markdown(
                    "<div class='retrieved-context'>📚 Retrieved Context (with similarity scores):<br>"
                    + "<br>".join([f"- {ctx}" for ctx in retrieved_list])
                    + "</div>",
                    unsafe_allow_html=True,
                )

    # Chat input
    prompt = st.chat_input("Type your message…")
    if prompt:
        # Save user input
        st.session_state.chat_history.append({"role": "user", "content": prompt})

        # Temporary assistant "typing..." bubble
        st.session_state.chat_history.append(
            {"role": "assistant", "content": "<div class='typing'><span></span><span></span><span></span></div>"}
        )

        st.rerun()

    # If last message is typing animation → fetch real answer
    if st.session_state.chat_history and "typing" in st.session_state.chat_history[-1]["content"]:
        # Get last user message
        last_user_message = None
        for turn in reversed(st.session_state.chat_history):
            if turn["role"] == "user":
                last_user_message = turn["content"]
                break

        if last_user_message:
            ctx = {
            }

            payload = {
                "session_id": st.session_state.session_id,
                "history": st.session_state.chat_history[:-2],  # exclude typing bubble
                "message": last_user_message,
                "context": ctx
            }
            data = {}
            try:
                resp = requests.post(f"{BACKEND}/chat", json=payload, timeout=60)
                data = resp.json() if resp.ok else {}
                answer = data.get("answer") or data.get("reply", "")
                retrieved = data.get("retrieved", [])
            except Exception as e:
                answer = f"Request failed: {e}"
                retrieved = []

            # Remove typing bubble
            if "typing" in st.session_state.chat_history[-1]["content"]:
                st.session_state.chat_history.pop()

            # Add real assistant response
            st.session_state.chat_history.append(
                {"role": "assistant", "content": answer, "retrieved": retrieved, "flow_tag": data.get("flow_tag", None)}
            )

            st.rerun()
