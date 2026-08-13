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

def generate_relocate_moves(routes, truck_names, node_names):
    moves = []
    num_routes = len(routes)
    for r1 in range(num_routes):
        for i in range(len(routes[r1])):
            node = routes[r1][i]
            for r2 in range(num_routes):
                insert_positions = len(routes[r2]) if r1 == r2 else len(routes[r2]) + 1
                for j in range(insert_positions):
                    if r1 == r2 and j == i:
                        continue
                    new_routes = [list(r) for r in routes]
                    new_routes[r1].pop(i)
                    new_routes[r2].insert(j, node)
                    
                    target_truck = truck_names[r2] if r1 != r2 else f"{truck_names[r2]} (different position)"
                    desc = f"Move '{node_names[node]}' from {truck_names[r1]} to {target_truck}"
                    moves.append((new_routes, desc))
    return moves

def generate_swap_moves(routes, truck_names, node_names):
    moves = []
    num_routes = len(routes)
    for r1 in range(num_routes):
        for i in range(len(routes[r1])):
            for r2 in range(r1, num_routes):
                start_j = i + 1 if r1 == r2 else 0
                for j in range(start_j, len(routes[r2])):
                    node1 = routes[r1][i]
                    node2 = routes[r2][j]
                    new_routes = [list(r) for r in routes]
                    new_routes[r1][i] = node2
                    new_routes[r2][j] = node1
                    desc = f"Swap the deliveries for '{node_names[node1]}' (on {truck_names[r1]}) and '{node_names[node2]}' (on {truck_names[r2]})"
                    moves.append((new_routes, desc))
    return moves

def generate_2opt_moves(routes, truck_names, node_names):
    moves = []
    num_routes = len(routes)
    for r in range(num_routes):
        route = routes[r]
        n = len(route)
        for i in range(n - 1):
            for j in range(i + 1, n):
                if j - i == 1:
                    continue # Already covered by adjacent swap
                new_routes = [list(rt) for rt in routes]
                new_routes[r] = route[:i] + route[i:j+1][::-1] + route[j+1:]
                desc = f"Reorder the stops on {truck_names[r]} (reverse the sequence between '{node_names[route[i]]}' and '{node_names[route[j]]}') to uncross the route"
                moves.append((new_routes, desc))
    return moves

def generate_cross_exchange_moves(routes, truck_names, node_names):
    moves = []
    num_routes = len(routes)
    for r1 in range(num_routes):
        for r2 in range(r1 + 1, num_routes):
            # Try swapping tails
            for i in range(len(routes[r1]) + 1):
                for j in range(len(routes[r2]) + 1):
                    # Skip if both tails are empty or both are full (just swaps whole routes)
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
                    moves.append((new_routes, desc))
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

