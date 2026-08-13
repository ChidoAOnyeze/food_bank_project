import re

with open("app_valhalla.py", "r") as f:
    content = f.read()

# Add imports if not present
if "import requests" not in content:
    content = "import requests\nimport json\nimport os\n" + content

valhalla_func = """
VALHALLA_CACHE_FILE = "valhalla_cache.json"

def get_valhalla_distance_matrix(locations):
    # Load cache
    if os.path.exists(VALHALLA_CACHE_FILE):
        with open(VALHALLA_CACHE_FILE, "r") as f:
            cache = json.load(f)
    else:
        cache = {}

    num_nodes = len(locations)
    distance_matrix = [[0] * num_nodes for _ in range(num_nodes)]
    
    missing_indices = set()
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i == j: continue
            k = f"{locations[i][0]},{locations[i][1]}|{locations[j][0]},{locations[j][1]}"
            if k not in cache:
                missing_indices.add(i)
                missing_indices.add(j)
                
    if missing_indices:
        import streamlit as st
        # Ask valhalla for a matrix of ONLY the locations that are missing data
        missing_list = list(missing_indices)
        req_locations = [{"lat": locations[idx][0], "lon": locations[idx][1]} for idx in missing_list]
        
        payload = {
            "sources": req_locations,
            "targets": req_locations,
            "costing": "truck",
            "units": "kilometers"
        }
        
        try:
            resp = requests.post("https://valhalla1.openstreetmap.de/sources_to_targets", json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get("sources_to_targets", [])
                for r_idx, row in enumerate(data):
                    for c_idx, target in enumerate(row):
                        orig_i = missing_list[r_idx]
                        orig_j = missing_list[c_idx]
                        k = f"{locations[orig_i][0]},{locations[orig_i][1]}|{locations[orig_j][0]},{locations[orig_j][1]}"
                        # Valhalla returns distance in kilometers, we convert to meters for OR-Tools
                        cache[k] = int(target['distance'] * 1000)
                        
                # Save cache
                with open(VALHALLA_CACHE_FILE, "w") as f:
                    json.dump(cache, f)
            else:
                print(f"Valhalla API Error: {resp.status_code}")
        except Exception as e:
            print(f"Valhalla Request Failed: {e}")

    # Now populate matrix
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i == j: continue
            k = f"{locations[i][0]},{locations[i][1]}|{locations[j][0]},{locations[j][1]}"
            if k in cache:
                distance_matrix[i][j] = cache[k]
            else:
                # Fallback to geodesic if API fails
                distance_matrix[i][j] = int(geodesic(locations[i], locations[j]).meters)
                
    return distance_matrix

def solve_routing(locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_coef=0, latency_coef=0, ui_container=None, test_mode=False, allow_overcapacity=False, rejected_moves=None):
    # 1. Create Data Model
    data = {}
    num_nodes = len(locations)
    data['distance_matrix'] = get_valhalla_distance_matrix(locations)
"""

content = re.sub(
    r"def solve_routing.*?data\['distance_matrix'\]\[i\]\[j\] = int\(geodesic\(locations\[i\], locations\[j\]\)\.meters\)",
    valhalla_func, content, flags=re.DOTALL
)

with open("app_valhalla.py", "w") as f:
    f.write(content)

