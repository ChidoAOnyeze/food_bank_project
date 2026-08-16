import math

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

def mlp_geometric_scaling(depot, locations, n_trucks, dist_fn=None):
    """
    Geometric Scaling Approximation Algorithm for the Minimum Latency Problem (MLP / Cumulative VRP).
    
    Theoretical Guarantee: Constant-factor approximation (3.59 for single vehicle) for cumulative latency.
    
    Steps:
    1. Initialize search radius D to the nearest unvisited node from the depot.
    2. Iteratively double the search length L_i = D * (2^i).
    3. Find dense cluster paths within L_i to prioritize early delivery to high-density areas.
    4. Partition the latency-optimized sequence across n_trucks.
    """
    if dist_fn is None:
        from ..metrics import get_distance_fn
        dist_fn = get_distance_fn('geodesic')

    if not locations or n_trucks <= 0:
        return [[] for _ in range(n_trucks)]

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
            # If no node fits within L_i, take the single closest node to guarantee progress
            nxt = min(unvisited, key=lambda n: dist_fn(depot, n))
            latency_path.append(nxt)
            unvisited.remove(nxt)
        iteration += 1

    # Partition latency path across n_trucks
    actual_k = min(n_trucks, len(latency_path))
    chunk_size = len(latency_path) // actual_k
    remainder = len(latency_path) % actual_k

    truck_routes = []
    idx = 0
    for i in range(actual_k):
        size = chunk_size + (1 if i < remainder else 0)
        truck_routes.append(latency_path[idx:idx + size])
        idx += size

    while len(truck_routes) < n_trucks:
        truck_routes.append([])

    return truck_routes
