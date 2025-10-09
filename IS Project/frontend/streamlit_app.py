import streamlit as st
import requests
from datetime import datetime, timezone
from st_audiorec import st_audiorec
from pydub import AudioSegment
import tempfile, hashlib, requests
from streamlit_js_eval import streamlit_js_eval

BACKEND = "http://fastapi:8000"

user_agent = streamlit_js_eval(js_expressions="navigator.userAgent", key="ua")
is_mobile = False
if user_agent and any(m in user_agent.lower() for m in ["iphone", "android", "mobile"]):
    is_mobile = True

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
        .typing { display: inline-block; }
        .typing span {
            display: inline-block;
            width: 6px;
            height: 6px;
            margin: 0 2px;
            background: #555;
            border-radius: 50%;
            animation: blink 1.4s infinite both;
        }
        .typing span:nth-child(2) { animation-delay: 0.2s; }
        .typing span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes blink {
            0% { opacity: 0.2; }
            20% { opacity: 1; }
            100% { opacity: 0.2; }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "editable_input" not in st.session_state:
        st.session_state.editable_input = ""
    if "stt_last_md5" not in st.session_state:
        st.session_state.stt_last_md5 = None
    if "stt_buffer" not in st.session_state:
        st.session_state.stt_buffer = None

    if st.session_state.stt_buffer:
        st.session_state.editable_input = st.session_state.stt_buffer
        st.session_state.stt_buffer = None

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

    def send_message():
        prompt = st.session_state.editable_input.strip()
        if prompt:
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            st.session_state.chat_history.append(
                {"role": "assistant", "content": "<div class='typing'><span></span><span></span><span></span></div>"}
            )
            st.session_state.editable_input = ""

    cols = st.columns([5, 1])
    with cols[0]:
        st.text_area(
            "💬 Type or edit your message:",
            key="editable_input",
            height=80,
            label_visibility="collapsed",
            placeholder="Type your message…"
        )
    with cols[1]:
        st.write("")
        st.button("Send", on_click=send_message)

    if is_mobile:
        st.info("🎙️ Tip: On your phone, you can tap the keyboard’s microphone icon to speak.")

    else:

        st.markdown("""
        <style>
        iframe[title="st_audiorec.st_audiorec"],
        iframe[title^="st_audiorec"] {
            height: 56px !important;
            min-height: 56px !important;
            max-height: 56px !important;
            width: 240px !important;
            overflow: hidden !important;
            border: none !important;
            display: block !important;
            margin-top: 10px !important;
            margin-bottom: 0 !important;
        }
        div[data-testid="stComponent"] {
            padding: 0 !important;
            margin: 0 !important;
        }
        audio, .stAudio { display: none !important; }
        iframe[title="st_audiorec.st_audiorec"] + div,
        iframe[title^="st_audiorec"] + div { display: none !important; }
        div[data-testid="stVerticalBlock"] > div:has(iframe[title^="st_audiorec"]) {
            margin-bottom: 0 !important;
        }
        </style>
        """, unsafe_allow_html=True)

        st.write("🎤 Record your voice to fill the input box")
        wav_audio_data = st_audiorec()

        if wav_audio_data is not None:
            md5 = hashlib.md5(wav_audio_data).hexdigest()
            if md5 != st.session_state.stt_last_md5:
                st.session_state.stt_last_md5 = md5

                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_in:
                    tmp_in.write(wav_audio_data)
                    wav_in_path = tmp_in.name
                sound = AudioSegment.from_wav(wav_in_path).set_frame_rate(16000).set_channels(1)
                with tempfile.NamedTemporaryFile(delete=False, suffix="_16k.wav") as tmp_out:
                    wav_16k_path = tmp_out.name
                    sound.export(wav_16k_path, format="wav")

                try:
                    with open(wav_16k_path, "rb") as f:
                        files = {"file": ("audio_16k.wav", f, "audio/wav")}
                        res = requests.post(f"{BACKEND}/speech_to_text/", files=files, timeout=30)

                    if res.ok:
                        data = res.json()
                        recognized_text = data.get("result", "")
                        if isinstance(recognized_text, list):
                            recognized_text = "\n".join(recognized_text)

                        if recognized_text.strip():
                            st.session_state.stt_buffer = recognized_text
                            st.rerun()
                    else:
                        st.error(f"Speech API error: {res.status_code}")
                except Exception as e:
                    st.error(f"Speech recognition failed: {e}")

    if st.session_state.chat_history and "typing" in st.session_state.chat_history[-1]["content"]:
        last_user_message = next(
            (t["content"] for t in reversed(st.session_state.chat_history) if t["role"] == "user"), None
        )
        if last_user_message:
            ctx = {
                "device_id": device_id,
                "blood_pressure": blood_pressure,
                "heart_rate": int(heart_rate) if heart_rate else 0,
                "blood_glucose": int(blood_glucose) if blood_glucose else 0,
                "blood_oxygen": int(blood_oxygen) if blood_oxygen else 0,
                "timestamp": timestamp or None,
            }
            payload = {
                "history": st.session_state.chat_history[:-2],
                "message": last_user_message,
                "context_vitals": ctx
            }

            try:
                resp = requests.post(f"{BACKEND}/chat", json=payload, timeout=60)
                data = resp.json() if resp.ok else {}
                answer = data.get("answer") or data.get("reply", "")
                retrieved = data.get("retrieved", [])
            except Exception as e:
                answer = f"Request failed: {e}"
                retrieved = []

            st.session_state.chat_history.pop()
            st.session_state.chat_history.append(
                {"role": "assistant", "content": answer, "retrieved": retrieved}
            )
            st.rerun()
