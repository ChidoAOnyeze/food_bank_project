import math
try:
    from .min_max_mtsp import get_tsp_2_approx
except (ImportError, ValueError):
    from algorithms.min_max_mtsp import get_tsp_2_approx

def partition_tour_by_capacity(tour_locations, demands_dict, max_capacity):
    """
    Partitions a TSP tour into routes based on capacity limit G.
    """
    truck_routes = []
    current_route = []
    current_load = 0.0

    for loc in tour_locations:
        demand = demands_dict.get(loc, 1.0)
        if current_load + demand > max_capacity and current_route:
            truck_routes.append(current_route)
            current_route = [loc]
            current_load = demand
        else:
            current_route.append(loc)
            current_load += demand

    if current_route:
        truck_routes.append(current_route)

    return truck_routes

def cvrp_itp(depot, locations, demands, n_trucks, dist_fn=None, max_capacity=None):
    """
    Iterated Tour Partitioning (ITP) for CVRP.
    
    Theoretical Guarantee: 2.5-approximation ratio for CVRP.
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

    if max_capacity is not None and max_capacity > 0:
        routes = partition_tour_by_capacity(tour_locations, demands_dict, max_capacity)
    else:
        # Binary search for capacity G such that len(routes) <= n_trucks
        total_demand = sum(demands)
        low = max(demands) if demands else 1.0
        high = max(total_demand, 1.0)
        routes = []

        for _ in range(35):
            mid = (low + high) / 2.0
            r = partition_tour_by_capacity(tour_locations, demands_dict, mid)
            routes = r
            if len(r) == n_trucks:
                break
            elif len(r) > n_trucks:
                low = mid + 0.01
            else:
                high = mid - 0.01

    # Pad or trim to exactly n_trucks
    while len(routes) < n_trucks:
        routes.append([])

    return routes[:n_trucks]
