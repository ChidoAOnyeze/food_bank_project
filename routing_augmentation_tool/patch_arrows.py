import re

with open('app.py', 'r') as f:
    content = f.read()

old_block = """                    # Solid original
                    r_orig = initial_routes[idx]
                    if r_orig:
                        route_coords_orig = [locations[0]] + [locations[n] for n in r_orig] + [locations[0]]
                        folium.PolyLine(route_coords_orig, color=r_color, weight=6, opacity=0.3, popup=f"Original {truck_names[idx]}").add_to(m)
                    
                    # Dotted new
                    r_new = selected_new_routes[idx]
                    if r_new:
                        route_coords_new = [locations[0]] + [locations[n] for n in r_new] + [locations[0]]
                        folium.PolyLine(route_coords_new, color=r_color, weight=5, opacity=1.0, dash_array='5, 10', popup=f"Improved {truck_names[idx]}").add_to(m)"""

new_block = """                    # Solid original
                    r_orig = initial_routes[idx]
                    if r_orig:
                        route_coords_orig = [locations[0]] + [locations[n] for n in r_orig] + [locations[0]]
                        pl_orig = folium.PolyLine(route_coords_orig, color=r_color, weight=6, opacity=0.3, popup=f"Original {truck_names[idx]}")
                        pl_orig.add_to(m)
                        PolyLineTextPath(pl_orig, '►', repeat=True, offset=7, attributes={'fill': r_color, 'font-weight': 'bold', 'font-size': '18'}).add_to(m)
                    
                    # Dotted new
                    r_new = selected_new_routes[idx]
                    if r_new:
                        route_coords_new = [locations[0]] + [locations[n] for n in r_new] + [locations[0]]
                        pl_new = folium.PolyLine(route_coords_new, color=r_color, weight=5, opacity=1.0, dash_array='5, 10', popup=f"Improved {truck_names[idx]}")
                        pl_new.add_to(m)
                        PolyLineTextPath(pl_new, '►', repeat=True, offset=7, attributes={'fill': r_color, 'font-weight': 'bold', 'font-size': '18'}).add_to(m)"""

content = content.replace(old_block, new_block)

with open('app.py', 'w') as f:
    f.write(content)

