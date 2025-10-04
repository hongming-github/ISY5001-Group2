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

    # 拼接活动文本（和你 main 里的一样）
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
    print("开始生成 embedding ...")
    df["activity_vector"] = list(MODEL.encode(df["activity_text"].tolist(), show_progress_bar=True))

    # 保存为 pickle，加快后续加载
    output_path = os.path.join(base_dir, "activities_with_vec.pkl")
    df.to_pickle(output_path)
    print(f"保存完成: {output_path}")
