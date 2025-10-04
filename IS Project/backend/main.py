from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from recommendation_model import main as rec_main
from fastapi.middleware.cors import CORSMiddleware
from vital_signs_processor import HealthData, process_vital_signs
from chatbot.chatbot_service import ChatRequest, ChatResponse, handle_chat, format_recommendations
from dotenv import load_dotenv
import os
#import joblib

app = FastAPI()

origins = [
    "http://localhost",  
    "http://localhost:8501",  # Streamlit default port
    "http://yourdomain.com",  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load .env file automatically
load_dotenv()

# Load your ML model here
#model = joblib.load("your_model.joblib")  

@app.get("/")
async def root():
    return {"message": "Hello World"}


#Endpoint to process health data
@app.post("/submit")
async def submit_data(data: HealthData):
    ts = data.timestamp
    data.timestamp = ts  # make sure timestamp is set
    result = process_vital_signs(data)
    return {"status": "processed", "result": result}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
    return handle_chat(payload)

class LocationRecommendRequest(BaseModel):
    session_id: str
    lat: float
    lon: float

@app.post("/recommend_with_location", response_model=ChatResponse)
async def recommend_with_location(payload: LocationRecommendRequest):
    """处理位置选择后的推荐请求"""
    from chatbot.chatbot_service import context_manager, profile_parser, recommender
    
    session_id = payload.session_id
    lat = payload.lat
    lon = payload.lon
    
    # 获取当前profile
    profile = context_manager.get_profile(session_id)
    
    # 更新profile with location
    profile = profile_parser.update_profile_with_map_location(profile, lat, lon)
    profile = context_manager.update_profile(session_id, profile)
    
    # 执行推荐
    print(f"[location-recommendation] Profile with location: {profile}")
    recs = recommender.recommend(profile=profile, vitals=None)
    
    if not recs:
        return {
            "answer": "I couldn't find suitable activities right now.", 
            "result": [],
            "user_location": {"lat": lat, "lon": lon}
        }
    
    activities_text = format_recommendations(recs)
    return {
        "answer": f"Here are my recommended activities:\n\n{activities_text}", 
        "result": recs,
        "user_location": {"lat": lat, "lon": lon}
    }

class ClearLocationRequest(BaseModel):
    session_id: str

@app.post("/clear_location")
async def clear_location(payload: ClearLocationRequest):
    """清空用户的位置信息"""
    from chatbot.chatbot_service import context_manager
    
    session_id = payload.session_id
    
    # 获取当前profile
    profile = context_manager.get_profile(session_id)
    
    # 清空位置相关字段
    profile.pop("lat", None)
    profile.pop("lon", None)
    profile.pop("location", None)
    
    # 更新profile
    context_manager.update_profile(session_id, profile)
    
    print(f"[clear-location] Cleared location for session {session_id}")
    return {"status": "success", "message": "Location cleared successfully"}


class RecommendRequest(BaseModel):
    user_interests: List[str]
    user_languages: List[str]
    user_time_slots: List[str]
    user_budget: float
    user_need_free: bool
    user_lat: float
    user_lon: float
    sourcetypes: Optional[List[str]] = None  # course | event | interest_group


@app.post("/recommend")
async def recommend(req: RecommendRequest):
    df = rec_main(
        req.user_interests,
        req.user_languages,
        req.user_time_slots,
        req.user_budget,
        req.user_need_free,
        req.user_lat,
        req.user_lon,
        req.sourcetypes,
    )
    items = df.to_dict(orient="records") if hasattr(df, "to_dict") else []
    return {"items": items}