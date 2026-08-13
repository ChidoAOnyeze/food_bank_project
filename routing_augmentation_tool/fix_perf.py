import re

with open("app_valhalla_road_path.py", "r") as f:
    content = f.read()

# 1. Implement Fast In-Memory Geometry Caching
fast_geom_cache_logic = """
VALHALLA_GEOM_CACHE_FILE = "valhalla_geom_cache.json"

# In-Memory cache to avoid reading 2MB+ JSON files from disk repeatedly in tight loops
_IN_MEMORY_GEOM_CACHE = {}

def load_geom_cache():
    global _IN_MEMORY_GEOM_CACHE
    if not _IN_MEMORY_GEOM_CACHE and os.path.exists(VALHALLA_GEOM_CACHE_FILE):
        try:
            with open(VALHALLA_GEOM_CACHE_FILE, "r") as f:
                _IN_MEMORY_GEOM_CACHE = json.load(f)
        except Exception:
            _IN_MEMORY_GEOM_CACHE = {}
    return _IN_MEMORY_GEOM_CACHE

def save_geom_cache():
    global _IN_MEMORY_GEOM_CACHE
    try:
        with open(VALHALLA_GEOM_CACHE_FILE, "w") as f:
            json.dump(_IN_MEMORY_GEOM_CACHE, f)
    except Exception:
        pass

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
    geom_cache = load_geom_cache()
    missing_legs = False
    
    for route in routes_list:
        if not route: continue
        stop_seq = [locations[0]] + [locations[n] for n in route] + [locations[0]]
        
        # Quick in-memory check
        all_cached = True
        for i in range(len(stop_seq) - 1):
            k = f"{stop_seq[i][0]},{stop_seq[i][1]}|{stop_seq[i+1][0]},{stop_seq[i+1][1]}"
            if k not in geom_cache:
                all_cached = False
                break
        if all_cached:
            continue

        missing_legs = True
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

    if missing_legs:
        save_geom_cache()

def get_road_path(p1, p2):
    geom_cache = load_geom_cache()
    k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
    if k in geom_cache:
        return geom_cache[k]
    return [p1, p2]
"""

# Replace the geometry functions block
start_str = "VALHALLA_GEOM_CACHE_FILE = \"valhalla_geom_cache.json\""
end_str = "def get_full_route_geometry("

start_idx = content.find(start_str)
end_idx = content.find(end_str)

content = content[:start_idx] + fast_geom_cache_logic.strip() + "\n\n" + content[end_idx:]

# 2. Fix st_folium to prevent unnecessary script reruns on zoom/pan
content = content.replace("st_folium(m, width=900, height=600)", "st_folium(m, width=900, height=600, returned_objects=[])")

with open("app_valhalla_road_path.py", "w") as f:
    f.write(content)

print("Optimized memory caching and zooming performance!")
