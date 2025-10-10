import pandas as pd
import numpy as np
import re
import os
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from haversine import haversine

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
    # Step 1: Language filter
    df = language_filter(df, user_languages)

    # Step 2: Geographic filter
    user_coords = (user_lat, user_lon)
    distances = []
    for lat, lon in zip(df['lat'], df['lon']):
        try:
            dist = haversine(user_coords, (lat, lon))  # unit: km
            distances.append(dist)
        except:
            distances.append(float('inf'))
    df = df.copy()
    df.loc[:, 'distance'] = distances
    df = df[df['distance'] <= max_distance]

    # Step 3: Time slot penalty
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
                        alpha=0.55, beta=0.15, gamma=0.1, delta=0.2):
    if len(df) == 0:
        return df

    # InterestScore match
    activity_vectors = np.stack(df['activity_vector'].values)
    df['InterestScore'] = cosine_similarity([user_vector], activity_vectors)[0]

    # -------- Keyword-based enhancements --------
    def keyword_match_bonus(row):
        title = str(row['title']).lower()
        desc = str(row['description']).lower()
        bonus = 0.0
        for kw in user_interests:
            kw = kw.lower().strip()
            # Title completely matches (directly hits the keyword)
            if re.search(rf'\b{re.escape(kw)}\b', title):
                bonus += 0.25
            # Description contains
            elif kw in desc:
                bonus += 0.15
        return min(bonus, 0.4)  # Limit the maximum bonus to 0.4, avoid too high

    df['KeywordBonus'] = df.apply(keyword_match_bonus, axis=1)
    df['InterestScore'] = (df['InterestScore'] + df['KeywordBonus']).clip(0, 1)

    # Smoothly amplify high interest range
    df['InterestScore'] = np.sqrt(df['InterestScore'])

    # Distance penalty
    max_dist = 50
    df['normalized_distance'] = df['distance'].apply(lambda x: min(x / max_dist, 1.0))
    df['distance_penalty'] = 0.5 * df['normalized_distance'] + 0.5 * (df['normalized_distance'] ** 2)

    # Price penalty
    df['price_penalty'] = np.clip((df['price_num'] - user_budget) / user_budget, 0, 1)

    # Free activity preference bonus
    df['free_bonus'] = df['is_free'].apply(lambda x: 0.1 if (user_need_free and x == 1) else 0)

    # Composite score
    df['score'] = (
        alpha * df['InterestScore']
        - beta * df['price_penalty']
        - gamma * df['is_wrong_time_slot']
        - delta * df['distance_penalty']
        + df['free_bonus']
    )

    return df

def normalize_score(series, temperature=2.0):
    s = pd.Series(series, dtype=float)
    if len(s) == 0:
        return s
    mu = s.mean()
    sigma = s.std()
    if sigma == 0 or np.isnan(sigma):
        return pd.Series([0.5] * len(s), index=s.index)
    z = (s - mu) / (sigma * temperature)
    return 1 / (1 + np.exp(-z))

def explain_recommendation(row, user_interests, user_budget, user_need_free,
                           user_provided_budget=True, user_provided_time_slots=True):
    reasons = []

    # InterestScore
    if row['InterestScore'] >= 0.85:
        matched_kw = [kw for kw in user_interests if kw.lower() in row['title'].lower() or kw.lower() in str(row['description']).lower()]
        if matched_kw:
            reasons.append(f"strongly matches your interest in {', '.join(matched_kw)}")
        else:
            reasons.append("is highly relevant to your interests")
    elif row['InterestScore'] >= 0.7:
        reasons.append("matches your interests")
    else:
        reasons.append("is somewhat related to your interests")

    # Price and Budget
    if row['is_free'] == 1:
        if user_need_free:
            reasons.append("is free, perfectly fitting your preference for free activities")
        else:
            reasons.append("is free to join")
    elif user_provided_budget:
        if row['price_num'] <= user_budget:
            reasons.append(f"is within your budget (SGD {row['price_num']:.2f})")
        else:
            reasons.append(f"is slightly above your budget (SGD {row['price_num']:.2f})")

    # Distance
    if row['distance'] <= 2:
        reasons.append("is very close to your location")
    elif row['distance'] <= 8:
        reasons.append("is reasonably near you")
    else:
        reasons.append("is a bit farther but still accessible")

    # Time slot
    if user_provided_time_slots and row['is_wrong_time_slot'] == 0:
        reasons.append("matches your preferred time slot")

    explanation = (
        f"This activity {', '.join(reasons)}. "
    )
    return explanation

