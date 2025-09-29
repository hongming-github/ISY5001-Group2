# Health Monitoring & Chatbot App

This project is a **machine learning application** with:

- **Frontend**: [Streamlit](https://streamlit.io/) — user interface for data entry and chatting.  
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) — API server with two endpoints:  
  - `/submit` → process vital signs  
  - `/chat` → chatbot with integrated recommendation model  
- **Logic Modules**:  
  - `vital_signs_processor.py` → defines `HealthData` model and processes vital signs  
  - `chatbot.py` → handles chatbot logic, including recommendation calls  
  - `recommender.py` → contains the elderly activity recommendation logic  

Deployment is managed with [Docker Compose](https://docs.docker.com/compose/).

---

## 📂 Project Structure

```
.
├──── backend                # Backend
├── main.py                  # FastAPI entrypoint
├── vital_signs_processor.py # HealthData model + vital signs processing
├── chatbot.py               # Chatbot logic (integrated with recommender)
├── recommender.py           # Elderly activity recommendation model
├── requirements.txt         # Python dependencies
├──Dockerfile                # Container build definition
├──── frontend               # Frontend
├── streamlit_app.py         # Streamlit frontend (form + chat UI)
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container build definition
├──── docker-compose.yml     # Service orchestration
└──── README.md              # Documentation
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
- Build the image(s) from `Dockerfile`  
- Start **FastAPI backend** (default: `http://localhost:8000`)  
- Start **Streamlit frontend** (default: `http://localhost:8501`)  

### 3. Access the Application

- **Frontend (UI)**: [http://localhost:8501](http://localhost:8501)  
- **Backend (API)**: [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI)  

---

## 🔗 API Endpoints

### POST `/submit`

**Request Body (JSON):**

```json
{
  "device_id": "ABC123",
  "blood_pressure": "120/80",
  "heart_rate": 72,
  "blood_glucose": 95,
  "blood_oxygen": 98,
  "timestamp": "2025-09-29T10:15:30"
}
```

**Response:**

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
    "timestamp": "2025-09-29T10:15:30"
  }
}
```

---

### POST `/chat`

**Request Body (JSON):**

```json
{
  "history": [
    {"role": "user", "content": "hello"}
  ],
  "message": "recommend activities",
  "context_vitals": {
    "device_id": "ABC123",
    "blood_pressure": "150/95",
    "heart_rate": 88,
    "blood_glucose": 165,
    "blood_oxygen": 96,
    "timestamp": "2025-09-29T07:45:00Z"
  }
}
```

**Response:**

```json
{
  "reply": "Based on your current readings (BP 150/95, HR 88, GLU 165, SpO2 96), here are my recommended activities:\n- Post-meal walk (intensity: low)\n- Tai Chi / Qigong (intensity: low)"
}
```

---

## 🏗 Code Flow

1. **Streamlit UI** collects user input or chat messages.  
2. **FastAPI `/submit`** → validates input with `HealthData`, calls `process_vital_signs`.  
3. **FastAPI `/chat`** → handles conversation logic via `chatbot.py`, optionally invokes `recommender`.  
4. **`vital_signs_processor.py`** centralizes vital signs model & processing logic.  
5. **`recommender.py`** provides activity recommendations based on health status.  

---

## 🛑 Stopping Services

Press `CTRL+C` in terminal, then clean up with:

```bash
docker compose down
```
