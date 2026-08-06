import streamlit as st
import pandas as pd
import numpy as np
import folium
import math
from streamlit_folium import st_folium
from geopy.distance import geodesic
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp
import itertools

def generate_relocate_moves(routes):
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
                    desc = f"Relocate node {node} from vehicle {r1} to vehicle {r2} at pos {j}"
                    moves.append((new_routes, desc))
    return moves

def generate_swap_moves(routes):
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
                    desc = f"Swap node {node1} (vehicle {r1}) with node {node2} (vehicle {r2})"
                    moves.append((new_routes, desc))
    return moves

def generate_2opt_moves(routes):
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
                desc = f"2-Opt (Uncross) on vehicle {r}: Reverse path between node {route[i]} and node {route[j]}"
                moves.append((new_routes, desc))
    return moves

def generate_cross_exchange_moves(routes):
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
                    
                    desc = f"Inter-route 2-Opt (Uncross Overlap) between vehicle {r1} (after pos {i}) and vehicle {r2} (after pos {j})"
                    moves.append((new_routes, desc))
    return moves

def solve_routing(locations, demands, vehicle_capacities, initial_routes, makespan_coef=0, latency_coef=0):
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
    routing.AddDimensionWithVehicleCapacity(demand_callback_index, 0, data['vehicle_capacities'], True, 'Capacity')

    # Read Initial Assignment
    initial_solution = routing.ReadAssignmentFromRoutes(initial_routes, True)
    if not initial_solution:
        return None, None, None, None

    initial_cost = initial_solution.ObjectiveValue()

    # Analyze local changes
    moves = (generate_relocate_moves(initial_routes) + 
             generate_swap_moves(initial_routes) + 
             generate_2opt_moves(initial_routes) + 
             generate_cross_exchange_moves(initial_routes))
    evaluated_moves = []
    for new_routes, desc in moves:
        sol = routing.ReadAssignmentFromRoutes(new_routes, True)
        if sol:
            cost = sol.ObjectiveValue()
            if initial_cost - cost > 0:
                evaluated_moves.append((initial_cost - cost, cost, desc))
    evaluated_moves.sort(key=lambda x: x[0], reverse=True)
    top_moves = evaluated_moves[:5]

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
default_depot_lat = 40.7128
default_depot_lng = -74.0060

depot_lat = st.sidebar.number_input("Depot Latitude", value=default_depot_lat, format="%.6f")
depot_lng = st.sidebar.number_input("Depot Longitude", value=default_depot_lng, format="%.6f")

st.sidebar.header("Objective Weights")
st.sidebar.markdown(
    "Adjust these to see how they impact routing! Setting them to 0 focuses on pure distance (avoiding crossings). "
    "Setting them > 0 balances the routes but may result in visual crossings."
)
makespan_ui = st.sidebar.slider("Makespan Penalty (Balance Routes)", min_value=1, max_value=5, value=1, step=1)
latency_ui = st.sidebar.slider("Latency Penalty (Prioritize Early Arrivals)", min_value=1, max_value=5, value=1, step=1)

makespan_weight = makespan_ui * 10
latency_weight = latency_ui * 10

uploaded_file = st.file_uploader("Upload Stops CSV", type=["csv"])

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    st.subheader("Input Data")
    st.dataframe(df.head(10))
    
    required_cols = ['Name', 'Longitude', 'Latitude', 'Rt', 'Food Pallets', 'Pet Food Pallets', 'Chemical Pallets']
    if not all(c in df.columns for c in required_cols):
        st.error(f"Missing required columns. Found columns: {list(df.columns)}")
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
        
        st.subheader("Trucks Configuration")
        unique_rts = grouped['Rt'].unique()
        truck_df = pd.DataFrame({
            "Name": unique_rts,
            "Capacity in Pallets": [20] * len(unique_rts)
        })
        
        st.markdown("Adjust the capacities for each truck:")
        edited_trucks = st.data_editor(truck_df, num_rows="dynamic")
        truck_names = edited_trucks["Name"].tolist()
        vehicle_capacities = [int(c) for c in edited_trucks["Capacity in Pallets"].tolist()]
        
        # Build locations and demands lists
        locations = [depot_coords]
        demands = [0]
        coord_to_node = {depot_coords: 0}
        
        for _, row in grouped.iterrows():
            coord = (row['Latitude'], row['Longitude'])
            if coord not in coord_to_node:
                coord_to_node[coord] = len(locations)
                locations.append(coord)
                demands.append(int(row['Total Pallets']))
                
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
                    
        st.info("Parsing completed. Running route optimization (this will take ~5 seconds)...")
        
        with st.spinner("Optimizing routes..."):
            init_cost, top_moves, final_cost, improved_routes = solve_routing(
                locations, demands, vehicle_capacities, initial_routes, makespan_weight, latency_weight
            )

        if init_cost is None:
            st.error("Failed to load the initial routes. Ensure initial assignment doesn't violate truck capacity!")
        else:
            if init_cost > 0:
                total_pct = ((init_cost - final_cost) / init_cost) * 100
                st.metric("Total Route Improvement", f"{total_pct:.1f}%")
            else:
                st.write("No initial cost to compare.")

            st.subheader("Top 5 Local Improvements on Initial Route")
            if top_moves:
                for i, (imp, cost, desc) in enumerate(top_moves):
                    pct = (imp / init_cost) * 100 if init_cost > 0 else 0
                    st.write(f"**{i+1}.** {desc} (Improves by {pct:.1f}%)")
            else:
                st.write("No single-node moves improve the objective.")

            st.subheader("Route Visualization")
            show_proposed = st.toggle("Overlay Proposed Changes (Dotted Line)", value=True)

            # Map Visualization
            center_lat, center_lng = locations[0]
            m = folium.Map(location=[center_lat, center_lng], zoom_start=13)
            
            colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred',
                      'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue',
                      'darkpurple', 'pink', 'lightblue', 'lightgreen',
                      'gray', 'black', 'lightgray']

            # Add Markers
            for idx, (lat, lng) in enumerate(locations):
                if idx == 0:
                    folium.Marker([lat, lng], popup="Depot", icon=folium.Icon(color="black", icon="star")).add_to(m)
                else:
                    demand = demands[idx]
                    folium.Marker([lat, lng], popup=f"Node {idx} (Pallets: {demand})", icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)

            # Plot Original Routes (Always drawn, Solid)
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

            # Plot Improved Routes (if toggled, Dotted)
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

            st_folium(m, width=900, height=600)
