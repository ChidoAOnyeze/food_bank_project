"""
improve_routing.py
This script takes a sub-optimal initial route provided by the user
and utilizes OR-Tools local search metaheuristics to improve it.
"""
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def create_data_model():
    """Stores the exact same data as the baseline."""
    data = {}
    data['distance_matrix'] = [
        [0, 2451, 713, 1018, 1631, 1374, 2408, 213, 2571, 875, 1420, 2145, 1972],
        [2451, 0, 1745, 1524, 831, 1240, 959, 2596, 403, 1589, 1374, 357, 579],
        [713, 1745, 0, 355, 920, 803, 1737, 851, 1858, 262, 940, 1453, 1260],
        [1018, 1524, 355, 0, 700, 862, 1395, 1123, 1584, 466, 1056, 1280, 987],
        [1631, 831, 920, 700, 0, 663, 1021, 1769, 949, 796, 879, 586, 371],
        [1374, 1240, 803, 862, 663, 0, 1681, 1551, 1765, 547, 225, 887, 999],
        [2408, 959, 1737, 1395, 1021, 1681, 0, 2493, 678, 1724, 1891, 1114, 701],
        [213, 2596, 851, 1123, 1769, 1551, 2493, 0, 2699, 1038, 1605, 2300, 2099],
        [2571, 403, 1858, 1584, 949, 1765, 678, 2699, 0, 1744, 1645, 653, 600],
        [875, 1589, 262, 466, 796, 547, 1724, 1038, 1744, 0, 679, 1272, 1162],
        [1420, 1374, 940, 1056, 879, 225, 1891, 1605, 1645, 679, 0, 1017, 1200],
        [2145, 357, 1453, 1280, 586, 887, 1114, 2300, 653, 1272, 1017, 0, 504],
        [1972, 579, 1260, 987, 371, 999, 701, 2099, 600, 1162, 1200, 504, 0],
    ]
    data['demands'] = [0, 1, 1, 2, 4, 2, 4, 8, 8, 1, 2, 1, 2]
    data['vehicle_capacities'] = [15, 15, 15, 15]
    data['num_vehicles'] = 4
    data['depot'] = 0
    return data

def print_solution(data, manager, routing, solution):
    """Prints solution on console."""
    print(f'Objective (Total Distance): {solution.ObjectiveValue()}\n')
    total_distance = 0
    total_load = 0
    for vehicle_id in range(data['num_vehicles']):
        index = routing.Start(vehicle_id)
        plan_output = f'Route for vehicle {vehicle_id}:\n'
        route_distance = 0
        route_load = 0
        while not routing.IsEnd(index):
            node_index = manager.IndexToNode(index)
            route_load += data['demands'][node_index]
            plan_output += f' {node_index} Load({route_load}) -> '
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            route_distance += routing.GetArcCostForVehicle(
                previous_index, index, vehicle_id)
        plan_output += f' {manager.IndexToNode(index)} Load({route_load})\n'
        plan_output += f'Distance of the route: {route_distance}m\n'
        plan_output += f'Load of the route: {route_load}\n'
        print(plan_output)
        total_distance += route_distance
        total_load += route_load
    print(f'Total distance of all routes: {total_distance}m')
    print(f'Total load of all routes: {total_load}')

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

def analyze_local_changes(routing, initial_routes, initial_cost, top_n=5):
    print("Analyzing local neighborhood for the best immediate improvements...")
    moves = generate_relocate_moves(initial_routes) + generate_swap_moves(initial_routes) + generate_2opt_moves(initial_routes)
    
    evaluated_moves = []
    for new_routes, desc in moves:
        sol = routing.ReadAssignmentFromRoutes(new_routes, True)
        if sol:
            cost = sol.ObjectiveValue()
            improvement = initial_cost - cost
            if improvement > 0:
                evaluated_moves.append((improvement, cost, desc, new_routes))
                
    evaluated_moves.sort(key=lambda x: x[0], reverse=True)
    
    if not evaluated_moves:
        print("No immediate local changes improve the objective.\n")
        return
        
    print(f"Top {min(top_n, len(evaluated_moves))} local changes:")
    for i, (improvement, cost, desc, _) in enumerate(evaluated_moves[:top_n]):
        print(f" {i+1}. {desc} -> New Cost: {cost} (Improvement: {improvement})")
    print()

def main():
    """Takes a suboptimal initial route and uses local search to improve it."""
    # 1. Instantiate the data problem
    data = create_data_model()

    # 2. Create the routing index manager and Routing Model
    manager = pywrapcp.RoutingIndexManager(len(data['distance_matrix']),
                                           data['num_vehicles'], data['depot'])
    routing = pywrapcp.RoutingModel(manager)

    # 3. Create and register a transit callback
    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data['distance_matrix'][from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # 3.b Add Distance dimension for makespan and latency
    routing.AddDimension(
        transit_callback_index,
        0,  # no slack
        30000, # maximum possible distance per vehicle
        True,  # start cumul to zero
        'Distance')
        
    distance_dimension = routing.GetDimensionOrDie('Distance')
    
    # Coefficients as variables
    makespan_coefficient = 1
    latency_coefficient = 1
    
    # Apply makespan coefficient
    distance_dimension.SetGlobalSpanCostCoefficient(makespan_coefficient)
    
    # Apply latency coefficient to all non-depot nodes
    for i in range(1, len(data['distance_matrix'])):
        node_index = manager.NodeToIndex(i)
        distance_dimension.SetCumulVarSoftUpperBound(node_index, 0, latency_coefficient)

    # 4. Add Capacity constraint
    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return data['demands'][from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  
        data['vehicle_capacities'],  
        True,  
        'Capacity')

    # 5. Define an initial, suboptimal route.
    # IMPORTANT: Do NOT include the depot in these lists! OR-Tools handles it.
    # This is an intentionally bad assignment to see if OR-Tools can fix it.
    initial_routes = [
        [7, 1],          # Vehicle 0 visits nodes 7 and 1
        [4, 3, 11, 2],   # Vehicle 1 visits nodes 4, 3, 11, and 2
        [9, 10, 5, 8],   # Vehicle 2 visits nodes 9, 10, 5, and 8
        [12, 6]          # Vehicle 3 visits nodes 12 and 6
    ]

    print("Loading initial sub-optimal routes into model...")
    # Read Assignment from routes. The second argument (True) means it handles partial assignments
    initial_solution = routing.ReadAssignmentFromRoutes(initial_routes, True)
    
    if initial_solution:
        initial_cost = initial_solution.ObjectiveValue()
        print("\n--- Initial Cost ---")
        print(f"Objective (Total Distance): {initial_cost}\n")
        
        # Analyze and print the best manual local moves
        analyze_local_changes(routing, initial_routes, initial_cost)
    else:
        print("Failed to load initial assignment.")
        return

    # 6. Set Search Parameters aggressively for improvement
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    # Apply powerful local search metaheuristic to escape local minima
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    
    # We give the solver 5 seconds to try 2-opt, relocate, exchange, and LNS
    search_parameters.time_limit.seconds = 5 

    # 7. Solve starting specifically from our assignment!
    print("Applying local search algorithms to improve the route (this will take 5 seconds)...\n")
    solution = routing.SolveFromAssignmentWithParameters(initial_solution, search_parameters)

    # Print the improved solution
    if solution:
        print("\n--- Improved Final Route ---")
        print_solution(data, manager, routing, solution)
    else:
        print("No solution found!")

if __name__ == '__main__':
    main()
