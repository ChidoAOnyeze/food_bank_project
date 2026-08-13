import re

with open("app_valhalla_road_path.py", "r") as f:
    content = f.read()

# 1. Add threading import at top
if "import threading" not in content:
    content = "import threading\nimport time\n" + content

# 2. Add start_background_geometry_prefetch function definition right after get_full_route_geometry
prefetch_def = """
def start_background_geometry_prefetch(top_moves, locations, limit=30):
    \"\"\"
    Fires off a silent background daemon thread that politely downloads and caches
    all street shapes for the top 30 candidate moves while the user is using the app.
    \"\"\"
    def worker():
        total_to_fetch = min(limit, len(top_moves))
        print(f"--> [Background Prefetch] Starting geometry downloads for top {total_to_fetch} moves...")
        for m_idx, move in enumerate(top_moves[:limit]):
            try:
                candidate_routes = move[3]
                prefetch_and_cache_routes_geometry(candidate_routes, locations)
                time.sleep(0.4) # Respectful delay between batches
            except Exception as e:
                print(f"--> [Background Prefetch] Exception on move {m_idx}: {e}")
        print("--> [Background Prefetch] Completed! All top candidate moves are fully cached.")

    t = threading.Thread(target=worker, daemon=True)
    t.start()
"""

content = content.replace("def solve_routing(", prefetch_def.strip() + "\n\ndef solve_routing(")

# 3. Call start_background_geometry_prefetch when optimization completes and renders
old_unpack = """        if not needs_optimization:
            init_cost, top_moves, final_cost, improved_routes = st.session_state['optimization_results']"""

new_unpack = """        if not needs_optimization:
            init_cost, top_moves, final_cost, improved_routes = st.session_state['optimization_results']
            # Launch background worker for top 30 moves once per run
            if 'background_prefetch_params' not in st.session_state or st.session_state['background_prefetch_params'] != current_params:
                st.session_state['background_prefetch_params'] = current_params
                start_background_geometry_prefetch(top_moves, locations, limit=30)"""

content = content.replace(old_unpack, new_unpack)

with open("app_valhalla_road_path.py", "w") as f:
    f.write(content)

print("Injected background geometry prefetching into app_valhalla_road_path.py!")
