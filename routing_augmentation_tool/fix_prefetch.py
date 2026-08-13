import re
with open("app_valhalla_road_path.py", "r") as f:
    content = f.read()

replacement = """            if selected_option == "Show Full OR-Tools Optimization":
                show_proposed = st.toggle("Overlay Proposed Changes (Dotted Line)", value=True)
                # Prefetch all missing legs across both initial and improved routes in one super-batch call
                prefetch_and_cache_routes_geometry(initial_routes + improved_routes, locations)"""

content = re.sub(
    r"""            if selected_option == "Show Full OR-Tools Optimization":\n                # Prefetch all missing legs across all routes in one single super-batch API call\n                prefetch_and_cache_routes_geometry\(initial_routes \+ \(improved_routes if show_proposed else \[\]\), locations\)\n                show_proposed = st\.toggle\("Overlay Proposed Changes \(Dotted Line\)", value=True\)""",
    replacement, content
)

with open("app_valhalla_road_path.py", "w") as f:
    f.write(content)
