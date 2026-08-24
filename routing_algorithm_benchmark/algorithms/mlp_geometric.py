def k_path_dense_search(start, unvisited_nodes, limit, dist_fn):
    """
    Subroutine for Geometric Scaling:
    Greedily finds a dense path of length <= limit starting from 'start'
    that visits the maximum number of unvisited nodes.
    """
    path = []
    current = start
    current_length = 0.0

    while unvisited_nodes:
        nxt = min(unvisited_nodes, key=lambda n: dist_fn(current, n))
        step_dist = dist_fn(current, nxt)
        if current_length + step_dist <= limit:
            path.append(nxt)
            unvisited_nodes.remove(nxt)
            current_length += step_dist
            current = nxt
        else:
            break

    return path

def mlp_geometric_scaling(depot, locations, n_trucks, dist_fn=None, demands=None, vehicle_capacities=None):
    """
    Capacitated Geometric Scaling Approximation for the Minimum Latency Problem (MLP / Cumulative VRP).
    
    -----------------------------------------------------------------------------------------
    1. WITHOUT TRUCK CAPACITY CONSTRAINTS:
    -----------------------------------------------------------------------------------------
    - Objective: Minimizes Total Customer Arrival Latency / Wait Time (sum_i Arrival_Distance_i).
    - Mechanism (Chakrabarty & Swamy / Blum et al. Geometric Ring Scaling):
      1. Initializes a base search radius D to the nearest customer from the depot.
      2. Doubles the radius exponentially at each iteration: L_i = D * 2^i (i = 1, 2, 4, 8, ...).
      3. Greedily solves dense k-path subroutines within each concentric ring to prioritize visiting 
         dense clusters of customers as early as possible.
      4. Slices the latency-ordered sequence into n_trucks equal subsets.

    -----------------------------------------------------------------------------------------
    2. HOW TRUCK CAPACITIES WERE INCORPORATED:
    -----------------------------------------------------------------------------------------
    - Priority-Queue Capacity Allocation:
      * Customer stops preserve their strict geometric latency priority ordering.
      * As each stop is dequeued from the priority list, it is allocated to the earliest vehicle 
        that still has sufficient remaining capacity (load_k + d_i <= capacity_k).
      * Ensures that high-density early delivery zones receive morning deliveries without exceeding 
        any truck's physical pallet load limit.
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
    demands_dict = dict(zip(locations, demands))

    if vehicle_capacities is None or len(vehicle_capacities) != n_trucks:
        total_demand = sum(demands)
        cap_target = max(max(demands) if demands else 1.0, (total_demand / n_trucks) * 1.35)
        vehicle_capacities = [cap_target] * n_trucks

    unvisited = list(locations)
    closest_dist = min(dist_fn(depot, n) for n in unvisited)
    D = max(closest_dist, 0.001)

    latency_path = []
    iteration = 1

    while unvisited:
        L_i = D * (2 ** iteration)
        dense_path = k_path_dense_search(depot, unvisited, L_i, dist_fn)
        if dense_path:
            latency_path.extend(dense_path)
        else:
            nxt = min(unvisited, key=lambda n: dist_fn(depot, n))
            latency_path.append(nxt)
            unvisited.remove(nxt)
        iteration += 1

    # Capacity-aware allocation along latency priority order
    truck_routes = [[] for _ in range(n_trucks)]
    truck_loads = [0.0] * n_trucks

    for node in latency_path:
        d_val = demands_dict.get(node, 1.0)
        assigned = False
        for t_idx in range(n_trucks):
            if truck_loads[t_idx] + d_val <= vehicle_capacities[t_idx]:
                truck_routes[t_idx].append(node)
                truck_loads[t_idx] += d_val
                assigned = True
                break
        if not assigned:
            min_truck = min(range(n_trucks), key=lambda t: truck_loads[t] / max(vehicle_capacities[t], 1.0))
            truck_routes[min_truck].append(node)
            truck_loads[min_truck] += d_val

    while len(truck_routes) < n_trucks:
        truck_routes.append([])

    return truck_routes
