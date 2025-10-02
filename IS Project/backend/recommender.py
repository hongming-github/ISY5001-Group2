# recommender.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
import math
from recommendation_model import main as rec_main

try:
    import joblib  # optional if you have a trained model
except Exception:
    joblib = None

# Define your own data structure
@dataclass
class VitalInput:
    device_id: str
    systolic: int
    diastolic: int
    heart_rate: int
    blood_glucose: int
    blood_oxygen: int
    timestamp: str  # ISO string


# class ElderlyActivityRecommender:
#     """
#     Replace the stub logic with your actual model.
#     You can load artifacts in __init__ (e.g., joblib.load('model.pkl')).
#     """
#     def __init__(self, model_path: Optional[str] = None):
#         self.model = None
#         if model_path and joblib:
#             try:
#                 self.model = joblib.load(model_path)
#             except Exception:
#                 self.model = None  # fall back to rules

#     def recommend(self, profile: Dict, vitals: VitalInput, k: int = 3) -> List[Dict]:
#         """
#         Returns a ranked list of recommended activities.
#         Profile can include age, mobility_level, interests, etc.
#         """
class ElderlyActivityRecommender:
    def __init__(self, model_path: Optional[str] = None):
        self.model = None  

    def recommend(self, profile: Dict, vitals: Optional[VitalInput] = None) -> List[Dict]:
        """
        - profile: Dict - interests, languages, time_slots, budget, need_free, lat, lon, sourcetypes
        - vitals: none

        return: List[Dict] - recommendation_model Top-5
        """
        df = rec_main(
            profile.get("interests", []),
            profile.get("languages", []),
            profile.get("time_slots", []),
            profile.get("budget", 999),
            profile.get("need_free", False),
            profile.get("lat", 0.0),
            profile.get("lon", 0.0),
            profile.get("sourcetypes", None),
        )
        if df is None or len(df) == 0:
            return []

        def _safe_float(x, default=0.0):
            try:
                f = float(x)
                return f if math.isfinite(f) else default
            except Exception:
                return default

        def _safe_int(x, default=0):
            try:
                return int(x)
            except Exception:
                return default

        results: List[Dict] = []
        for _, row in df.iterrows(): 
            results.append({
                "activity": row.get("title", "") or "",
                # "intensity": self._map_intensity(row),
                "description": row.get("description", "") or "",
                "score": _safe_float(row.get("score", 0)),
                "distance": _safe_float(row.get("distance", -1)),
                "price": _safe_float(row.get("price_num", 0)),
                "date": row.get("date", "") or "",
                "start_time": row.get("start_time", "") or "",
                "end_time": row.get("end_time", "") or "",
                "language": row.get("language", "") or "",
                "source_type": row.get("source_type", "") or "",
            })
        return results

    def _map_intensity(self, row) -> str:
        interest = row.get("InterestScore", 0) or 0
        if interest > 0.7:
            return "high"
        elif interest > 0.5:
            return "medium"
        else:
            return "low"