from pydantic import BaseModel
from typing import Optional

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

    # Example health score calculation (replace with ML model if needed)
    health_score = round(
        0.1 * systolic +
        0.1 * diastolic +
        0.3 * data.heart_rate +
        0.2 * data.blood_glucose +
        0.3 * data.blood_oxygen, 2
    )

    return {
        "device_id": data.device_id,
        "systolic": systolic,
        "diastolic": diastolic,
        "heart_rate": data.heart_rate,
        "blood_glucose": data.blood_glucose,
        "blood_oxygen": data.blood_oxygen,
        "health_score": health_score,
        "timestamp": data.timestamp,
    }