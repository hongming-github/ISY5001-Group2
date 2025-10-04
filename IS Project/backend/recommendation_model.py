import pandas as pd
import numpy as np
import re
import os
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from haversine import haversine


print("Loading SentenceTransformer model...")  
MODEL = SentenceTransformer('all-MiniLM-L6-v2')  

# -----------------------------
# Language filter
# -----------------------------
def language_filter(df, user_languages):
    if isinstance(user_languages, str):
        user_languages = [user_languages]  # Normalize to list
    user_languages = [lang.lower().strip() for lang in user_languages]

    def check_lang(activity_lang):
        if pd.isna(activity_lang):
            return False
        langs = re.split(r'[,/;| ]+', str(activity_lang).lower())
        langs = [l.strip() for l in langs if l.strip()]
        return any(user_lang in langs for user_lang in user_languages)

    return df[df['language'].apply(check_lang)]


# -----------------------------
# Time slot penalty function
# -----------------------------
def time_slot_penalty(activity_slot, user_time_slots):
    if pd.isna(activity_slot):
        return 0.5  # Unknown time slot, penalty 0.5
    if activity_slot.lower() in [slot.lower() for slot in user_time_slots]:
        return 0   # Match → no penalty
    return 1       # Mismatch → penalty 1


# -----------------------------
# Multi-rule filtering
# -----------------------------
def multi_rule_filter(df, user_languages, user_budget, user_time_slots, user_lat, user_lon, max_distance=50):
    # df['registration_closing_date'] = pd.to_datetime(df['registration_closing_date'], errors='coerce')
    # df = df[(df['registration_closing_date'].isna()) | (df['registration_closing_date'] > pd.Timestamp.now())]

    initial_count = len(df)
    # print(f"初始数量: {initial_count}")

    # Step 1: Language filter
    before = len(df)
    df = language_filter(df, user_languages)
    after = len(df)
    # print(f"语言过滤: {before} -> {after} (过滤掉 {before - after})")

    # Step 2: Timeliness + capacity filter
    # df = df[(df['registration_closing_date'] > pd.Timestamp.now()) & (df['enrolled'] < df['capacity'])]

    # Step 3: Geographic filter
    before = len(df)
    user_coords = (user_lat, user_lon)
    distances = []
    for lat, lon in zip(df['lat'], df['lon']):
        try:
            dist = haversine(user_coords, (lat, lon))  # 单位 km
            distances.append(dist)
        except:
            distances.append(float('inf'))
    df = df.copy()
    df.loc[:, 'distance'] = distances
    df = df[df['distance'] <= max_distance]
    after = len(df)
    # print(f"地理过滤 (<= {max_distance} km): {before} -> {after} (过滤掉 {before - after})")    

    # Step 4: Time slot penalty
    df['is_wrong_time_slot'] = df['time_slot'].apply(lambda x: time_slot_penalty(x, user_time_slots))

    return df


# -----------------------------
# Embedding utilities
# -----------------------------
def generate_vectors(texts, model):
    return model.encode(texts)


def enhance_with_keywords(text, keywords, weight=3):
    words = text.split()
    for keyword in keywords:
        if keyword.lower() not in [w.lower() for w in words]:
            words.extend([keyword] * weight)
    return ' '.join(words)


# -----------------------------
# Composite scoring function
# -----------------------------
def comprehensive_score(df, user_vector, user_budget, user_need_free, user_interests,
                        alpha=0.5, beta=0.1, gamma=0.1, delta=0.3):
    if len(df) == 0:
        return df

 
    activity_vectors = np.stack(df['activity_vector'].values)
    df['InterestScore'] = cosine_similarity([user_vector], activity_vectors)[0]

    df['KeywordMatch'] = df['title'].str.lower().apply(
        lambda t: 1 if any(kw.lower() in t for kw in user_interests) else 0
    )


    df['InterestScore'] = df['InterestScore'] + 0.2 * df['KeywordMatch']

 
    # Distance normalization with stronger penalty for far distances
    max_dist = 50
    df['normalized_distance'] = df['distance'].apply(lambda x: min(x / max_dist, 1.0))
    
    # Apply exponential penalty for distance to make nearby activities much more attractive
    df['distance_penalty'] = df['normalized_distance'].apply(lambda x: x ** 2)

    # Composite score with increased distance weight
    df['score'] = (
        alpha * df['InterestScore']
        - beta * (df['price_num'] > user_budget * 1.5).astype(int)     # 超预算惩罚
        - beta * (df['is_free'].apply(lambda x: 0 if not user_need_free else (0 if x == 1 else 1))) # 偏好免费
        - gamma * df['is_wrong_time_slot']
        - delta * df['distance_penalty']  # 使用距离惩罚而不是标准化距离
    )
    return df


