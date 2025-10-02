from typing import List, Dict, Optional
from pydantic import BaseModel

from vital_signs_processor import HealthData, process_vital_signs
from recommender import ElderlyActivityRecommender, VitalInput
from chatbot.rag import rag_answer
from chatbot.intent_classifier import IntentClassifier
from chatbot.profile_parser import ProfileParser

# Initialize recommender (load model if any)
recommender = ElderlyActivityRecommender(model_path=None)
# Initialize the intent classifier globally
intent_clf = IntentClassifier()
# Initialize profile parser
profile_parser = ProfileParser()

class ChatTurn(BaseModel):
    role: str
    content: str
    flow_tag: Optional[str] = None


class ChatRequest(BaseModel):
    history: List[ChatTurn] = []
    message: str
    context_vitals: Optional[HealthData] = None
    profile: Optional[Dict] = None


class ChatResponse(BaseModel):
    answer: str
    result: Optional[List[Dict]] = None
    retrieved: List[str] | None = None
    flow_tag: Optional[str] = None

def handle_chat(payload):
    user_msg = payload.message.lower()
    original_msg = payload.message

    # 1. Rule-based intent detection (highest priority)
    # Keywords that strongly indicate recommendation request
    rec_keywords = ["recommend", "activity", "suggestion", "recommendation", "suggest"]
    if any(k in user_msg for k in rec_keywords):
        if not payload.profile or not payload.profile.get("interests"):
            return {
                "answer": (
                    "Sure! To recommend activities, could you tell me:\n"
                    "- Your interests (e.g., yoga, tai chi)\n"
                    "- Preferred language\n"
                    "- Preferred time slots (morning/afternoon/evening)\n"
                    "- Your budget (number)\n"
                    "- Do you prefer free activities?\n"
                    "- Your location\n"
                ),
                "result": [],
                "flow_tag": "REC_FLOW"
            }
        
        # 如果 profile 已经有了，就直接调用推荐系统
        print(f"[recommend-keyword] Profile for recommendation: {payload.profile}")
        recs = recommender.recommend(profile=payload.profile, vitals=None)
        print(f"[recommend-keyword] Recs count: {len(recs) if recs else 0}")
        if not recs:
            return {"answer": "I couldn't find suitable activities right now.", "result": []}
        activities_text = format_recommendations(recs)
        return {"answer": f"Here are my recommended activities:\n\n{activities_text}", "result": recs}

    # 2. 检查对话历史，看是否在推荐流程中
    if payload.history:
        # 找到上一条系统/助手消息
        last_turn = payload.history[-1]
        if isinstance(last_turn, dict):
            last_turn = ChatTurn(**last_turn)

        # 通过 flow_tag 判断是否在推荐流程
        if getattr(last_turn, "flow_tag", None) == "REC_FLOW":
            print("Detected recommendation context via flow_tag, parsing user profile...")
            profile = profile_parser.parse_user_profile(
                original_msg, conversation_history=[t.dict() for t in payload.history]
            )
            profile = profile_parser.enhance_profile_with_location(profile)

            print(f"[recommend-context] Profile for recommendation: {profile}")
            recs = recommender.recommend(profile=profile, vitals=None)
            if not recs:
                return {"answer": "I couldn't find suitable activities right now.", "result": []}
            activities_text = format_recommendations(recs)
            return {
                "answer": f"Here are my recommended activities:\n\n{activities_text}",
                "result": recs
            }


    # 3. Intent classifier (ML-based routing)
    intent = intent_clf.predict(user_msg)

    if intent == "recommend_activity":
        if not payload.profile:
            # 用 LLM 解析用户的自然语言 → profile
            profile = profile_parser.parse_user_profile(original_msg, conversation_history=[t.dict() for t in payload.history])
            profile = profile_parser.enhance_profile_with_location(profile)

            print(f"[recommend-intent] Profile for recommendation: {profile}")
            recs = recommender.recommend(profile=profile, vitals=None)
            print(f"[recommend-intent] Recs count: {len(recs) if recs else 0}")
            if not recs:
                return {"answer": "I couldn't find suitable activities right now.", "result": []}
            activities_text = format_recommendations(recs)
            return {"answer": f"Here are my recommended activities:\n\n{activities_text}", "result": recs}
        else:
            # 已有 profile，直接推荐
            print(f"[recommend-intent-existing] Profile for recommendation: {payload.profile}")
            recs = recommender.recommend(profile=payload.profile, vitals=None)
            print(f"[recommend-intent-existing] Recs count: {len(recs) if recs else 0}")
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

        # --- 格式化数值 ---
        if isinstance(price, (int, float)):
            price = "Free" if price == 0 else f"${price:.0f}"
        if isinstance(distance, (int, float)):
            distance = f"{distance:.1f} km"

        block = (
            f"{i}. {activity}  \n"
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