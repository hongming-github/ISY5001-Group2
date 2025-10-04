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
    if any(k in user_msg for k in rec_keywords):
        
        profile = context_manager.get_profile(session_id)

        # parse user profile from current message + recent history
        profile = profile_parser.parse_user_profile(
            user_msg, conversation_history=history
        )
        profile = profile_parser.enhance_profile_with_location(profile)

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

        # Profile complete, proceed to recommend
        print(f"[recommendation] Final profile: {profile}")
        recs = recommender.recommend(profile=profile, vitals=None)

        if not recs:
            return {"answer": "I couldn't find suitable activities right now.", "result": []}
        activities_text = format_recommendations(recs)
        return {"answer": f"Here are my recommended activities:\n\n{activities_text}", "result": recs}

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


    # 3. Intent classifier (ML-based routing)
    # Build context-aware input for classifier
    history_text = " ".join([f"{h['role']}: {h['content']}" for h in history])
    classifier_input = f"{history_text}\nuser: {user_msg}"
    intent = intent_clf.predict(classifier_input)

    if intent == "recommend_activity":
        
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

        # profile 完整，直接推荐
        print(f"[recommendation] Final profile: {profile}")
        recs = recommender.recommend(profile=profile, vitals=None)

        if not recs:
            return {"answer": "I couldn't find suitable activities right now.", "result": []}
        activities_text = format_recommendations(recs)
        return {"answer": f"Here are my recommended activities:\n\n{activities_text}", "result": recs}


    elif intent == "health_qa":
        output = rag_answer(user_msg)
        return {"answer": output["answer"], "retrieved": output["retrieved"]}

    elif intent == "chitchat":
        return {"answer": "I can help with your health-related questions or recommend suitable activities."}

    # 3. Default fallback (send to RAG by default)
    output = rag_answer(user_msg)
    return {"answer": output["answer"], "retrieved": output["retrieved"]}


def format_recommendations(recommendations: List[Dict]) -> str:
    if not recommendations:
        return "No activities found."

    formatted = []
    for i, rec in enumerate(recommendations, 1):
        activity = rec.get("activity", "Unknown Activity") or "Unknown Activity"
        # intensity = rec.get("intensity", "Not provided")
        price = rec.get("price", "Not provided")
        distance = rec.get("distance", "Not provided")
        date = rec.get("date", "Not provided")
        start_time = rec.get("start_time", "Not provided")
        end_time = rec.get("end_time", "Not provided")
        language = rec.get("language", "Not provided")
        # remaining = rec.get("remaining", "Not provided")
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
            # f"Remaining slots: {remaining}  \n"
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