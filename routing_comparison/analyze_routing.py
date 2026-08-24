import csv
import collections
import math
import sys
import utils

# Import our algorithms
from min_max_mtsp import tour_partitioning_mtsp
from cvrp_itp import cvrp_itp
from mlp_geometric import mlp_geometric_scaling
from bi_objective import bi_objective_routing

def distance(p1, p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

def exact_chunk(lst, n):
    if not lst: return []
    n = min(n, len(lst))
    sz = len(lst) // n
    rem = len(lst) % n
    res = []
    idx = 0
    for i in range(n):
        s = sz + (1 if i < rem else 0)
        res.append(lst[idx:idx+s])
        idx += s
    return res

def evaluate_routes(depot, routes):
    if not routes:
        return 0, 0, 0
    # routes is a list of lists of points
    if isinstance(routes[0], tuple): # single route
        routes = [routes]
        
    makespan = 0
    total_dist = 0
    total_latency = 0
    
    for route in routes:
        if not route: continue
        d = 0
        lat = 0
        curr = depot
        for p in route:
            d += distance(curr, p)
            lat += d
            curr = p
        d += distance(curr, depot)
        makespan = max(makespan, d)
        total_dist += d
        total_latency += lat
        
    return total_dist, makespan, total_latency

def process_period(name, stops, filename_prefix, out_f):
    def log(msg):
        print(msg)
        out_f.write(msg + '\n')

    log(f"\n{'='*50}")
    log(f"Analyzing {name} ({len(stops)} stops)")
    log(f"{'='*50}")
    
    if not stops:
        log("No stops.")
        return
        
    # Fixed Depot
    depot = (-73.87299938, 40.80594755)
    log(f"Using Fixed Depot: {depot}")
    
    # 1. Actual Routes
    actual = collections.defaultdict(list)
    for s in stops:
        actual[s['Rt']].append(s)
    
    for rt in actual:
        actual[rt].sort(key=lambda x: int(x['Seq']))
    
    actual_routes = []
    for rt in sorted(actual.keys()):
        route_coords = [(float(s['Longitude']), float(s['Latitude'])) for s in actual[rt]]
        actual_routes.append(route_coords)
        
    k = len(actual_routes)
    log(f"Actual Number of Trucks: {k}")
    
    act_dist, act_makespan, act_latency = evaluate_routes(depot, actual_routes)
    log(f"[Actual]        Total Dist: {act_dist:.4f} | Makespan: {act_makespan:.4f} | Latency: {act_latency:.4f} (Used {len(actual_routes)} trucks)")
    log(f"  -> Stops per truck: {[len(r) for r in actual_routes]}")
    utils.plot_routes(depot, actual_routes, f"Actual Routes ({name})", f"{filename_prefix}_actual.png")
    
    # Extract locations and demands
    locations = []
    demands = []
    for s in stops:
        locations.append((float(s['Longitude']), float(s['Latitude'])))
        weight = float(s['Weight'].replace(',', '')) if s['Weight'] else 1.0
        demands.append(weight)
        
    # 2. Min-Max mTSP
    try:
        mtsp_routes = tour_partitioning_mtsp(depot, locations, k)
        m_dist, m_makespan, m_lat = evaluate_routes(depot, mtsp_routes)
        log(f"[Min-Max mTSP]  Total Dist: {m_dist:.4f} | Makespan: {m_makespan:.4f} | Latency: {m_lat:.4f} (Used {len(mtsp_routes)} trucks)")
        log(f"  -> Stops per truck: {[len(r) for r in mtsp_routes]}")
        utils.plot_routes(depot, mtsp_routes, f"Min-Max mTSP ({name})", f"{filename_prefix}_mtsp.png")
    except Exception as e:
        log(f"Min-Max mTSP failed: {e}")
        
    # 3. CVRP ITP (Binary search for capacity to hit exactly k trucks)
    try:
        low = max(demands) if demands else 1
        high = sum(demands) if demands else 10
        cvrp_routes = []
        for _ in range(50):
            mid = (low + high) / 2
            r = cvrp_itp(depot, locations, demands, mid)
            cvrp_routes = r
            if len(r) == k:
                break
            elif len(r) > k:
                low = mid + 0.1
            else:
                high = mid - 0.1
                
        # Hard cap: if we undershot, pad with empty trucks
        while len(cvrp_routes) < k:
            cvrp_routes.append([])
            
        c_dist, c_makespan, c_lat = evaluate_routes(depot, cvrp_routes)
        log(f"[CVRP ITP]      Total Dist: {c_dist:.4f} | Makespan: {c_makespan:.4f} | Latency: {c_lat:.4f} (Used {len(cvrp_routes)} trucks)")
        log(f"  -> Stops per truck: {[len(r) for r in cvrp_routes]}")
        utils.plot_routes(depot, cvrp_routes, f"CVRP ITP ({name})", f"{filename_prefix}_cvrp.png")
    except Exception as e:
        log(f"CVRP ITP failed: {e}")
        
    # 4. MLP Geometric Scaling (Split into exactly k routes)
    try:
        mlp_path = mlp_geometric_scaling(depot, locations)
        mlp_routes = exact_chunk(mlp_path, k)
        
        # Hard cap: pad with empty trucks if needed
        while len(mlp_routes) < k:
            mlp_routes.append([])
            
        ml_dist, ml_makespan, ml_lat = evaluate_routes(depot, mlp_routes)
        log(f"[MLP Geometric] Total Dist: {ml_dist:.4f} | Makespan: {ml_makespan:.4f} | Latency: {ml_lat:.4f} (Used {len(mlp_routes)} trucks)")
        log(f"  -> Stops per truck: {[len(r) for r in mlp_routes]}")
        utils.plot_routes(depot, mlp_routes, f"MLP Geometric ({name})", f"{filename_prefix}_mlp.png")
    except Exception as e:
        log(f"MLP Geometric failed: {e}")

    # 5. Bi-Objective
    try:
        bi_routes = bi_objective_routing(depot, locations, k)
        b_dist, b_makespan, b_lat = evaluate_routes(depot, bi_routes)
        log(f"[Bi-Objective]  Total Dist: {b_dist:.4f} | Makespan: {b_makespan:.4f} | Latency: {b_lat:.4f} (Used {len(bi_routes)} trucks)")
        log(f"  -> Stops per truck: {[len(r) for r in bi_routes]}")
        utils.plot_routes(depot, bi_routes, f"Bi-Objective ({name})", f"{filename_prefix}_bi.png")
    except Exception as e:
        log(f"Bi-Objective failed: {e}")

def main(csv_file):
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        data = list(reader)
        
    morning = [row for row in data if row.get('Open1') == '0830' and row.get('Close1') == '1230']
    afternoon = [row for row in data if row.get('Open1') == '1230' and row.get('Close1') == '1630']
    
    with open('analysis_results.txt', 'w', encoding='utf-8') as out_f:
        process_period('Morning Stops', morning, 'morning', out_f)
        process_period('Afternoon Stops', afternoon, 'afternoon', out_f)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        for p in [
            os.path.join(os.path.dirname(__file__), "..", "dataset", "sample_orders_routing.csv"),
            os.path.join(os.path.dirname(__file__), "sample_orders_routing.csv"),
            os.path.join("dataset", "sample_orders_routing.csv"),
            "sample_orders_routing.csv"
        ]:
            if os.path.exists(p):
                file_path = p
                break
        else:
            file_path = "sample_orders_routing.csv"
    main(file_path)
