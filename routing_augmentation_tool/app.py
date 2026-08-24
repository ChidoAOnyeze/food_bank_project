
def generate_accepted_changes_report(accepted_history, baseline_routes, current_routes, truck_names, node_names, demands, file_label="Routing Optimization"):
    """
    Generates a clean, comprehensive text audit report describing all accepted route changes.
    """
    import time
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

import threading
import time
import requests
import json
import os
import streamlit as st
import pandas as pd
import numpy as np
import folium
from folium.plugins import PolyLineTextPath
import math
from streamlit_folium import st_folium
from geopy.distance import geodesic
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import itertools

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
        import time
        # Ask valhalla for a matrix of ONLY the locations that are missing data
        missing_list = list(missing_indices)
        req_locations = [{"lat": locations[idx][0], "lon": locations[idx][1]} for idx in missing_list]
        
        api_success_count = 0
        api_fail_count = 0
        
        def fetch_chunk_with_retry(s_chunk, t_chunk, idx_i, idx_j, allow_halving=True):
            s_count = 0
            f_count = 0
            delays = [0, 5, 10, 15] # 0 for the first attempt
            
            for attempt, delay in enumerate(delays):
                if delay > 0:
                    print(f"Retrying in {delay} seconds (Attempt {attempt + 1})...")
                    time.sleep(delay)
                    
                payload = {
                    "sources": s_chunk,
                    "targets": t_chunk,
                    "costing": "truck",
                    "units": "kilometers"
                }
                
                try:
                    resp = requests.post("https://valhalla1.openstreetmap.de/sources_to_targets", json=payload, timeout=20)
                    if resp.status_code == 200:
                        data = resp.json().get("sources_to_targets", [])
                        for r_idx, row in enumerate(data):
                            for c_idx, target in enumerate(row):
                                orig_i = idx_i[r_idx]
                                orig_j = idx_j[c_idx]
                                k = f"{locations[orig_i][0]},{locations[orig_i][1]}|{locations[orig_j][0]},{locations[orig_j][1]}"
                                
                                if target and target.get('distance') is not None:
                                    cache[k] = int(target['distance'] * 1000)
                                    s_count += 1
                                else:
                                    from geopy.distance import geodesic
                                    print(f"Warning: Unroutable path between {locations[orig_i]} and {locations[orig_j]}. Using penalized fallback.")
                                    cache[k] = int(geodesic(locations[orig_i], locations[orig_j]).meters * 1.5)
                                    f_count += 1
                        time.sleep(0.5) # Rate limit respect
                        return True, s_count, f_count
                    else:
                        print(f"Valhalla API Error {resp.status_code}: {resp.text}")
                except Exception as e:
                    print(f"Valhalla Request Failed: {e}")
                    
            # All 4 attempts failed
            if allow_halving:
                print("All 4 attempts failed. Halving batch size and repeating once...")
                mid_s = len(s_chunk) // 2
                mid_t = len(t_chunk) // 2
                
                s_chunks = [(s_chunk[:mid_s], idx_i[:mid_s]), (s_chunk[mid_s:], idx_i[mid_s:])] if mid_s > 0 else [(s_chunk, idx_i)]
                t_chunks = [(t_chunk[:mid_t], idx_j[:mid_t]), (t_chunk[mid_t:], idx_j[mid_t:])] if mid_t > 0 else [(t_chunk, idx_j)]
                
                for sc, i_i in s_chunks:
                    if not sc: continue
                    for tc, i_j in t_chunks:
                        if not tc: continue
                        success, scount, fcount = fetch_chunk_with_retry(sc, tc, i_i, i_j, allow_halving=False)
                        s_count += scount
                        f_count += fcount
                        if not success:
                            return False, s_count, f_count
                return True, s_count, f_count
            else:
                return False, s_count, f_count

        # Max matrix elements is 2500 (e.g. 50x50 = 2500).
        # We chunk into 40x40 batches = 1600 elements per request to be safe.
        chunk_size = 40
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
                    error_msg = "Valhalla API permanently failed after all retries and halving."
                    print(error_msg)
                    st.error(error_msg)
                    st.stop()
                    
        print(f"Valhalla API Summary -> Successful Routes: {api_success_count} | Failed/Fallback Routes: {api_fail_count}")
                
        # Save cache after all chunks succeed
        with open(VALHALLA_CACHE_FILE, "w") as f:
            json.dump(cache, f)

    # Now populate matrix
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i == j: continue
            k = f"{locations[i][0]},{locations[i][1]}|{locations[j][0]},{locations[j][1]}"
            if k in cache:
                distance_matrix[i][j] = cache[k]

            else:
                # Fallback to geodesic if API fails
                print(f"Warning: Cache miss for {locations[i]} to {locations[j]}. Using geodesic fallback.")
                distance_matrix[i][j] = int(geodesic(locations[i], locations[j]).meters)

                
    return distance_matrix


