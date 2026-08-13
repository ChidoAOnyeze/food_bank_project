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
    Batches ALL missing road segments across all routes into compact Valhalla /route API requests.
    Extracts each leg and permanently caches it in valhalla_geom_cache.json.
    \"\"\"
    if os.path.exists(VALHALLA_GEOM_CACHE_FILE):
        try:
            with open(VALHALLA_GEOM_CACHE_FILE, "r") as f:
                geom_cache = json.load(f)
        except Exception:
            geom_cache = {}
    else:
        geom_cache = {}

    missing_legs = []
    seen = set()
    for route in routes_list:
        if not route: continue
        stop_seq = [locations[0]] + [locations[n] for n in route] + [locations[0]]
        for i in range(len(stop_seq) - 1):
            p1 = stop_seq[i]
            p2 = stop_seq[i+1]
            k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
            if k not in geom_cache and k not in seen:
                seen.add(k)
                missing_legs.append((p1, p2))

    if not missing_legs:
        return

    # Super-batch in chunks of 25 legs (50 locations) to stay well within safe limits
    chunk_size = 25
    for c_idx in range(0, len(missing_legs), chunk_size):
        chunk = missing_legs[c_idx : c_idx + chunk_size]
        req_locations = []
        for p1, p2 in chunk:
            req_locations.append({"lat": p1[0], "lon": p1[1]})
            req_locations.append({"lat": p2[0], "lon": p2[1]})

        payload = {
            "locations": req_locations,
            "costing": "truck",
            "units": "kilometers"
        }
        
        try:
            resp = requests.post("https://valhalla1.openstreetmap.de/route", json=payload, timeout=25)
            if resp.status_code == 200:
                legs = resp.json().get("trip", {}).get("legs", [])
                for l_idx, (p1, p2) in enumerate(chunk):
                    leg_pos = l_idx * 2
                    if leg_pos < len(legs) and "shape" in legs[leg_pos]:
                        pts = decode_polyline(legs[leg_pos]["shape"])
                        k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
                        geom_cache[k] = pts
            else:
                print(f"Valhalla route super-batch error {resp.status_code}: {resp.text}")
        except Exception as e:
            print("Valhalla route super-batch request failed:", e)

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
    
    # Fallback to straight line if cache miss occurs
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

# Replace the geometry functions block
start_str = "VALHALLA_GEOM_CACHE_FILE = \"valhalla_geom_cache.json\""
end_str = "def solve_routing("

start_idx = content.find(start_str)
end_idx = content.find(end_str)

new_content = content[:start_idx] + geom_logic.strip() + "\n\n" + content[end_idx:]

# Now let's inject prefetch calls before map rendering
# 1. Global view prefetch
old_global_map = "            if selected_option == \"Show Full OR-Tools Optimization\":"
new_global_map = """            if selected_option == \"Show Full OR-Tools Optimization\":
                # Prefetch all missing legs across all routes in one single super-batch API call
                prefetch_and_cache_routes_geometry(initial_routes + (improved_routes if show_proposed else []), locations)"""

new_content = new_content.replace(old_global_map, new_global_map)

# 2. Local moves view prefetch
old_local_map = "            else:\n\n                # User selected a specific local move"
new_local_map = """            else:
                # User selected a specific local move
                # Prefetch affected routes geometry in one batched call
                prefetch_and_cache_routes_geometry([initial_routes[i] for i in changed_route_indices] + [selected_new_routes[i] for i in changed_route_indices], locations)"""

new_content = new_content.replace(old_local_map, new_local_map)

with open("app_valhalla_road_path.py", "w") as f:
    f.write(new_content)

print("Super-batching successfully injected into app_valhalla_road_path.py!")
