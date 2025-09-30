import os
from pinecone import Pinecone
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from openai import OpenAI

load_dotenv()

# ---------------- Init Pinecone ----------------
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

INDEX_NAME = "health-knowledge-vector"

# if INDEX_NAME not in pinecone.list_indexes():
#     pinecone.create_index(INDEX_NAME, dimension=2560, metric="cosine")

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
            base_url="https://ark.cn-beijing.volces.com/api/v3"
        )
        self.model = embeddingModel

    def embed_documents(self, texts):
        resp = self.client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]

    def embed_query(self, text):
        return self.embed_documents([text])[0]
    
# class ArkEmbeddings:
#     def embed_documents(self, texts):
#         resp = client.embeddings.create(model=embeddingModel, input=texts, encoding_format="float")
#         return [d.embedding for d in resp.data]

#     def embed_query(self, text):
#         return self.embed_documents([text])[0]

# # ---------------- LLM Wrapper ----------------
# class ArkLLM:
#     """Minimal wrapper to let Ark work with LangChain chains"""
#     def __init__(self, model=llmModel):
#         self.model = model

#     def __call__(self, prompt: str) -> str:
#         resp = client.chat.completions.create(
#             model=self.model,
#             messages=[{"role": "user", "content": prompt}]
#         )
#         return resp.choices[0].message.content