VALHALLA_GEOM_CACHE_FILE = "valhalla_geom_cache.json"

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

def save_geom_cache_async():
    def _async_writer(cache_copy):
        try:
            with open(VALHALLA_GEOM_CACHE_FILE, "w") as f:
                json.dump(cache_copy, f)
        except Exception:
            pass
    t = threading.Thread(target=_async_writer, args=(dict(_IN_MEMORY_GEOM_CACHE),), daemon=True)
    t.start()

def save_geom_cache():
    save_geom_cache_async()

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

def fetch_single_leg_geometry(p1, p2):
    """
    Fetches the true road path between p1 and p2 using Valhalla /route API.
    Tries 'truck' costing first, falls back to 'auto' costing if restricted.
    Returns list of (lat, lon) coordinates if successful, or None.
    """
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
                    if coords:
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

def get_road_path(p1, p2, use_road_geometry=True):
    if not use_road_geometry:
        return [p1, p2]
    geom_cache = load_geom_cache()
    k = f"{p1[0]},{p1[1]}|{p2[0]},{p2[1]}"
    if k in geom_cache:
        return geom_cache[k]
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

def start_background_geometry_prefetch(top_moves, locations, limit=5):
    if not top_moves or not locations:
        return
        
    def worker():
        if not top_moves:
            return
        total_to_fetch = min(limit, len(top_moves))
        print(f"--> [Background Prefetch] Starting geometry downloads for top {total_to_fetch} moves...")
        for m_idx, move in enumerate(top_moves[:limit]):
            try:
                candidate_routes = move[3]
                prefetch_and_cache_routes_geometry(candidate_routes, locations)
                time.sleep(0.2)
            except Exception as e:
                print(f"--> [Background Prefetch] Exception on move {m_idx}: {e}")
        save_geom_cache_async()
        print("--> [Background Prefetch] Completed! All top candidate moves are fully cached.")

    t = threading.Thread(target=worker, daemon=True)
    t.start()

