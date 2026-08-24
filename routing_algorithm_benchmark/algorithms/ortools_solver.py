from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

def ortools_routing(depot, locations, demands, n_trucks, dist_fn=None, time_limit_seconds=3, vehicle_capacities=None, balance_makespan=True):
    """
    Google OR-Tools Guided Local Search Metaheuristic for Multi-Objective CVRP.
    
    -----------------------------------------------------------------------------------------
    1. WITHOUT TRUCK CAPACITY CONSTRAINTS:
    -----------------------------------------------------------------------------------------
    - Objective: Solves Multi-Objective Vehicle Routing / mTSP for minimal distance and makespan balance.
    - Mechanism: Sets arc costs to integer road meters, adds distance span dimension for makespan.

    -----------------------------------------------------------------------------------------
    2. HOW TRUCK CAPACITIES WERE INCORPORATED:
    -----------------------------------------------------------------------------------------
    - Exact Constraint Programming Dimension:
      * Registers unary callback demand_callback(node) -> d_i.
      * Adds dedicated Capacity dimension with vehicle-specific capacity bounds:
          routing.AddDimensionWithVehicleCapacity(demand_callback, 0, vehicle_capacities, True, 'Capacity')
      * Guided Local Search strictly restricts all neighborhood operators (2-opt, Relocate, Cross-exchange) 
        to solutions that strictly satisfy vehicle pallet capacity limits.
    """
    if dist_fn is None:
        try:
            from ..metrics import get_distance_fn
        except (ImportError, ValueError):
            from metrics import get_distance_fn
        dist_fn = get_distance_fn('geodesic')

    if not locations or n_trucks <= 0:
        return [[] for _ in range(n_trucks)]

    all_nodes = [depot] + list(locations)
    num_nodes = len(all_nodes)
    
    # 1. Distance matrix in integer meters for OR-Tools integer solver
    dist_matrix = []
    for i in range(num_nodes):
        row = []
        for j in range(num_nodes):
            d = dist_fn(all_nodes[i], all_nodes[j])
            row.append(int(d * 1000)) # integer meters
        dist_matrix.append(row)

    manager = pywrapcp.RoutingIndexManager(num_nodes, n_trucks, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return dist_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Add distance dimension with makespan span cost so all trucks are utilized
    routing.AddDimension(
        transit_callback_index,
        0,
        10000000, # 10,000 km max span
        True,
        'Distance'
    )
    distance_dimension = routing.GetDimensionOrDie('Distance')
    if balance_makespan and n_trucks > 1:
        distance_dimension.SetGlobalSpanCostCoefficient(100)

    # Capacity dimension if demands are provided
    if demands:
        all_demands = [0] + [max(int(d * 100), 1) for d in demands]
        def demand_callback(from_index):
            from_node = manager.IndexToNode(from_index)
            return all_demands[from_node]

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        if vehicle_capacities:
            caps = [int(c * 100) for c in vehicle_capacities]
        else:
            total_scaled_demand = sum(all_demands)
            caps = [max(int((total_scaled_demand / n_trucks) * 1.5), 1000)] * n_trucks

        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,
            caps,
            True,
            'Capacity'
        )

    # Search parameters
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    search_parameters.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search_parameters.time_limit.seconds = time_limit_seconds

    solution = routing.SolveWithParameters(search_parameters)

    truck_routes = []
    if solution:
        for vehicle_id in range(n_trucks):
            index = routing.Start(vehicle_id)
            route = []
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                if node_index != 0:
                    route.append(all_nodes[node_index])
                index = solution.Value(routing.NextVar(index))
            truck_routes.append(route)
    else:
        truck_routes = [[] for _ in range(n_trucks)]

    return truck_routes
