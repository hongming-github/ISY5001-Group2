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
    user_location: Optional[Dict] = None


class ChatResponse(BaseModel):
    answer: str
    result: Optional[List[Dict]] = None
    retrieved: List[str] | None = None
    flow_tag: Optional[str] = None
    show_map: Optional[bool] = None
    user_location: Optional[Dict] = None

def should_show_map(user_message: str) -> bool:
    """判断是否需要显示地图让用户选择位置"""
    recommendation_keywords = ["recommend", "suggest", "activities", "recommendation", "suggestion"]
    return any(keyword in user_message.lower() for keyword in recommendation_keywords)

def handle_location_selection(payload):
    """处理用户地图位置选择"""
    user_msg = payload.message.lower()
    original_msg = payload.message
    
    # 检查是否是位置选择相关的消息
    if "location" in user_msg or "skip" in user_msg or "default" in user_msg:
        # 解析用户消息获取位置信息
        profile = profile_parser.parse_user_profile(original_msg, conversation_history=[t.dict() for t in payload.history])
        
        # 如果用户选择跳过，使用默认位置
        if "skip" in user_msg or "default" in user_msg:
            profile["lat"] = 1.3521  # 新加坡默认坐标
            profile["lon"] = 103.8198
            profile["location"] = "Singapore (default)"
        
        # 增强profile
        profile = profile_parser.enhance_profile_with_location(profile)
        
        return {
            "answer": "Great! Location selected. Now please tell me your preferences:\n\n"
                     "🎯 **Your preferences:**\n"
                     "   - Interests (e.g., yoga, tai chi, fitness)\n"
                     "   - Language preference\n"
                     "   - Time slots (morning/afternoon/evening)\n"
                     "   - Budget (or \"free\")\n"
                     "   - Any other requirements?",
            "result": [],
            "flow_tag": "REC_FLOW",
            "user_location": {"lat": profile.get("lat"), "lon": profile.get("lon")}
        }
    
    return None

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
                    "Sure! To recommend activities, I'll need some details:\n\n"
                    "📍 **Step 1: Choose your location** (or skip to use default)\n"
                    "   👉 Please click on the map to select your area\n\n"
                    "🎯 **Step 2: Tell me your preferences**\n"
                    "   - Interests (e.g., yoga, tai chi, fitness)\n"
                    "   - Language preference\n"
                    "   - Time slots (morning/afternoon/evening)\n"
                    "   - Budget (or \"free\")\n"
                    "   - Any other requirements?\n\n"
                    "You can provide all details at once or step by step!"
                ),
                "result": [],
                "flow_tag": "REC_FLOW",
                "show_map": True
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
            
            # 检查是否有用户位置信息
            user_location = payload.user_location or getattr(last_turn, "user_location", None)
            
            profile = profile_parser.parse_user_profile(
                original_msg, conversation_history=[t.dict() for t in payload.history]
            )
            
            # 如果有用户选择的位置，使用它
            if user_location:
                profile["lat"] = user_location.get("lat", 1.3521)
                profile["lon"] = user_location.get("lon", 103.8198)
                print(f"Using user selected location: lat={profile['lat']}, lon={profile['lon']}")
            else:
                profile = profile_parser.enhance_profile_with_location(profile)
                print(f"Using default location: lat={profile['lat']}, lon={profile['lon']}")

            print(f"[recommend-context] Profile for recommendation: {profile}")
            recs = recommender.recommend(profile=profile, vitals=None)
            if not recs:
                return {"answer": "I couldn't find suitable activities right now.", "result": []}
            activities_text = format_recommendations(recs)
            return {
                "answer": f"Here are my recommended activities:\n\n{activities_text}",
                "result": recs,
                "user_location": user_location
            }


    # 3. Intent classifier (ML-based routing)
    intent = intent_clf.predict(user_msg)

    if intent == "recommend_activity":
        if not payload.profile:
            # 用 LLM 解析用户的自然语言 → profile
            profile = profile_parser.parse_user_profile(original_msg, conversation_history=[t.dict() for t in payload.history])
            
            # 如果有用户选择的位置，使用它
            if payload.user_location:
                profile["lat"] = payload.user_location.get("lat", 1.3521)
                profile["lon"] = payload.user_location.get("lon", 103.8198)
                print(f"Using user selected location (intent): lat={profile['lat']}, lon={profile['lon']}")
            else:
                profile = profile_parser.enhance_profile_with_location(profile)
                print(f"Using default location (intent): lat={profile['lat']}, lon={profile['lon']}")

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