import os
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain_pinecone import PineconeVectorStore
from rag_utils import DoubaoEmbeddings, INDEX_NAME

# ---------------- Helpers ----------------
def txt_to_docs(txt_path: str):
    """Load txt file and split into LangChain Documents"""
    with open(txt_path, "r", encoding="utf-8") as f:
        text = f.read()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.split_text(text)
    return [Document(page_content=chunk, metadata={"source": os.path.basename(txt_path)}) for chunk in chunks]

def upload_all_txt(docs_dir: str = "chatbot/docs"):
    """Scan docs/ directory and upload all txt files to Pinecone"""
    all_docs = []
    for fname in os.listdir(docs_dir):
        if fname.endswith(".txt"):
            path = os.path.join(docs_dir, fname)
            print(f"📖 Processing {path} ...")
            docs = txt_to_docs(path)
            all_docs.extend(docs)

    if not all_docs:
        print("⚠️ No txt files found in docs/ directory")
        return

    embeddings = DoubaoEmbeddings()
    PineconeVectorStore.from_documents(
        all_docs,
        embedding=embeddings,
        index_name=INDEX_NAME,
    )
    print(f"✅ Uploaded {len(all_docs)} chunks from {len([d for d in os.listdir(docs_dir) if d.endswith('.txt')])} files to Pinecone.")

# ---------------- Run ----------------
if __name__ == "__main__":
    docs_dir = os.path.join(os.path.dirname(__file__), "docs")
    upload_all_txt(docs_dir)
