from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from recommendation_model import main as rec_main
from fastapi.middleware.cors import CORSMiddleware
from vital_signs_processor import HealthData, process_vital_signs
from chatbot import ChatRequest, ChatResponse, handle_chat
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