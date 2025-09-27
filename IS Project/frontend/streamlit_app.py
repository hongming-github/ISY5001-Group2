import streamlit as st
import requests
from datetime import datetime

st.title("Health Monitoring Input Form")

device_id = st.text_input("Device ID")
blood_pressure = st.text_input("Blood Pressure (format: systolic/diastolic)")
heart_rate = st.number_input("Heart Rate (bpm)", min_value=0, step=1)
blood_glucose = st.number_input("Blood Glucose (mg/dL)", min_value=0, step=1)
blood_oxygen = st.number_input("Blood Oxygen (%)", min_value=0, max_value=100, step=1)

timestamp_option = st.radio(
    "Timestamp option:",
    ("Use current time", "Enter manually")
)

if timestamp_option == "Enter manually":
    timestamp = st.text_input("Enter timestamp (YYYY-MM-DD HH:MM:SS)")
else:
    timestamp = datetime.utcnow().isoformat()

if st.button("Submit"):
    payload = {
        "device_id": device_id,
        "blood_pressure": blood_pressure,
        "heart_rate": heart_rate,
        "blood_glucose": blood_glucose,
        "blood_oxygen": blood_oxygen,
        "timestamp": timestamp if timestamp else None
    }
    
    response = requests.post("http://localhost:8000/submit", json=payload)
    if response.status_code == 200:
        st.success(f"Server Response: {response.json()}")
    else:
        st.error("Failed to submit data")

st.title("Machine Learning Model Prediction")

feature1 = st.number_input("Feature 1")
feature2 = st.number_input("Feature 2")

if st.button("Predict"):
    # Call the FastAPI endpoint
    response = requests.post(
        "http://localhost:8000/predict",  # Make FastAPI expose 8000 port
        json={"feature1": feature1, "feature2": feature2},
    )

    # Process the response
    if response.status_code == 200:
        prediction = response.json()["prediction"]
        st.success(f"Prediction: {prediction}")
    else:
        st.error("Error: Could not connect to the API")

# Inputbox for user input
user_input = st.number_input("Please key in a number", value=0.0, step=0.1)

# Button to process the input
if st.button("Process Data"):
    # Display a loading spinner while processing
    with st.spinner("Processing..."):
        try:
            # Send the input to the FastAPI backend
            response = requests.post(
                "http://fastapi:8000/process",
                json={"value": user_input}
            )
            
            # Check the response status
            if response.status_code == 200:
                result = response.json()
                # Display the result
                st.success("Done!")
                st.write(f"Orinical data: {result['original_value']}")
                st.write(f"Processed data: {result['processed_value']}")
            else:
                st.error(f"Failed: {response.status_code}")
                
        except Exception as e:
            st.error(f"Error: {str(e)}")