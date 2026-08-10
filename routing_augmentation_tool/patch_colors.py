import re

with open('app.py', 'r') as f:
    content = f.read()

old_block = """                # Identify changed routes
                changed_route_indices = []
                for i in range(len(initial_routes)):
                    if initial_routes[i] != selected_new_routes[i]:
                        changed_route_indices.append(i)
                        
                # Add Markers ONLY for nodes in these routes, plus depot
                nodes_to_draw = {0}
                for idx in changed_route_indices:
                    nodes_to_draw.update(initial_routes[idx])
                    nodes_to_draw.update(selected_new_routes[idx])
                    
                for idx, (lat, lng) in enumerate(locations):
                    if idx in nodes_to_draw:
                        if idx == 0:
                            folium.Marker([lat, lng], popup="Depot", icon=folium.Icon(color="black", icon="star")).add_to(m)
                        else:
                            demand = demands[idx]
                            orig_route = node_to_route_idx.get(idx, 0)
                            marker_color = colors[orig_route % len(colors)]
                            folium.Marker([lat, lng], popup=f"{node_names[idx]} (Pallets: {demand})", icon=folium.Icon(color=marker_color, icon="info-sign")).add_to(m)

                # Draw ONLY the affected routes
                for idx in changed_route_indices:
                    # Solid original
                    r_orig = initial_routes[idx]
                    if r_orig:
                        route_coords_orig = [locations[0]] + [locations[n] for n in r_orig] + [locations[0]]
                        folium.PolyLine(route_coords_orig, color=colors[idx % len(colors)], weight=6, opacity=0.3, popup=f"Original {truck_names[idx]}").add_to(m)
                    
                    # Dotted new
                    r_new = selected_new_routes[idx]
                    if r_new:
                        route_coords_new = [locations[0]] + [locations[n] for n in r_new] + [locations[0]]
                        folium.PolyLine(route_coords_new, color=colors[idx % len(colors)], weight=5, opacity=1.0, dash_array='5, 10', popup=f"Improved {truck_names[idx]}").add_to(m)"""

new_block = """                # Identify changed routes
                changed_route_indices = []
                for i in range(len(initial_routes)):
                    if initial_routes[i] != selected_new_routes[i]:
                        changed_route_indices.append(i)
                        
                # Assign collision-free colors for the involved routes
                local_colors = {}
                used_colors = set()
                for idx in changed_route_indices:
                    desired_color = colors[idx % len(colors)]
                    if desired_color in used_colors:
                        for fallback in colors:
                            if fallback not in used_colors:
                                desired_color = fallback
                                break
                    used_colors.add(desired_color)
                    local_colors[idx] = desired_color
                        
                # Add Markers ONLY for nodes in these routes, plus depot
                nodes_to_draw = {0}
                for idx in changed_route_indices:
                    nodes_to_draw.update(initial_routes[idx])
                    nodes_to_draw.update(selected_new_routes[idx])
                    
                for idx, (lat, lng) in enumerate(locations):
                    if idx in nodes_to_draw:
                        if idx == 0:
                            folium.Marker([lat, lng], popup="Depot", icon=folium.Icon(color="black", icon="star")).add_to(m)
                        else:
                            demand = demands[idx]
                            orig_route = node_to_route_idx.get(idx, 0)
                            marker_color = local_colors.get(orig_route, colors[orig_route % len(colors)])
                            folium.Marker([lat, lng], popup=f"{node_names[idx]} (Pallets: {demand})", icon=folium.Icon(color=marker_color, icon="info-sign")).add_to(m)

                # Draw ONLY the affected routes
                for idx in changed_route_indices:
                    r_color = local_colors[idx]
                    
                    # Solid original
                    r_orig = initial_routes[idx]
                    if r_orig:
                        route_coords_orig = [locations[0]] + [locations[n] for n in r_orig] + [locations[0]]
                        folium.PolyLine(route_coords_orig, color=r_color, weight=6, opacity=0.3, popup=f"Original {truck_names[idx]}").add_to(m)
                    
                    # Dotted new
                    r_new = selected_new_routes[idx]
                    if r_new:
                        route_coords_new = [locations[0]] + [locations[n] for n in r_new] + [locations[0]]
                        folium.PolyLine(route_coords_new, color=r_color, weight=5, opacity=1.0, dash_array='5, 10', popup=f"Improved {truck_names[idx]}").add_to(m)"""

content = content.replace(old_block, new_block)

with open('app.py', 'w') as f:
    f.write(content)

