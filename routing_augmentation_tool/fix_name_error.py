import re

with open("app_valhalla_road_path.py", "r") as f:
    content = f.read()

# Remove the premature prefetch call
old_code = """            else:
                # User selected a specific local move
                # Prefetch affected routes geometry in one batched call
                prefetch_and_cache_routes_geometry([initial_routes[i] for i in changed_route_indices] + [selected_new_routes[i] for i in changed_route_indices], locations)
                move_idx = int(selected_option.split(" ")[1]) - 1"""

new_code = """            else:
                # User selected a specific local move
                move_idx = int(selected_option.split(" ")[1]) - 1"""

content = content.replace(old_code, new_code)

# Add prefetch after changed_route_indices is defined
old_indices = """                # Identify changed routes
                changed_route_indices = []
                for i in range(len(initial_routes)):
                    if initial_routes[i] != selected_new_routes[i]:
                        changed_route_indices.append(i)"""

new_indices = """                # Identify changed routes
                changed_route_indices = []
                for i in range(len(initial_routes)):
                    if initial_routes[i] != selected_new_routes[i]:
                        changed_route_indices.append(i)
                        
                # Prefetch affected routes geometry in one batched call
                prefetch_and_cache_routes_geometry([initial_routes[i] for i in changed_route_indices] + [selected_new_routes[i] for i in changed_route_indices], locations)"""

content = content.replace(old_indices, new_indices)

with open("app_valhalla_road_path.py", "w") as f:
    f.write(content)

print("Fixed NameError in app_valhalla_road_path.py!")
