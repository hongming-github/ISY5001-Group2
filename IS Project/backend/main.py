from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from vital_signs_processor import HealthData, process_vital_signs
from chatbot.chatbot_service import ChatRequest, ChatResponse, handle_chat
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