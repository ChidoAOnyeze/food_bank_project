import re

with open("app_valhalla_road_path.py", "r") as f:
    content = f.read()

geom_logic = """
VALHALLA_GEOM_CACHE_FILE = "valhalla_geom_cache.json"

def decode_polyline(encoded, precision=6):
    inv = 1.0 / (10 ** precision)
    decoded = []
    lat = 0
    lng = 0
    index = 0
    length = len(encoded)
    while index < length:
        shift = 0; result = 0
        while True:
            byte = ord(encoded[index]) - 63; index += 1
            result |= (byte & 0x1f) << shift; shift += 5
            if byte < 0x20: break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat
        
        shift = 0; result = 0
        while True:
            byte = ord(encoded[index]) - 63; index += 1
            result |= (byte & 0x1f) << shift; shift += 5
            if byte < 0x20: break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng
        decoded.append((lat * inv, lng * inv))
    return decoded

def get_road_path(p1, p2):
    if os.path.exists(VALHALLA_GEOM_CACHE_FILE):
        try:
            with open(VALHALLA_GEOM_CACHE_FILE, "r") as f:
                geom_cache = json.load(f)
        except Exception:
            geom_cache = {}
    else:
        geom_cache = {}

    k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
    if k in geom_cache:
        return geom_cache[k]
    
    payload = {
        "locations": [{"lat": p1[0], "lon": p1[1]}, {"lat": p2[0], "lon": p2[1]}],
        "costing": "truck",
        "units": "kilometers"
    }
    try:
        resp = requests.post("https://valhalla1.openstreetmap.de/route", json=payload, timeout=10)
        if resp.status_code == 200:
            legs = resp.json().get("trip", {}).get("legs", [])
            if legs and "shape" in legs[0]:
                pts = decode_polyline(legs[0]["shape"])
                geom_cache[k] = pts
                try:
                    with open(VALHALLA_GEOM_CACHE_FILE, "w") as f:
                        json.dump(geom_cache, f)
                except Exception:
                    pass
                return pts
    except Exception as e:
        print("Valhalla route geom fetch failed:", e)
        
    return [p1, p2]

def get_full_route_geometry(locations_list):
    full_path = []
    for i in range(len(locations_list) - 1):
        p1 = locations_list[i]
        p2 = locations_list[i+1]
        leg_pts = get_road_path(p1, p2)
        if full_path:
            full_path.extend(leg_pts[1:])
        else:
            full_path.extend(leg_pts)
    return full_path
"""

# Insert geom_logic right above `def solve_routing(`
content = content.replace("def solve_routing(", geom_logic + "\ndef solve_routing(")

# Replace the PolyLine plotting in the Global View
old_plot_global = """                # Plot All Original Routes (Always drawn, Solid)
                for route_idx, route in enumerate(initial_routes):
                    if not route:
                        continue
                    route_coords = [locations[0]] + [locations[n] for n in route] + [locations[0]]
                    color = colors[route_idx % len(colors)]
                    folium.PolyLine(
                        route_coords,
                        color=color,
                        weight=5,
                        opacity=0.8,
                        tooltip=f"Original Route {route_idx} ({truck_names[route_idx]})", popup=f"Original Route {route_idx} ({truck_names[route_idx]})"
                    ).add_to(m)

                # Plot All Improved Routes (if toggled, Dotted)
                if show_proposed:
                    for route_idx, route in enumerate(improved_routes):
                        if not route:
                            continue
                        route_coords = [locations[0]] + [locations[n] for n in route] + [locations[0]]
                        color = colors[route_idx % len(colors)]
                        folium.PolyLine(
                            route_coords,
                            color=color,
                            weight=4,
                            opacity=0.9,
                            dash_array='5, 10', # Dotted line
                            tooltip=f"Improved Route {route_idx} ({truck_names[route_idx]})", popup=f"Improved Route {route_idx} ({truck_names[route_idx]})"
                        ).add_to(m)"""

