import csv
import collections
import statistics
import math

from analyze_routing import evaluate_routes
from min_max_mtsp import tour_partitioning_mtsp
from cvrp_itp import cvrp_itp
from mlp_geometric import mlp_geometric_scaling
from bi_objective import bi_objective_routing
from analyze_routing import exact_chunk

DEPOT = (-73.87299938, 40.80594755)

import os

def _find_csv(filename):
    for p in [
        os.path.join(os.path.dirname(__file__), "..", "dataset", filename),
        os.path.join(os.path.dirname(__file__), filename),
        os.path.join("dataset", filename),
        filename
    ]:
        if os.path.exists(p):
            return p
    return filename

def analyze():
    # 1. Parse routes_sample.csv
    csv_path = _find_csv('routes_sample.csv')
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        data = list(reader)

    # 2. Group by Date and Route Name
    grouped = collections.defaultdict(list)
    for row in data:
        date = row['Date'].strip()
        route_name = row['Route Name'].strip()
        grouped[(date, route_name)].append(row)

    valid_routes = []
    valid_data_rows = []

    # 3. Validate
    for (date, route_name), stops in grouped.items():
        # Sort by "Stop Sequence ID (index)"
        stops.sort(key=lambda x: int(x['Stop Sequence ID (index)']))
        
        is_valid = True
        
        # Check continuous sequence from 1
        for i, stop in enumerate(stops):
            seq = int(stop['Stop Sequence ID (index)'])
            if seq != i + 1:
                is_valid = False
                break
                
            # Check Lat/Long
            lat = stop.get('Latitude', '').strip()
            lng = stop.get('Longitude', '').strip()
            if not lat or not lng:
                is_valid = False
                break
                
        if is_valid:
            valid_routes.append((date, route_name, stops))
            valid_data_rows.extend(stops)

    # Save valid routes
    if valid_data_rows:
        with open('valid_routes.csv', 'w', encoding='utf-8', newline='') as f:
            fieldnames = data[0].keys() if data else []
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(valid_data_rows)
            
    # 4. Group valid routes by Date
    date_to_routes = collections.defaultdict(list)
    for date, route_name, stops in valid_routes:
        date_to_routes[date].append(stops)

    # Objective ratios
    ratios = {
        'Min-Max mTSP': {'Dist': [], 'Makespan': [], 'Latency': []},
        'CVRP ITP': {'Dist': [], 'Makespan': [], 'Latency': []},
        'MLP Geometric': {'Dist': [], 'Makespan': [], 'Latency': []},
        'Bi-Objective': {'Dist': [], 'Makespan': [], 'Latency': []},
    }

    results = []

    for date, routes_for_date in date_to_routes.items():
        k = len(routes_for_date)
        all_stops = []
        for r in routes_for_date:
            all_stops.extend(r)
            
        locations = []
        demands = []
        actual_routes = []
        
        for r in routes_for_date:
            curr_route = []
            for stop in r:
                loc = (float(stop['Longitude']), float(stop['Latitude']))
                # Exclude depot from locations passed to algorithms if they are just doing VRP
                # But wait! 'routes_sample.csv' contains the depot in the stops (sequence 1 and last).
                # We should NOT include the depot in the "locations" list passed to VRP algos.
                if distance(loc, DEPOT) < 0.001: 
                    # It's a depot
                    continue
                locations.append(loc)
                demands.append(1.0) # default demand
                curr_route.append(loc)
            actual_routes.append(curr_route)

        if not locations:
            continue

        act_dist, act_makespan, act_latency = evaluate_routes(DEPOT, actual_routes)
        
        res_str = f"=== Date: {date} (Trucks: {k}, Stops: {len(locations)}) ===\n"
        res_str += f"[Actual] Dist: {act_dist:.4f} | Makespan: {act_makespan:.4f} | Latency: {act_latency:.4f}\n"

        # 1. Min-Max mTSP
        try:
            mtsp_routes = tour_partitioning_mtsp(DEPOT, locations, k)
            m_dist, m_makespan, m_lat = evaluate_routes(DEPOT, mtsp_routes)
            res_str += f"[Min-Max mTSP] Dist: {m_dist:.4f} | Makespan: {m_makespan:.4f} | Latency: {m_lat:.4f}\n"
            if m_dist > 0: ratios['Min-Max mTSP']['Dist'].append(act_dist / m_dist)
            if m_makespan > 0: ratios['Min-Max mTSP']['Makespan'].append(act_makespan / m_makespan)
            if m_lat > 0: ratios['Min-Max mTSP']['Latency'].append(act_latency / m_lat)
        except Exception as e:
            res_str += f"[Min-Max mTSP] Failed: {e}\n"

        # 2. CVRP ITP
        try:
            low = 1
            high = sum(demands)
            cvrp_routes = []
            for _ in range(50):
                mid = (low + high) / 2
                r = cvrp_itp(DEPOT, locations, demands, mid)
                cvrp_routes = r
                if len(r) == k:
                    break
                elif len(r) > k:
                    low = mid + 0.1
                else:
                    high = mid - 0.1
            while len(cvrp_routes) < k:
                cvrp_routes.append([])
            c_dist, c_makespan, c_lat = evaluate_routes(DEPOT, cvrp_routes)
            res_str += f"[CVRP ITP] Dist: {c_dist:.4f} | Makespan: {c_makespan:.4f} | Latency: {c_lat:.4f}\n"
            if c_dist > 0: ratios['CVRP ITP']['Dist'].append(act_dist / c_dist)
            if c_makespan > 0: ratios['CVRP ITP']['Makespan'].append(act_makespan / c_makespan)
            if c_lat > 0: ratios['CVRP ITP']['Latency'].append(act_latency / c_lat)
        except Exception as e:
            res_str += f"[CVRP ITP] Failed: {e}\n"

        # 3. MLP Geometric
        try:
            mlp_path = mlp_geometric_scaling(DEPOT, locations)
            mlp_routes = exact_chunk(mlp_path, k)
            while len(mlp_routes) < k:
                mlp_routes.append([])
            ml_dist, ml_makespan, ml_lat = evaluate_routes(DEPOT, mlp_routes)
            res_str += f"[MLP Geometric] Dist: {ml_dist:.4f} | Makespan: {ml_makespan:.4f} | Latency: {ml_lat:.4f}\n"
            if ml_dist > 0: ratios['MLP Geometric']['Dist'].append(act_dist / ml_dist)
            if ml_makespan > 0: ratios['MLP Geometric']['Makespan'].append(act_makespan / ml_makespan)
            if ml_lat > 0: ratios['MLP Geometric']['Latency'].append(act_latency / ml_lat)
        except Exception as e:
            res_str += f"[MLP Geometric] Failed: {e}\n"

        # 4. Bi-Objective
        try:
            bi_routes = bi_objective_routing(DEPOT, locations, k)
            b_dist, b_makespan, b_lat = evaluate_routes(DEPOT, bi_routes)
            res_str += f"[Bi-Objective] Dist: {b_dist:.4f} | Makespan: {b_makespan:.4f} | Latency: {b_lat:.4f}\n"
            if b_dist > 0: ratios['Bi-Objective']['Dist'].append(act_dist / b_dist)
            if b_makespan > 0: ratios['Bi-Objective']['Makespan'].append(act_makespan / b_makespan)
            if b_lat > 0: ratios['Bi-Objective']['Latency'].append(act_latency / b_lat)
        except Exception as e:
            res_str += f"[Bi-Objective] Failed: {e}\n"
            
        res_str += "\n"
        results.append(res_str)

    # 5. Compute statistics
    stat_str = "=== Competitive Ratios (Realized / Algorithm) Statistics ===\n\n"
    for algo, metrics in ratios.items():
        stat_str += f"Algorithm: {algo}\n"
        for metric, vals in metrics.items():
            if vals:
                mean = statistics.mean(vals)
                median = statistics.median(vals)
                min_v = min(vals)
                max_v = max(vals)
                std_v = statistics.stdev(vals) if len(vals) > 1 else 0
                stat_str += f"  - {metric}: Mean={mean:.4f}, Median={median:.4f}, Min={min_v:.4f}, Max={max_v:.4f}, Std={std_v:.4f}\n"
            else:
                stat_str += f"  - {metric}: N/A\n"
        stat_str += "\n"

    # Store test results in a single script/file
    with open('test_results.txt', 'w', encoding='utf-8') as f:
        for r in results:
            f.write(r)
        f.write(stat_str)

    print("Analysis complete. Check valid_routes.csv and test_results.txt")
    print(stat_str)

def distance(p1, p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

if __name__ == '__main__':
    analyze()
