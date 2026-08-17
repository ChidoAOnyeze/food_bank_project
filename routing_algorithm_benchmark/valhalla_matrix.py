import os
import json
import time
import requests
import math
from geopy.distance import geodesic

POSSIBLE_CACHE_PATHS = [
    os.path.join(os.path.dirname(__file__), "valhalla_cache.json"),
    os.path.join(os.path.dirname(__file__), "..", "routing_augmentation_tool", "valhalla_cache.json"),
    "valhalla_cache.json"
]

def find_or_create_cache_file():
    for p in POSSIBLE_CACHE_PATHS:
        if os.path.exists(p):
            return os.path.abspath(p)
    # Default to placing in current benchmark directory
    default_p = os.path.join(os.path.dirname(__file__), "valhalla_cache.json")
    return os.path.abspath(default_p)

def fetch_valhalla_chunk(s_chunk, t_chunk, idx_i, idx_j, locations, cache, allow_halving=True):
    delays = [0, 2, 5, 10]
    for attempt, delay in enumerate(delays):
        if delay > 0:
            time.sleep(delay)
        payload = {
            "sources": s_chunk,
            "targets": t_chunk,
            "costing": "truck",
            "units": "kilometers"
        }
        try:
            resp = requests.post("https://valhalla1.openstreetmap.de/sources_to_targets", json=payload, timeout=15)
            if resp.status_code == 200:
                data = resp.json().get("sources_to_targets", [])
                for r_idx, row in enumerate(data):
                    for c_idx, target in enumerate(row):
                        orig_i = idx_i[r_idx]
                        orig_j = idx_j[c_idx]
                        k = f"{locations[orig_i][0]},{locations[orig_i][1]}|{locations[orig_j][0]},{locations[orig_j][1]}"
                        if target and target.get('distance') is not None:
                            cache[k] = int(target['distance'] * 1000) # store in meters
                        else:
                            cache[k] = int(geodesic(locations[orig_i], locations[orig_j]).meters * 1.5)
                time.sleep(0.2)
                return True
        except Exception:
            pass

    if allow_halving:
        mid_s = len(s_chunk) // 2
        mid_t = len(t_chunk) // 2
        s_chunks = [(s_chunk[:mid_s], idx_i[:mid_s]), (s_chunk[mid_s:], idx_i[mid_s:])] if mid_s > 0 else [(s_chunk, idx_i)]
        t_chunks = [(t_chunk[:mid_t], idx_j[:mid_t]), (t_chunk[mid_t:], idx_j[mid_t:])] if mid_t > 0 else [(t_chunk, idx_j)]
        for sc, i_i in s_chunks:
            if not sc: continue
            for tc, i_j in t_chunks:
                if not tc: continue
                if not fetch_valhalla_chunk(sc, tc, i_i, i_j, locations, cache, allow_halving=False):
                    return False
        return True
    return False

def build_valhalla_matrix(locations, cache_file=None, fetch_missing=True):
    """
    Builds an in-memory distance matrix for a list of (lat, lon) coordinates
    using the Valhalla OpenStreetMap road network (in kilometers).
    """
    cache_file = cache_file or find_or_create_cache_file()
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    else:
        cache = {}

    num_nodes = len(locations)
    missing_indices = set()

    for i in range(num_nodes):
        for j in range(num_nodes):
            if i == j: continue
            k = f"{locations[i][0]},{locations[i][1]}|{locations[j][0]},{locations[j][1]}"
            if k not in cache:
                missing_indices.add(i)
                missing_indices.add(j)

    if missing_indices and fetch_missing:
        missing_list = list(missing_indices)
        req_locations = [{"lat": locations[idx][0], "lon": locations[idx][1]} for idx in missing_list]
        chunk_size = 40
        print(f"  [Valhalla API] Fetching road driving distances for {len(missing_list)} new stops...")

        for i in range(0, len(req_locations), chunk_size):
            sources_chunk = req_locations[i : i + chunk_size]
            indices_i = missing_list[i : i + chunk_size]
            for j in range(0, len(req_locations), chunk_size):
                targets_chunk = req_locations[j : j + chunk_size]
                indices_j = missing_list[j : j + chunk_size]
                fetch_valhalla_chunk(sources_chunk, targets_chunk, indices_i, indices_j, locations, cache)

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f)
        except Exception:
            pass

    # Build 2D lookup array in kilometers
    node_to_idx = {loc: idx for idx, loc in enumerate(locations)}
    km_matrix = [[0.0] * num_nodes for _ in range(num_nodes)]

    for i in range(num_nodes):
        for j in range(num_nodes):
            if i == j: continue
            k = f"{locations[i][0]},{locations[i][1]}|{locations[j][0]},{locations[j][1]}"
            if k in cache:
                km_matrix[i][j] = cache[k] / 1000.0 # Convert meters to kilometers
            else:
                km_matrix[i][j] = geodesic(locations[i], locations[j]).kilometers * 1.5

    class ValhallaCallableMatrix:
        def __init__(self, matrix, mapping):
            self.matrix = matrix
            self.mapping = mapping

        def __call__(self, p1, p2):
            if p1 == p2:
                return 0.0
            i = self.mapping.get(p1)
            j = self.mapping.get(p2)
            if i is not None and j is not None:
                return self.matrix[i][j]
            k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
            if k in cache:
                return cache[k] / 1000.0
            return geodesic(p1, p2).kilometers * 1.5

    return ValhallaCallableMatrix(km_matrix, node_to_idx)
