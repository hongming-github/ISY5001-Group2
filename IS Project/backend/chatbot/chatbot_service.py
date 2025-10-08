from typing import List, Dict, Optional
from pydantic import BaseModel
import textwrap
import html

from vital_signs_processor import HealthData
from recommender import ElderlyActivityRecommender
from chatbot.rag import rag_answer
from chatbot.intent_classifier import IntentClassifier
from chatbot.profile_parser import ProfileParser
from chatbot.context_manager import ContextManager

# Initialize recommender (load model if any)
recommender = ElderlyActivityRecommender(model_path=None)
# Initialize the intent classifier globally
intent_clf = IntentClassifier()
# Initialize profile parser
profile_parser = ProfileParser()
# Initialize context manager
context_manager = ContextManager()

class ChatTurn(BaseModel):
    role: str
    content: str
    flow_tag: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: str = "default"
    history: List[ChatTurn] = []
    message: str
    context: Optional[Dict] = None
    profile: Optional[Dict] = None


class ChatResponse(BaseModel):
    answer: str
    result: Optional[List[Dict]] = None
    retrieved: List[str] | None = None
    flow_tag: Optional[str] = None
    show_map: Optional[bool] = False
    user_location: Optional[Dict] = None

def _needs_location_selection(profile: Dict) -> bool:
    """Check if location selection is needed."""
    # If lat/lon missing or zero, need location selection
    lat = profile.get("lat")
    lon = profile.get("lon")
    return lat is None or lon is None or lat == 0 or lon == 0

def update_profile_with_random_location(profile: dict) -> dict:
    """
    Update the user's profile with a random HDB latitude/longitude pair.
    """
    import random

    hdb_locations = [
        (1.379580207, 103.8549406),
        (1.398409465, 103.9084376),
        (1.386981291, 103.771091),
        (1.282936929, 103.700293),
        (1.377351206, 103.8723059),
        (1.41442708, 103.8779589),
        (1.392607595, 103.8752596),
        (1.328696852, 103.8832186),
        (1.356721167, 103.6984026),
        (1.417147491, 103.8049968),
    ]

    lat, lon = random.choice(hdb_locations)
    profile["lat"] = lat
    profile["lon"] = lon
    profile["location"] = "Random HDB Area"

    return profile


def check_missing_profile_fields(profile: dict, session_id: str, context_manager, required_fields: Optional[List[str]] = None) -> Optional[Dict]:
    """
    Check if required fields exist in the user's profile.
    If missing, return an early response message and empty result.
    """
    if required_fields is None:
        required_fields = ["interests"]
    missing = [f for f in required_fields if not profile.get(f)]
    if missing:
        reply = (
            "To recommend activities, I still need the following info: "
            + ", ".join(missing)
            + "."
        )
        context_manager.add_message(session_id, "assistant", reply)
        return {"answer": reply, "result": []}
    return None


