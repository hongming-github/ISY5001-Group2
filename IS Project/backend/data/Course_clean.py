import pandas as pd
import numpy as np
import re
import json

# === Configure input and output paths ===
course_path = "data_sgcourse.xlsx"      # course data
geo_path = "CommunityClubs.geojson"         # CC GeoJSON
output_path = "cleaned_courses.xlsx"  # output file

# === Read data ===
df = pd.read_excel(course_path)
with open(geo_path, "r", encoding="utf-8") as f:
    geo = json.load(f)

# === Construct CC name → coordinates mapping ===
import re

cc_name_to_coords = {}
for feat in geo.get("features", []):
    props = feat.get("properties", {}) or {}
    geom = feat.get("geometry", {}) or {}

    # Parse the actual CC name from Description
    desc = props.get("Description", "")
    name = None
    if desc:
        m = re.search(r"<th>NAME</th>\s*<td>(.*?)</td>", desc, re.I)
        if m:
            name = m.group(1).strip()

    # Get coordinates from geometry (GeoJSON standard is [lon, lat, z])
    coords = None
    if geom and geom.get("type") == "Point":
        try:
            lon, lat = geom.get("coordinates", [None, None])[:2]
            coords = (float(lat), float(lon))  # Store as (lat, lon) for convenience
        except Exception as e:
            pass

    if name and coords:
        cc_name_to_coords[name.lower()] = coords


# === Category mapping ===
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

# === Subcategory combination ===
def combine_subcategory(row):
    second = str(row.get("second_classification", "") or "").replace("&", "_").strip()
    third = str(row.get("third_classification", "") or "").replace("&", "_").strip()
    return f"{second} ({third})" if third else second

# === vacancy splitting ===
def split_vacancy(vacancy):
    m = re.search(r"(\d+)\s*/\s*(\d+)", str(vacancy))
    if m: return int(m.group(1)), int(m.group(2))
    return np.nan, np.nan

# === date_&_time splitting ===
time_pat = re.compile(r"(\d{1,2}:\d{2}\s*[AP]M)", re.I)
sess_pat = re.compile(r"(\d+)\s*sessions?", re.I)

def parse_date_time(val):
    if pd.isna(val): return pd.Series([np.nan]*5)
    parts = [p.strip() for p in str(val).split("|")]
    date = parts[1] if len(parts) > 1 else np.nan
    tail = " | ".join(parts[2:])
    ms = sess_pat.search(tail)
    sessions = int(ms.group(1)) if ms else np.nan
    times = time_pat.findall(tail)
    start_time, end_time = (times+[np.nan,np.nan])[:2]
    def slot(st):
        if not isinstance(st, str): return np.nan
        h = int(re.search(r"\d+", st).group())
        if "PM" in st.upper() and h != 12: h += 12
        if 6 <= h < 12: return "morning"
        if 12 <= h < 18: return "afternoon"
        if 18 <= h < 23: return "evening"
        return "other"
    return pd.Series([date, sessions, start_time, end_time, slot(start_time)])

# === price parsing ===
def parse_price(val):
    if pd.isna(val):
        return np.nan, 0
    s = str(val).strip()

    # Free
    if s.lower().startswith("free"):
        return 0.0, 1

    # Price range: From $230.00 to $240.00
    if "to" in s.lower():
        nums = re.findall(r"[\d\.]+", s)
        if len(nums) >= 2:
            try:
                low, high = float(nums[0]), float(nums[1])
                mid = (low + high) / 2
                return mid, int(mid == 0)
            except:
                return np.nan, 0

    # Single price
    s = s.replace("$","").replace(",","").replace("SGD","").strip()
    try:
        p = float(s)
        return p, int(p == 0)
    except:
        return np.nan, 0


# === Children course filtering ===
child_keywords = ["child","children","kid","kids","toddler","youth","teen","junior",
                  "nursery","preschool","kindergarten","primary","secondary",
                  "teenager","youth","children","kids","toddler","preschool","children","parent-child","primary-secondary students"]
age_pat = re.compile(r"(?:age|年龄).{0,5}?(\d{1,2})(?:\D+(\d{1,2}))?", re.I)
under_pat = re.compile(r"(under|below)\s*(\d{1,2})", re.I)

def is_child_course(row):
    blob = " ".join(str(row.get(c,"")) for c in ["title","course_description","requirements"]).lower()
    if any(kw in blob for kw in child_keywords): return True
    m = age_pat.search(blob)
    if m:
        ages = [int(x) for x in m.groups() if x]
        if ages and max(ages)<18: return True
    m2 = under_pat.search(blob)
    if m2 and int(m2.group(2))<=18: return True
    return False

# === Associate CC coordinates ===
def lookup_cc_coords(name):
    if pd.isna(name):
        return (np.nan, np.nan)
    s = str(name).lower().strip()
    return cc_name_to_coords.get(s, (np.nan, np.nan))

# === Start cleaning ===
dfc = df.copy()
dfc.rename(columns={"course_number":"id","classification":"category",
                    "course_description":"description"}, inplace=True)
dfc["category"] = dfc["category"].apply(map_category)
dfc["subcategory"] = dfc.apply(combine_subcategory, axis=1)
dfc[["enrolled","capacity"]] = dfc["current_vacancy"].apply(lambda x: pd.Series(split_vacancy(x)))
dfc = dfc[dfc["enrolled"]<dfc["capacity"]]  # Remove full courses
dfc[["date","sessions","start_time","end_time","time_slot"]] = dfc["date_&_time"].apply(parse_date_time)
dfc[["price_num","is_free"]] = dfc["price"].apply(lambda x: pd.Series(parse_price(x)))
latlon = dfc["organising_commitee"].apply(lookup_cc_coords)
dfc["lat"] = latlon.apply(lambda x:x[0]); dfc["lon"] = latlon.apply(lambda x:x[1])
dfc = dfc.dropna(subset=["lat", "lon"])
dfc["source_type"] = "course"
dfc = dfc[~dfc.apply(is_child_course, axis=1)]

# === Adjust field order: replace original position ===
new_cols = []
for c in df.columns:
    if c=="course_number": new_cols.append("id")
    elif c=="classification": new_cols.append("category")
    elif c=="second_classification" or c=="third_classification":
        if "subcategory" not in new_cols: new_cols.append("subcategory")
    elif c=="current_vacancy": new_cols.extend(["enrolled","capacity"])
    elif c=="date_&_time": new_cols.extend(["date","sessions","start_time","end_time","time_slot"])
    elif c=="course_description": new_cols.append("description")
    else: new_cols.append(c)
if "price" in new_cols:
    idx_price = new_cols.index("price")
    new_cols[idx_price:idx_price+1] = ["price_num","is_free"]  # Replace original price with new fields
idx_org = new_cols.index("organising_commitee")+1 if "organising_commitee" in new_cols else len(new_cols)
new_cols[idx_org:idx_org] = ["lat","lon"]
new_cols.append("source_type")

dfc[new_cols].to_excel(output_path, index=False)
print("Cleaning completed:", output_path)
