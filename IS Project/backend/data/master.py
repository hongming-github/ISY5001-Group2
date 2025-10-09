import pandas as pd

# === Input three cleaned tables ===
course_path = "cleaned_courses.xlsx"
event_path = "cleaned_events.xlsx"
ig_path = "cleaned_interestgroups.xlsx"
output_path = "activities.xlsx"

# Read data
df_course = pd.read_excel(course_path)
df_event = pd.read_excel(event_path)
df_ig = pd.read_excel(ig_path)

# Use course field order as standard
course_cols = df_course.columns.tolist()

# Find all columns from three tables (union set)
all_cols = list(set(df_course.columns) | set(df_event.columns) | set(df_ig.columns))

# Follow course column order + place other missing columns at the end
final_cols = course_cols + [c for c in all_cols if c not in course_cols]

# Fill missing fields
df_course = df_course.reindex(columns=final_cols)
df_event = df_event.reindex(columns=final_cols)
df_ig = df_ig.reindex(columns=final_cols)

# Merge
df_all = pd.concat([df_course, df_event, df_ig], ignore_index=True)

# Fill missing values: subcategory, description left empty, others filled with NA
fill_cols = [c for c in final_cols if c not in ["subcategory", "description"]]
df_all[fill_cols] = df_all[fill_cols].fillna("NA")

# Remove duplicates (by id)
before_count = len(df_all)
df_all = df_all.drop_duplicates(subset=["id"], keep="first")
after_count = len(df_all)

print(f"Before deduplication: {before_count}, After deduplication: {after_count}, Removed {before_count - after_count} duplicate records")

# Output to original file path
df_all.to_excel(output_path, index=False)
print("Merge and deduplication completed:", output_path)
