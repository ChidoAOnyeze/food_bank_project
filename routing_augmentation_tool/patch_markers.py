import re

with open('app.py', 'r') as f:
    content = f.read()

# We need to compute node_to_route_idx before we draw markers
calc_node_to_route = """            colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred',
                      'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue',
                      'darkpurple', 'pink', 'lightblue', 'lightgreen',
                      'gray', 'black', 'lightgray']

            # Map each node to its original route for marker coloring
            node_to_route_idx = {}
            for route_idx, route in enumerate(initial_routes):
                for n in route:
                    node_to_route_idx[n] = route_idx"""

content = content.replace("            colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred',\n                      'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue',\n                      'darkpurple', 'pink', 'lightblue', 'lightgreen',\n                      'gray', 'black', 'lightgray']", calc_node_to_route)


# Replace marker drawing in Full map
old_full_markers = """                # Add All Markers
                for idx, (lat, lng) in enumerate(locations):
                    if idx == 0:
                        folium.Marker([lat, lng], popup="Depot", icon=folium.Icon(color="black", icon="star")).add_to(m)
                    else:
                        demand = demands[idx]
                        folium.Marker([lat, lng], popup=f"{node_names[idx]} (Pallets: {demand})", icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)"""

new_full_markers = """                # Add All Markers
                for idx, (lat, lng) in enumerate(locations):
                    if idx == 0:
                        folium.Marker([lat, lng], popup="Depot", icon=folium.Icon(color="black", icon="star")).add_to(m)
                    else:
                        demand = demands[idx]
                        orig_route = node_to_route_idx.get(idx, 0)
                        marker_color = colors[orig_route % len(colors)]
                        folium.Marker([lat, lng], popup=f"{node_names[idx]} (Pallets: {demand})", icon=folium.Icon(color=marker_color, icon="info-sign")).add_to(m)"""

content = content.replace(old_full_markers, new_full_markers)

# Replace marker drawing in Local map
old_local_markers = """                for idx, (lat, lng) in enumerate(locations):
                    if idx in nodes_to_draw:
                        if idx == 0:
                            folium.Marker([lat, lng], popup="Depot", icon=folium.Icon(color="black", icon="star")).add_to(m)
                        else:
                            demand = demands[idx]
                            folium.Marker([lat, lng], popup=f"{node_names[idx]} (Pallets: {demand})", icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)"""

new_local_markers = """                for idx, (lat, lng) in enumerate(locations):
                    if idx in nodes_to_draw:
                        if idx == 0:
                            folium.Marker([lat, lng], popup="Depot", icon=folium.Icon(color="black", icon="star")).add_to(m)
                        else:
                            demand = demands[idx]
                            orig_route = node_to_route_idx.get(idx, 0)
                            marker_color = colors[orig_route % len(colors)]
                            folium.Marker([lat, lng], popup=f"{node_names[idx]} (Pallets: {demand})", icon=folium.Icon(color=marker_color, icon="info-sign")).add_to(m)"""

content = content.replace(old_local_markers, new_local_markers)


with open('app.py', 'w') as f:
    f.write(content)
