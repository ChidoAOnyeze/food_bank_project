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

def solve_routing(locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_coef=0, latency_coef=0, ui_container=None, test_mode=False, allow_overcapacity=False):
    # 1. Create Data Model
    data = {}
    num_nodes = len(locations)
    data['distance_matrix'] = [[0]*num_nodes for _ in range(num_nodes)]
    for i in range(num_nodes):
        for j in range(num_nodes):
            if i != j:
                # distance in meters
                data['distance_matrix'][i][j] = int(geodesic(locations[i], locations[j]).meters)
    
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
**Required columns**: `Name`, `Longitude`, `Latitude`, `Rt`, `Food Pallets`, `Pet Food Pallets`, `Chemical Pallets`.
Optional columns: `Weight`, `seq`
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
    df = pd.read_csv(uploaded_file)
    
    # Safely handle 'Seq' vs 'seq' column casing
    if 'Seq' in df.columns and 'seq' not in df.columns:
        df = df.rename(columns={'Seq': 'seq'})
        
    with st.expander("View Raw Input Data", expanded=False):
        st.dataframe(df)
    
    required_cols = ['Name', 'Longitude', 'Latitude', 'Rt', 'Food Pallets', 'Pet Food Pallets', 'Chemical Pallets']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(
            f"Missing required columns: {missing_cols}. Found columns: {list(df.columns)}"
        )
    else:
        # Pre-process: group by location to merge deliveries
        if 'seq' not in df.columns:
            df['seq'] = df.index
            
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
            unique_rts = grouped['Rt'].unique()
            
            # Calculate assigned load per route from the grouped data
            route_loads = grouped.groupby('Rt')['Total Pallets'].sum()
            
            truck_df = pd.DataFrame({
                "Name": unique_rts,
                "Initial Load": [int(route_loads.get(rt, 0)) for rt in unique_rts],
                "Capacity in Pallets": [25] * len(unique_rts)
            })
            
            st.markdown("Adjust the capacities for each truck:")
            edited_trucks = st.data_editor(truck_df, num_rows="dynamic", disabled=["Initial Load"])
        truck_names = edited_trucks["Name"].tolist()
        vehicle_capacities = [int(c) for c in edited_trucks["Capacity in Pallets"].tolist()]
        
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
        initial_routes = [[] for _ in truck_names]
        truck_name_to_idx = {name: idx for idx, name in enumerate(truck_names)}
        
        for _, row in grouped.iterrows():
            coord = (row['Latitude'], row['Longitude'])
            node_id = coord_to_node[coord]
            if node_id == 0:
                continue
                
            t_name = row['Rt']
            if t_name in truck_name_to_idx:
                t_idx = truck_name_to_idx[t_name]
                # avoid consecutive duplicates
                if not initial_routes[t_idx] or initial_routes[t_idx][-1] != node_id:
                    initial_routes[t_idx].append(node_id)
                    
        st.info("Parsing completed. Preparing routing engine...")
        
        # Check if parameters changed to avoid re-running when just interacting with UI
        current_params = (locations, demands, vehicle_capacities, initial_routes, makespan_weight, latency_weight, test_mode, allow_overcapacity)
        
        if 'last_run_params' not in st.session_state or st.session_state['last_run_params'] != current_params:
            st.subheader("Live Feed: Top 5 Local Improvements on Initial Route")
            feed_container = st.empty()
            
            with st.spinner("Optimizing routes..."):
                results = solve_routing(
                    locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_weight, latency_weight, ui_container=feed_container, test_mode=test_mode, allow_overcapacity=allow_overcapacity
                )
            st.session_state['optimization_results'] = results
            st.session_state['last_run_params'] = current_params
        
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
                feed_container.write("No single-node moves improve the objective.")

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
                        folium.Marker([lat, lng], popup=f"{node_names[idx]} (Pallets: {demand})", icon=folium.Icon(color=marker_color, icon="info-sign")).add_to(m)

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
                        popup=f"Original Route {route_idx} ({truck_names[route_idx]})"
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
                            popup=f"Improved Route {route_idx} ({truck_names[route_idx]})"
                        ).add_to(m)
            else:
                # User selected a specific local move
                move_idx = int(selected_option.split(" ")[1]) - 1
                selected_new_routes = top_moves[move_idx][3]
                
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
                            folium.Marker([lat, lng], popup=f"{node_names[idx]} (Pallets: {demand})", icon=folium.Icon(color=marker_color, icon="info-sign")).add_to(m)

                # Draw ONLY the affected routes
                for idx in changed_route_indices:
                    r_color = local_colors[idx]
                    
                    # Solid original
                    r_orig = initial_routes[idx]
                    if r_orig:
                        route_coords_orig = [locations[0]] + [locations[n] for n in r_orig] + [locations[0]]
                        pl_orig = folium.PolyLine(route_coords_orig, color=r_color, weight=6, opacity=0.3, popup=f"Original {truck_names[idx]}")
                        pl_orig.add_to(m)
                        PolyLineTextPath(pl_orig, '        ►        ', repeat=True, offset=7, attributes={'fill': r_color, 'fill-opacity': '0.3', 'font-weight': 'bold', 'font-size': '18'}).add_to(m)
                    
                    # Dotted new
                    r_new = selected_new_routes[idx]
                    if r_new:
                        route_coords_new = [locations[0]] + [locations[n] for n in r_new] + [locations[0]]
                        pl_new = folium.PolyLine(route_coords_new, color=r_color, weight=5, opacity=1.0, dash_array='5, 10', popup=f"Improved {truck_names[idx]}")
                        pl_new.add_to(m)
                        PolyLineTextPath(pl_new, '        ►        ', repeat=True, offset=7, attributes={'fill': r_color, 'fill-opacity': '1.0', 'font-weight': 'bold', 'font-size': '18'}).add_to(m)

            st_folium(m, width=900, height=600)