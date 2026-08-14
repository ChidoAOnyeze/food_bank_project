with open("app_valhalla_road_path.py", "r") as f:
    content = f.read()

# Update fetch_single_leg_geometry and get_road_path
old_single = """def fetch_single_leg_geometry(p1, p2):
    \"\"\"
    Fetches the true road path between p1 and p2 using Valhalla /route API.
    Tries 'truck' costing first, falls back to 'auto' costing if restricted.
    Returns list of (lat, lon) coordinates if successful, or None.
    \"\"\"
    for costing in ["truck", "auto"]:
        payload = {
            "locations": [{"lat": p1[0], "lon": p1[1]}, {"lat": p2[0], "lon": p2[1]}],
            "costing": costing,
            "units": "kilometers"
        }
        try:
            resp = requests.post("https://valhalla1.openstreetmap.de/route", json=payload, timeout=8)
            if resp.status_code == 200:
                legs = resp.json().get("trip", {}).get("legs", [])
                if legs and "shape" in legs[0]:
                    coords = decode_polyline(legs[0]["shape"])
                    if len(coords) > 2:
                        return coords
        except Exception:
            pass
    return None"""

new_single = """def fetch_single_leg_geometry(p1, p2):
    \"\"\"
    Fetches the true road path between p1 and p2 using Valhalla /route API.
    Tries 'truck' costing first, falls back to 'auto' costing if restricted.
    Returns list of (lat, lon) coordinates if successful, or None.
    \"\"\"
    for costing in ["truck", "auto"]:
        payload = {
            "locations": [{"lat": p1[0], "lon": p1[1]}, {"lat": p2[0], "lon": p2[1]}],
            "costing": costing,
            "units": "kilometers"
        }
        try:
            resp = requests.post("https://valhalla1.openstreetmap.de/route", json=payload, timeout=8)
            if resp.status_code == 200:
                legs = resp.json().get("trip", {}).get("legs", [])
                if legs and "shape" in legs[0]:
                    coords = decode_polyline(legs[0]["shape"])
                    if coords:
                        return coords
        except Exception:
            pass
    return None"""

old_road_path = """def get_road_path(p1, p2):
    geom_cache = load_geom_cache()
    k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
    if k in geom_cache and len(geom_cache[k]) > 2:
        return geom_cache[k]
    
    # On-demand fetch if missing or straight line
    coords = fetch_single_leg_geometry(p1, p2)
    if coords:
        geom_cache[k] = coords
        save_geom_cache()
        return coords
        
    return [p1, p2]"""

new_road_path = """def get_road_path(p1, p2):
    geom_cache = load_geom_cache()
    k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
    if k in geom_cache:
        return geom_cache[k]
    
    # On-demand fetch if missing from cache
    coords = fetch_single_leg_geometry(p1, p2)
    if coords:
        geom_cache[k] = coords
        save_geom_cache()
        return coords
        
    return [p1, p2]"""

content = content.replace(old_single, new_single).replace(old_road_path, new_road_path)

with open("app_valhalla_road_path.py", "w") as f:
    f.write(content)

print("Updated app_valhalla_road_path.py successfully.")
