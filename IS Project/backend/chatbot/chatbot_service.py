from typing import List, Dict, Optional
from pydantic import BaseModel

from vital_signs_processor import HealthData, process_vital_signs
from recommender import ElderlyActivityRecommender, VitalInput
from chatbot.rag import rag_answer
from chatbot.intent_classifier import IntentClassifier

# Initialize recommender (load model if any)
recommender = ElderlyActivityRecommender(model_path=None)
# Initialize the intent classifier globally
intent_clf = IntentClassifier()

class ChatTurn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    history: List[ChatTurn] = []
    message: str
    context_vitals: Optional[HealthData] = None


class ChatResponse(BaseModel):
    answer: str
    retrieved: List[str] | None = None

def handle_chat(payload):
    user_msg = payload.message.lower()

    # 1. Rule-based intent detection (highest priority)
    # Keywords that strongly indicate recommendation request
    rec_keywords = ["recommend", "activity", "suggestion", "recommendation", "suggest"]
    if any(k in user_msg for k in rec_keywords):
        recs = recommender.recommend(profile={}, vitals=None, k=3)
        activities = "\n".join([f"- {r['activity']} (intensity: {r['intensity']})" for r in recs])
        reply = f"Here are my recommended activities:\n{activities}"
        return {"answer": reply}

    # 2. Intent classifier (ML-based routing)
    intent = intent_clf.predict(user_msg)

    if intent == "recommend_activity":
        recs = recommender.recommend(profile={}, vitals=None, k=3)
        activities = "\n".join([f"- {r['activity']} (intensity: {r['intensity']})" for r in recs])
        reply = f"Here are my recommended activities:\n{activities}"
        return {"answer": reply}

    elif intent == "health_qa":
        output = rag_answer(user_msg)
        return {"answer": output["answer"], "retrieved": output["retrieved"]}

    elif intent == "chitchat":
        return {"answer": "I can help with your health-related questions or recommend suitable activities."}

    # 3. Default fallback (send to RAG by default)
    output = rag_answer(user_msg)
    return {"answer": output["answer"], "retrieved": output["retrieved"]}