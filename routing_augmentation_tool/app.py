import os
import sys
import io
import json
import time
import math
import threading
import concurrent.futures
import streamlit as st
import pandas as pd
import folium
from folium.plugins import PolyLineTextPath
from streamlit_folium import st_folium
from ortools.constraint_solver import routing_enums_pb2, pywrapcp

# Ensure common package is in sys.path
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_common_dir = os.path.join(_parent_dir, "common")
for _p in [_common_dir, _parent_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from common.valhalla_api import (
        default_valhalla_client,
        get_valhalla_distance_matrix as _get_valhalla_distance_matrix,
    )
    from common.osrm_api import (
        default_osrm_client,
        fetch_osrm_leg_geometry,
        fetch_osrm_route_geometry,
    )
except ImportError:
    try:
        from valhalla_api import (
            default_valhalla_client,
            get_valhalla_distance_matrix as _get_valhalla_distance_matrix,
        )
        from osrm_api import (
            default_osrm_client,
            fetch_osrm_leg_geometry,
            fetch_osrm_route_geometry,
        )
    except ImportError:
        from .valhalla_api import (
            default_valhalla_client,
            get_valhalla_distance_matrix as _get_valhalla_distance_matrix,
        )
        from .osrm_api import (
            default_osrm_client,
            fetch_osrm_leg_geometry,
            fetch_osrm_route_geometry,
        )


def _get_cache_file_path(filename):
    dir_path = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(dir_path)
    common_p = os.path.join(parent_dir, "common", filename)
    if os.path.exists(common_p):
        return common_p
    local_p = os.path.join(dir_path, filename)
    if os.path.exists(local_p):
        return local_p
    root_p = os.path.join(parent_dir, filename)
    if os.path.exists(root_p):
        return root_p
    return common_p


VALHALLA_CACHE_FILE = _get_cache_file_path("valhalla_cache.json")
VALHALLA_GEOM_CACHE_FILE = _get_cache_file_path("valhalla_geom_cache.json")


def generate_accepted_changes_report(accepted_history, baseline_routes, current_routes, truck_names, node_names, demands, file_label="Routing Optimization"):
    """
    Generates a clean, comprehensive text audit report describing all accepted route changes.
    """
    lines = []
    lines.append("=" * 80)
    lines.append("  ROUTING OPTIMIZATION - ACCEPTED CHANGES AUDIT REPORT")
    lines.append(f"  Dataset / File: {file_label}")
    lines.append(f"  Generated On:   {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Modifications:  {len(accepted_history)} accepted change(s)")
    lines.append("=" * 80)
    lines.append("")

    # Section 1: Chronological Changes
    lines.append("--------------------------------------------------------------------------------")
    lines.append("1. CHRONOLOGICAL LOG OF ACCEPTED MODIFICATIONS")
    lines.append("--------------------------------------------------------------------------------")
    if not accepted_history:
        lines.append("  No local improvements or manual modifications have been accepted yet.")
        lines.append("  All routes remain in their original baseline configuration.")
        lines.append("")
    else:
        for entry in accepted_history:
            lines.append(f"\n[CHANGE #{entry['step']}] - {entry.get('timestamp', 'N/A')}")
            lines.append(f"  Summary: {entry.get('description', 'Route Improvement')}")
            lines.append("  Truck Details:")
            for chg in entry.get('changes', []):
                lines.append(f"    * Truck: {chg['truck_name']}")
                lines.append(f"      - Original: {chg['orig_sequence']}")
                lines.append(f"        Load: {chg['orig_load']} pallets ({chg['orig_stops']} stops)")
                lines.append(f"      - Improved: {chg['new_sequence']}")
                lines.append(f"        Load: {chg['new_load']} pallets ({chg['new_stops']} stops)")
            lines.append("")

    # Section 2: Final State
    lines.append("--------------------------------------------------------------------------------")
    lines.append("2. FINAL CURRENT ROUTE SCHEDULE")
    lines.append("--------------------------------------------------------------------------------")
    total_stops = 0
    total_pallets = 0
    for idx, r in enumerate(current_routes):
        t_name = truck_names[idx]
        load = sum(demands[n] for n in r)
        total_stops += len(r)
        total_pallets += load
        stop_names = ["Depot"] + [f"{node_names[n]} (#{i+1})" for i, n in enumerate(r)] + ["Depot"]
        lines.append(f"\nTruck: {t_name}")
        lines.append(f"  Total Stops: {len(r)} | Pallet Load: {load} pallets")
        lines.append(f"  Sequence:    {' -> '.join(stop_names)}")

    lines.append("")
    lines.append("=" * 80)
    lines.append(f"FLEET TOTALS: {len(current_routes)} Active Trucks | {total_stops} Total Stops | {total_pallets} Total Pallets")
    lines.append("=" * 80)
    return "\n".join(lines)

def generate_relocate_moves(routes, truck_names, node_names, touched_routes=None):
    moves = []
    num_routes = len(routes)
    for r1 in range(num_routes):
        for i in range(len(routes[r1])):
            node = routes[r1][i]
            for r2 in range(num_routes):
                if touched_routes is not None and r1 not in touched_routes and r2 not in touched_routes:
                    continue
                insert_positions = len(routes[r2]) if r1 == r2 else len(routes[r2]) + 1
                for j in range(insert_positions):
                    if r1 == r2 and j == i:
                        continue
                    new_routes = [list(r) for r in routes]
                    new_routes[r1].pop(i)
                    new_routes[r2].insert(j, node)
                    
                    target_truck = truck_names[r2] if r1 != r2 else f"{truck_names[r2]} (different position)"
                    desc = f"Move '{node_names[node]}' from {truck_names[r1]} to {target_truck}"
                    affected = (r1,) if r1 == r2 else tuple(sorted((r1, r2)))
                    sub = {r1: new_routes[r1], r2: new_routes[r2]}
                    moves.append((new_routes, desc, affected, sub))
    return moves

def generate_swap_moves(routes, truck_names, node_names, touched_routes=None):
    moves = []
    num_routes = len(routes)
    for r1 in range(num_routes):
        for i in range(len(routes[r1])):
            for r2 in range(r1, num_routes):
                if touched_routes is not None and r1 not in touched_routes and r2 not in touched_routes:
                    continue
                start_j = i + 1 if r1 == r2 else 0
                for j in range(start_j, len(routes[r2])):
                    node1 = routes[r1][i]
                    node2 = routes[r2][j]
                    new_routes = [list(r) for r in routes]
                    new_routes[r1][i] = node2
                    new_routes[r2][j] = node1
                    desc = f"Swap the deliveries for '{node_names[node1]}' (on {truck_names[r1]}) and '{node_names[node2]}' (on {truck_names[r2]})"
                    affected = (r1,) if r1 == r2 else tuple(sorted((r1, r2)))
                    sub = {r1: new_routes[r1], r2: new_routes[r2]}
                    moves.append((new_routes, desc, affected, sub))
    return moves

def generate_2opt_moves(routes, truck_names, node_names, touched_routes=None):
    moves = []
    num_routes = len(routes)
    for r in range(num_routes):
        if touched_routes is not None and r not in touched_routes:
            continue
        route = routes[r]
        n = len(route)
        for i in range(n - 1):
            for j in range(i + 1, n):
                if j - i == 1:
                    continue
                new_routes = [list(rt) for rt in routes]
                new_routes[r] = route[:i] + route[i:j+1][::-1] + route[j+1:]
                desc = f"Reorder the stops on {truck_names[r]} (reverse the sequence between '{node_names[route[i]]}' and '{node_names[route[j]]}') to uncross the route"
                affected = (r,)
                sub = {r: new_routes[r]}
                moves.append((new_routes, desc, affected, sub))
    return moves

def generate_cross_exchange_moves(routes, truck_names, node_names, touched_routes=None):
    moves = []
    num_routes = len(routes)
    for r1 in range(num_routes):
        for r2 in range(r1 + 1, num_routes):
            if touched_routes is not None and r1 not in touched_routes and r2 not in touched_routes:
                continue
            for i in range(len(routes[r1]) + 1):
                for j in range(len(routes[r2]) + 1):
                    if (i == 0 and j == 0) or (i == len(routes[r1]) and j == len(routes[r2])):
                        continue
                        
                    new_routes = [list(rt) for rt in routes]
                    tail1 = routes[r1][i:]
                    tail2 = routes[r2][j:]
                    
                    new_routes[r1] = routes[r1][:i] + tail2
                    new_routes[r2] = routes[r2][:j] + tail1
                    
                    n1 = f"'{node_names[routes[r1][i-1]]}'" if i > 0 else "the start"
                    n2 = f"'{node_names[routes[r2][j-1]]}'" if j > 0 else "the start"
                    
                    desc = f"Exchange the end-portions of {truck_names[r1]} (after {n1}) and {truck_names[r2]} (after {n2}) to untangle them"
                    affected = tuple(sorted((r1, r2)))
                    sub = {r1: new_routes[r1], r2: new_routes[r2]}
                    moves.append((new_routes, desc, affected, sub))
    return moves


def load_default_trucks_dataframe():
    possible_paths = [
        "dataset/trucks.csv",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dataset", "trucks.csv"),
        os.path.join(os.path.dirname(__file__), "..", "dataset", "trucks.csv"),
        os.path.join(os.path.dirname(__file__), "trucks.csv"),
        "trucks.csv"
    ]
    for p in possible_paths:
        if os.path.exists(p):
            try:
                df_t = pd.read_csv(p)
                df_t.columns = df_t.columns.astype(str).str.strip()
                cols_lower = [c.lower() for c in df_t.columns]
                has_veh = any(c in cols_lower for c in ['vehicle', 'truck', 'truck name', 'name', 'rt'])
                has_cap = any(c in cols_lower for c in ['pallet capacity', 'pallet_capacity', 'capacity', 'pallets', 'cap'])
                if has_veh and has_cap:
                    return df_t
            except Exception:
                continue
    return None


def assign_trucks_to_routes(tdf, unique_rts, route_loads):
    tdf = tdf.copy()
    tdf.columns = tdf.columns.astype(str).str.strip()
    cols_map = {str(c).strip().lower(): c for c in tdf.columns}
    
    veh_col = None
    for cand in ['vehicle', 'truck', 'truck name', 'name', 'rt']:
        if cand in cols_map:
            veh_col = cols_map[cand]
            break
            
    cap_col = None
    for cand in ['pallet capacity', 'pallet_capacity', 'capacity', 'pallets', 'cap']:
        if cand in cols_map:
            cap_col = cols_map[cand]
            break
            
    if veh_col and cap_col:
        tdf['Pallet Capacity'] = pd.to_numeric(tdf[cap_col], errors='coerce').fillna(25).astype(int)
        tdf['Vehicle'] = tdf[veh_col].astype(str).str.strip()
        available_trucks = tdf[['Vehicle', 'Pallet Capacity']].to_dict('records')
        
        assigned_names = []
        assigned_caps = []
        
        # Sort routes by load descending (Largest loads first)
        rts_by_load = sorted(unique_rts, key=lambda r: int(route_loads.get(r, 0)), reverse=True)
        assignment_map = {}
        
        for rt in rts_by_load:
            load = int(route_loads.get(rt, 0))
            # Best-fit: find smallest available vehicle that fits this load
            fitting_indices = [i for i, t in enumerate(available_trucks) if int(t['Pallet Capacity']) >= load]
            if fitting_indices:
                best_idx = min(fitting_indices, key=lambda i: int(available_trucks[i]['Pallet Capacity']))
                chosen_truck = available_trucks.pop(best_idx)
                assignment_map[rt] = (str(chosen_truck['Vehicle']), int(chosen_truck['Pallet Capacity']))
            elif available_trucks:
                # Fallback to largest remaining vehicle in fleet
                best_idx = max(range(len(available_trucks)), key=lambda i: int(available_trucks[i]['Pallet Capacity']))
                chosen_truck = available_trucks.pop(best_idx)
                assignment_map[rt] = (str(chosen_truck['Vehicle']), int(chosen_truck['Pallet Capacity']))
            else:
                assignment_map[rt] = (f"Truck_{rt}", 25)
                
        for rt in unique_rts:
            assigned_names.append(assignment_map[rt][0])
            assigned_caps.append(assignment_map[rt][1])
            
        return pd.DataFrame({
            "Rt": unique_rts,
            "Vehicle Name": assigned_names,
            "Initial Load": [int(route_loads.get(rt, 0)) for rt in unique_rts],
            "Capacity in Pallets": assigned_caps
        })
    else:
        return pd.DataFrame({
            "Rt": unique_rts,
            "Vehicle Name": unique_rts,
            "Initial Load": [int(route_loads.get(rt, 0)) for rt in unique_rts],
            "Capacity in Pallets": [25] * len(unique_rts)
        })


def get_valhalla_distance_matrix(locations):
    def on_error(msg):
        st.error(msg)
        st.stop()
    return _get_valhalla_distance_matrix(locations, cache_file=VALHALLA_CACHE_FILE, on_error=on_error)


def get_osrm_distance_matrix(locations):
    try:
        matrix = default_osrm_client.get_distance_matrix(locations)
        if matrix and len(matrix) == len(locations):
            return matrix
    except Exception as e:
        print(f"[OSRM API Warning] Table query failed, falling back to Valhalla: {e}")
    return get_valhalla_distance_matrix(locations)




_IN_MEMORY_GEOM_CACHE = {}

def load_geom_cache():
    global _IN_MEMORY_GEOM_CACHE
    if not _IN_MEMORY_GEOM_CACHE:
        dir_path = os.path.dirname(os.path.abspath(__file__))
        parent_dir = os.path.dirname(dir_path)
        paths_to_try = [
            VALHALLA_GEOM_CACHE_FILE,
            os.path.join(parent_dir, "common", "valhalla_geom_cache.json"),
            os.path.join(dir_path, "valhalla_geom_cache.json"),
            "valhalla_geom_cache.json"
        ]
        for p in paths_to_try:
            if os.path.exists(p):
                try:
                    with open(p, "r") as f:
                        data = json.load(f)
                        _IN_MEMORY_GEOM_CACHE.update(data)
                except Exception:
                    pass
    return _IN_MEMORY_GEOM_CACHE

def save_geom_cache_async():
    def _async_writer(cache_copy):
        try:
            with open(VALHALLA_GEOM_CACHE_FILE, "w", encoding="utf-8") as f:
                f.write("{\n")
                items = list(cache_copy.items())
                for idx, (k, coords) in enumerate(items):
                    comma = "," if idx < len(items) - 1 else ""
                    f.write(f'  "{k}": {json.dumps(coords)}{comma}\n')
                f.write("}\n")
        except Exception:
            pass
    t = threading.Thread(target=_async_writer, args=(dict(_IN_MEMORY_GEOM_CACHE),), daemon=True)
    t.start()

def save_geom_cache():
    save_geom_cache_async()

def fetch_single_leg_geometry(p1, p2, use_osrm_first=True):
    if p1 == p2:
        return [p1, p2]
    
    if use_osrm_first:
        osrm_coords = fetch_osrm_leg_geometry(p1, p2)
        if osrm_coords and len(osrm_coords) >= 2 and osrm_coords != [p1, p2]:
            return osrm_coords
        coords = default_valhalla_client.fetch_single_leg_geometry(p1, p2)
        if coords and len(coords) >= 2:
            return coords
    else:
        coords = default_valhalla_client.fetch_single_leg_geometry(p1, p2)
        if coords and len(coords) >= 2:
            return coords
        print(f"[OSRM Fallback] Valhalla timed out/unavailable. Querying OSRM road geometry...")
        osrm_coords = fetch_osrm_leg_geometry(p1, p2)
        if osrm_coords and len(osrm_coords) >= 2 and osrm_coords != [p1, p2]:
            return osrm_coords

    return [p1, p2]


def is_move_geometry_ready(move_routes, locations):
    geom_cache = load_geom_cache()
    for route in move_routes:
        if not route: continue
        stop_seq = [locations[0]] + [locations[n] for n in route] + [locations[0]]
        for i in range(len(stop_seq) - 1):
            p1, p2 = stop_seq[i], stop_seq[i+1]
            if p1 == p2:
                continue
            k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
            if k not in geom_cache or len(geom_cache[k]) < 2:
                return False
    return True

def fetch_subseq_geometry_batch(sub_seq, use_osrm_first=True):
    results = {}
    if len(sub_seq) < 2:
        return results

    if use_osrm_first:
        for l_idx in range(len(sub_seq) - 1):
            p1 = sub_seq[l_idx]
            p2 = sub_seq[l_idx + 1]
            k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
            c = fetch_single_leg_geometry(p1, p2, use_osrm_first=True)
            if c and len(c) > 2:
                results[k] = c
        return results

    results = default_valhalla_client.fetch_subseq_batch_geometry(sub_seq)
    # If batch failed or timed out, fallback to OSRM / single legs
    if len(results) < len(sub_seq) - 1:
        for l_idx in range(len(sub_seq) - 1):
            p1 = sub_seq[l_idx]
            p2 = sub_seq[l_idx + 1]
            k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
            if k not in results:
                c = fetch_single_leg_geometry(p1, p2, use_osrm_first=use_osrm_first)
                if c and len(c) > 2:
                    results[k] = c
    return results

def prefetch_and_cache_routes_geometry(routes_list, locations, use_osrm_first=True):
    geom_cache = load_geom_cache()
    sub_seqs_to_fetch = []
    
    for route in routes_list:
        if not route: continue
        stop_seq = [locations[0]] + [locations[n] for n in route] + [locations[0]]
        max_locs = 15
        for start_idx in range(0, len(stop_seq) - 1, max_locs - 1):
            sub_seq = stop_seq[start_idx : start_idx + max_locs]
            if len(sub_seq) < 2: continue
            needs_sub = False
            for l_i in range(len(sub_seq) - 1):
                p1, p2 = sub_seq[l_i], sub_seq[l_i+1]
                if p1 == p2:
                    continue
                k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
                if k not in geom_cache or len(geom_cache[k]) < 2:
                    needs_sub = True
                    break
            if needs_sub:
                sub_seqs_to_fetch.append(sub_seq)
                
    if not sub_seqs_to_fetch:
        return

    engine_name = "OSRM" if use_osrm_first else "Valhalla"
    print(f"[Geometry Prefetch] Found {len(sub_seqs_to_fetch)} uncached route sub-sequences. Fetching from {engine_name}...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        batch_results = list(executor.map(lambda s: fetch_subseq_geometry_batch(s, use_osrm_first=use_osrm_first), sub_seqs_to_fetch))
        
    new_cached_count = 0
    for res in batch_results:
        for k, coords in res.items():
            if coords and len(coords) > 2:
                geom_cache[k] = coords
                new_cached_count += 1
                
    print(f"[Geometry Cache] Cached {new_cached_count} new road leg geometries to memory.")
    save_geom_cache_async()

def get_road_path(p1, p2, use_road_geometry=True):
    if not use_road_geometry or p1 == p2:
        return [p1, p2]
    geom_cache = load_geom_cache()
    k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
    if k in geom_cache and len(geom_cache[k]) >= 2:
        return geom_cache[k]
    # Non-blocking immediate fallback to prevent freezing during map rendering
    return [p1, p2]

def get_full_route_geometry(locations_list, use_road_geometry=True):
    if not use_road_geometry or len(locations_list) < 2:
        return locations_list
    full_path = []
    for i in range(len(locations_list) - 1):
        p1 = locations_list[i]
        p2 = locations_list[i+1]
        leg_pts = get_road_path(p1, p2, use_road_geometry=True)
        if full_path:
            full_path.extend(leg_pts[1:])
        else:
            full_path.extend(leg_pts)
    return full_path

def start_background_geometry_prefetch(top_moves, improved_routes, locations, limit=10, use_osrm_first=True):
    if not locations:
        return
        
    def worker():
        # 1. First Priority: Pre-fetch Full OR-Tools improved routes
        if improved_routes:
            print("[Background Worker] Pre-fetching road geometry for full fleet solution...")
            try:
                prefetch_and_cache_routes_geometry(improved_routes, locations, use_osrm_first=use_osrm_first)
            except Exception as e:
                print(f"[Background Worker Warning] Full fleet geometry: {e}")
                
        # 2. Second Priority: Pre-fetch top candidate moves
        if top_moves:
            total_to_fetch = min(limit, len(top_moves))
            print(f"[Background Worker] Pre-fetching road geometry for top {total_to_fetch} candidate moves...")
            for m_idx, move in enumerate(top_moves[:limit]):
                try:
                    candidate_routes = move[3]
                    prefetch_and_cache_routes_geometry(candidate_routes, locations, use_osrm_first=use_osrm_first)
                    time.sleep(0.15)
                except Exception as e:
                    print(f"[Background Worker Warning] Move {m_idx}: {e}")
        save_geom_cache_async()

    t = threading.Thread(target=worker, daemon=True)
    t.start()

def solve_routing(locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_coef=0, latency_coef=0, ui_container=None, test_mode=False, allow_overcapacity=False, rejected_moves=None, touched_routes=None, previous_candidates=None, use_osrm=True):
    # 1. Create Data Model
    data = {}
    num_nodes = len(locations)
    if use_osrm:
        data['distance_matrix'] = get_osrm_distance_matrix(locations)
    else:
        data['distance_matrix'] = get_valhalla_distance_matrix(locations)
    dist_matrix = data['distance_matrix']
    
    data['demands'] = demands
    data['num_vehicles'] = len(vehicle_capacities)
    data['vehicle_capacities'] = vehicle_capacities
    data['depot'] = 0

    # 2. OR-Tools Setup
    manager = pywrapcp.RoutingIndexManager(num_nodes, data['num_vehicles'], data['depot'])
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return dist_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)
    
    routing.AddDimension(transit_callback_index, 0, 10000000, True, 'Distance')
    distance_dimension = routing.GetDimensionOrDie('Distance')
    distance_dimension.SetGlobalSpanCostCoefficient(makespan_coef)
    
    for i in range(1, num_nodes):
        distance_dimension.SetCumulVarSoftUpperBound(manager.NodeToIndex(i), 0, latency_coef)

    def demand_callback(from_index):
        return data['demands'][manager.IndexToNode(from_index)]
    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    
    if allow_overcapacity:
        large_caps = [1000000] * data['num_vehicles']
        routing.AddDimensionWithVehicleCapacity(demand_callback_index, 0, large_caps, True, 'Capacity')
        capacity_dimension = routing.GetDimensionOrDie('Capacity')
        penalty_cost = 1000000  # High penalty per pallet over capacity
        for vehicle_id in range(data['num_vehicles']):
            end_index = routing.End(vehicle_id)
            actual_capacity = data['vehicle_capacities'][vehicle_id]
            capacity_dimension.SetCumulVarSoftUpperBound(end_index, actual_capacity, penalty_cost)
    else:
        routing.AddDimensionWithVehicleCapacity(demand_callback_index, 0, data['vehicle_capacities'], True, 'Capacity')

    # Read Initial Assignment
    initial_solution = routing.ReadAssignmentFromRoutes(initial_routes, True)
    if not initial_solution:
        return None, None, None, None, None

    initial_cost = initial_solution.ObjectiveValue()

    # Precompute fast route metrics (distance, latency, loads) in pure Python (< 0.001s)
    def compute_route_metrics(r):
        if not r:
            return 0, 0
        seq = [0] + r + [0]
        cumul = 0
        r_lat = 0
        for i in range(len(seq) - 1):
            d = dist_matrix[seq[i]][seq[i+1]]
            cumul += d
            if i < len(r):
                r_lat += cumul
        return cumul, r_lat

    route_metrics = [compute_route_metrics(r) for r in initial_routes]
    route_dists = [m[0] for m in route_metrics]
    route_latencies = [m[1] for m in route_metrics]
    route_loads = [sum(demands[n] for n in r) for r in initial_routes]

    base_dist = sum(route_dists)
    base_makespan = max(route_dists) if route_dists else 0
    base_latency = sum(route_latencies)
    base_obj = base_dist + makespan_coef * base_makespan + latency_coef * base_latency

    # Multi-Objective Neighborhood Search (< 0.08s across entire fleet)
    fast_candidates = []
    num_routes = len(initial_routes)
    eval_routes = range(num_routes)

    # 1. Relocate Moves (Single Stop Transfers)
    for r1 in eval_routes:
        for i, node in enumerate(initial_routes[r1]):
            node_demand = demands[node]
            for r2 in range(num_routes):
                if not allow_overcapacity and r1 != r2 and route_loads[r2] + node_demand > vehicle_capacities[r2]:
                    continue
                insert_positions = len(initial_routes[r2]) if r1 == r2 else len(initial_routes[r2]) + 1
                for j in range(insert_positions):
                    if r1 == r2 and (j == i or j == i + 1): continue
                    new_r1 = list(initial_routes[r1])
                    new_r1.pop(i)
                    if r1 == r2:
                        new_r1.insert(j, node)
                        d1, lat1 = compute_route_metrics(new_r1)
                        new_dists = list(route_dists)
                        new_dists[r1] = d1
                        new_obj = sum(new_dists) + makespan_coef * max(new_dists) + latency_coef * (base_latency - route_latencies[r1] + lat1)
                        if new_obj < base_obj or allow_overcapacity:
                            new_routes = [list(r) for r in initial_routes]
                            new_routes[r1] = new_r1
                            desc = f"Re-sequence '{node_names[node]}' on {truck_names[r1]} to stop #{j+1}"
                            fast_candidates.append((base_obj - new_obj, new_routes, desc))
                    else:
                        new_r2 = list(initial_routes[r2])
                        new_r2.insert(j, node)
                        d1, lat1 = compute_route_metrics(new_r1)
                        d2, lat2 = compute_route_metrics(new_r2)
                        new_dists = list(route_dists)
                        new_dists[r1] = d1
                        new_dists[r2] = d2
                        new_obj = sum(new_dists) + makespan_coef * max(new_dists) + latency_coef * (base_latency - route_latencies[r1] - route_latencies[r2] + lat1 + lat2)
                        if new_obj < base_obj or allow_overcapacity:
                            new_routes = [list(r) for r in initial_routes]
                            new_routes[r1] = new_r1
                            new_routes[r2] = new_r2
                            desc = f"Move '{node_names[node]}' from {truck_names[r1]} to {truck_names[r2]}"
                            fast_candidates.append((base_obj - new_obj, new_routes, desc))

    # 2. Swap Moves (Stop Swaps)
    for r1 in eval_routes:
        for i, n1 in enumerate(initial_routes[r1]):
            d1 = demands[n1]
            for r2 in range(r1, num_routes):
                start_j = i + 1 if r1 == r2 else 0
                for j in range(start_j, len(initial_routes[r2])):
                    n2 = initial_routes[r2][j]
                    d2 = demands[n2]
                    if not allow_overcapacity and r1 != r2:
                        if route_loads[r1] - d1 + d2 > vehicle_capacities[r1]: continue
                        if route_loads[r2] - d2 + d1 > vehicle_capacities[r2]: continue
                    new_r1 = list(initial_routes[r1])
                    new_r2 = list(initial_routes[r2])
                    if r1 == r2:
                        new_r1[i] = n2
                        new_r1[j] = n1
                        d_new1, lat_new1 = compute_route_metrics(new_r1)
                        new_dists = list(route_dists)
                        new_dists[r1] = d_new1
                        new_obj = sum(new_dists) + makespan_coef * max(new_dists) + latency_coef * (base_latency - route_latencies[r1] + lat_new1)
                        if new_obj < base_obj or allow_overcapacity:
                            new_routes = [list(r) for r in initial_routes]
                            new_routes[r1] = new_r1
                            desc = f"Swap positions of '{node_names[n1]}' and '{node_names[n2]}' on {truck_names[r1]}"
                            fast_candidates.append((base_obj - new_obj, new_routes, desc))
                    else:
                        new_r1[i] = n2
                        new_r2[j] = n1
                        d_new1, lat_new1 = compute_route_metrics(new_r1)
                        d_new2, lat_new2 = compute_route_metrics(new_r2)
                        new_dists = list(route_dists)
                        new_dists[r1] = d_new1
                        new_dists[r2] = d_new2
                        new_obj = sum(new_dists) + makespan_coef * max(new_dists) + latency_coef * (base_latency - route_latencies[r1] - route_latencies[r2] + lat_new1 + lat_new2)
                        if new_obj < base_obj or allow_overcapacity:
                            new_routes = [list(r) for r in initial_routes]
                            new_routes[r1] = new_r1
                            new_routes[r2] = new_r2
                            desc = f"Swap '{node_names[n1]}' ({truck_names[r1]}) and '{node_names[n2]}' ({truck_names[r2]})"
                            fast_candidates.append((base_obj - new_obj, new_routes, desc))

    # 3. 2-opt Moves (Route Uncrossing)
    for r in eval_routes:
        route = initial_routes[r]
        n = len(route)
        for i in range(n - 1):
            for j in range(i + 1, n):
                if j - i == 1: continue
                new_r = route[:i] + route[i:j+1][::-1] + route[j+1:]
                d_new, lat_new = compute_route_metrics(new_r)
                new_dists = list(route_dists)
                new_dists[r] = d_new
                new_obj = sum(new_dists) + makespan_coef * max(new_dists) + latency_coef * (base_latency - route_latencies[r] + lat_new)
                if new_obj < base_obj or allow_overcapacity:
                    new_routes = [list(rt) for rt in initial_routes]
                    new_routes[r] = new_r
                    desc = f"Uncross stops on {truck_names[r]} (reverse sequence between '{node_names[route[i]]}' and '{node_names[route[j]]}')"
                    fast_candidates.append((base_obj - new_obj, new_routes, desc))

    # 4. Cross-Exchange Moves (Tail Swaps)
    for r1 in eval_routes:
        for r2 in range(r1 + 1, num_routes):
            for i in range(len(initial_routes[r1]) + 1):
                for j in range(len(initial_routes[r2]) + 1):
                    if (i == 0 and j == 0) or (i == len(initial_routes[r1]) and j == len(initial_routes[r2])):
                        continue
                    t1_d = sum(demands[n] for n in initial_routes[r1][i:])
                    t2_d = sum(demands[n] for n in initial_routes[r2][j:])
                    if not allow_overcapacity:
                        if route_loads[r1] - t1_d + t2_d > vehicle_capacities[r1]: continue
                        if route_loads[r2] - t2_d + t1_d > vehicle_capacities[r2]: continue
                    new_r1 = initial_routes[r1][:i] + initial_routes[r2][j:]
                    new_r2 = initial_routes[r2][:j] + initial_routes[r1][i:]
                    d_new1, lat_new1 = compute_route_metrics(new_r1)
                    d_new2, lat_new2 = compute_route_metrics(new_r2)
                    new_dists = list(route_dists)
                    new_dists[r1] = d_new1
                    new_dists[r2] = d_new2
                    new_obj = sum(new_dists) + makespan_coef * max(new_dists) + latency_coef * (base_latency - route_latencies[r1] - route_latencies[r2] + lat_new1 + lat_new2)
                    if new_obj < base_obj or allow_overcapacity:
                        new_routes = [list(rt) for rt in initial_routes]
                        new_routes[r1] = new_r1
                        new_routes[r2] = new_r2
                        desc = f"Exchange route tails between {truck_names[r1]} and {truck_names[r2]} to untangle paths"
                        fast_candidates.append((base_obj - new_obj, new_routes, desc))

    # Sort candidates by algebraic delta savings
    fast_candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Evaluate top 80 candidates with exact OR-Tools C++ solver
    all_candidates = []
    seen_states = set()
    for est_savings, new_routes, desc in fast_candidates[:80]:
        state_hash = tuple(tuple(r) for r in new_routes)
        if state_hash in seen_states: continue
        seen_states.add(state_hash)
        
        sol = routing.ReadAssignmentFromRoutes(new_routes, True)
        if sol:
            cost = sol.ObjectiveValue()
            savings = initial_cost - cost
            if savings > 0 or allow_overcapacity:
                all_candidates.append((savings, cost, desc, new_routes))

    all_candidates.sort(key=lambda x: x[0], reverse=True)
    top_moves = all_candidates[:50]

    # Guided Local Search Solve (3.0s timeout)
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.seconds = 3

    solution = routing.SolveFromAssignmentWithParameters(initial_solution, search_parameters)

    improved_routes = []
    if solution:
        for vehicle_id in range(data['num_vehicles']):
            index = routing.Start(vehicle_id)
            route = []
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                if node_index != data['depot']:
                    route.append(node_index)
                index = solution.Value(routing.NextVar(index))
            improved_routes.append(route)

    return initial_cost, top_moves, solution.ObjectiveValue() if solution else None, improved_routes, all_candidates

st.set_page_config(layout="wide")

# Custom CSS: Replace animated running/biking/swimming icons with a clean, professional circular spinner
st.markdown("""
<style>
[data-testid="stStatusWidget"] svg,
.stStatusWidget svg {
    display: none !important;
}

[data-testid="stStatusWidget"],
.stStatusWidget {
    display: inline-flex !important;
    align-items: center !important;
    gap: 8px !important;
}

[data-testid="stStatusWidget"]::before,
.stStatusWidget::before {
    content: "" !important;
    display: inline-block !important;
    width: 16px !important;
    height: 16px !important;
    border: 2.5px solid #cbd5e1 !important;
    border-top-color: #2563eb !important;
    border-radius: 50% !important;
    animation: customSpinner 0.75s linear infinite !important;
}

@keyframes customSpinner {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
</style>
""", unsafe_allow_html=True)

st.title("Fleet Route Optimization & Evaluation Platform")

st.markdown("""
Upload a CSV file containing scheduled deliveries to inspect baseline routes, evaluate candidate improvements, 
and execute multi-objective CVRP solvers.
""")

st.sidebar.header("Depot Location")
# Default Depot Location (Food Bank for NYC)
default_depot_lat = 40.80594755
default_depot_lng = -73.87299938

depot_lat = st.sidebar.number_input("Depot Latitude", value=default_depot_lat, format="%.8f")
depot_lng = st.sidebar.number_input("Depot Longitude", value=default_depot_lng, format="%.8f")

st.sidebar.header("Objective Weights")
st.sidebar.markdown(
    "Configure objective weights to balance route makespan and customer arrival latency against total fleet distance."
)
makespan_ui = st.sidebar.slider("Makespan Penalty (Route Balance)", min_value=1, max_value=5, value=1, step=1)
latency_ui = st.sidebar.slider("Latency Penalty (Early Arrivals)", min_value=1, max_value=5, value=1, step=1)

makespan_weight = makespan_ui * 10
latency_weight = latency_ui * 10

st.sidebar.header("Map Visualization")
render_street_paths = st.sidebar.toggle(
    "Render True Road Paths",
    value=True,
    help="Toggle ON to render turn-by-turn street network paths. Toggle OFF for straight-line connections."
)

st.sidebar.header("Routing Engine")
routing_engine = st.sidebar.selectbox(
    "Primary Routing Engine",
    ["OSRM (Fast General Road Routing)", "Valhalla (Truck Routing & Commercial Restrictions)"],
    index=0,
    help="OSRM provides fast, sub-second route geometries and distance tables. Valhalla enforces commercial vehicle parkway restrictions and bridge clearances."
)
use_osrm_engine = ("OSRM" in routing_engine)

st.sidebar.header("Execution Mode")
test_mode = st.sidebar.toggle("Test Mode (Limit search space)", value=False)
allow_overcapacity = st.sidebar.toggle("Allow Over-Capacity (Soft Constraint)", value=False)


uploaded_file = st.file_uploader("Upload Delivery Stops CSV", type=["csv"])

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    file_hash = hash(file_bytes)
    
    if 'current_file_hash' not in st.session_state or st.session_state['current_file_hash'] != file_hash:
        st.session_state['current_file_hash'] = file_hash
        if 'accepted_routes' in st.session_state:
            del st.session_state['accepted_routes']
        if 'accepted_moves_history' in st.session_state:
            del st.session_state['accepted_moves_history']
        if 'baseline_routes' in st.session_state:
            del st.session_state['baseline_routes']
        if 'rejected_moves' in st.session_state:
            del st.session_state['rejected_moves']
            
    if 'rejected_moves' not in st.session_state:
        st.session_state['rejected_moves'] = set()
        
    df = pd.read_csv(io.BytesIO(file_bytes))
    df.columns = df.columns.astype(str).str.strip()
    orig_columns = list(df.columns)
    had_upper_seq = ('Seq' in df.columns and 'seq' not in df.columns)
    
    # Safely handle 'Seq' vs 'seq' column casing
    if had_upper_seq:
        df = df.rename(columns={'Seq': 'seq'})
        
    with st.expander("View Raw Input Data", expanded=False):
        st.dataframe(df)
    
    required_cols = ['Name', 'Longitude', 'Latitude', 'Rt', 'seq', 'Food Pallets', 'Pet Food Pallets', 'Chemical Pallets']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(
            f"Missing required columns: {missing_cols}. Found columns: {list(df.columns)}"
        )
    else:
        # Pre-process: attach unique stop key to preserve all original columns and rows on export
        df['_stop_key'] = df['Latitude'].astype(str) + '_' + df['Longitude'].astype(str) + '_' + df['Name'].astype(str) + '_' + df['Rt'].astype(str)
            
        agg_funcs = {
            'Food Pallets': 'sum',
            'Pet Food Pallets': 'sum',
            'Chemical Pallets': 'sum',
            'seq': 'min'
        }
        if 'Weight' in df.columns:
            agg_funcs['Weight'] = 'sum'
            
        # Group by Latitude, Longitude, Name, AND Rt to ensure separate truck deliveries to the same customer are NOT merged!
        grouped = df.groupby(['Latitude', 'Longitude', 'Name', 'Rt', '_stop_key'], as_index=False).agg(agg_funcs)
        
        # Calculate Pallets using math.ceil
        def calc_pallets(row):
            return math.ceil(row['Food Pallets']) + math.ceil(row['Pet Food Pallets']) + math.ceil(row['Chemical Pallets'])
        
        grouped['Total Pallets'] = grouped.apply(calc_pallets, axis=1)
        
        # Sort by Rt and seq to build initial routes in correct order
        grouped = grouped.sort_values(by=['Rt', 'seq']).reset_index(drop=True)
        
        # Determine Depot from the sidebar inputs
        depot_coords = (depot_lat, depot_lng)

        with st.expander("Trucks Configuration", expanded=False):
            unique_rts = sorted(grouped['Rt'].dropna().unique())
            route_loads = grouped.groupby('Rt')['Total Pallets'].sum()
            
            uploaded_trucks = st.file_uploader("Upload Custom Trucks CSV (Defaults to dataset/trucks.csv)", type=["csv"], key="truck_uploader")
            
            trucks_source_df = None
            if uploaded_trucks is not None:
                try:
                    trucks_source_df = pd.read_csv(uploaded_trucks)
                except Exception as e:
                    st.error(f"Error reading uploaded trucks CSV: {e}")
            else:
                trucks_source_df = load_default_trucks_dataframe()

            if trucks_source_df is not None:
                truck_df = assign_trucks_to_routes(trucks_source_df, unique_rts, route_loads)
            else:
                truck_df = pd.DataFrame({
                    "Rt": unique_rts,
                    "Vehicle Name": unique_rts,
                    "Initial Load": [int(route_loads.get(rt, 0)) for rt in unique_rts],
                    "Capacity in Pallets": [25] * len(unique_rts)
                })

            # Sort the truck list by capacity descending, then by initial load descending
            truck_df = truck_df.sort_values(by=["Capacity in Pallets", "Initial Load"], ascending=[False, False]).reset_index(drop=True)

            st.markdown("Adjust the assignments and capacities:")
            edited_trucks = st.data_editor(truck_df, num_rows="dynamic", disabled=["Initial Load", "Rt"])

            
        truck_names = edited_trucks["Vehicle Name"].tolist()
        vehicle_capacities = [int(c) for c in edited_trucks["Capacity in Pallets"].tolist()]
        rt_to_vehicle = dict(zip(edited_trucks["Rt"], edited_trucks["Vehicle Name"]))
        
        # Build locations and demands lists directly from grouped rows (1 node per grouped delivery)
        locations = [depot_coords]
        demands = [0]
        node_names = ["Depot"]
        
        for _, row in grouped.iterrows():
            locations.append((row['Latitude'], row['Longitude']))
            demands.append(int(row['Total Pallets']))
            node_names.append(row['Name'])
                
        total_demand = sum(demands)
        total_capacity = sum(vehicle_capacities)
        
        cap_col1, cap_col2 = st.columns(2)
        cap_col1.metric("Total Pallets Needed (Demand)", total_demand)
        
        if total_capacity < total_demand:
            cap_col2.metric("Total Truck Capacity", total_capacity, "-Insufficient Capacity", delta_color="normal")
        else:
            cap_col2.metric("Total Truck Capacity", total_capacity)


        # Build initial routes based on the trucks configuration
        if 'accepted_routes' not in st.session_state:
            initial_routes = [[] for _ in truck_names]
            truck_name_to_idx = {name: idx for idx, name in enumerate(truck_names)}
            
            for row_idx, row in grouped.iterrows():
                node_id = row_idx + 1 # 1-indexed (0 is Depot)
                rt_name = row['Rt']
                if rt_name in rt_to_vehicle:
                    t_name = rt_to_vehicle[rt_name]
                    if t_name in truck_name_to_idx:
                        t_idx = truck_name_to_idx[t_name]
                        initial_routes[t_idx].append(node_id)
            st.session_state['accepted_routes'] = [list(r) for r in initial_routes]
            st.session_state['baseline_routes'] = [list(r) for r in initial_routes]
            st.session_state['accepted_moves_history'] = []
        else:
            initial_routes = st.session_state['accepted_routes']

        if 'accepted_moves_history' not in st.session_state:
            st.session_state['accepted_moves_history'] = []
        if 'baseline_routes' not in st.session_state:
            st.session_state['baseline_routes'] = [list(r) for r in initial_routes]

                    
        st.info("Parsing completed. Preparing routing engine...")
        
        # Check if parameters changed to avoid re-running when just interacting with UI
        current_params = (locations, demands, vehicle_capacities, initial_routes, makespan_weight, latency_weight, test_mode, allow_overcapacity, routing_engine)

        needs_optimization = ('last_run_params' not in st.session_state or st.session_state['last_run_params'] != current_params)
        
        if needs_optimization:
            touched_routes = st.session_state.get('touched_routes', None)
            prev_candidates = st.session_state.get('all_candidates_pool', None)
            with st.spinner("Running Google OR-Tools Guided Local Search and evaluating route improvements..."):
                res_tuple = solve_routing(
                    locations, demands, vehicle_capacities, initial_routes, truck_names, node_names,
                    makespan_weight, latency_weight, test_mode=test_mode,
                    allow_overcapacity=allow_overcapacity,
                    rejected_moves=st.session_state.get('rejected_moves', set()),
                    touched_routes=touched_routes,
                    previous_candidates=prev_candidates,
                    use_osrm=use_osrm_engine
                )
                if res_tuple[0] is not None:
                    init_c, t_moves, f_cost, imp_routes, all_cands = res_tuple
                    st.session_state['optimization_results'] = (init_c, t_moves, f_cost, imp_routes)
                    st.session_state['all_candidates_pool'] = all_cands
                else:
                    st.session_state['optimization_results'] = (None, None, None, None)
                st.session_state['touched_routes'] = None
                st.session_state['last_run_params'] = current_params

        init_cost, all_top_moves, final_cost, improved_routes = st.session_state.get('optimization_results', (None, None, None, None))
        
        if all_top_moves:
            rejected_set = st.session_state.get('rejected_moves', set())
            top_moves = [m for m in all_top_moves if m[2] not in rejected_set][:10]
        else:
            top_moves = []

        if 'background_prefetch_params' not in st.session_state or st.session_state['background_prefetch_params'] != current_params:
            st.session_state['background_prefetch_params'] = current_params
            if render_street_paths:
                start_background_geometry_prefetch(top_moves, improved_routes, locations, limit=10, use_osrm_first=use_osrm_engine)

        if init_cost is None:
            st.error("Failed to load the initial routes. The starting assignment violates constraints.")
            
            # Show specific capacity violations
            violations = []
            for i, route in enumerate(initial_routes):
                truck_name = truck_names[i]
                capacity = vehicle_capacities[i]
                load = sum(demands[node] for node in route)
                if load > capacity:
                    violations.append(f"**{truck_name}**: Load = {load} pallets, Capacity = {capacity} pallets (Over by {load - capacity})")
            
            if violations:
                st.warning("### Capacity Violations Found in Initial Data:")
                for v in violations:
                    st.write(f"- {v}")
                st.info("Please adjust the capacities in the 'Trucks Configuration' table above, or modify your CSV route assignments so they fit.")
            else:
                st.write("No capacity violations detected. Check other potential constraint violations.")
        else:
            if allow_overcapacity:
                violations = []
                for i, route in enumerate(improved_routes):
                    if not route: continue
                    truck_name = truck_names[i]
                    capacity = vehicle_capacities[i]
                    load = sum(demands[node] for node in route)
                    if load > capacity:
                        violations.append(f"**{truck_name}**: Load = {load} pallets, Capacity = {capacity} pallets (Over by {load - capacity})")
                if violations:
                    st.warning("### Warning: Some trucks are still over capacity (Soft Constraint Active)")
                    for v in violations:
                        st.write(f"- {v}")

            had_penalties = False
            total_pct = 0.0
            if init_cost and init_cost > 0:
                initial_violations = False
                for i, route in enumerate(initial_routes):
                    if not route: continue
                    if sum(demands[node] for node in route) > vehicle_capacities[i]:
                        initial_violations = True
                        break
                        
                had_penalties = allow_overcapacity and initial_violations

                if not had_penalties:
                    total_pct = ((init_cost - final_cost) / init_cost) * 100 if final_cost is not None else 0.0
                    st.metric("Total Route Improvement (OR-Tools Guided Local Search)", f"{total_pct:.1f}%")
                else:
                    st.metric("Penalty Score Improvement (Soft Constraints)", f"{init_cost - final_cost} points")
            else:
                st.write("No initial cost to compare.")

            st.subheader("Route Visualization")
            
            # Format Options: Full Fleet Optimization + Individual high-impact moves
            full_ortools_label = f"Full Fleet Optimization (OR-Tools Guided Local Search: {total_pct:.1f}% overall improvement)" if not had_penalties else "Full Fleet Optimization (OR-Tools Guided Local Search)"
            
            options = [full_ortools_label]
            if top_moves:
                for i, m in enumerate(top_moves):
                    if not had_penalties:
                        pct_m = ((m[0] / init_cost) * 100) if init_cost and init_cost > 0 else 0.0
                        options.append(f"Move {i+1} (Improves by {pct_m:.1f}%): {m[2]}")
                    else:
                        options.append(f"Move {i+1} (Fixes Capacity Penalty): {m[2]}")
                        
            selected_option = st.selectbox("Visualize a specific route improvement:", options)

            center_lat, center_lng = locations[0]
            m = folium.Map(location=[center_lat, center_lng], zoom_start=13)
            
            colors = ['#dc2626', '#2563eb', '#9333ea', '#ea580c', '#16a34a', '#0891b2',
                      '#db2777', '#4f46e5', '#ca8a04', '#059669', '#6366f1', '#0284c7',
                      '#b91c1c', '#475569', '#1e293b']

            # Helper function for edge-level diffing
            def diff_route_legs(r_orig, r_new):
                seq_orig = [0] + r_orig + [0] if r_orig else []
                seq_new = [0] + r_new + [0] if r_new else []
                legs_orig = [(seq_orig[i], seq_orig[i+1]) for i in range(len(seq_orig) - 1)]
                legs_new = [(seq_new[i], seq_new[i+1]) for i in range(len(seq_new) - 1)]
                set_orig = set(legs_orig)
                set_new = set(legs_new)
                
                common = [leg for leg in legs_orig if leg in set_new]
                removed = [leg for leg in legs_orig if leg not in set_new]
                added = [leg for leg in legs_new if leg not in set_orig]
                return common, removed, added

            if selected_option == full_ortools_label:
                show_proposed = st.toggle("Overlay Proposed Changes (Dotted Line)", value=True)
                
                # If proposed road geometry is missing, prefetch politely so full road curves show
                if render_street_paths and show_proposed and improved_routes:
                    if not is_move_geometry_ready(improved_routes, locations):
                        with st.spinner("Downloading exact turn-by-turn road curves for new OR-Tools routes..."):
                            prefetch_and_cache_routes_geometry(improved_routes, locations)
                
                # Check which routes were modified by OR-Tools
                ortools_changed_indices = []
                for i in range(len(initial_routes)):
                    if improved_routes and i < len(improved_routes) and initial_routes[i] != improved_routes[i]:
                        ortools_changed_indices.append(i)
                
                if ortools_changed_indices:
                    st.info(f"Google OR-Tools Guided Local Search found a global solution optimizing **{len(ortools_changed_indices)}** out of **{len(truck_names)}** trucks for a total fleet objective improvement of **{total_pct:.1f}%**.")
                    
                    if st.button("Accept Full OR-Tools Optimization", type="primary"):
                        import time
                        change_records = []
                        for idx in ortools_changed_indices:
                            t_name = truck_names[idx]
                            r_orig = initial_routes[idx]
                            r_new = improved_routes[idx]
                            orig_names = ["Depot"] + [f"{node_names[n]} (#{i+1})" for i, n in enumerate(r_orig)] + ["Depot"]
                            new_names = ["Depot"] + [f"{node_names[n]} (#{i+1})" for i, n in enumerate(r_new)] + ["Depot"]
                            change_records.append({
                                'truck_name': t_name,
                                'orig_sequence': " -> ".join(orig_names),
                                'new_sequence': " -> ".join(new_names),
                                'orig_load': sum(demands[n] for n in r_orig),
                                'new_load': sum(demands[n] for n in r_new),
                                'orig_stops': len(r_orig),
                                'new_stops': len(r_new)
                            })
                        history_entry = {
                            'step': len(st.session_state.get('accepted_moves_history', [])) + 1,
                            'description': f"Full OR-Tools Fleet Optimization ({len(ortools_changed_indices)} trucks re-routed, {total_pct:.1f}% fleet improvement)",
                            'changes': change_records,
                            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                        if 'accepted_moves_history' not in st.session_state:
                            st.session_state['accepted_moves_history'] = []
                        st.session_state['accepted_moves_history'].append(history_entry)
                        st.session_state['accepted_routes'] = [list(r) for r in improved_routes]
                        if 'last_run_params' in st.session_state:
                            del st.session_state['last_run_params']
                        st.rerun()
                
                # Map each node to its route and sequence position
                node_to_route_info = {}
                for route_idx, route in enumerate(initial_routes):
                    for seq_idx, n in enumerate(route):
                        node_to_route_info[n] = (route_idx, seq_idx + 1)

                # Add All Markers with Numbered Badges
                for idx, (lat, lng) in enumerate(locations):
                    if idx == 0:
                        folium.Marker(
                            [lat, lng],
                            tooltip="Depot (Start & End)",
                            popup="Depot (Start & End)",
                            icon=folium.DivIcon(
                                html='''<div style="background-color: #0f172a; color: #facc15; border: 2px solid white; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-size: 15px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.6);"></div>''',
                                icon_size=(28, 28),
                                icon_anchor=(14, 14)
                            )
                        ).add_to(m)
                    else:
                        demand = demands[idx]
                        orig_route, seq_num = node_to_route_info.get(idx, (0, 1))
                        marker_color = colors[orig_route % len(colors)]
                        tooltip_text = f"{node_names[idx]} | Stop #{seq_num} on Route {truck_names[orig_route]} | Pallets: {demand}"
                        folium.Marker(
                            [lat, lng],
                            tooltip=tooltip_text,
                            popup=tooltip_text,
                            icon=folium.DivIcon(
                                html=f'''<div style="background-color: {marker_color}; color: white; border: 2px solid white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.4);">{seq_num}</div>''',
                                icon_size=(24, 24),
                                icon_anchor=(12, 12)
                            )
                        ).add_to(m)

                # Plot All Original Routes (Always drawn, Solid, Real Road Paths)
                for route_idx, route in enumerate(initial_routes):
                    if not route:
                        continue
                    stop_sequence = [locations[0]] + [locations[n] for n in route] + [locations[0]]
                    route_coords = get_full_route_geometry(stop_sequence, use_road_geometry=render_street_paths)
                    color = colors[route_idx % len(colors)]
                    pl = folium.PolyLine(
                        route_coords,
                        color=color,
                        weight=5,
                        opacity=0.75,
                        tooltip=f"Original Route {route_idx} ({truck_names[route_idx]})",
                        popup=f"Original Route {route_idx} ({truck_names[route_idx]})"
                    )
                    pl.add_to(m)
                    PolyLineTextPath(pl, '        >        ', repeat=True, offset=6, attributes={'fill': color, 'fill-opacity': '0.8', 'font-weight': 'bold', 'font-size': '14'}).add_to(m)

                # Plot All Improved Routes (if toggled, Dotted, Real Road Paths)
                if show_proposed and improved_routes:
                    for route_idx, route in enumerate(improved_routes):
                        if not route:
                            continue
                        stop_sequence = [locations[0]] + [locations[n] for n in route] + [locations[0]]
                        route_coords = get_full_route_geometry(stop_sequence, use_road_geometry=render_street_paths)
                        color = colors[route_idx % len(colors)]
                        pl = folium.PolyLine(
                            route_coords,
                            color=color,
                            weight=4,
                            opacity=0.9,
                            dash_array='6, 8',
                            tooltip=f"Improved Route {route_idx} ({truck_names[route_idx]})",
                            popup=f"Improved Route {route_idx} ({truck_names[route_idx]})"
                        )
                        pl.add_to(m)
                        PolyLineTextPath(pl, '        >        ', repeat=True, offset=6, attributes={'fill': color, 'fill-opacity': '0.9', 'font-weight': 'bold', 'font-size': '14'}).add_to(m)
            else:
                # User selected a specific local move
                move_idx = int(selected_option.split(" ")[1]) - 1
                selected_new_routes = top_moves[move_idx][3]
                
                # Identify changed routes FIRST before buttons and rendering
                changed_route_indices = []
                for i in range(len(initial_routes)):
                    if initial_routes[i] != selected_new_routes[i]:
                        changed_route_indices.append(i)

                # --- ACCEPT / REJECT BUTTONS ---
                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if st.button("Accept Improvement", type="primary"):
                        import time
                        change_records = []
                        for idx in changed_route_indices:
                            t_name = truck_names[idx]
                            r_orig = initial_routes[idx]
                            r_new = selected_new_routes[idx]
                            orig_names = ["Depot"] + [f"{node_names[n]} (#{i+1})" for i, n in enumerate(r_orig)] + ["Depot"]
                            new_names = ["Depot"] + [f"{node_names[n]} (#{i+1})" for i, n in enumerate(r_new)] + ["Depot"]
                            change_records.append({
                                'truck_name': t_name,
                                'orig_sequence': " -> ".join(orig_names),
                                'new_sequence': " -> ".join(new_names),
                                'orig_load': sum(demands[n] for n in r_orig),
                                'new_load': sum(demands[n] for n in r_new),
                                'orig_stops': len(r_orig),
                                'new_stops': len(r_new)
                            })
                        
                        history_entry = {
                            'step': len(st.session_state.get('accepted_moves_history', [])) + 1,
                            'description': top_moves[move_idx][2],
                            'changes': change_records,
                            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
                        }
                        if 'accepted_moves_history' not in st.session_state:
                            st.session_state['accepted_moves_history'] = []
                        st.session_state['accepted_moves_history'].append(history_entry)

                        st.session_state['accepted_routes'] = selected_new_routes
                        if 'last_run_params' in st.session_state:
                            del st.session_state['last_run_params']
                        st.rerun()
                with b_col2:
                    if st.button("Reject Improvement"):
                        st.session_state['rejected_moves'].add(top_moves[move_idx][2])
                        st.rerun()
                        
                # Assign distinct bold base colors for each involved route
                highlight_colors = ['#dc2626', '#2563eb', '#9333ea', '#ea580c', '#16a34a', '#0891b2']
                local_colors = {idx: highlight_colors[i % len(highlight_colors)] for i, idx in enumerate(changed_route_indices)}

                # Display Visual Breadcrumb & Diff Summary Cards
                st.markdown("#### Route Improvement Sequence Comparison")
                for idx in changed_route_indices:
                    t_name = truck_names[idx]
                    r_orig = initial_routes[idx]
                    r_new = selected_new_routes[idx]
                    r_color = local_colors[idx]
                    
                    orig_names = ["Depot"] + [f"{node_names[n]} (#{i+1})" for i, n in enumerate(r_orig)] + ["Depot"]
                    new_names = ["Depot"] + [f"{node_names[n]} (#{i+1})" for i, n in enumerate(r_new)] + ["Depot"]
                    
                    orig_str = " -> ".join(orig_names)
                    new_str = " -> ".join(new_names)
                    
                    orig_pallets = sum(demands[n] for n in r_orig)
                    new_pallets = sum(demands[n] for n in r_new)
                    
                    st.markdown(f'''
                    <div style="border-left: 5px solid {r_color}; padding: 8px 12px; margin-bottom: 10px; background-color: #f8fafc; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        <div style="font-size: 15px; font-weight: bold; color: {r_color}; margin-bottom: 4px;">
                            Truck {t_name}
                            <span style="font-size: 12px; font-weight: normal; color: #64748b; margin-left: 8px;">
                                Load: {orig_pallets}p -> <strong>{new_pallets}p</strong> | Stops: {len(r_orig)} -> <strong>{len(r_new)}</strong>
                            </span>
                        </div>
                        <div style="font-size: 13px; color: #334155; line-height: 1.5;">
                            <span style="color: #64748b;"><strong>Original:</strong></span> {orig_str}<br/>
                            <span style="color: #059669;"><strong>Improved:</strong></span> {new_str}
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)
                st.write("---")

                # Map nodes to their before & after routes and sequences
                orig_node_info = {}
                for r_idx in changed_route_indices:
                    for s_idx, n in enumerate(initial_routes[r_idx]):
                        orig_node_info[n] = (r_idx, s_idx + 1)
                        
                new_node_info = {}
                for r_idx in changed_route_indices:
                    for s_idx, n in enumerate(selected_new_routes[r_idx]):
                        new_node_info[n] = (r_idx, s_idx + 1)

                # Nodes to draw: all nodes in affected routes + depot
                nodes_to_draw = {0}
                for idx in changed_route_indices:
                    nodes_to_draw.update(initial_routes[idx])
                    nodes_to_draw.update(selected_new_routes[idx])

                # Draw Markers
                for idx in nodes_to_draw:
                    lat, lng = locations[idx]
                    if idx == 0:
                        folium.Marker(
                            [lat, lng],
                            tooltip="Depot (Start & End)",
                            popup="Depot (Start & End)",
                            icon=folium.DivIcon(
                                html='''<div style="background-color: #0f172a; color: #facc15; border: 2px solid white; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-size: 15px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.6);"></div>''',
                                icon_size=(28, 28),
                                icon_anchor=(14, 14)
                            )
                        ).add_to(m)
                    else:
                        demand = demands[idx]
                        orig_rt, orig_seq = orig_node_info.get(idx, (None, None))
                        new_rt, new_seq = new_node_info.get(idx, (None, None))
                        
                        target_rt = new_rt if new_rt is not None else orig_rt
                        bg_color = local_colors.get(target_rt, '#2563eb')
                        
                        if orig_rt is not None and new_rt is not None and orig_rt != new_rt:
                            # Transferred between trucks
                            badge_text = f"#{orig_seq}->#{new_seq}"
                            tooltip_text = f"{node_names[idx]} | Transferred: Truck {truck_names[orig_rt]} (Stop #{orig_seq}) -> Truck {truck_names[new_rt]} (Stop #{new_seq}) | Pallets: {demand}"
                            html = f'''<div style="background-color: {bg_color}; color: white; border: 2px solid #f59e0b; border-radius: 12px; padding: 0 5px; height: 24px; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.5); white-space: nowrap;">{badge_text}</div>'''
                            icon = folium.DivIcon(html=html, icon_size=(54, 24), icon_anchor=(27, 12))
                        elif orig_seq is not None and new_seq is not None and orig_seq != new_seq:
                            # Re-sequenced / Inverted / Reversed on same truck
                            badge_text = f"#{orig_seq}->#{new_seq}"
                            tooltip_text = f"{node_names[idx]} | Position Changed: Stop #{orig_seq} -> Stop #{new_seq} on Truck {truck_names[target_rt]} | Pallets: {demand}"
                            html = f'''<div style="background-color: {bg_color}; color: white; border: 2px solid #f59e0b; border-radius: 12px; padding: 0 5px; height: 24px; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.5); white-space: nowrap;">{badge_text}</div>'''
                            icon = folium.DivIcon(html=html, icon_size=(54, 24), icon_anchor=(27, 12))
                        else:
                            # Unchanged sequence position
                            seq_display = new_seq if new_seq is not None else orig_seq
                            badge_text = f"{seq_display}"
                            tooltip_text = f"{node_names[idx]} | Stop #{seq_display} on Truck {truck_names[target_rt]} | Pallets: {demand}"
                            html = f'''<div style="background-color: {bg_color}; color: white; border: 2px solid white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.4);">{badge_text}</div>'''
                            icon = folium.DivIcon(html=html, icon_size=(24, 24), icon_anchor=(12, 12))
                            
                        folium.Marker([lat, lng], tooltip=tooltip_text, popup=tooltip_text, icon=icon).add_to(m)

                # Draw Route Legs by Type (Unchanged Common, Cut Removed, Added Improved)
                for idx in changed_route_indices:
                    r_color = local_colors[idx]
                    t_name = truck_names[idx]
                    r_orig = initial_routes[idx]
                    r_new = selected_new_routes[idx]
                    
                    legs_common, legs_removed, legs_added = diff_route_legs(r_orig, r_new)
                    
                    # 1. Unchanged Legs: Faint gray-tinted line
                    for u, v in legs_common:
                        leg_coords = get_full_route_geometry([locations[u], locations[v]], use_road_geometry=render_street_paths)
                        pl = folium.PolyLine(
                            leg_coords,
                            color='#94a3b8',
                            weight=3,
                            opacity=0.4,
                            tooltip=f"Unchanged: {node_names[u]} -> {node_names[v]} (Truck {t_name})"
                        )
                        pl.add_to(m)
                        PolyLineTextPath(pl, '        >        ', repeat=True, offset=5, attributes={'fill': '#94a3b8', 'fill-opacity': '0.4', 'font-weight': 'bold', 'font-size': '12'}).add_to(m)
                    
                    # 2. Removed Legs: Solid line in route's color (opacity 0.45)
                    for u, v in legs_removed:
                        leg_coords = get_full_route_geometry([locations[u], locations[v]], use_road_geometry=render_street_paths)
                        pl = folium.PolyLine(
                            leg_coords,
                            color=r_color,
                            weight=5,
                            opacity=0.45,
                            tooltip=f"Original (Cut): {node_names[u]} -> {node_names[v]} (Truck {t_name})"
                        )
                        pl.add_to(m)
                        PolyLineTextPath(pl, '        >        ', repeat=True, offset=6, attributes={'fill': r_color, 'fill-opacity': '0.45', 'font-weight': 'bold', 'font-size': '15'}).add_to(m)

                    # 3. Added Improved Legs: Thick Dotted line with bold directional arrows in route's color
                    for u, v in legs_added:
                        leg_coords = get_full_route_geometry([locations[u], locations[v]], use_road_geometry=render_street_paths)
                        pl = folium.PolyLine(
                            leg_coords,
                            color=r_color,
                            weight=6,
                            opacity=1.0,
                            dash_array='6, 8',
                            tooltip=f"Improved (New): {node_names[u]} -> {node_names[v]} (Truck {t_name})"
                        )
                        pl.add_to(m)
                        PolyLineTextPath(pl, '        >        ', repeat=True, offset=7, attributes={'fill': r_color, 'fill-opacity': '1.0', 'font-weight': 'bold', 'font-size': '18'}).add_to(m)

            st_folium(m, width=900, height=600, returned_objects=[])
            
            st.markdown("### Export Updated Routes")
            
            # Map each optimized stop back to its new route and sequence number
            stop_to_new_rt = {}
            stop_to_new_seq = {}
            for t_idx, route in enumerate(initial_routes):
                truck_name = truck_names[t_idx]
                for seq_idx, node in enumerate(route):
                    # Node index corresponds to grouped index (0 is depot, 1..N are stops)
                    if 1 <= node <= len(grouped):
                        stop_k = grouped.iloc[node - 1]['_stop_key']
                        stop_to_new_rt[stop_k] = truck_name
                        stop_to_new_seq[stop_k] = seq_idx + 1

            # Build export dataframe preserving 100% of original rows and columns
            export_df = df.copy()
            if '_stop_key' in export_df.columns:
                export_df['Rt'] = export_df['_stop_key'].map(stop_to_new_rt).fillna(export_df['Rt'])
                export_df['seq'] = export_df['_stop_key'].map(stop_to_new_seq).fillna(export_df['seq'])
                export_df = export_df.sort_values(by=['Rt', 'seq']).drop(columns=['_stop_key'])
                
            if had_upper_seq and 'seq' in export_df.columns:
                export_df = export_df.rename(columns={'seq': 'Seq'})
                
            # Guarantee exact original columns and ordering
            final_export_cols = [c for c in orig_columns if c in export_df.columns]
            export_df = export_df[final_export_cols]
            csv_str = export_df.to_csv(index=False)

            st.markdown("---")
            st.subheader("Export Routes & Change Log")

            accepted_hist = st.session_state.get('accepted_moves_history', [])
            report_text = generate_accepted_changes_report(
                accepted_hist,
                st.session_state.get('baseline_routes', initial_routes),
                initial_routes,
                truck_names,
                node_names,
                demands,
                file_label=uploaded_file.name if uploaded_file else "Routing Optimization"
            )

            if accepted_hist:
                with st.expander(f"View Accepted Changes History ({len(accepted_hist)} modification{'s' if len(accepted_hist) > 1 else ''} applied)", expanded=False):
                    for item in accepted_hist:
                        st.markdown(f"**Change #{item['step']}** ({item.get('timestamp', '')}): *{item['description']}*")
                        for c in item.get('changes', []):
                            st.caption(f"• **Truck {c['truck_name']}**: {c['orig_sequence']} -> **{c['new_sequence']}** (Load: {c['new_load']} plts)")

            exp_col1, exp_col2, exp_col3 = st.columns([1.2, 1, 1])
            with exp_col1:
                st.download_button(
                    label=f"Download Accepted Changes Log ({len(accepted_hist)} applied)",
                    data=report_text,
                    file_name="accepted_changes_log.txt",
                    mime="text/plain",
                    type="primary" if accepted_hist else "secondary"
                )
            with exp_col2:
                st.download_button(
                    label="Download Updated Routes CSV",
                    data=csv_str,
                    file_name="updated_routes.csv",
                    mime="text/csv"
                )
            with exp_col3:
                if accepted_hist:
                    if st.button("Revert All Accepted Changes"):
                        st.session_state['accepted_routes'] = [list(r) for r in st.session_state['baseline_routes']]
                        st.session_state['accepted_moves_history'] = []
                        st.rerun()


