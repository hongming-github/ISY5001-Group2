import os
from pinecone import Pinecone
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import OpenAI

load_dotenv()

# ---------------- Init Pinecone ----------------
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
INDEX_NAME = "health-knowledge-vector"

embeddingModel = "doubao-embedding-text-240715"
llmModel = "deepseek-v3-1-250821"

Embeddings = OpenAIEmbeddings(
    model=embeddingModel
)

LLM = ChatOpenAI(
    model=llmModel
)

class DoubaoEmbeddings:
    def __init__(self):
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_API_BASE")
        )
        self.model = embeddingModel

    def embed_documents(self, texts):
        resp = self.client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]

    def embed_query(self, text):
        return self.embed_documents([text])[0]