def handle_chat(payload):
    user_msg = payload.message.lower()
    original_msg = payload.message
    session_id = payload.session_id or "default"
    print(f"session_id: {session_id}")
    history = context_manager.get_history(session_id, limit=3)
    # Store user message in context manager
    context_manager.add_message(session_id, "user", original_msg)
    
    # 1. Rule-based intent detection (highest priority)
    # Keywords that strongly indicate recommendation request
    rec_keywords = ["recommend", "activity", "suggestion", "recommendation", "suggest"]
    print(f"[DEBUG] Rule-based check: user_msg='{user_msg}', rec_keywords={rec_keywords}")
    if any(k in user_msg for k in rec_keywords):
        print(f"[DEBUG] Rule-based: Entering recommendation flow")
        
        # parse user profile from current message + recent history
        new_profile = profile_parser.parse_user_profile(
            user_msg, conversation_history=history
        )
        new_profile = profile_parser.enhance_profile_with_location(new_profile)
        new_profile = update_profile_with_random_location(new_profile)
        # Get existing profile and merge
        existing_profile = context_manager.get_profile(session_id)
        # Merge profiles, new values overwrite old ones
        profile = {**existing_profile, **new_profile}
        profile = context_manager.update_profile(session_id, profile)
  
        # Check if profile is complete 
        missing_resp = check_missing_profile_fields(profile, session_id, context_manager)
        if missing_resp:
            return missing_resp
        
        # Check if location is needed
        # print(f"[DEBUG] Checking location in rule-based: lat={profile.get('lat')}, lon={profile.get('lon')}")
        # print(f"[DEBUG] Needs location selection: {_needs_location_selection(profile)}")
        # if _needs_location_selection(profile):
        #     reply = "I need to know your location to recommend nearby activities. Please select your location on the map below, or click 'Skip' to use the default Singapore location."
        #     context_manager.add_message(session_id, "assistant", reply)
        #     return {
        #         "answer": reply, 
        #         "result": [],
        #         "show_map": True,
        #         "user_location": None
        #     }

        # Profile complete with location, proceed to recommend
        print(f"[recommendation] Final profile: {profile}")
        recs = recommender.recommend(profile=profile, vitals=None)

        if not recs:
            return {"answer": "I couldn't find suitable activities right now.", "result": []}
        activities_text = format_recommendations(recs)
        return {
            "answer": f"Here are my recommended activities:\n\n{activities_text}", 
            "result": recs,
            "user_location": {"lat": profile.get("lat"), "lon": profile.get("lon")}
        }


    # 2. Check for follow-up recommendation requests (context-aware)
    # Keywords that indicate follow-up recommendation with new criteria
    follow_up_keywords = ["morning", "afternoon", "evening", "free", "cheap", "expensive", "nearby", "far", "different"]
    has_follow_up = any(k in user_msg for k in follow_up_keywords)
    
    # Check if last assistant message was a recommendation
    last_assistant_msg = None
    if history:
        for turn in reversed(history):
            if turn.get("role") == "assistant" and turn.get("content"):
                last_assistant_msg = turn.get("content")
                break
    
    is_follow_up_recommendation = (
        has_follow_up and 
        last_assistant_msg and 
        ("recommended activities" in last_assistant_msg.lower() or "here are" in last_assistant_msg.lower())
    )
    
    if is_follow_up_recommendation:
        print("[follow-up] Detected follow-up recommendation request")
        profile = context_manager.get_profile(session_id)
        
        # Parse new criteria from user message
        parsed = profile_parser.parse_user_profile(
            user_msg, conversation_history=history
        )
        if parsed:
            # Update profile with new criteria while keeping existing location
            existing_location = {"lat": profile.get("lat"), "lon": profile.get("lon")}
            profile = context_manager.update_profile(session_id, parsed)
            # Ensure location is preserved
            if existing_location.get("lat") and existing_location.get("lon"):
                profile["lat"] = existing_location["lat"]
                profile["lon"] = existing_location["lon"]
                profile = context_manager.update_profile(session_id, profile)
        
        # Execute recommendation with updated profile
        print(f"[follow-up-recommendation] Updated profile: {profile}")
        recs = recommender.recommend(profile=profile, vitals=None)
        
        if not recs:
            return {"answer": "I couldn't find suitable activities with your new criteria.", "result": []}
        
        activities_text = format_recommendations(recs)
        return {
            "answer": f"Here are updated recommendations based on your new criteria:\n\n{activities_text}", 
            "result": recs,
            "user_location": {"lat": profile.get("lat"), "lon": profile.get("lon")}
        }

    # 3. Intent classifier (ML-based routing)
    # Build context-aware input for classifier
    history_text = " ".join([f"{h['role']}: {h['content']}" for h in history])
    classifier_input = f"{history_text}\nuser: {user_msg}"
    intent = intent_clf.predict(classifier_input)
    print(f"[DEBUG] Intent classifier input: '{classifier_input}'")
    print(f"[DEBUG] Intent classifier result: '{intent}'")

    if intent == "recommend_activity":
        # Additional check: ensure the message actually contains recommendation keywords
        # This prevents false positives from the intent classifier
        if not any(k in user_msg for k in ["recommend", "activity", "suggestion", "recommendation", "suggest", "morning", "afternoon", "evening", "free", "cheap", "expensive", "nearby", "far", "different"]):
            print(f"[DEBUG] Intent classifier returned 'recommend_activity' but no relevant keywords found, treating as chitchat")
            return {"answer": "I can help with your health-related questions or recommend suitable activities."}
        
        profile = context_manager.get_profile(session_id)
        print(f"[recommendation] Existing profile: {profile}")
        # Update profile with parsed info from current message + recent history
        parsed = profile_parser.parse_user_profile(
            user_msg, conversation_history=context_manager.get_history(session_id)
        )
        parsed = profile_parser.enhance_profile_with_location(parsed)
        if parsed:
            profile = context_manager.update_profile(session_id, parsed)

        # Check if profile is complete 
        missing_resp = check_missing_profile_fields(profile, session_id, context_manager)
        if missing_resp:
            return missing_resp

        # Check if location is needed
        if _needs_location_selection(profile):
            reply = "I need to know your location to recommend nearby activities. Please select your location on the map below, or click 'Skip' to use the default Singapore location."
            context_manager.add_message(session_id, "assistant", reply)
            return {
                "answer": reply, 
                "result": [],
                "show_map": True,
                "user_location": None
            }

        # profile complete with location, proceed to recommend
        print(f"[recommendation] Final profile: {profile}")
        recs = recommender.recommend(profile=profile, vitals=None)

        if not recs:
            return {"answer": "I couldn't find suitable activities right now.", "result": []}
        activities_text = format_recommendations(recs)
        return {
            "answer": f"Here are my recommended activities:\n\n{activities_text}", 
            "result": recs,
            "user_location": {"lat": profile.get("lat"), "lon": profile.get("lon")}
        }

    elif intent == "health_qa":
        output = rag_answer(user_msg)
        return {"answer": output["answer"], "retrieved": output["retrieved"]}

    elif intent == "chitchat":
        return {"answer": "I can help with your health-related questions or recommend suitable activities."}

    # === 3) Default fallback ===
    output = rag_answer(user_msg)
    return {"answer": output["answer"], "retrieved": output["retrieved"]}


