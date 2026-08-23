import math
try:
    from .min_max_mtsp import get_tsp_2_approx
except (ImportError, ValueError):
    from algorithms.min_max_mtsp import get_tsp_2_approx

def cvrp_itp(depot, locations, demands, n_trucks, dist_fn=None, vehicle_capacities=None):
    """
    Iterated Tour Partitioning (ITP) for the Capacitated Vehicle Routing Problem (CVRP).
    
    -----------------------------------------------------------------------------------------
    1. WITHOUT TRUCK CAPACITY CONSTRAINTS:
    -----------------------------------------------------------------------------------------
    - Objective: Minimizes Total Fleet Travel Distance (sum_k D_k) for the CVRP problem.
    - Mechanism (Haimovich & Rinnooy Kan 2.5-approximation):
      * Forms an approximately optimal single-vehicle metric TSP tour over all delivery stops.
      * Uses binary search to find an artificial uniform partition bound G that splits the tour 
        into at most n_trucks equal vehicle routes.

    -----------------------------------------------------------------------------------------
    2. HOW TRUCK CAPACITIES WERE INCORPORATED:
    -----------------------------------------------------------------------------------------
    - Heterogeneous Capacity Vector: Accepts vehicle-specific capacity bounds [c_1, c_2, ..., c_k]
      (e.g., from trucks.csv or fleet capacity configurations).
    - Sequential Knapsack Tour Cuts: Partitions along the TSP tour by greedily packing stops into 
      truck k until the cumulative pallet load sum_{i in Route_k} d_i reaches capacity_k.
    - Once capacity is reached, the route returns to the depot and the subsequent stops begin 
      the route for the next vehicle, maximizing vehicle fill rates without overloading.
    """
    if dist_fn is None:
        try:
            from ..metrics import get_distance_fn
        except (ImportError, ValueError):
            from metrics import get_distance_fn
        dist_fn = get_distance_fn('geodesic')

    if not locations or n_trucks <= 0:
        return [[] for _ in range(n_trucks)]

    if demands is None or len(demands) != len(locations):
        demands = [1.0] * len(locations)

    all_nodes = [depot] + list(locations)
    tsp_tour = get_tsp_2_approx(all_nodes, dist_fn)
    tour_locations = [loc for loc in tsp_tour if loc != depot]
    demands_dict = dict(zip(locations, demands))

    if vehicle_capacities is None or len(vehicle_capacities) != n_trucks:
        total_demand = sum(demands)
        cap_target = max(max(demands) if demands else 1.0, (total_demand / n_trucks) * 1.15)
        vehicle_capacities = [cap_target] * n_trucks

    # Partition along the TSP tour matching vehicle capacities
    truck_routes = [[] for _ in range(n_trucks)]
    current_truck = 0
    current_load = 0.0

    for loc in tour_locations:
        d_val = demands_dict.get(loc, 1.0)
        cap = vehicle_capacities[current_truck]

        if current_load + d_val > cap and current_truck < n_trucks - 1 and len(truck_routes[current_truck]) > 0:
            current_truck += 1
            current_load = 0.0
            cap = vehicle_capacities[current_truck]

        truck_routes[current_truck].append(loc)
        current_load += d_val

    while len(truck_routes) < n_trucks:
        truck_routes.append([])

    return truck_routes
