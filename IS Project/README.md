# Health Monitoring ML App

This project is a **machine learning application** with:  

- **Frontend**: [Streamlit](https://streamlit.io/) — user interface to enter health data.  
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) — API server to process input data.  
- **Processor**: `data_processor.py` — contains logic for parsing and analyzing health metrics.  
- **Deployment**: [Docker Compose](https://docs.docker.com/compose/) — runs frontend and backend services together.  

---

## 📂 Project Structure

```
.
├── backend                   # Backend project
├──── main.py                 # FastAPI backend (API server)
├──── data_processor.py       # Data processing & ML logic
├──── requirements.txt        # Python dependencies (backend)
├──── Dockerfile              # Base Dockerfile (for building app image)
├── frontend                  # Frontend project
├──── streamlit_app.py        # Streamlit frontend (UI form)
├──── requirements.txt        # Python dependencies (frontend)
├──── Dockerfile              # Base Dockerfile (for building app image)
├── docker-compose.yml        # Compose file (orchestration)
└── README.md                 # Documentation
```

---

## 🚀 How to Run

### 1. Prerequisites
- Docker  
- Docker Compose  

Check installation:

```bash
docker -v
docker compose version
```

### 2. Build and Start Services

From the project root, run:

```bash
docker compose up --build
```

This will:  
- Build the images from `Dockerfile`  
- Start **FastAPI** backend (default: `http://localhost:8000`)  
- Start **Streamlit** frontend (default: `http://localhost:8501`)  

### 3. Access the Application
- Open frontend in browser: **http://localhost:8501**  
- Streamlit UI provides input boxes for:
  - Device ID  
  - Blood Pressure (Systolic/Diastolic)  
  - Heart Rate  
  - Blood Glucose  
  - Blood Oxygen  
  - Timestamp (manual or current time)  

On submit, the data is sent to the backend.

---

## 🔗 API Endpoint

### POST `/submit`
- **Request Body** (JSON):
```json
{
  "device_id": "ABC123",
  "blood_pressure": "120/80",
  "heart_rate": 72,
  "blood_glucose": 95,
  "blood_oxygen": 98,
  "timestamp": "2025-09-26T10:15:30"
}
```

- **Response**:
```json
{
  "status": "processed",
  "result": {
    "device_id": "ABC123",
    "systolic": 120,
    "diastolic": 80,
    "heart_rate": 72,
    "blood_glucose": 95,
    "blood_oxygen": 98,
    "health_score": 122.5,
    "timestamp": "2025-09-26T10:15:30"
  }
}
```

---

## 🏗 Code Flow

1. **Streamlit UI** collects user input.  
2. Data sent via **HTTP POST** to FastAPI `/submit`.  
3. **FastAPI** validates input (`pydantic` models).  
4. Data passed to **`data_processor.py`** for parsing/ML processing.  
5. Processed results returned as JSON and displayed in Streamlit.  

---

## 🛑 Stopping Services

Press `CTRL+C` in terminal, then clean up with:

```bash
docker compose down
```
