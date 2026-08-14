with open("app_valhalla_road_path.py", "r") as f:
    content = f.read()

target_block = """def prefetch_and_cache_routes_geometry(routes_list, locations):
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
    return [p1, p2]"""

replacement_block = """def fetch_single_leg_geometry(p1, p2):
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
    return None

def prefetch_and_cache_routes_geometry(routes_list, locations):
    geom_cache = load_geom_cache()
    missing_legs = False
    
    for route in routes_list:
        if not route: continue
        stop_seq = [locations[0]] + [locations[n] for n in route] + [locations[0]]
        
        # Check which legs need fetching (missing or only straight 2-point fallback)
        needed_indices = []
        for i in range(len(stop_seq) - 1):
            p1 = stop_seq[i]
            p2 = stop_seq[i+1]
            k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
            if k not in geom_cache or len(geom_cache[k]) <= 2:
                needed_indices.append(i)
                
        if not needed_indices:
            continue

        missing_legs = True
        max_locs = 15
        for start_idx in range(0, len(stop_seq) - 1, max_locs - 1):
            sub_seq = stop_seq[start_idx : start_idx + max_locs]
            if len(sub_seq) < 2: continue

            # Check if any leg in this sub_seq needs geometry
            needs_sub = False
            for l_i in range(len(sub_seq) - 1):
                p1 = sub_seq[l_i]
                p2 = sub_seq[l_i+1]
                k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
                if k not in geom_cache or len(geom_cache[k]) <= 2:
                    needs_sub = True
                    break
            if not needs_sub:
                continue

            req_locations = [{"lat": p[0], "lon": p[1]} for p in sub_seq]
            payload = {
                "locations": req_locations,
                "costing": "truck",
                "units": "kilometers"
            }
            
            batch_success = False
            try:
                resp = requests.post("https://valhalla1.openstreetmap.de/route", json=payload, timeout=12)
                if resp.status_code == 200:
                    legs = resp.json().get("trip", {}).get("legs", [])
                    if len(legs) == len(sub_seq) - 1:
                        batch_success = True
                        for l_idx, leg in enumerate(legs):
                            p1 = sub_seq[l_idx]
                            p2 = sub_seq[l_idx + 1]
                            k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
                            if "shape" in leg:
                                coords = decode_polyline(leg["shape"])
                                if len(coords) > 2:
                                    geom_cache[k] = coords
            except Exception:
                batch_success = False

            # If batch failed, fallback to individual leg fetches with auto-fallback
            if not batch_success:
                for l_idx in range(len(sub_seq) - 1):
                    p1 = sub_seq[l_idx]
                    p2 = sub_seq[l_idx + 1]
                    k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
                    if k not in geom_cache or len(geom_cache[k]) <= 2:
                        coords = fetch_single_leg_geometry(p1, p2)
                        if coords:
                            geom_cache[k] = coords

    if missing_legs:
        save_geom_cache()

def get_road_path(p1, p2):
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

if target_block in content:
    content = content.replace(target_block, replacement_block)
    with open("app_valhalla_road_path.py", "w") as f:
        f.write(content)
    print("Successfully updated geometry engine in app_valhalla_road_path.py")
else:
    print("Could not find target_block")
