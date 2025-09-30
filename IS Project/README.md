# ISY5001-Group2 Matching Pattern Project

This project is a **full-stack RAG (Retrieval-Augmented Generation) system** for elderly health knowledge assistance.  
It integrates:

- **Frontend**: Streamlit UI (for vital signs input & chatbot interface)  
- **Backend**: FastAPI API service (for data processing & chatbot logic)  
- **RAG Knowledge Base**: Pinecone vector database + Doubao API (embedding + LLM)  
- **Containerization**: Docker Compose for one-click setup  

---

## 📂 Project Structure

```
.
├── backend/
│   ├── main.py                       # FastAPI entrypoint
│   ├── vital_signs_processor.py      # Business logic for vital signs
│   ├── chatbot/
│   │   ├──── docs/                   # Knowledge base
│   │   ├──── elderly_health_qa.txt   # health knowledge
│   │   ├── chatbot_service.py        # Chatbot handler
│   │   ├── rag.py                    # RAG workflow (search + QA chain)
│   │   ├── rag_utils.py              # Pinecone + Doubao embeddings/LLM config
│   │   └── build_index.py            # Build Pinecone index from TXT files
│   └── recommender.py                # Elderly activity recommendation model
├── frontend/
│   └── streamlit_app.py              # Streamlit UI
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## ⚙️ Environment Setup

### 1. Create `.env`
In the project root, add a `.env` file:

```ini
# Pinecone
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_ENVIRONMENT=us-east-1

# Doubao (Ark API)
OPENAI_API_KEY=your-doubao-api-key
OPENAI_API_BASE=https://ark.cn-beijing.volces.com/api/v3
```

⚠️ Use `OPENAI_API_KEY` and `OPENAI_API_BASE` for compatibility with `langchain-openai`.

---

## 🐳 Run with Docker Compose

Build and start services:
```bash
docker compose build
docker compose up
```

- FastAPI backend → http://localhost:8000  
- Streamlit frontend → http://localhost:8501  

---

## 📚 Build Knowledge Base

All `.txt` files should be placed in:
```
backend/chatbot/docs/
```

Run the index builder:
```bash
docker compose run --rm fastapi python chatbot/build_index.py
```

This script will:
- Load all `.txt` files
- Split them into chunks
- Embed them with Doubao
- Upload to Pinecone

---

## 💬 Chatbot Usage

1. Open Streamlit UI → http://localhost:8501  
2. Switch to **Chatbot** tab  
3. Ask questions such as:  
   > "How can high blood pressure be prevented?"  

### Returned Result
- **Answer**: Generated summary based on retrieved documents  
- **Retrieved Context**: Shows top-k documents with similarity scores  

---

## 🔀 Modes

You can switch answer modes in `rag.py`:

- **Summary mode (default)**:  
  Uses LangChain QA Chain (`load_qa_chain`) to generate a summarized answer.

- **Top-1 mode**:  
  Returns only the highest-ranked document content:  

  ```python
  top_doc, score = docs_and_scores[0]
  return {"answer": top_doc.page_content, "retrieved": context_with_scores}
  ```

---

## 🧪 Timeout Configuration

- **LLM / Embeddings**: Configured with `request_timeout=60`  
- **Frontend (Streamlit)**: `requests.post(..., timeout=60)`  
- **Backend (FastAPI)**: default Uvicorn timeout is used, can be tuned in `docker-compose.yml`.

---

## ✅ Requirements

See `requirements.txt` for full dependencies (FastAPI, Streamlit, LangChain, Pinecone, OpenAI SDK, python-dotenv, etc.).  
Install locally with:
```bash
pip install -r requirements.txt
```

---

## 📌 Notes
- Ensure `.env` is correctly mounted in Docker.  
- Pinecone index must be built before querying.  
- Doubao API keys are compatible with `langchain-openai` by setting `OPENAI_API_KEY`.  

---