# -----------------------------
# Main function
# -----------------------------
def main(user_interests, user_languages, user_time_slots,
         user_budget, user_need_free, user_lat, user_lon, sourcetypes=None):
    try:
        base_dir = os.path.dirname(__file__)
        data_path = os.path.join(base_dir, '..', 'data', 'activities.xlsx')
        df = pd.read_excel(data_path)
    except Exception as e:
        print(f"Failed to read data: {e}")
        return pd.DataFrame()

    # Process defaults for missing inputs
    # 1. Language default to English
    if not user_languages or len(user_languages) == 0:
        user_languages = ["English"]
    
    # 2. Time slots default to all
    user_provided_time_slots = True
    if not user_time_slots or len(user_time_slots) == 0:
        user_time_slots = ["morning", "afternoon", "evening"]
        user_provided_time_slots = False
    
    # 3. Budget default to 999
    user_provided_budget = True
    if user_budget is None or user_budget <= 0:
        user_budget = 999.0
        user_provided_budget = False
    
    # 4. need_free default to False
    if user_need_free is None:
        user_need_free = False
    
    # 5. lat/lon missing or zero → skip distance filtering
    skip_distance_filter = False
    if user_lat is None or user_lon is None or (user_lat == 0.0 and user_lon == 0.0):
        skip_distance_filter = True
        user_lat = 0.0
        user_lon = 0.0
    
    # 6. sourcetype missing or empty → all types
    if not sourcetypes or len(sourcetypes) == 0:
        sourcetypes = None

    # Source type filter (default to all if None/empty)
    valid_types = {"course", "event", "interest_group"}
    if sourcetypes:
        selected = {s.strip().lower() for s in sourcetypes if isinstance(s, str)}
        selected = selected & valid_types
        if len(selected) > 0 and 'source_type' in df.columns:
            df = df[df['source_type'].str.lower().isin(selected)]

    # 7. Interests missing or empty → return random activities
    user_interests = [i for i in user_interests if i.strip()]
    if not user_interests or len(user_interests) == 0:
        print("No user interests provided, returning random activities")
        random_activities = df.sample(n=min(3, len(df)))

        # Add necessary fields
        random_activities = random_activities.copy()
        random_activities['score'] = 0.5  # Random score
        random_activities['InterestScore'] = 0.5
        random_activities['remaining'] = random_activities['capacity'] - random_activities['enrolled']
        
        # Calculate distances if lat/lon provided
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
        
        # Add score_normalized and explanation for random activities
        random_activities['score_normalized'] = 0.5  # Random normalized score
        random_activities['explanation'] = "This is a randomly selected activity for you to explore."
        
        return random_activities[['title', 'category', 'description', 'score', 'InterestScore',
                                  'language', 'distance', 'remaining', 'date',
                                  'start_time', 'end_time', 'price_num', 'source_type', 'lat', 'lon', 'score_normalized', 'explanation']]

    # Multi-rule filtering (Update: skip distance filter if no valid lat/lon)
    if skip_distance_filter:
        # Skip distance filtering
        df = language_filter(df, user_languages)
        df['is_wrong_time_slot'] = df['time_slot'].apply(lambda x: time_slot_penalty(x, user_time_slots))
        df['distance'] = 0.0  # Set distance to 0
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
    data_path = os.path.join(base_dir, '..', "data", "activities_with_vec.pkl")
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
    df['score_normalized'] = normalize_score(df['score'])

    df['remaining'] = df['capacity'] - df['enrolled']

    # Interest threshold filtering (lowered to allow more activities while still prioritizing distance)
    interest_threshold = 0.6
    relevant_activities = df[df['InterestScore'] >= interest_threshold]

    if len(relevant_activities) < 3:
        top_3 = pd.concat([relevant_activities, df[df['InterestScore'] < interest_threshold]]).head(3)
    else:
        top_3 = relevant_activities.head(3)
    
    # Remove duplicates based on title (keep the one with highest score)
    top_3 = top_3.drop_duplicates(subset=['title'], keep='first')
    
    # If we have less than 3 after deduplication, fill with more activities
    if len(top_3) < 3:
        remaining_activities = df[~df['title'].isin(top_3['title'])]
        additional_needed = 3 - len(top_3)
        if len(remaining_activities) > 0:
            additional = remaining_activities.head(additional_needed)
            top_3 = pd.concat([top_3, additional])

    # Add score_normalized and explanation to the final top_3 results
    top_3['explanation'] = top_3.apply(
        lambda r: explain_recommendation(r, user_interests, user_budget, user_need_free, user_provided_budget, user_provided_time_slots), axis=1
    )

    return top_3[['title', 'category', 'description', 'score', 'InterestScore',
                  'language', 'distance', 'date',
                  'start_time', 'end_time', 'price_num', 'source_type', 'lat', 'lon', 'score_normalized', 'explanation']]
