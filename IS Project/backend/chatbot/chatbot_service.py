# chatbot.py
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel

from vital_signs_processor import HealthData, process_vital_signs
from recommender import ElderlyActivityRecommender, VitalInput
from chatbot.rag import rag_answer

# Initialize recommender (load model if any)
recommender = ElderlyActivityRecommender(model_path=None)

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


def handle_chat(payload: ChatRequest) -> ChatResponse:
    """
    Process chat logic, including invoking the recommendation model
    """
    user_msg = payload.message.lower()
    vitals_text = ""
    vitals_input = None

    # Ff context vitals are provided, process them
    # if payload.context_vitals:
    #     ts = payload.context_vitals.timestamp or datetime.utcnow().isoformat()
    #     processed = process_vital_signs(
    #         payload.context_vitals.device_id,
    #         payload.context_vitals.blood_pressure,
    #         payload.context_vitals.heart_rate,
    #         payload.context_vitals.blood_glucose,
    #         payload.context_vitals.blood_oxygen,
    #     )
    #     vitals_input = VitalInput(
    #         device_id=payload.context_vitals.device_id,
    #         systolic=processed["systolic"],
    #         diastolic=processed["diastolic"],
    #         heart_rate=processed["heart_rate"],
    #         blood_glucose=processed["blood_glucose"],
    #         blood_oxygen=processed["blood_oxygen"],
    #         timestamp=ts,
    #     )
    #     vitals_text = (
    #         f"(BP {processed['systolic']}/{processed['diastolic']}, "
    #         f"HR {processed['heart_rate']}, "
    #         f"GLU {processed['blood_glucose']}, "
    #         f"SpO2 {processed['blood_oxygen']})"
    #     )

    # Simple keyword-based intent recognition
    # Activity recommendation
    if any(k in user_msg for k in ["recommend", "activity", "suggestion"]):
        if vitals_input:
            recs = recommender.recommend(profile={}, vitals=vitals_input, k=3)
            activities = "\n".join(
                [f"- {r['activity']} (intensity: {r['intensity']})" for r in recs]
            )
            reply = f"Based on your current readings {vitals_text}, here are my recommended activities:\n{activities}"
        else:
            reply = "Please provide your latest health data before I can recommend suitable activities."
        return ChatResponse(reply=reply)

    # Knowledge base Q&A (RAG)
    if any(k in user_msg for k in ["blood pressure", "heart rate", "exercise", "diet", "health", "diabetes", "training"]):
        output = rag_answer(payload.message)
        return ChatResponse(answer=output["answer"], retrieved=output["retrieved"])

    # Default response
    return ChatResponse(answer="Hello! You can provide health data for activity recommendations, or ask me health-related questions.")
