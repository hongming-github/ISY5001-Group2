from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
import httpx, asyncio
import os

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

class HealthData(BaseModel):
    device_id: str
    blood_pressure: str  # systolic/diastolic format
    heart_rate: int
    blood_glucose: int
    blood_oxygen: int
    timestamp: str | None = None  # optional (ISO format string)

def process_vital_signs(data: HealthData) -> dict:
    """
    Parse blood pressure string and compute a simple health score.
    Accepts a HealthData object.
    """
    try:
        parts = data.blood_pressure.replace(" ", "").split("/")
        systolic = int(parts[0])
        diastolic = int(parts[1])
    except Exception:
        raise ValueError("Blood pressure must be 'systolic/diastolic', e.g., 120/80")

    # Collect results from each classifier
    alerts = [
        classify_blood_pressure(systolic, diastolic),
        classify_heart_rate(data.heart_rate),
        classify_blood_glucose(data.blood_glucose),
        classify_blood_oxygen(data.blood_oxygen)
    ]

    alerts = [a for a in alerts if a]
    
    # Send alerts if threshold is met
    if alerts:
        msg = format_alert_msg(data.device_id, data.timestamp, alerts)
        asyncio.get_running_loop().create_task(send_alerts(msg))

    return {
        "device_id": data.device_id,
        "systolic": systolic,
        "diastolic": diastolic,
        "heart_rate": data.heart_rate,
        "blood_glucose": data.blood_glucose,
        "blood_oxygen": data.blood_oxygen,
        "alerts": alerts,
        "timestamp": data.timestamp,
    }


def classify_blood_pressure(systolic: int, diastolic: int) -> str:
    if systolic > 139 and diastolic > 89:
        return f"Blood Pressure: Signs of stage 2 Hypertension. Reading = {systolic}/{diastolic}"
    elif systolic > 129 and diastolic > 79:
        return f"Blood Pressure: Signs of stage 1 Hypertension. Reading = {systolic}/{diastolic}"
    elif systolic > 119 and diastolic < 80:
        return f"Blood Pressure: Elevated. Reading = {systolic}/{diastolic}"
    

def classify_heart_rate(heart_rate: int) -> str:
    if heart_rate > 100:
        return f"Heart Rate: High. Reading = {heart_rate}"
    elif heart_rate < 60: 
        return f"Heart Rate: Low. Reading = {heart_rate}"


def classify_blood_glucose(blood_glucose: int) -> str:
    if blood_glucose > 125:
        return f"Blood Glucose: Signs of diabetes. Reading = {blood_glucose}"
    elif blood_glucose > 99:
        return f"Blood Glucose: Signs of pre-diabetes. Reading = {blood_glucose}"
    elif blood_glucose < 70:
        return f"Blood Glucose: Signs of low blood sugar. Reading = {blood_glucose}"
    

def classify_blood_oxygen(blood_oxygen: int) -> str:
    if blood_oxygen > 93 and blood_oxygen < 96:
        return f"Blood Oxygen: Borderline Low -> monitor closely. Reading = {blood_oxygen}"
    elif blood_oxygen > 89:
        return f"Blood Oxygen: Low -> consult doctor. Reading = {blood_oxygen}"
    elif blood_oxygen < 90:
        return f"Blood Oxygen: Extremely Low -> medical emergency. Reading = {blood_oxygen}"
    

def format_alert_msg(device_id: str, timestamp: str, alerts: list[str]) -> str: 
    lines = []
    lines.append("<b>🚨 Vital Signs Alert 🚨</b>\n")
    lines.append(f"<b>Device ID</b>: {device_id}")
    lines.append(f"<b>Time</b>: {timestamp}\n")
    for a in alerts:
        lines.append(f"⚠️ {a}\n")

    return "\n".join(lines)
    
import traceback

async def send_alerts(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(url, json=payload)
    except Exception:
        pass