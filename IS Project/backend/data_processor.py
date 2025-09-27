# Example data processing function
def process_data(input_value: float) -> float:
    return input_value * 2

def process_health_data(device_id, blood_pressure, heart_rate, blood_glucose, blood_oxygen):
    # Example: simple parsing and normalization
    systolic, diastolic = map(int, blood_pressure.split("/"))
    
    health_score = (0.3 * heart_rate) + (0.2 * blood_glucose) + (0.1 * systolic) + (0.1 * diastolic) + (0.3 * blood_oxygen)

    return {
        "device_id": device_id,
        "systolic": systolic,
        "diastolic": diastolic,
        "heart_rate": heart_rate,
        "blood_glucose": blood_glucose,
        "blood_oxygen": blood_oxygen,
        "health_score": round(health_score, 2)
    }