def solve_routing(locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_coef=0, latency_coef=0, ui_container=None, test_mode=False, allow_overcapacity=False, rejected_moves=None, touched_routes=None, previous_candidates=None):
    # 1. Create Data Model
    data = {}
    num_nodes = len(locations)
    data['distance_matrix'] = get_valhalla_distance_matrix(locations)

    
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
        return data['distance_matrix'][from_node][to_node]

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

    # Incremental / Delta Neighborhood Evaluation:
    # 1. Retain candidates from previous evaluation that do NOT touch any modified route
    retained_moves = []
    if touched_routes is not None and previous_candidates:
        touched_set = set(touched_routes)
        for cand in previous_candidates:
            savings, cost, desc, _, affected_trucks, sub_routes = cand
            if touched_set.isdisjoint(set(affected_trucks)):
                # Reconstruct onto new initial_routes baseline
                reconstructed_routes = [list(r) for r in initial_routes]
                for t_idx, t_route in sub_routes.items():
                    reconstructed_routes[t_idx] = t_route
                retained_moves.append((savings, cost, desc, reconstructed_routes, affected_trucks, sub_routes))

    # 2. Generate local moves ONLY for the touched routes (or all routes on first run)
    moves = (generate_relocate_moves(initial_routes, truck_names, node_names, touched_routes) + 
             generate_swap_moves(initial_routes, truck_names, node_names, touched_routes) + 
             generate_2opt_moves(initial_routes, truck_names, node_names, touched_routes) + 
             generate_cross_exchange_moves(initial_routes, truck_names, node_names, touched_routes))

    all_candidates = list(retained_moves)
    seen_states = set(tuple(tuple(r) for r in m[3]) for m in retained_moves)
    total_improvements_found = len(retained_moves)
    
    for new_routes, desc, affected_trucks, sub_routes in moves:
        state_hash = tuple(tuple(r) for r in new_routes)
        if state_hash in seen_states:
            continue
        seen_states.add(state_hash)
        
        sol = routing.ReadAssignmentFromRoutes(new_routes, True)
        if sol:
            cost = sol.ObjectiveValue()
            savings = initial_cost - cost
            if savings > 0:
                total_improvements_found += 1
                all_candidates.append((savings, cost, desc, new_routes, affected_trucks, sub_routes))
                
                # Throttle UI updates
                if ui_container and total_improvements_found % 15 == 0:
                    ui_container.empty()
                    with ui_container.container():
                        import streamlit as st
                        st.write(f"*(Testing local neighborhood (incremental)... found **{total_improvements_found}** total improvements so far)*")
                        top_preview = sorted(all_candidates, key=lambda x: x[0], reverse=True)[:5]
                        for rank, (imp, c, d, _, _, _) in enumerate(top_preview):
                            pct = (imp / initial_cost) * 100 if initial_cost > 0 else 0
                            st.write(f"**{rank+1}.** {d} (Improves by {pct:.1f}%)")
                            
                if test_mode and total_improvements_found >= 200:
                    break
                            
    # Final flush to UI
    all_candidates.sort(key=lambda x: x[0], reverse=True)
    all_candidates = all_candidates[:50]
    top_moves = [(m[0], m[1], m[2], m[3]) for m in all_candidates]

    if ui_container:
        ui_container.empty()
        with ui_container.container():
            import streamlit as st
            st.write(f"*(Finished evaluating. Found **{total_improvements_found}** total improvements)*")
            for rank, (imp, c, d, _) in enumerate(top_moves[:5]):
                pct = (imp / initial_cost) * 100 if initial_cost > 0 else 0
                st.write(f"**{rank+1}.** {d} (Improves by {pct:.1f}%)")

    # Solve
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.seconds = 5

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
st.title("Route Optimization & GUI")

st.markdown("""
Upload a CSV file containing your deliveries. 
**Required columns**: `Name`, `Longitude`, `Latitude`, `Rt`, `seq`, `Food Pallets`, `Pet Food Pallets`, `Chemical Pallets`.
Optional columns: `Weight`
*The Depot location can be configured in the sidebar.*
""")

st.sidebar.header("Depot Location")
# HARDCODE DEFAULT DEPOT LOCATION HERE:
default_depot_lat = 40.80594755
default_depot_lng = -73.87299938

depot_lat = st.sidebar.number_input("Depot Latitude", value=default_depot_lat, format="%.8f")
depot_lng = st.sidebar.number_input("Depot Longitude", value=default_depot_lng, format="%.8f")

st.sidebar.header("Objective Weights")
st.sidebar.markdown(
    "Adjust these to see how they impact routing! Setting them to 0 focuses on pure distance (avoiding crossings). "
    "Setting them > 0 balances the routes but may result in visual crossings."
)
makespan_ui = st.sidebar.slider("Makespan Penalty (Balance Routes)", min_value=1, max_value=5, value=1, step=1)
latency_ui = st.sidebar.slider("Latency Penalty (Prioritize Early Arrivals)", min_value=1, max_value=5, value=1, step=1)

makespan_weight = makespan_ui * 10
latency_weight = latency_ui * 10

st.sidebar.header("Map Visualization")
render_street_paths = st.sidebar.toggle(
    "Render True Road Paths",
    value=True,
    help="Toggle ON to render turn-by-turn road curves and bridge navigation. Toggle OFF for fast straight-line spider routes between stops (app_valhalla mode)."
)

st.sidebar.header("Testing")
test_mode = st.sidebar.toggle("Test Mode (Limit to 200 improvements)", value=False)
allow_overcapacity = st.sidebar.toggle("Allow Over-Capacity (Soft Constraint)", value=False)


uploaded_file = st.file_uploader("Upload Stops CSV", type=["csv"])