new_plot_global = """                # Plot All Original Routes (Always drawn, Solid, Real Road Paths)
                for route_idx, route in enumerate(initial_routes):
                    if not route:
                        continue
                    stop_sequence = [locations[0]] + [locations[n] for n in route] + [locations[0]]
                    route_coords = get_full_route_geometry(stop_sequence)
                    color = colors[route_idx % len(colors)]
                    folium.PolyLine(
                        route_coords,
                        color=color,
                        weight=5,
                        opacity=0.8,
                        tooltip=f"Original Route {route_idx} ({truck_names[route_idx]})", popup=f"Original Route {route_idx} ({truck_names[route_idx]})"
                    ).add_to(m)

                # Plot All Improved Routes (if toggled, Dotted, Real Road Paths)
                if show_proposed:
                    for route_idx, route in enumerate(improved_routes):
                        if not route:
                            continue
                        stop_sequence = [locations[0]] + [locations[n] for n in route] + [locations[0]]
                        route_coords = get_full_route_geometry(stop_sequence)
                        color = colors[route_idx % len(colors)]
                        folium.PolyLine(
                            route_coords,
                            color=color,
                            weight=4,
                            opacity=0.9,
                            dash_array='5, 10', # Dotted line
                            tooltip=f"Improved Route {route_idx} ({truck_names[route_idx]})", popup=f"Improved Route {route_idx} ({truck_names[route_idx]})"
                        ).add_to(m)"""

content = content.replace(old_plot_global, new_plot_global)

# Replace the PolyLine plotting in the Local Move View
old_plot_local = """                    # Solid original
                    r_orig = initial_routes[idx]
                    if r_orig:
                        route_coords_orig = [locations[0]] + [locations[n] for n in r_orig] + [locations[0]]
                        pl_orig = folium.PolyLine(route_coords_orig, color=r_color, weight=6, opacity=0.3, tooltip=f"Original Route {truck_names[idx]}", popup=f"Original Route {truck_names[idx]}")
                        pl_orig.add_to(m)
                        PolyLineTextPath(pl_orig, '        ►        ', repeat=True, offset=7, attributes={'fill': r_color, 'fill-opacity': '0.3', 'font-weight': 'bold', 'font-size': '18'}).add_to(m)
                    
                    # Dotted new
                    r_new = selected_new_routes[idx]
                    if r_new:
                        route_coords_new = [locations[0]] + [locations[n] for n in r_new] + [locations[0]]
                        pl_new = folium.PolyLine(route_coords_new, color=r_color, weight=5, opacity=1.0, dash_array='5, 10', tooltip=f"Improved Route {truck_names[idx]}", popup=f"Improved Route {truck_names[idx]}")
                        pl_new.add_to(m)
                        PolyLineTextPath(pl_new, '        ►        ', repeat=True, offset=7, attributes={'fill': r_color, 'fill-opacity': '1.0', 'font-weight': 'bold', 'font-size': '18'}).add_to(m)"""

new_plot_local = """                    # Solid original (Real Road Paths)
                    r_orig = initial_routes[idx]
                    if r_orig:
                        stops_orig = [locations[0]] + [locations[n] for n in r_orig] + [locations[0]]
                        route_coords_orig = get_full_route_geometry(stops_orig)
                        pl_orig = folium.PolyLine(route_coords_orig, color=r_color, weight=6, opacity=0.3, tooltip=f"Original Route {truck_names[idx]}", popup=f"Original Route {truck_names[idx]}")
                        pl_orig.add_to(m)
                        PolyLineTextPath(pl_orig, '        ►        ', repeat=True, offset=7, attributes={'fill': r_color, 'fill-opacity': '0.3', 'font-weight': 'bold', 'font-size': '18'}).add_to(m)
                    
                    # Dotted new (Real Road Paths)
                    r_new = selected_new_routes[idx]
                    if r_new:
                        stops_new = [locations[0]] + [locations[n] for n in r_new] + [locations[0]]
                        route_coords_new = get_full_route_geometry(stops_new)
                        pl_new = folium.PolyLine(route_coords_new, color=r_color, weight=5, opacity=1.0, dash_array='5, 10', tooltip=f"Improved Route {truck_names[idx]}", popup=f"Improved Route {truck_names[idx]}")
                        pl_new.add_to(m)
                        PolyLineTextPath(pl_new, '        ►        ', repeat=True, offset=7, attributes={'fill': r_color, 'fill-opacity': '1.0', 'font-weight': 'bold', 'font-size': '18'}).add_to(m)"""

content = content.replace(old_plot_local, new_plot_local)

with open("app_valhalla_road_path.py", "w") as f:
    f.write(content)

print("Updated app_valhalla_road_path.py with real road geometries!")