# ========= Format result =========
def format_recommendations(recommendations: List[Dict]) -> str:
    if not recommendations:
        return "No activities found."

    blocks = []
    for i, rec in enumerate(recommendations, 1):
        activity    = html.escape(rec.get("activity", "Unknown Activity") or "Unknown Activity")
        price       = rec.get("price", "Not provided")
        distance    = rec.get("distance", "Not provided")
        date        = safe_html(rec.get("date"))
        start_time  = safe_html(rec.get("start_time"))
        end_time    = safe_html(rec.get("end_time"))
        language    = safe_html(rec.get("language"))
        source_type = safe_html(rec.get("source_type"))
        description = safe_html(rec.get("description"))

        # number formatting
        if isinstance(price, (int, float)):
            price = "Free" if price == 0 else f"${price:.0f}"
        else:
            price = safe_html(price)

        if isinstance(distance, (int, float)):
            distance = f"{distance:.1f} km"
        else:
            distance = safe_html(distance)

        # Default to show preview if too long
        preview_len = 200
        if len(description) > preview_len:
            short_desc = description[:preview_len].rstrip() + "..."
            desc_html = (
                f"<details>"
                f"<summary><b>Description:</b> {short_desc} (click to expand)</summary>"
                f"<p style='margin-left:1em; color:#444;'>{description}</p>"
                f"</details>"
            )
        else:
            desc_html = f"<b>Description:</b> {description}"

        block = textwrap.dedent(f"""
        <div style="margin-bottom:12px; line-height:1.45; font-size:14px;">
          <b>{i}. {activity}</b><br>
          <b>Price:</b> {price}<br>
          <b>Distance:</b> {distance}<br>
          <b>Date:</b> {date}<br>
          <b>Time:</b> {start_time} - {end_time}<br>
          <b>Language:</b> {language}<br>
          <b>Source type:</b> {source_type}<br>
          {desc_html}
        </div>
        """).strip()

        blocks.append(block)

    # join with newline; Streamlit will handle <br> inside each block
    return "\n".join(blocks)

def safe_html(value):
    """Ensure html.escape always gets a string."""
    return html.escape(str(value) if value is not None else "Not provided")