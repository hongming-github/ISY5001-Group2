from sentence_transformers import SentenceTransformer
import joblib
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), "intent_clf.pkl")

class IntentClassifier:
    def __init__(self):
        # Load saved model
        saved = joblib.load(MODEL_PATH)
        self.model = SentenceTransformer(saved["model_name"])
        self.clf = saved["clf"]

    def predict(self, text: str) -> str:
        emb = self.model.encode([text])
        return self.clf.predict(emb)[0]