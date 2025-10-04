import streamlit as st
import requests
from datetime import datetime, timezone
import folium
from streamlit_folium import st_folium
import json
import uuid

BACKEND = "http://fastapi:8000"

# Initialize session state for map functionality
if "user_location" not in st.session_state:
    st.session_state.user_location = None
if "location_selected" not in st.session_state:
    st.session_state.location_selected = False
if "show_map" not in st.session_state:
    st.session_state.show_map = False
if "recommendations" not in st.session_state:
    st.session_state.recommendations = []

def create_singapore_map(center_lat=1.3521, center_lon=103.8198, zoom_start=12):
    """创建新加坡地图"""
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles='OpenStreetMap'
    )
    
    # # 添加一些地标帮助用户定位
    # landmarks = [
    #     ("Marina Bay", 1.2833, 103.8607),
    #     ("Orchard Road", 1.3048, 103.8318),
    #     ("Chinatown", 1.2833, 103.8443),
    #     ("Little India", 1.3048, 103.8520),
    #     ("Sentosa", 1.2494, 103.8303),
    #     ("Jurong East", 1.3329, 103.7436),
    #     ("Woodlands", 1.4382, 103.7890),
    #     ("Tampines", 1.3496, 103.9568)
    # ]
    
    # for name, lat, lon in landmarks:
    #     folium.Marker(
    #         [lat, lon],
    #         popup=name,
    #         tooltip=name,
    #         icon=folium.Icon(color='blue', icon='info-sign')
    #     ).add_to(m)
    
    return m

