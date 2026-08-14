import re

# 1. Update app_valhalla_road_path.py
with open("app_valhalla_road_path.py", "r") as f:
    content = f.read()

# Fix background prefetch worker NoneType
old_prefetch = """def start_background_geometry_prefetch(top_moves, locations, limit=30):
    \"\"\"
    Fires off a silent background daemon thread that politely downloads and caches
    all street shapes for the top 30 candidate moves while the user is using the app.
    \"\"\"
    def worker():
        total_to_fetch = min(limit, len(top_moves))"""

new_prefetch = """def start_background_geometry_prefetch(top_moves, locations, limit=30):
    \"\"\"
    Fires off a silent background daemon thread that politely downloads and caches
    all street shapes for the top 30 candidate moves while the user is using the app.
    \"\"\"
    if not top_moves or not locations:
        return
        
    def worker():
        if not top_moves:
            return
        total_to_fetch = min(limit, len(top_moves))"""

content = content.replace(old_prefetch, new_prefetch)

# Update colors and highlight_colors to prioritize Red and Blue
content = content.replace(
    "highlight_colors = ['#2563eb', '#16a34a', '#dc2626', '#9333ea', '#ea580c', '#0891b2']",
    "highlight_colors = ['#dc2626', '#2563eb', '#9333ea', '#ea580c', '#16a34a', '#0891b2']"
)
content = content.replace(
    "colors = ['#2563eb', '#16a34a', '#dc2626', '#9333ea', '#ea580c', '#0891b2',",
    "colors = ['#dc2626', '#2563eb', '#9333ea', '#ea580c', '#16a34a', '#0891b2',"
)

with open("app_valhalla_road_path.py", "w") as f:
    f.write(content)
print("Updated app_valhalla_road_path.py")

# 2. Update app_valhalla.py
with open("app_valhalla.py", "r") as f:
    content_v = f.read()

content_v = content_v.replace(
    "highlight_colors = ['#2563eb', '#16a34a', '#dc2626', '#9333ea', '#ea580c', '#0891b2']",
    "highlight_colors = ['#dc2626', '#2563eb', '#9333ea', '#ea580c', '#16a34a', '#0891b2']"
)
content_v = content_v.replace(
    "colors = ['#2563eb', '#16a34a', '#dc2626', '#9333ea', '#ea580c', '#0891b2',",
    "colors = ['#dc2626', '#2563eb', '#9333ea', '#ea580c', '#16a34a', '#0891b2',"
)

with open("app_valhalla.py", "w") as f:
    f.write(content_v)
print("Updated app_valhalla.py")

