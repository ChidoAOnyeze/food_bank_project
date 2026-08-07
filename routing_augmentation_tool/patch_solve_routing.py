import re

with open('app.py', 'r') as f:
    content = f.read()

# 1. Replace solve_routing signature and local search logic
new_solve_routing = """def solve_routing(locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_coef=0, latency_coef=0, ui_container=None):
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
    moves = (generate_relocate_moves(initial_routes, truck_names, node_names) + 
             generate_swap_moves(initial_routes, truck_names, node_names) + 
             generate_2opt_moves(initial_routes, truck_names, node_names) + 
             generate_cross_exchange_moves(initial_routes, truck_names, node_names))
    top_moves = []
    
    for new_routes, desc in moves:
        sol = routing.ReadAssignmentFromRoutes(new_routes, True)
        if sol:
            cost = sol.ObjectiveValue()
            savings = initial_cost - cost
            if savings > 0:
                if len(top_moves) < 5 or savings > top_moves[-1][0]:
                    top_moves.append((savings, cost, desc))
                    top_moves.sort(key=lambda x: x[0], reverse=True)
                    top_moves = top_moves[:5]
                    
                    if ui_container:
                        ui_container.empty()
                        with ui_container.container():
                            for rank, (imp, c, d) in enumerate(top_moves):
                                pct = (imp / initial_cost) * 100 if initial_cost > 0 else 0
                                import streamlit as st
                                st.write(f"**{rank+1}.** {d} (Improves by {pct:.1f}%)")

    # Solve
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.seconds = 5

    solution = routing.SolveFromAssignmentWithParameters(initial_solution, search_parameters)
"""

pattern = re.compile(r"def solve_routing\(.*?solution = routing.SolveFromAssignmentWithParameters\(initial_solution, search_parameters\)", re.DOTALL)
content = pattern.sub(new_solve_routing, content)

with open('app.py', 'w') as f:
    f.write(content)
