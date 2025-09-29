# chatbot.py
from typing import List, Dict, Optional
from datetime import datetime
from pydantic import BaseModel

from vital_signs_processor import HealthData, process_vital_signs
from recommender import ElderlyActivityRecommender, VitalInput

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
    reply: str


def handle_chat(payload: ChatRequest) -> ChatResponse:
    """
    Process chat logic, including invoking the recommendation model
    """
    user_msg = payload.message.lower()
    vitals_text = ""
    vitals_input = None

    # Ff context vitals are provided, process them
    if payload.context_vitals:
        ts = payload.context_vitals.timestamp or datetime.utcnow().isoformat()
        processed = process_vital_signs(
            payload.context_vitals.device_id,
            payload.context_vitals.blood_pressure,
            payload.context_vitals.heart_rate,
            payload.context_vitals.blood_glucose,
            payload.context_vitals.blood_oxygen,
        )
        vitals_input = VitalInput(
            device_id=payload.context_vitals.device_id,
            systolic=processed["systolic"],
            diastolic=processed["diastolic"],
            heart_rate=processed["heart_rate"],
            blood_glucose=processed["blood_glucose"],
            blood_oxygen=processed["blood_oxygen"],
            timestamp=ts,
        )
        vitals_text = (
            f"(BP {processed['systolic']}/{processed['diastolic']}, "
            f"HR {processed['heart_rate']}, "
            f"GLU {processed['blood_glucose']}, "
            f"SpO2 {processed['blood_oxygen']})"
        )

    # Simple keyword-based intent recognition
    if any(k in user_msg for k in ["recommend", "活动", "建议"]):
        if vitals_input:
            recs = recommender.recommend(profile={}, vitals=vitals_input, k=3)
            activities = "\n".join(
                [f"- {r['activity']} (intensity: {r['intensity']})" for r in recs]
            )
            reply = f"Based on your current readings {vitals_text}, here are my recommended activities:\n{activities}"
        else:
            reply = "Please provide your latest health data so I can recommend suitable activities."
    else:
        reply = (
            "Hello! You can ask me about your readings "
            "or say 'recommend activities' to get suggestions."
        )

    return ChatResponse(reply=reply)
