from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
import numpy as np
import joblib
import os

def main():
    # Use lightweight pretrained model
    model = SentenceTransformer("all-MiniLM-L6-v2")

    # Training examples
    examples = [
        # --- Activity Recommendation ---
        ("recommend some exercises", "recommend_activity"),
        ("what activities can I do", "recommend_activity"),
        ("suggest activity for seniors", "recommend_activity"),
        ("give me an exercise recommendation", "recommend_activity"),
        ("which activity is suitable for me", "recommend_activity"),
        ("any suggestions for physical activity", "recommend_activity"),
        ("can you recommend a workout", "recommend_activity"),
        ("suggest me something to do", "recommend_activity"),
        ("activities for elderly", "recommend_activity"),

        # --- Health Q&A ---
        ("what is normal blood pressure", "health_qa"),
        ("tell me about diabetes", "health_qa"),
        ("how to lower heart rate", "health_qa"),
        ("diet for elderly people", "health_qa"),
        ("what foods should seniors avoid", "health_qa"),
        ("how can I manage hypertension", "health_qa"),
        ("what are symptoms of high cholesterol", "health_qa"),
        ("is walking good for health", "health_qa"),
        ("exercise for diabetes", "health_qa"),
        ("how to improve blood oxygen", "health_qa"),

        # --- Chitchat / Fallback ---
        ("hello", "chitchat"),
        ("hi there", "chitchat"),
        ("how are you", "chitchat"),
        ("tell me a joke", "chitchat"),
        ("thank you", "chitchat"),
        ("who are you", "chitchat"),
        ("goodbye", "chitchat"),
        ("nice to meet you", "chitchat"),
        ("what's your name", "chitchat"),
        ("see you later", "chitchat"),
    ]

    # Build dataset
    texts, labels = zip(*examples)
    X = model.encode(texts)
    y = np.array(labels)

    # Train classifier
    clf = LogisticRegression(max_iter=2000)
    clf.fit(X, y)

    # Save both embedding model name and classifier
    output_path = os.path.join(os.path.dirname(__file__), "intent_clf.pkl")
    joblib.dump(
        {"model_name": "all-MiniLM-L6-v2", "clf": clf},output_path)
    
    print(f"✅ Intent classifier saved to {output_path}")

if __name__ == "__main__":
    main()
