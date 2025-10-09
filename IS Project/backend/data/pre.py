import pandas as pd
from sentence_transformers import SentenceTransformer
import os

MODEL = SentenceTransformer('all-MiniLM-L6-v2')

def enhance_with_keywords(text, keywords, weight=3):
    words = text.split()
    for keyword in keywords:
        if keyword.lower() not in [w.lower() for w in words]:
            words.extend([keyword] * weight)
    return ' '.join(words)

if __name__ == "__main__":
    base_dir = os.path.dirname(__file__)
    data_path = os.path.join(base_dir, "activities.xlsx")

    df = pd.read_excel(data_path)

    # Concatenate activity text 
    activity_texts = []
    for _, row in df.iterrows():
        title = str(row.get("title", ""))
        category = str(row.get("category", ""))
        subcategory = str(row.get("subcategory", ""))
        description = str(row.get("description", ""))

        parts = [
            (title, 5),
            (category, 2),
            (subcategory, 2),
            (description, 1)
        ]
        weighted_parts = []
        for text, w in parts:
            if text.strip():
                weighted_parts.extend([text] * w)

        activity_text = " ".join(weighted_parts)
        activity_texts.append(activity_text)

    df["activity_text"] = activity_texts
    print("Starting to generate embeddings...")
    df["activity_vector"] = list(MODEL.encode(df["activity_text"].tolist(), show_progress_bar=True))

    # Save as pickle to speed up subsequent loading
    output_path = os.path.join(base_dir, "activities_with_vec.pkl")
    df.to_pickle(output_path)
    print(f"Save completed: {output_path}")
