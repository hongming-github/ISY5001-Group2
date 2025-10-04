import pandas as pd
import numpy as np
import re
import json
import difflib

# === 输入输出路径 ===
ig_path = "data_interestgroup.xlsx"
geo_path = "CommunityClubs.geojson"
output_path = "cleaned_interestgroups.xlsx"

# === 读取数据 ===
df = pd.read_excel(ig_path)
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

def normalize_cc_name(name: str) -> str:
    s = str(name).lower().strip()
    s = s.replace("community club", "").replace("cc", "").strip()
    return s

def lookup_cc_coords(name):
    if pd.isna(name):
        return (np.nan, np.nan)
    raw = str(name).lower().strip()
    if raw in cc_name_to_coords:
        return cc_name_to_coords[raw]
    norm = normalize_cc_name(raw)
    for key in cc_name_to_coords:
        if normalize_cc_name(key) == norm:
            return cc_name_to_coords[key]
    raw_tokens = norm.split()
    for key in cc_name_to_coords:
        key_tokens = normalize_cc_name(key).split()
        if raw_tokens and key_tokens and raw_tokens[0] == key_tokens[0]:
            return cc_name_to_coords[key]
    close = difflib.get_close_matches(norm, [normalize_cc_name(k) for k in cc_name_to_coords], n=1, cutoff=0.8)
    if close:
        for key in cc_name_to_coords:
            if normalize_cc_name(key) == close[0]:
                return cc_name_to_coords[key]
    return (np.nan, np.nan)

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

# === 子类合并（如果有） ===
def combine_subcategory(row):
    second = str(row.get("second_classification", "") or "").replace("&", "_").strip()
    third = str(row.get("third_classification", "") or "").replace("&", "_").strip()
    return f"{second} ({third})" if third else second

# === 开始清洗 ===
dfi = df.copy()
dfi.rename(columns={
    "ig_number": "id",
    "group_description": "description",
    "classification": "category"
}, inplace=True)

# id 原样保留
dfi["id"] = dfi["id"].astype(str).str.strip()
dfi["category"] = dfi["category"].apply(map_category)

if "second_classification" in dfi.columns or "third_classification" in dfi.columns:
    dfi["subcategory"] = dfi.apply(combine_subcategory, axis=1)
else:
    dfi["subcategory"] = ""

# vacancy = 无限
dfi["enrolled"] = 0
dfi["capacity"] = -1

# price 字段替换为数值化字段
dfi["price_num"] = np.nan
dfi["is_free"] = 1   # IG 默认免费

# 经纬度匹配
latlon = dfi["organising_commitee"].apply(lookup_cc_coords)
dfi["lat"] = latlon.apply(lambda x:x[0])
dfi["lon"] = latlon.apply(lambda x:x[1])
dfi = dfi.dropna(subset=["lat","lon"])

dfi["language"] = "English"
dfi["source_type"] = "interest_group"

# === 调整字段顺序 ===
new_cols = []
for c in df.columns:
    if c == "ig_number": new_cols.append("id")
    elif c == "classification": new_cols.append("category")
    elif c in ["second_classification", "third_classification"]:
        if "subcategory" not in new_cols: new_cols.append("subcategory")
    elif c == "current_vacancy":
        new_cols.extend(["enrolled","capacity"])  # 替换 vacancy
    elif c == "price":
        new_cols.extend(["price_num","is_free"])  # 替换 price
    elif c == "group_description": new_cols.append("description")
    else:
        new_cols.append(c)

# 插入 lat/lon
idx_org = new_cols.index("organising_commitee")+1 if "organising_commitee" in new_cols else len(new_cols)
new_cols[idx_org:idx_org] = ["lat","lon"]

# 插入额外字段
new_cols.append("language")
new_cols.append("source_type")

# === 输出 ===
dfi[new_cols].to_excel(output_path, index=False)
print("清洗完成:", output_path)
