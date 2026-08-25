"""
Valhalla API Client & Distance Matrix Engine
---------------------------------------------
Provides modular abstractions for querying Valhalla routing services:
- Distance Matrix calculation (/sources_to_targets) with intelligent chunking,
  exponential retry backoffs, automatic batch-halving, and caching.
- Turn-by-turn route geometry extraction (/route) with polyline6 decoding.
- Multi-stop sub-sequence batch routing.
"""

import os
import json
import time
import requests
from geopy.distance import geodesic

DEFAULT_VALHALLA_URL = "https://valhalla1.openstreetmap.de"
DEFAULT_VALHALLA_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "valhalla_cache.json")


def decode_polyline(encoded: str, precision: int = 6):
    """
    Decodes an encoded polyline string (precision 6 for Valhalla & OSRM)
    into a list of (latitude, longitude) float tuples.
    """
    if not encoded:
        return []
    inv = 1.0 / (10 ** precision)
    decoded = []
    lat = 0
    lng = 0
    index = 0
    length = len(encoded)
    while index < length:
        shift = 0
        result = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        shift = 0
        result = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng
        decoded.append((lat * inv, lng * inv))
    return decoded


class ValhallaClient:
    """
    Client for interacting with Valhalla Routing and Matrix APIs.
    """
    def __init__(self, base_url: str = DEFAULT_VALHALLA_URL, costing: str = "truck", units: str = "kilometers"):
        self.base_url = base_url.rstrip("/")
        self.default_costing = costing
        self.default_units = units

    def fetch_matrix_chunk(self, sources, targets, costing: str = None, timeout: int = 20):
        """
        Sends a /sources_to_targets request to Valhalla.
        Returns the parsed JSON 'sources_to_targets' matrix.
        """
        costing = costing or self.default_costing
        payload = {
            "sources": sources,
            "targets": targets,
            "costing": costing,
            "units": self.default_units
        }
        url = f"{self.base_url}/sources_to_targets"
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("sources_to_targets", [])

    def fetch_route(self, locations, costing: str = None, timeout: float = 3.0):
        """
        Sends a /route request to Valhalla for a sequence of locations.
        locations: list of dicts with 'lat' and 'lon' keys, or list of (lat, lon) tuples.
        """
        costing = costing or self.default_costing
        formatted_locs = []
        for loc in locations:
            if isinstance(loc, (list, tuple)):
                formatted_locs.append({"lat": loc[0], "lon": loc[1]})
            else:
                formatted_locs.append(loc)

        payload = {
            "locations": formatted_locs,
            "costing": costing,
            "units": self.default_units
        }
        url = f"{self.base_url}/route"
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def fetch_single_leg_geometry(self, p1, p2, costing_list=("truck", "auto"), timeout: float = 2.5):
        """
        Fetches turn-by-turn road geometry between two points p1 and p2.
        Tries truck costing first, falling back to auto costing.
        Returns decoded coordinates [(lat, lon), ...] or None if failed.
        """
        if p1 == p2:
            return [p1, p2]

        print(f"[Valhalla API] Cache miss for leg ({p1[0]:.5f}, {p1[1]:.5f}) -> ({p2[0]:.5f}, {p2[1]:.5f}). Querying Valhalla route API...")
        for costing in costing_list:
            try:
                data = self.fetch_route([p1, p2], costing=costing, timeout=timeout)
                legs = data.get("trip", {}).get("legs", [])
                if legs and "shape" in legs[0]:
                    coords = decode_polyline(legs[0]["shape"], precision=6)
                    if coords and len(coords) >= 2:
                        print(f"[Valhalla API] Received {len(coords)} points for leg ({p1[0]:.5f}, {p1[1]:.5f}) -> ({p2[0]:.5f}, {p2[1]:.5f})")
                        return coords
            except Exception:
                continue
        return None

    def fetch_subseq_batch_geometry(self, sub_seq, costing: str = "truck", timeout: float = 3.0):
        """
        Batch queries road geometry for a multi-stop sequence.
        Returns a dict mapping 'lat1,lon1|lat2,lon2' -> list of (lat, lon) coordinates.
        """
        results = {}
        if len(sub_seq) < 2:
            return results

        print(f"[Valhalla API] Batch querying road geometry for {len(sub_seq)} stops [({sub_seq[0][0]:.4f}, {sub_seq[0][1]:.4f}) ... ({sub_seq[-1][0]:.4f}, {sub_seq[-1][1]:.4f})]...")
        try:
            data = self.fetch_route(sub_seq, costing=costing, timeout=timeout)
            legs = data.get("trip", {}).get("legs", [])
            if len(legs) == len(sub_seq) - 1:
                for l_idx, leg in enumerate(legs):
                    p1 = sub_seq[l_idx]
                    p2 = sub_seq[l_idx + 1]
                    k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
                    if "shape" in leg:
                        coords = decode_polyline(leg["shape"], precision=6)
                        if len(coords) > 2:
                            results[k] = coords
                print(f"[Valhalla API] Batch downloaded geometry for {len(results)}/{len(sub_seq)-1} route legs.")
        except Exception as e:
            print(f"[Valhalla API Warning] Batch query error: {e}")

        return results

    def get_distance_matrix(self, locations, cache=None, cache_file=None, chunk_size: int = 40, retry_delays=(0, 5, 10, 15), on_error=None):
        """
        Computes the complete distance matrix (in meters) for a list of locations.
        Utilizes provided cache dict / cache_file to look up existing distances,
        and queries Valhalla for missing pairs with exponential retry delays and batch halving.
        """
        if cache is None:
            cache = {}
            if cache_file and os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                except Exception:
                    cache = {}

        num_nodes = len(locations)
        distance_matrix = [[0] * num_nodes for _ in range(num_nodes)]

        missing_indices = set()
        for i in range(num_nodes):
            for j in range(num_nodes):
                if i == j:
                    continue
                k = f"{locations[i][0]},{locations[i][1]}|{locations[j][0]},{locations[j][1]}"
                if k not in cache:
                    missing_indices.add(i)
                    missing_indices.add(j)

        if missing_indices:
            missing_list = list(missing_indices)
            req_locations = [{"lat": locations[idx][0], "lon": locations[idx][1]} for idx in missing_list]
            api_success_count = 0
            api_fail_count = 0

            def fetch_chunk_with_retry(s_chunk, t_chunk, idx_i, idx_j, allow_halving=True):
                s_count = 0
                f_count = 0

                for attempt, delay in enumerate(retry_delays):
                    if delay > 0:
                        print(f"Retrying in {delay} seconds (Attempt {attempt + 1})...")
                        time.sleep(delay)
                    try:
                        data = self.fetch_matrix_chunk(s_chunk, t_chunk, costing=self.default_costing, timeout=20)
                        for r_idx, row in enumerate(data):
                            for c_idx, target in enumerate(row):
                                orig_i = idx_i[r_idx]
                                orig_j = idx_j[c_idx]
                                k = f"{locations[orig_i][0]},{locations[orig_i][1]}|{locations[orig_j][0]},{locations[orig_j][1]}"
                                if target and target.get("distance") is not None:
                                    cache[k] = int(target["distance"] * 1000)
                                    s_count += 1
                                else:
                                    print(f"Warning: Unroutable path between {locations[orig_i]} and {locations[orig_j]}. Using penalized fallback.")
                                    cache[k] = int(geodesic(locations[orig_i], locations[orig_j]).meters * 1.5)
                                    f_count += 1
                        time.sleep(0.5)
                        return True, s_count, f_count
                    except Exception as e:
                        print(f"Valhalla Request Failed: {e}")

                if allow_halving:
                    print("All retry attempts failed. Halving batch size and repeating once...")
                    mid_s = len(s_chunk) // 2
                    mid_t = len(t_chunk) // 2
                    s_chunks = [(s_chunk[:mid_s], idx_i[:mid_s]), (s_chunk[mid_s:], idx_i[mid_s:])] if mid_s > 0 else [(s_chunk, idx_i)]
                    t_chunks = [(t_chunk[:mid_t], idx_j[:mid_t]), (t_chunk[mid_t:], idx_j[mid_t:])] if mid_t > 0 else [(t_chunk, idx_j)]

                    for sc, i_i in s_chunks:
                        if not sc:
                            continue
                        for tc, i_j in t_chunks:
                            if not tc:
                                continue
                            success, scount, fcount = fetch_chunk_with_retry(sc, tc, i_i, i_j, allow_halving=False)
                            s_count += scount
                            f_count += fcount
                            if not success:
                                return False, s_count, f_count
                    return True, s_count, f_count
                return False, s_count, f_count

            for i in range(0, len(req_locations), chunk_size):
                sources_chunk = req_locations[i : i + chunk_size]
                indices_i = missing_list[i : i + chunk_size]
                for j in range(0, len(req_locations), chunk_size):
                    targets_chunk = req_locations[j : j + chunk_size]
                    indices_j = missing_list[j : j + chunk_size]
                    success, s_count, f_count = fetch_chunk_with_retry(sources_chunk, targets_chunk, indices_i, indices_j, allow_halving=True)
                    api_success_count += s_count
                    api_fail_count += f_count
                    if not success:
                        error_msg = "Valhalla API permanently failed after all retries and halving. Using geodesic fallback for remaining pairs."
                        print(f"[Valhalla API Warning] {error_msg}")
                        if on_error:
                            on_error(error_msg)
                        else:
                            for idx_a in indices_i:
                                for idx_b in indices_j:
                                    if idx_a == idx_b: continue
                                    k_fall = f"{locations[idx_a][0]},{locations[idx_a][1]}|{locations[idx_b][0]},{locations[idx_b][1]}"
                                    if k_fall not in cache:
                                        cache[k_fall] = int(geodesic(locations[idx_a], locations[idx_b]).meters * 1.5)
                                        api_fail_count += 1

            print(f"Valhalla API Summary -> Successful Routes: {api_success_count} | Failed/Fallback Routes: {api_fail_count}")

            if cache_file:
                try:
                    with open(cache_file, "w", encoding="utf-8") as f:
                        json.dump(cache, f, indent=2)
                except Exception as e:
                    print(f"Warning: Failed to persist Valhalla cache: {e}")

        # Populate matrix
        for i in range(num_nodes):
            for j in range(num_nodes):
                if i == j:
                    continue
                k = f"{locations[i][0]},{locations[i][1]}|{locations[j][0]},{locations[j][1]}"
                if k in cache:
                    distance_matrix[i][j] = cache[k]
                else:
                    distance_matrix[i][j] = int(geodesic(locations[i], locations[j]).meters * 1.5)

        return distance_matrix


# Default singleton instance
default_valhalla_client = ValhallaClient()

def get_valhalla_distance_matrix(locations, cache_file=None, on_error=None):
    """
    Convenience function to compute distance matrix using the default Valhalla client.
    """
    return default_valhalla_client.get_distance_matrix(locations, cache_file=cache_file, on_error=on_error)

def fetch_single_leg_geometry(p1, p2, costing_list=("truck", "auto")):
    """
    Convenience function to fetch turn-by-turn road geometry for a single leg.
    """
    return default_valhalla_client.fetch_single_leg_geometry(p1, p2, costing_list=costing_list)

def fetch_subseq_geometry_batch(sub_seq, costing="truck"):
    """
    Convenience function to batch-query road geometry for a sub-sequence of stops.
    """
    return default_valhalla_client.fetch_subseq_batch_geometry(sub_seq, costing=costing)