def solve_routing(locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_coef=0, latency_coef=0, ui_container=None, test_mode=False, allow_overcapacity=False, rejected_moves=None):
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
        return None, None, None, None

    initial_cost = initial_solution.ObjectiveValue()

    # Analyze local changes
    moves = (generate_relocate_moves(initial_routes, truck_names, node_names) + 
             generate_swap_moves(initial_routes, truck_names, node_names) + 
             generate_2opt_moves(initial_routes, truck_names, node_names) + 
             generate_cross_exchange_moves(initial_routes, truck_names, node_names))
    top_moves = []
    total_improvements_found = 0
    seen_states = set()
    
    for new_routes, desc in moves:
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
                added_to_top = False
                
                if len(top_moves) < 5 or savings > top_moves[-1][0]:
                    top_moves.append((savings, cost, desc, new_routes))
                    top_moves.sort(key=lambda x: x[0], reverse=True)
                    top_moves = top_moves[:5]
                    added_to_top = True
                    
                # Throttle UI updates to either when top 5 changes, or every 10 improvements to avoid lag
                if ui_container and (added_to_top or total_improvements_found % 10 == 0):
                    ui_container.empty()
                    with ui_container.container():
                        import streamlit as st
                        st.write(f"*(Testing local neighborhood... found **{total_improvements_found}** total improvements so far)*")
                        for rank, (imp, c, d, _) in enumerate(top_moves):
                            pct = (imp / initial_cost) * 100 if initial_cost > 0 else 0
                            st.write(f"**{rank+1}.** {d} (Improves by {pct:.1f}%)")
                            
                if test_mode and total_improvements_found >= 200:
                    break
                            
    # Final flush to UI to ensure the exact final count is displayed
    if ui_container:
        ui_container.empty()
        with ui_container.container():
            import streamlit as st
            st.write(f"*(Finished evaluating. Found **{total_improvements_found}** total improvements)*")
            for rank, (imp, c, d, _) in enumerate(top_moves):
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

    return initial_cost, top_moves, solution.ObjectiveValue() if solution else None, improved_routes

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
        if 'rejected_moves' in st.session_state:
            del st.session_state['rejected_moves']
            
    if 'rejected_moves' not in st.session_state:
        st.session_state['rejected_moves'] = set()
        
    df = pd.read_csv(io.BytesIO(file_bytes))

    
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
            'Rt': 'first',
            'seq': 'min'
        }
        if 'Weight' in df.columns:
            agg_funcs['Weight'] = 'sum'
            
        grouped = df.groupby(['Latitude', 'Longitude', 'Name'], as_index=False).agg(agg_funcs)
        
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
        
        # Build locations and demands lists
        locations = [depot_coords]
        demands = [0]
        node_names = ["Depot"]
        coord_to_node = {depot_coords: 0}
        
        for _, row in grouped.iterrows():
            coord = (row['Latitude'], row['Longitude'])
            if coord not in coord_to_node:
                coord_to_node[coord] = len(locations)
                locations.append(coord)
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
            
            for _, row in grouped.iterrows():
                coord = (row['Latitude'], row['Longitude'])
                node_id = coord_to_node[coord]
                if node_id == 0:
                    continue
                    
                rt_name = row['Rt']
                if rt_name in rt_to_vehicle:
                    t_name = rt_to_vehicle[rt_name]
                    if t_name in truck_name_to_idx:
                        t_idx = truck_name_to_idx[t_name]
                        # avoid consecutive duplicates
                        if not initial_routes[t_idx] or initial_routes[t_idx][-1] != node_id:
                            initial_routes[t_idx].append(node_id)
            st.session_state['accepted_routes'] = initial_routes
        else:
            initial_routes = st.session_state['accepted_routes']

                    
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
            init_cost, top_moves, final_cost, improved_routes = st.session_state['optimization_results']



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
                st.warning("### 🚨 Capacity Violations Found in Initial Data:")
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
                    st.warning("### ⚠️ Some trucks are still over capacity (Soft Constraint Active)")
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
            
            colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred',
                      'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue',
                      'darkpurple', 'pink', 'lightblue', 'lightgreen',
                      'gray', 'black', 'lightgray']

            # Map each node to its original route for marker coloring
            node_to_route_idx = {}
            for route_idx, route in enumerate(initial_routes):
                for n in route:
                    node_to_route_idx[n] = route_idx

            if selected_option == "Show Full OR-Tools Optimization":
                show_proposed = st.toggle("Overlay Proposed Changes (Dotted Line)", value=True)
                
                # Add All Markers
                for idx, (lat, lng) in enumerate(locations):
                    if idx == 0:
                        folium.Marker([lat, lng], popup="Depot", icon=folium.Icon(color="black", icon="star")).add_to(m)
                    else:
                        demand = demands[idx]
                        orig_route = node_to_route_idx.get(idx, 0)
                        marker_color = colors[orig_route % len(colors)]
                        folium.Marker([lat, lng], tooltip=f"{node_names[idx]} (Pallets: {demand})", popup=f"{node_names[idx]} (Pallets: {demand})", icon=folium.Icon(color=marker_color, icon="info-sign")).add_to(m)

                # Plot All Original Routes (Always drawn, Solid)
                for route_idx, route in enumerate(initial_routes):
                    if not route:
                        continue
                    route_coords = [locations[0]] + [locations[n] for n in route] + [locations[0]]
                    color = colors[route_idx % len(colors)]
                    folium.PolyLine(
                        route_coords,
                        color=color,
                        weight=5,
                        opacity=0.8,
                        tooltip=f"Original Route {route_idx} ({truck_names[route_idx]})", popup=f"Original Route {route_idx} ({truck_names[route_idx]})"
                    ).add_to(m)

                # Plot All Improved Routes (if toggled, Dotted)
                if show_proposed:
                    for route_idx, route in enumerate(improved_routes):
                        if not route:
                            continue
                        route_coords = [locations[0]] + [locations[n] for n in route] + [locations[0]]
                        color = colors[route_idx % len(colors)]
                        folium.PolyLine(
                            route_coords,
                            color=color,
                            weight=4,
                            opacity=0.9,
                            dash_array='5, 10', # Dotted line
                            tooltip=f"Improved Route {route_idx} ({truck_names[route_idx]})", popup=f"Improved Route {route_idx} ({truck_names[route_idx]})"
                        ).add_to(m)
            else:

                # User selected a specific local move
                move_idx = int(selected_option.split(" ")[1]) - 1
                selected_new_routes = top_moves[move_idx][3]
                
                # --- NEW BUTTONS ---
                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if st.button("Accept Improvement", type="primary"):
                        st.session_state['accepted_routes'] = selected_new_routes
                        if 'last_run_params' in st.session_state:
                            del st.session_state['last_run_params']
                        st.rerun()
                with b_col2:
                    if st.button("Reject Improvement"):
                        st.session_state['rejected_moves'].add(top_moves[move_idx][2])
                        if 'last_run_params' in st.session_state:
                            del st.session_state['last_run_params']
                        st.rerun()
                st.write("---")
                # -------------------

                
                # Identify changed routes
                changed_route_indices = []
                for i in range(len(initial_routes)):
                    if initial_routes[i] != selected_new_routes[i]:
                        changed_route_indices.append(i)
                        
                # Assign collision-free colors for the involved routes
                local_colors = {}
                used_colors = set()
                for idx in changed_route_indices:
                    desired_color = colors[idx % len(colors)]
                    if desired_color in used_colors:
                        for fallback in colors:
                            if fallback not in used_colors:
                                desired_color = fallback
                                break
                    used_colors.add(desired_color)
                    local_colors[idx] = desired_color
                        
                # Add Markers ONLY for nodes in these routes, plus depot
                nodes_to_draw = {0}
                for idx in changed_route_indices:
                    nodes_to_draw.update(initial_routes[idx])
                    nodes_to_draw.update(selected_new_routes[idx])
                    
                for idx, (lat, lng) in enumerate(locations):
                    if idx in nodes_to_draw:
                        if idx == 0:
                            folium.Marker([lat, lng], popup="Depot", icon=folium.Icon(color="black", icon="star")).add_to(m)
                        else:
                            demand = demands[idx]
                            orig_route = node_to_route_idx.get(idx, 0)
                            marker_color = local_colors.get(orig_route, colors[orig_route % len(colors)])
                            folium.Marker([lat, lng], tooltip=f"{node_names[idx]} (Pallets: {demand})", popup=f"{node_names[idx]} (Pallets: {demand})", icon=folium.Icon(color=marker_color, icon="info-sign")).add_to(m)

                # Draw ONLY the affected routes
                for idx in changed_route_indices:
                    r_color = local_colors[idx]
                    
                    # Solid original
                    r_orig = initial_routes[idx]
                    if r_orig:
                        route_coords_orig = [locations[0]] + [locations[n] for n in r_orig] + [locations[0]]
                        pl_orig = folium.PolyLine(route_coords_orig, color=r_color, weight=6, opacity=0.3, tooltip=f"Original Route {truck_names[idx]}", popup=f"Original Route {truck_names[idx]}")
                        pl_orig.add_to(m)
                        PolyLineTextPath(pl_orig, '        ►        ', repeat=True, offset=7, attributes={'fill': r_color, 'fill-opacity': '0.3', 'font-weight': 'bold', 'font-size': '18'}).add_to(m)
                    
                    # Dotted new
                    r_new = selected_new_routes[idx]
                    if r_new:
                        route_coords_new = [locations[0]] + [locations[n] for n in r_new] + [locations[0]]
                        pl_new = folium.PolyLine(route_coords_new, color=r_color, weight=5, opacity=1.0, dash_array='5, 10', tooltip=f"Improved Route {truck_names[idx]}", popup=f"Improved Route {truck_names[idx]}")
                        pl_new.add_to(m)
                        PolyLineTextPath(pl_new, '        ►        ', repeat=True, offset=7, attributes={'fill': r_color, 'fill-opacity': '1.0', 'font-weight': 'bold', 'font-size': '18'}).add_to(m)


            st_folium(m, width=900, height=600)
            
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

            st.download_button(
                label="Download Updated Routes CSV",
                data=csv_str,
                file_name="updated_routes.csv",
                mime="text/csv"
            )
            
            if needs_optimization:
                st.subheader("Searching for Improvements...")
                feed_container = st.empty()
                
                with st.spinner("Optimizing routes (map is usable while this runs)..."):
                    results = solve_routing(
                        locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_weight, latency_weight, ui_container=feed_container, test_mode=test_mode, allow_overcapacity=allow_overcapacity, rejected_moves=st.session_state.get('rejected_moves', set())
                    )
                st.session_state['optimization_results'] = results
                st.session_state['last_run_params'] = current_params
                st.rerun()

