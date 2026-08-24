import os
import sys
import json
from geopy.distance import geodesic

# Ensure imports resolve regardless of current working directory
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_common_dir = os.path.join(_parent_dir, "common")
_aug_tool_dir = os.path.join(_parent_dir, "routing_augmentation_tool")
for _p in [_common_dir, _aug_tool_dir, _parent_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from common.valhalla_api import ValhallaClient, default_valhalla_client
except ImportError:
    try:
        from valhalla_api import ValhallaClient, default_valhalla_client
    except ImportError:
        ValhallaClient = None
        default_valhalla_client = None

POSSIBLE_CACHE_PATHS = [
    os.path.join(_parent_dir, "common", "valhalla_cache.json"),
    os.path.join(os.path.dirname(__file__), "valhalla_cache.json"),
    os.path.join(os.path.dirname(__file__), "..", "common", "valhalla_cache.json"),
    os.path.join(os.path.dirname(__file__), "..", "routing_augmentation_tool", "valhalla_cache.json"),
    os.path.join(_parent_dir, "valhalla_cache.json"),
    "valhalla_cache.json"
]

def find_or_create_cache_file():
    for p in POSSIBLE_CACHE_PATHS:
        if os.path.exists(p):
            return os.path.abspath(p)
    # Default to placing in common directory
    default_p = os.path.join(_parent_dir, "common", "valhalla_cache.json")
    return os.path.abspath(default_p)

def build_valhalla_matrix(locations, cache_file=None, fetch_missing=True):
    """
    Builds an in-memory distance matrix for a list of (lat, lon) coordinates
    using the Valhalla OpenStreetMap road network (in kilometers).
    Leverages the centralized ValhallaClient abstraction.
    """
    cache_file = cache_file or find_or_create_cache_file()
    client = default_valhalla_client or ValhallaClient()

    # Get full distance matrix in meters using the Valhalla API abstraction
    meter_matrix = client.get_distance_matrix(locations, cache_file=cache_file)

    num_nodes = len(locations)
    node_to_idx = {loc: idx for idx, loc in enumerate(locations)}
    km_matrix = [[meter_matrix[i][j] / 1000.0 for j in range(num_nodes)] for i in range(num_nodes)]

    # Load cache dictionary for callable fallback lookups
    cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}

    class ValhallaCallableMatrix:
        def __init__(self, matrix, mapping, cache_dict):
            self.matrix = matrix
            self.mapping = mapping
            self.cache = cache_dict

        def __call__(self, p1, p2):
            if p1 == p2:
                return 0.0
            i = self.mapping.get(p1)
            j = self.mapping.get(p2)
            if i is not None and j is not None:
                return self.matrix[i][j]
            k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
            if k in self.cache:
                return self.cache[k] / 1000.0
            return geodesic(p1, p2).kilometers * 1.5

    return ValhallaCallableMatrix(km_matrix, node_to_idx, cache)
