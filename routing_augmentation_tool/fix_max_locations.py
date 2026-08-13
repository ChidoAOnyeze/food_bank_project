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

def prefetch_and_cache_routes_geometry(routes_list, locations):
    \"\"\"
    Batches route legs cleanly per truck in windows of max 15 locations (well below public server max limit of 20).
    If any complex multi-stop sequence fails, automatically falls back to single-leg queries and straight lines.
    \"\"\"
    if os.path.exists(VALHALLA_GEOM_CACHE_FILE):
        try:
            with open(VALHALLA_GEOM_CACHE_FILE, "r") as f:
                geom_cache = json.load(f)
        except Exception:
            geom_cache = {}
    else:
        geom_cache = {}

    for route in routes_list:
        if not route: continue
        stop_seq = [locations[0]] + [locations[n] for n in route] + [locations[0]]
        
        # Check if all legs in this route are already cached
        all_cached = True
        for i in range(len(stop_seq) - 1):
            k = f"{stop_seq[i][0]},{stop_seq[i][1]}|{stop_seq[i+1][0]},{stop_seq[i+1][1]}"
            if k not in geom_cache:
                all_cached = False
                break
        if all_cached:
            continue

        # Valhalla /route allows max 20 locations per request.
        # We chunk into overlapping windows of max 15 locations (14 legs).
        max_locs = 15
        for start_idx in range(0, len(stop_seq) - 1, max_locs - 1):
            sub_seq = stop_seq[start_idx : start_idx + max_locs]
            if len(sub_seq) < 2: continue

            req_locations = [{"lat": p[0], "lon": p[1]} for p in sub_seq]
            payload = {
                "locations": req_locations,
                "costing": "truck",
                "units": "kilometers"
            }
            
            try:
                resp = requests.post("https://valhalla1.openstreetmap.de/route", json=payload, timeout=15)
                if resp.status_code == 200:
                    legs = resp.json().get("trip", {}).get("legs", [])
                    for l_idx, leg in enumerate(legs):
                        p1 = sub_seq[l_idx]
                        p2 = sub_seq[l_idx + 1]
                        k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
                        if "shape" in leg:
                            geom_cache[k] = decode_polyline(leg["shape"])
                else:
                    # Multi-stop batch failed for this chunk (e.g. no path found between certain stops)
                    # Fall back to resolving each leg individually so one bad stop doesn't break the whole route
                    for l_idx in range(len(sub_seq) - 1):
                        p1 = sub_seq[l_idx]
                        p2 = sub_seq[l_idx + 1]
                        k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
                        if k not in geom_cache:
                            try:
                                single_payload = {
                                    "locations": [{"lat": p1[0], "lon": p1[1]}, {"lat": p2[0], "lon": p2[1]}],
                                    "costing": "truck",
                                    "units": "kilometers"
                                }
                                s_resp = requests.post("https://valhalla1.openstreetmap.de/route", json=single_payload, timeout=10)
                                if s_resp.status_code == 200:
                                    s_legs = s_resp.json().get("trip", {}).get("legs", [])
                                    if s_legs and "shape" in s_legs[0]:
                                        geom_cache[k] = decode_polyline(s_legs[0]["shape"])
                                    else:
                                        geom_cache[k] = [p1, p2]
                                else:
                                    geom_cache[k] = [p1, p2]
                            except Exception:
                                geom_cache[k] = [p1, p2]
            except Exception as e:
                print(f"Valhalla route prefetch error: {e}")

    try:
        with open(VALHALLA_GEOM_CACHE_FILE, "w") as f:
            json.dump(geom_cache, f)
    except Exception:
        pass

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
    
    # Fallback to straight line if not cached
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

start_str = "VALHALLA_GEOM_CACHE_FILE = \"valhalla_geom_cache.json\""
end_str = "def solve_routing("

start_idx = content.find(start_str)
end_idx = content.find(end_str)

new_content = content[:start_idx] + geom_logic.strip() + "\n\n" + content[end_idx:]

with open("app_valhalla_road_path.py", "w") as f:
    f.write(new_content)

print("Fixed max locations and path errors in app_valhalla_road_path.py!")
