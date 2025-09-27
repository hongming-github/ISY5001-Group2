from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from data_processor import process_data
from data_processor import process_health_data
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
class InputData(BaseModel):
    feature1: float
    feature2: float

class InputData1(BaseModel):
    value: float

class HealthData(BaseModel):
    device_id: str
    blood_pressure: str  # systolic/diastolic format
    heart_rate: int
    blood_glucose: int
    blood_oxygen: int
    timestamp: str | None = None  # optional (ISO format string)

@app.get("/")
async def root():
    return {"message": "Hello World"}

# Endpoint to process data
@app.post("/process")
async def process(input_data: InputData1):
    result = process_data(input_data.value)
    return {"original_value": input_data.value, "processed_value": result}

@app.post("/predict")
async def predict(data: InputData):
    prediction = model.predict([[data.feature1, data.feature2]])[0]
    return {"prediction": prediction}

@app.post("/submit")
async def submit_data(data: HealthData):
    # Call your data processing logic
    result = process_health_data(
        data.device_id,
        data.blood_pressure,
        data.heart_rate,
        data.blood_glucose,
        data.blood_oxygen
    )
    return {"status": "processed", "result": result}