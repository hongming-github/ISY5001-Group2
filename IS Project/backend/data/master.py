import pandas as pd

# === 输入三个清洗好的表 ===
course_path = "cleaned_courses.xlsx"
event_path = "cleaned_events.xlsx"
ig_path = "cleaned_interestgroups.xlsx"
output_path = "activities.xlsx"

# 读取
df_course = pd.read_excel(course_path)
df_event = pd.read_excel(event_path)
df_ig = pd.read_excel(ig_path)

# 以 course 的字段顺序为标准
course_cols = df_course.columns.tolist()

# 找到三个表的所有列（全集）
all_cols = list(set(df_course.columns) | set(df_event.columns) | set(df_ig.columns))

# 按照 course 的列顺序 + 其他缺失列放在最后
final_cols = course_cols + [c for c in all_cols if c not in course_cols]

# 补齐缺失字段
df_course = df_course.reindex(columns=final_cols)
df_event = df_event.reindex(columns=final_cols)
df_ig = df_ig.reindex(columns=final_cols)

# 合并
df_all = pd.concat([df_course, df_event, df_ig], ignore_index=True)

# 填充缺失值：subcategory、description 不填，其他填 NA
fill_cols = [c for c in final_cols if c not in ["subcategory", "description"]]
df_all[fill_cols] = df_all[fill_cols].fillna("NA")

# 去重（按 id）
before_count = len(df_all)
df_all = df_all.drop_duplicates(subset=["id"], keep="first")
after_count = len(df_all)

print(f"去重前数量: {before_count}, 去重后数量: {after_count}, 去掉了 {before_count - after_count} 条重复记录")

# 输出到原文件路径
df_all.to_excel(output_path, index=False)
print("合并并去重完成:", output_path)
