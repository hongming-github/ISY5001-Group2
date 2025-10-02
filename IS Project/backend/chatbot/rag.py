from langchain_pinecone import PineconeVectorStore
from langchain.chains.question_answering import load_qa_chain
from chatbot.rag_utils import DoubaoEmbeddings, LLM

index_name = "health-knowledge-vector"

def rag_answer(query: str, top_k: int = 3) -> str:
    embeddings = DoubaoEmbeddings()
    vectorstore = PineconeVectorStore(index_name=index_name, embedding=embeddings)

    # 1. Retrieve documents
    docs_and_scores = vectorstore.similarity_search_with_score(query, k=top_k)

    # Build context with scores for display
    context_with_scores = []
    docs = []
    for doc, score in docs_and_scores:
        context_with_scores.append(f"[Score={score:.4f}] {doc.page_content}")
        docs.append(doc)

    # 2. Use LangChain's QA Chain
    llm = LLM
    qa_chain = load_qa_chain(llm, chain_type="stuff")

    # 3. Run QA chain
    result = qa_chain.invoke({"input_documents": docs, "question": query}, return_only_outputs=True)
    answer_text = result["output_text"] if isinstance(result, dict) else str(result)
    
    # 4. Return both retrieval results (with scores) and final answer
    return {
        "answer": answer_text,
        "retrieved": context_with_scores
    }