if uploaded_file is not None:
    import io
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

    
    # Safely handle 'Seq' vs 'seq' column casing
    if 'Seq' in df.columns and 'seq' not in df.columns:
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
        # Pre-process: group by location to merge deliveries
            
        agg_funcs = {
            'Food Pallets': 'sum',
            'Pet Food Pallets': 'sum',
            'Chemical Pallets': 'sum',
            'seq': 'min'
        }
        if 'Weight' in df.columns:
            agg_funcs['Weight'] = 'sum'
            
        # Group by Latitude, Longitude, Name, AND Rt to ensure separate truck deliveries to the same customer are NOT merged!
        grouped = df.groupby(['Latitude', 'Longitude', 'Name', 'Rt'], as_index=False).agg(agg_funcs)
        
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
            
            uploaded_trucks = st.file_uploader("Upload Trucks CSV (Optional)", type=["csv"], key="truck_uploader")
            
            if uploaded_trucks is not None:
                try:
                    tdf = pd.read_csv(uploaded_trucks)
                    tdf.columns = tdf.columns.astype(str).str.strip()
                    if 'Vehicle' in tdf.columns and 'Pallet Capacity' in tdf.columns:
                        # Sort by capacity DESCENDING to assign the absolute largest trucks to the largest loads, maximizing slack
                        tdf = tdf.sort_values(by='Pallet Capacity', ascending=False)
                        available_trucks = tdf.to_dict('records')
                        
                        assigned_names = []
                        assigned_caps = []
                        
                        rts_by_load = sorted(unique_rts, key=lambda r: int(route_loads.get(r, 0)), reverse=True)
                        assignment_map = {}
                        
                        for rt in rts_by_load:
                            load = int(route_loads.get(rt, 0))
                            assigned = False
                            for i, t in enumerate(available_trucks):
                                if int(t['Pallet Capacity']) >= load:
                                    assignment_map[rt] = (t['Vehicle'], int(t['Pallet Capacity']))
                                    available_trucks.pop(i)
                                    assigned = True
                                    break
                            
                            if not assigned:
                                if available_trucks:
                                    # Pop index 0 to get the largest remaining truck (since the list is sorted descending)
                                    t = available_trucks.pop(0)
                                    assignment_map[rt] = (t['Vehicle'], int(t['Pallet Capacity']))
                                else:
                                    assignment_map[rt] = (f"Unassigned_Truck_for_{rt}", 25)
                                    
                        for rt in unique_rts:
                            assigned_names.append(assignment_map[rt][0])
                            assigned_caps.append(assignment_map[rt][1])
                            
                        truck_df = pd.DataFrame({
                            "Rt": unique_rts,
                            "Vehicle Name": assigned_names,
                            "Initial Load": [int(route_loads.get(rt, 0)) for rt in unique_rts],
                            "Capacity in Pallets": assigned_caps
                        })
                    else:
                        st.error("Trucks CSV must contain 'Vehicle' and 'Pallet Capacity' columns.")
                        truck_df = pd.DataFrame({
                            "Rt": unique_rts,
                            "Vehicle Name": unique_rts,
                            "Initial Load": [int(route_loads.get(rt, 0)) for rt in unique_rts],
                            "Capacity in Pallets": [25] * len(unique_rts)
                        })
                except Exception as e:
                    st.error(f"Error reading trucks CSV: {e}")
                    truck_df = pd.DataFrame({
                        "Rt": unique_rts,
                        "Vehicle Name": unique_rts,
                        "Initial Load": [int(route_loads.get(rt, 0)) for rt in unique_rts],
                        "Capacity in Pallets": [25] * len(unique_rts)
                    })
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
        current_params = (locations, demands, vehicle_capacities, initial_routes, makespan_weight, latency_weight, test_mode, allow_overcapacity)
        


        needs_optimization = ('last_run_params' not in st.session_state or st.session_state['last_run_params'] != current_params)
        
        selected_option = "Show Full OR-Tools Optimization"
        show_proposed = False
        top_moves = []
        improved_routes = []
        init_cost = 0 # Prevent NameError, but avoid triggering init_cost > 0 logic
        final_cost = 0
        
        if not needs_optimization:
            init_cost, all_top_moves, final_cost, improved_routes = st.session_state['optimization_results']
            if all_top_moves:
                rejected_set = st.session_state.get('rejected_moves', set())
                top_moves = [m for m in all_top_moves if m[2] not in rejected_set][:5]
            else:
                top_moves = []
            # Launch background worker for top 30 moves once per run
            if 'background_prefetch_params' not in st.session_state or st.session_state['background_prefetch_params'] != current_params:
                st.session_state['background_prefetch_params'] = current_params
                if render_street_paths:
                    start_background_geometry_prefetch(top_moves, locations, limit=5)



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

            if init_cost > 0:
                # Check if the initial routes actually had any capacity violations
                initial_violations = False
                for i, route in enumerate(initial_routes):
                    if not route: continue
                    if sum(demands[node] for node in route) > vehicle_capacities[i]:
                        initial_violations = True
                        break
                        
                had_penalties = allow_overcapacity and initial_violations

                if not had_penalties:
                    total_pct = ((init_cost - final_cost) / init_cost) * 100
                    st.metric("Total Route Improvement", f"{total_pct:.1f}%")
                else:
                    st.metric("Penalty Score Improvement (Soft Constraints)", f"{init_cost - final_cost} points")
            else:
                st.write("No initial cost to compare.")

            if not top_moves:
                st.write("No single-node moves improve the objective.")

            st.subheader("Route Visualization")
            
            # Selection box for improvements
            if top_moves:
                if not locals().get('had_penalties', False):
                    options = ["Show Full OR-Tools Optimization"] + [f"Move {i+1} (Improves by {((m[0] / init_cost) * 100 if init_cost > 0 else 0):.1f}%): {m[2]}" for i, m in enumerate(top_moves)]
                else:
                    options = ["Show Full OR-Tools Optimization"] + [f"Move {i+1} (Fixes Capacity Penalty): {m[2]}" for i, m in enumerate(top_moves)]
                selected_option = st.selectbox("Visualize a specific route improvement:", options)
            else:
                selected_option = "Show Full OR-Tools Optimization"

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

            if selected_option == "Show Full OR-Tools Optimization":
                show_proposed = st.toggle("Overlay Proposed Changes (Dotted Line)", value=True)
                # Prefetch all missing legs across both initial and improved routes in one super-batch call
                prefetch_and_cache_routes_geometry(initial_routes + improved_routes, locations)
                
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
                if show_proposed:
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
                        st.session_state['touched_routes'] = set(changed_route_indices)
                        if 'last_run_params' in st.session_state:
                            del st.session_state['last_run_params']
                        st.rerun()
                with b_col2:
                    if st.button("Reject Improvement"):
                        st.session_state['rejected_moves'].add(top_moves[move_idx][2])
                        st.rerun()
                        
                # Prefetch affected routes geometry in one batched call
                if render_street_paths:
                    prefetch_and_cache_routes_geometry([initial_routes[i] for i in changed_route_indices] + [selected_new_routes[i] for i in changed_route_indices], locations)
                        
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
            export_rows = []
            for t_idx, route in enumerate(initial_routes):
                truck_name = truck_names[t_idx]
                for seq_idx, node in enumerate(route):
                    lat, lng = locations[node]
                    name = node_names[node]
                    
                    match = grouped[(grouped['Latitude'] == lat) & (grouped['Longitude'] == lng) & (grouped['Name'] == name)]
                    if not match.empty:
                        row_dict = match.iloc[0].to_dict()
                        row_dict['Rt'] = truck_name
                        row_dict['seq'] = seq_idx + 1
                        export_rows.append(row_dict)
                    else:
                        export_rows.append({
                            "Name": name, "Latitude": lat, "Longitude": lng, "Rt": truck_name, "seq": seq_idx + 1
                        })
                        
            export_df = pd.DataFrame(export_rows)
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
                        if 'last_run_params' in st.session_state:
                            del st.session_state['last_run_params']
                        st.rerun()
            
            if needs_optimization:
                st.subheader("Searching for Improvements...")
                feed_container = st.empty()
                
                with st.spinner("Optimizing routes (map is usable while this runs)..."):
                    touched_routes = st.session_state.get('touched_routes', None)
                    prev_candidates = st.session_state.get('all_candidates_pool', None)
                    res_tuple = solve_routing(
                        locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_weight, latency_weight, ui_container=feed_container, test_mode=test_mode, allow_overcapacity=allow_overcapacity, rejected_moves=st.session_state.get('rejected_moves', set()), touched_routes=touched_routes, previous_candidates=prev_candidates
                    )
                    if res_tuple[0] is not None:
                        init_c, t_moves, f_cost, imp_routes, all_cands = res_tuple
                        st.session_state['optimization_results'] = (init_c, t_moves, f_cost, imp_routes)
                        st.session_state['all_candidates_pool'] = all_cands
                    else:
                        st.session_state['optimization_results'] = (None, None, None, None)
                    st.session_state['touched_routes'] = None
                st.session_state['last_run_params'] = current_params
                st.rerun()

