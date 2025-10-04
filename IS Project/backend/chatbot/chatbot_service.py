from typing import List, Dict, Optional
from pydantic import BaseModel
import re

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
    """检查是否需要用户选择位置"""
    # 如果没有lat/lon坐标，或者坐标为0，则需要用户选择位置
    lat = profile.get("lat")
    lon = profile.get("lon")
    return lat is None or lon is None or lat == 0 or lon == 0

def _get_default_singapore_location() -> Dict:
    """获取新加坡默认位置"""
    return {"lat": 1.3521, "lon": 103.8198}

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

        # 获取现有profile并合并
        existing_profile = context_manager.get_profile(session_id)
        # 合并profile，但新解析的信息优先
        profile = {**existing_profile, **new_profile}
        profile = context_manager.update_profile(session_id, profile)
  
        # Check if profile is complete
        # required_fields = ["interests", "language", "time", "budget", "location"]
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

        # Check if location is needed
        print(f"[DEBUG] Checking location in rule-based: lat={profile.get('lat')}, lon={profile.get('lon')}")
        print(f"[DEBUG] Needs location selection: {_needs_location_selection(profile)}")
        if _needs_location_selection(profile):
            reply = "I need to know your location to recommend nearby activities. Please select your location on the map below, or click 'Skip' to use the default Singapore location."
            context_manager.add_message(session_id, "assistant", reply)
            return {
                "answer": reply, 
                "result": [],
                "show_map": True,
                "user_location": None
            }

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

    # # 2. 检查对话历史，看是否在推荐流程中
    # if payload.history:
    #     # 找到上一条系统/助手消息
    #     last_turn = payload.history[-1]
    #     if isinstance(last_turn, dict):
    #         last_turn = ChatTurn(**last_turn)

    #     # 通过 flow_tag 判断是否在推荐流程
    #     if getattr(last_turn, "flow_tag", None) == "REC_FLOW":
    #         print("Detected recommendation context via flow_tag, parsing user profile...")
    #         profile = profile_parser.parse_user_profile(
    #             original_msg, conversation_history=[t.dict() for t in payload.history]
    #         )
    #         profile = profile_parser.enhance_profile_with_location(profile)

    #         print(f"[recommend-context] Profile for recommendation: {profile}")
    #         recs = recommender.recommend(profile=profile, vitals=None)
    #         if not recs:
    #             return {"answer": "I couldn't find suitable activities right now.", "result": []}
    #         activities_text = format_recommendations(recs)
    #         return {
    #             "answer": f"Here are my recommended activities:\n\n{activities_text}",
    #             "result": recs
    #         }


    # 3. Check for follow-up recommendation requests (context-aware)
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

    # 4. Intent classifier (ML-based routing)
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

        # 用 parser + LLM 尝试解析用户输入并更新 profile
        parsed = profile_parser.parse_user_profile(
            user_msg, conversation_history=context_manager.get_history(session_id)
        )
        parsed = profile_parser.enhance_profile_with_location(parsed)
        if parsed:
            profile = context_manager.update_profile(session_id, parsed)

        # 检查 profile 是否完整
        # required_fields = ["interests", "language", "time", "budget", "location"]
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

        # profile 完整，直接推荐
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


# ========= 推荐结果格式化 =========
def format_recommendations(recommendations: List[Dict]) -> str:
    if not recommendations:
        return "No activities found."

    formatted = []
    for i, rec in enumerate(recommendations, 1):
        activity = rec.get("activity", "Unknown Activity") or "Unknown Activity"
        price = rec.get("price", "Not provided")
        distance = rec.get("distance", "Not provided")
        date = rec.get("date", "Not provided")
        start_time = rec.get("start_time", "Not provided")
        end_time = rec.get("end_time", "Not provided")
        language = rec.get("language", "Not provided")
        source_type = rec.get("source_type", "Not provided")
        description = rec.get("description", "Not provided")

        # format numbers
        if isinstance(price, (int, float)):
            price = "Free" if price == 0 else f"${price:.0f}"
        if isinstance(distance, (int, float)):
            distance = f"{distance:.1f} km"

        activity    = _escape_md(activity)
        price       = _escape_md(price)
        distance    = _escape_md(distance)
        date        = _escape_md(date)
        start_time  = _escape_md(start_time)
        end_time    = _escape_md(end_time)
        language    = _escape_md(language)
        source_type = _escape_md(source_type)
        description = _escape_md(description)
        
        block = (
            f"{i}. **{activity}**  \n"
            # f"Intensity: {intensity.title()}  \n"
            f"Price: {price}  \n"
            f"Distance: {distance}  \n"
            f"Date: {date}  \n"
            f"Time: {start_time} - {end_time}  \n"
            f"Language: {language}  \n"
            f"Source type: {source_type}  \n"
            f"Description: {description}"
        )

        formatted.append(block)

    return "\n\n".join(formatted)


_MD_SPECIAL = re.compile(r'([\\`*_{}\[\]()#+!|>])')

def _escape_md(text: str) -> str:
    """Escape Markdown special chars so Streamlit renders plain text."""
    if text is None:
        return ""
    s = str(text)
    # normalize weird whitespaces
    s = (s.replace("\u00A0", " ")   # non-breaking space
           .replace("\u200b", "")   # zero-width space
           .replace("\u2009", " "))
    # collapse long runs of spaces/tabs
    s = re.sub(r"[ \t]{2,}", " ", s)
    # escape markdown control characters
    s = _MD_SPECIAL.sub(r"\\\1", s)
    return s