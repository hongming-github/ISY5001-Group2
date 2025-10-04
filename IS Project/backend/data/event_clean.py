import pandas as pd
import numpy as np
import re
import json

# === 配置输入输出路径 ===
event_path = "data_sgevent.xlsx"      # event 数据
geo_path = "CommunityClubs.geojson"   # CC GeoJSON
output_path = "cleaned_events.xlsx"   # 输出文件

# === 读取数据 ===
df = pd.read_excel(event_path)
with open(geo_path, "r", encoding="utf-8") as f:
    geo = json.load(f)

# === 构造 CC 名称→经纬度映射 ===
cc_name_to_coords = {}
for feat in geo.get("features", []):
    props = feat.get("properties", {}) or {}
    geom = feat.get("geometry", {}) or {}
    desc = props.get("Description", "")
    name = None
    if desc:
        m = re.search(r"<th>NAME</th>\s*<td>(.*?)</td>", desc, re.I)
        if m:
            name = m.group(1).strip()
    coords = None
    if geom and geom.get("type") == "Point":
        try:
            lon, lat = geom.get("coordinates", [None, None])[:2]
            coords = (float(lat), float(lon))
        except Exception:
            pass
    if name and coords:
        cc_name_to_coords[name.lower()] = coords

# === 分类映射 ===
base_mapping = {
    "Health & Wellness": "Health_Fitness",
    "Sports & Fitness": "Health_Fitness",
    "Health & Fitness": "Health_Fitness",
    "Lifelong Learning": "Learning_PersonalGrowth",
    "Parenting & Education": "Learning_PersonalGrowth",
    "Lifestyle & Leisure": "Leisure_Culture",
    "Arts & Culture": "Leisure_Culture",
    "Celebrations & Festivities": "Community_Social",
    "Neighbourhood Parties": "Community_Social",
    "Outings & Tours": "Community_Social",
    "Charity & Volunteerism": "Community_Social",
}
def map_category(raw):
    if pd.isna(raw): return None
    raw_str = str(raw).strip()
    return base_mapping.get(raw_str, raw_str.replace("&", "_"))

# === vacancy 拆分 ===
def split_vacancy(vacancy):
    m = re.search(r"(\d+)\s*/\s*(\d+)", str(vacancy))
    if m: return int(m.group(1)), int(m.group(2))
    return np.nan, np.nan

# === datetime 拆分 ===
time_pat = re.compile(r"(\d{1,2}:\d{2}\s*[AP]M)", re.I)
def parse_event_datetime(val):
    if pd.isna(val): return pd.Series([np.nan]*5)
    s = str(val).strip()
    if "-" not in s: return pd.Series([np.nan]*5)
    parts = [p.strip() for p in s.split("-", 1)]
    date_tokens = parts[0].split()
    if len(date_tokens) >= 4:
        date_part = " ".join(date_tokens[:3])
    else:
        date_part = parts[0]
    time_part = " ".join(date_tokens[3:]) + " - " + parts[1]
    times = time_pat.findall(time_part)
    start_time, end_time = (times+[np.nan,np.nan])[:2]
    def slot(st):
        if not isinstance(st, str): return np.nan
        h = int(re.search(r"\d+", st).group())
        if "PM" in st.upper() and h != 12: h += 12
        if 6 <= h < 12: return "morning"
        if 12 <= h < 18: return "afternoon"
        if 18 <= h < 23: return "evening"
        return "other"
    return pd.Series([date_part, 1, start_time, end_time, slot(start_time)])

# === price 解析 ===
def parse_price(val):
    if pd.isna(val): return np.nan, 0
    s = str(val).strip()
    if s.lower().startswith("free"):
        return 0.0, 1
    if "to" in s.lower():
        nums = re.findall(r"[\d\.]+", s)
        if len(nums) >= 2:
            try:
                low, high = float(nums[0]), float(nums[1])
                mid = (low + high) / 2
                return mid, int(mid == 0)
            except:
                return np.nan, 0
    s = s.replace("$","").replace(",","").replace("SGD","").strip()
    try:
        p = float(s)
        return p, int(p == 0)
    except:
        return np.nan, 0

import difflib

def normalize_cc_name(name: str) -> str:
    """统一化 CC 名称：小写 + 去掉 cc/community club"""
    s = str(name).lower().strip()
    s = s.replace("community club", "").replace("cc", "").strip()
    return s

def lookup_cc_coords(name):
    if pd.isna(name):
        return (np.nan, np.nan)
    raw = str(name).lower().strip()

    # 1. 精确匹配
    if raw in cc_name_to_coords:
        return cc_name_to_coords[raw]

    # 2. 规范化匹配
    norm = normalize_cc_name(raw)
    for key in cc_name_to_coords:
        if normalize_cc_name(key) == norm:
            return cc_name_to_coords[key]

    # 3. 前半段单词匹配
    raw_tokens = norm.split()
    for key in cc_name_to_coords:
        key_tokens = normalize_cc_name(key).split()
        if raw_tokens and key_tokens and raw_tokens[0] == key_tokens[0]:
            return cc_name_to_coords[key]

    # 4. 字符串相似度匹配
    close = difflib.get_close_matches(norm, [normalize_cc_name(k) for k in cc_name_to_coords], n=1, cutoff=0.8)
    if close:
        for key in cc_name_to_coords:
            if normalize_cc_name(key) == close[0]:
                return cc_name_to_coords[key]

    # 5. 找不到 → NaN
    return (np.nan, np.nan)

# === 开始清洗 ===
dfe = df.copy()
dfe.rename(columns={
    "event_number":"id",
    "event_description":"description",
    "classification":"category"
}, inplace=True)

dfe["id"] = dfe["id"].apply(lambda x: f"E{int(x)}")
dfe["category"] = dfe["category"].apply(map_category)
dfe["subcategory"] = ""

dfe[["enrolled","capacity"]] = dfe["current_vacancy"].apply(lambda x: pd.Series(split_vacancy(x)))
dfe[["date","sessions","start_time","end_time","time_slot"]] = dfe["date_&_time"].apply(parse_event_datetime)
dfe[["price_num","is_free"]] = dfe["price"].apply(lambda x: pd.Series(parse_price(x)))

latlon = dfe["organising_commitee"].apply(lookup_cc_coords)
dfe["lat"] = latlon.apply(lambda x:x[0]); dfe["lon"] = latlon.apply(lambda x:x[1])
dfe = dfe.dropna(subset=["lat","lon"])

dfe["language"] = "English"
dfe["source_type"] = "event"

# === 调整字段顺序 ===
new_cols = []
for c in df.columns:
    if c=="event_number": new_cols.append("id")
    elif c=="classification": new_cols.append("category")
    elif c=="current_vacancy": new_cols.extend(["enrolled","capacity"])
    elif c=="date_&_time": new_cols.extend(["date","sessions","start_time","end_time","time_slot"])
    elif c=="event_description": new_cols.append("description")
    elif c=="price": new_cols.extend(["price_num","is_free"])
    else: new_cols.append(c)

# 插入额外字段
if "subcategory" not in new_cols:
    new_cols.insert(new_cols.index("category")+1, "subcategory")
idx_org = new_cols.index("organising_commitee")+1 if "organising_commitee" in new_cols else len(new_cols)
new_cols[idx_org:idx_org] = ["lat","lon"]
new_cols.append("language")
new_cols.append("source_type")

# === 输出 ===
dfe[new_cols].to_excel(output_path, index=False)
print("清洗完成:", output_path)