def create_recommendation_map(user_location, recommendations):
    """创建显示推荐结果的地图"""
    if not user_location or 'lat' not in user_location or 'lon' not in user_location:
        return create_singapore_map()
    
    # 以用户位置为中心
    m = folium.Map(
        location=[user_location['lat'], user_location['lon']],
        zoom_start=12,
        tiles='OpenStreetMap'
    )
    
    # 添加用户位置标记
    folium.Marker(
        [user_location['lat'], user_location['lon']],
        popup="Your Location",
        tooltip="Your Location",
        icon=folium.Icon(color='red', icon='home')
    ).add_to(m)
    
    # 添加推荐活动标记
    for i, rec in enumerate(recommendations[:10]):  # 只显示前10个
        if 'lat' in rec and 'lon' in rec and rec['lat'] != 0 and rec['lon'] != 0:
            # 格式化价格显示
            price_display = "Free" if rec.get('price', 0) == 0 else f"${rec.get('price', 0):.0f}"
            # 格式化距离显示
            distance_display = f"{rec.get('distance', 0):.1f} km" if rec.get('distance', 0) > 0 else "N/A"
            
            folium.Marker(
                [rec['lat'], rec['lon']],
                popup=f"""
                <b>{rec.get('activity', 'Unknown Activity')}</b><br>
                Price: {price_display}<br>
                Distance: {distance_display}<br>
                Time: {rec.get('start_time', 'N/A')} - {rec.get('end_time', 'N/A')}<br>
                Language: {rec.get('language', 'N/A')}<br>
                Date: {rec.get('date', 'N/A')}
                """,
                tooltip=f"{i+1}. {rec.get('activity', 'Unknown Activity')}",
                icon=folium.Icon(color='green', icon='star')
            ).add_to(m)
    
    return m

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
        # Check if this is a new recommendation request
        if any(keyword in prompt.lower() for keyword in ["recommend", "suggest", "activities", "recommendation"]):
            # Reset map state for new recommendation
            st.session_state.show_map = False
            st.session_state.location_selected = False
            st.session_state.user_location = None
            st.session_state.recommendations = []
        else:
            # For non-recommendation messages, hide the map
            st.session_state.show_map = False
            st.session_state.recommendations = []
        
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
                "context": ctx,
                "user_location": st.session_state.user_location  # 添加用户位置信息
            }
            data = {}
            try:
                resp = requests.post(f"{BACKEND}/chat", json=payload, timeout=60)
                data = resp.json() if resp.ok else {}
                answer = data.get("answer") or data.get("reply", "")
                retrieved = data.get("retrieved", [])
                
                # Handle map display and location selection
                if data.get("show_map"):
                    st.session_state.show_map = True
                if data.get("user_location"):
                    st.session_state.user_location = data.get("user_location")
                if data.get("result"):
                    st.session_state.recommendations = data.get("result")
                    # 如果有推荐结果但没有用户位置，使用默认位置
                    if not st.session_state.user_location:
                        st.session_state.user_location = {'lat': 1.3521, 'lon': 103.8198}
                        st.session_state.location_selected = True
                    # 如果有推荐结果，隐藏位置选择地图
                    st.session_state.show_map = False
                    
            except Exception as e:
                answer = f"Request failed: {e}"
                retrieved = []

            # Remove typing bubble
            if "typing" in st.session_state.chat_history[-1]["content"]:
                st.session_state.chat_history.pop()

            # Add real assistant response
            st.session_state.chat_history.append(
                {"role": "assistant", "content": answer, "retrieved": retrieved, "flow_tag": data.get("flow_tag", None), "user_location": data.get("user_location", None)}
            )

            st.rerun()

    # Map section - below chat interface
    if st.session_state.show_map or st.session_state.recommendations:
        st.markdown("---")
        st.subheader("📍 Location & Results")
        
        # Show map based on state
        if st.session_state.show_map and not st.session_state.location_selected:
            # Show location selection map
            st.write("**Step 1: Choose your location**")
            map_obj = create_singapore_map()
            map_data = st_folium(map_obj, width=700, height=400, key="location_map")
            
            if map_data['last_clicked']:
                lat = map_data['last_clicked']['lat']
                lng = map_data['last_clicked']['lng']
                st.session_state.user_location = {'lat': lat, 'lon': lng}
                st.session_state.location_selected = True
                st.success(f"Location selected: {lat:.4f}, {lng:.4f}")
                
                # 自动调用推荐API
                try:
                    payload = {
                        "session_id": st.session_state.session_id,
                        "lat": lat,
                        "lon": lng
                    }
                    resp = requests.post(f"{BACKEND}/recommend_with_location", json=payload, timeout=60)
                    if resp.ok:
                        data = resp.json()
                        # 添加推荐结果到聊天历史
                        st.session_state.chat_history.append({
                            "role": "assistant", 
                            "content": data.get("answer", ""), 
                            "result": data.get("result", []),
                            "user_location": data.get("user_location")
                        })
                        st.session_state.recommendations = data.get("result", [])
                        st.session_state.show_map = False  # 隐藏位置选择地图
                    else:
                        st.error(f"Failed to get recommendations: {resp.status_code}")
                except Exception as e:
                    st.error(f"Error getting recommendations: {e}")
                
                st.rerun()
            
            # Skip location button
            if st.button("Skip Location (Use Default)"):
                st.session_state.user_location = {'lat': 1.3521, 'lon': 103.8198}
                st.session_state.location_selected = True
                st.success("Using default Singapore location")
                
                # 自动调用推荐API
                try:
                    payload = {
                        "session_id": st.session_state.session_id,
                        "lat": 1.3521,
                        "lon": 103.8198
                    }
                    resp = requests.post(f"{BACKEND}/recommend_with_location", json=payload, timeout=60)
                    if resp.ok:
                        data = resp.json()
                        # 添加推荐结果到聊天历史
                        st.session_state.chat_history.append({
                            "role": "assistant", 
                            "content": data.get("answer", ""), 
                            "result": data.get("result", []),
                            "user_location": data.get("user_location")
                        })
                        st.session_state.recommendations = data.get("result", [])
                        st.session_state.show_map = False  # 隐藏位置选择地图
                    else:
                        st.error(f"Failed to get recommendations: {resp.status_code}")
                except Exception as e:
                    st.error(f"Error getting recommendations: {e}")
                
                st.rerun()
                
        elif st.session_state.recommendations:
            # Show recommendation results map (只要有推荐结果就显示)
            st.write("**Recommended Activities**")
            
            # 确保有用户位置（如果没有则使用默认位置）
            if not st.session_state.user_location:
                st.session_state.user_location = {'lat': 1.3521, 'lon': 103.8198}
            
            map_obj = create_recommendation_map(st.session_state.user_location, st.session_state.recommendations)
            st_folium(map_obj, width=700, height=400, key="results_map")
            
            # Clear location button
            if st.button("Clear Location"):
                # 清空前端状态
                st.session_state.show_map = False
                st.session_state.location_selected = False
                st.session_state.user_location = None
                st.session_state.recommendations = []
                
                # 调用后端API清空位置信息
                try:
                    payload = {
                        "session_id": st.session_state.session_id
                    }
                    resp = requests.post(f"{BACKEND}/clear_location", json=payload, timeout=10)
                    if resp.ok:
                        st.success("Location cleared. You can now request new recommendations.")
                    else:
                        st.error(f"Failed to clear location: {resp.status_code}")
                except Exception as e:
                    st.error(f"Error clearing location: {e}")
                
                st.rerun()