# -----------------------------
# Convert score to star rating
# -----------------------------
def score_to_stars(score):
    min_score, max_score = -0.5, 1.0
    normalized = (score - min_score) / (max_score - min_score)
    stars = int(round(normalized * 5))
    return '★' * max(stars, 1)


# -----------------------------
# Main function
# -----------------------------
def main(user_interests, user_languages, user_time_slots,
         user_budget, user_need_free, user_lat, user_lon, sourcetypes=None):
    try:
        base_dir = os.path.dirname(__file__)
        data_path = os.path.join(base_dir, 'data', 'activities.xlsx')
        df = pd.read_excel(data_path)
    except Exception as e:
        print(f"Failed to read data: {e}")
        return pd.DataFrame()

    # 处理缺失参数的默认值
    # 1. 语言缺失则默认英语
    if not user_languages or len(user_languages) == 0:
        user_languages = ["English"]
    
    # 2. 时段缺失则早中晚都可以
    if not user_time_slots or len(user_time_slots) == 0:
        user_time_slots = ["morning", "afternoon", "evening"]
    
    # 3. 预算缺失可以设置为999
    if user_budget is None or user_budget <= 0:
        user_budget = 999.0
    
    # 4. need_free缺失则默认为false
    if user_need_free is None:
        user_need_free = False
    
    # 5. 经纬度缺失则默认不考虑距离的计算
    skip_distance_filter = False
    if user_lat is None or user_lon is None or (user_lat == 0.0 and user_lon == 0.0):
        skip_distance_filter = True
        user_lat = 0.0
        user_lon = 0.0
    
    # 6. sourcetype缺失则默认全选
    if not sourcetypes or len(sourcetypes) == 0:
        sourcetypes = None

    # Source type filter (default to all if None/empty)
    valid_types = {"course", "event", "interest_group"}
    if sourcetypes:
        selected = {s.strip().lower() for s in sourcetypes if isinstance(s, str)}
        selected = selected & valid_types
        if len(selected) > 0 and 'source_type' in df.columns:
            df = df[df['source_type'].str.lower().isin(selected)]

    # 7. 兴趣缺失则从活动中随机抽取五条
    user_interests = [i for i in user_interests if i.strip()]
    if not user_interests or len(user_interests) == 0:
        print("No user interests provided, returning random activities")
        random_activities = df.sample(n=min(5, len(df)))

        # 添加必要的字段
        random_activities = random_activities.copy()
        random_activities['score'] = 0.5  # 随机推荐给个中等分数
        random_activities['InterestScore'] = 0.5
        random_activities['remaining'] = random_activities['capacity'] - random_activities['enrolled']
        
        # 计算距离（如果提供了坐标）
        if not skip_distance_filter:
            user_coords = (user_lat, user_lon)
            distances = []
            for lat, lon in zip(random_activities['lat'], random_activities['lon']):
                try:
                    dist = haversine(user_coords, (lat, lon))
                    distances.append(dist)
                except:
                    distances.append(float('inf'))
            random_activities['distance'] = distances
        else:
            random_activities['distance'] = 0.0
        
        return random_activities[['title', 'category', 'description', 'score', 'InterestScore',
                                  'language', 'distance', 'remaining', 'date',
                                  'start_time', 'end_time', 'price_num', 'source_type', 'lat', 'lon']]

    # Multi-rule filtering (修改以支持跳过距离过滤)
    if skip_distance_filter:
        # 跳过距离过滤的版本
        df = language_filter(df, user_languages)
        df['is_wrong_time_slot'] = df['time_slot'].apply(lambda x: time_slot_penalty(x, user_time_slots))
        df['distance'] = 0.0  # 设置距离为0，表示不考虑距离
    else:
        df = multi_rule_filter(df, user_languages, user_budget, user_time_slots, user_lat, user_lon)
    
    if len(df) == 0:
        print("No activities match after multi-rule filtering")
        return pd.DataFrame()

    # Load model
    model = MODEL

    # User interest vector: average multiple interests
    user_interest_vecs = model.encode(user_interests)
    user_vector = np.mean(user_interest_vecs, axis=0)

    # Generate activity vectors (with weights and safe field handling)
    activity_texts = []
    for _, row in df.iterrows():
        title = str(row['title']) if 'title' in row and pd.notna(row['title']) else ''
        category = str(row['category']) if 'category' in row and pd.notna(row['category']) else ''
        subcategory = str(row['subcategory']) if 'subcategory' in row and pd.notna(row['subcategory']) else ''
        description = str(row['description']) if 'description' in row and pd.notna(row['description']) else ''
        # requirements = str(row['requirements']) if 'requirements' in row and pd.notna(row['requirements']) else ''

        parts = [
            (title, 5),
            (category, 2),
            (subcategory, 2),
            (description, 1),
            # (requirements, 1)
        ]
        weighted_parts = []
        for text, w in parts:
            if text.strip():
                weighted_parts.extend([text] * w)

        activity_text = ' '.join(weighted_parts)

        activity_text = enhance_with_keywords(activity_text, user_interests, weight=3)
        activity_texts.append(activity_text)

    # df['activity_text'] = activity_texts
    # df['activity_vector'] = list(generate_vectors(df['activity_text'].tolist(), model))
    base_dir = os.path.dirname(__file__)
    data_path = os.path.join(base_dir, "data", "activities_with_vec.pkl")
    df_with_vec = pd.read_pickle(data_path)

    df = df.merge(
        df_with_vec[['id', 'activity_vector']], 
        on='id', 
        how='left'
    )

    # Compute composite score
    df = comprehensive_score(df, user_vector, user_budget, user_need_free, user_interests)
    if len(df) == 0:
        return pd.DataFrame()

    df = df.sort_values(by='score', ascending=False)
    df['remaining'] = df['capacity'] - df['enrolled']

    # Interest threshold filtering (lowered to allow more activities while still prioritizing distance)
    interest_threshold = 0.6
    relevant_activities = df[df['InterestScore'] >= interest_threshold]

    if len(relevant_activities) < 5:
        top_5 = pd.concat([relevant_activities, df[df['InterestScore'] < interest_threshold]]).head(5)
    else:
        top_5 = relevant_activities.head(5)
    
    # Remove duplicates based on title (keep the one with highest score)
    top_5 = top_5.drop_duplicates(subset=['title'], keep='first')
    
    # If we have less than 5 after deduplication, fill with more activities
    if len(top_5) < 5:
        remaining_activities = df[~df['title'].isin(top_5['title'])]
        additional_needed = 5 - len(top_5)
        if len(remaining_activities) > 0:
            additional = remaining_activities.head(additional_needed)
            top_5 = pd.concat([top_5, additional])

    # # Add recommendation reasons
    # reasons = []
    # for _, row in top_5.iterrows():
    #     reason = []
    #     if row['InterestScore'] > 0.6:
    #         reason.append("High interest match")
    #     if row['distance'] < 3:
    #         reason.append("Nearby")
    #     if row['is_free'] == 1:
    #         reason.append("Free activity")
    #     if row['price_num'] <= user_budget:
    #         reason.append("Within budget")
    #     reasons.append(", ".join(reason) if reason else "Recommended based on overall match")
    # top_5['reason'] = reasons

    return top_5[['title', 'category', 'description', 'score', 'InterestScore',
                  'language', 'distance', 'date',
                  'start_time', 'end_time', 'price_num', 'source_type', 'lat', 'lon']]
