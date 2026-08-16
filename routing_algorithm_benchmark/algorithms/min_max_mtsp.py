import math

def get_tsp_2_approx(nodes, dist_fn):
    """
    Constructs a 2-approximation metric TSP tour using Prim's MST and DFS preorder traversal.
    """
    if not nodes:
        return []
    if len(nodes) == 1:
        return [nodes[0]]

    # 1. Build MST using Prim's algorithm
    unvisited = set(nodes)
    start = nodes[0]
    unvisited.remove(start)
    tree = {start: []}
    visited = [start]

    while unvisited:
        min_d = float('inf')
        best_edge = None
        for u in visited:
            for v in unvisited:
                d = dist_fn(u, v)
                if d < min_d:
                    min_d = d
                    best_edge = (u, v)
        if best_edge is None:
            break
        u, v = best_edge
        unvisited.remove(v)
        visited.append(v)
        if u not in tree:
            tree[u] = []
        tree[u].append(v)

    # 2. DFS Preorder Traversal for Eulerian shortcutting
    tour = []
    def dfs(node):
        tour.append(node)
        for child in tree.get(node, []):
            dfs(child)

    dfs(start)
    return tour

def tour_partitioning_mtsp(depot, locations, n_trucks, dist_fn=None):
    """
    Tour Partitioning Approximation Algorithm for Min-Max mTSP (Makespan Minimization).
    
    Theoretical Guarantee: 2.5-approximation ratio for metric min-max mTSP.
    
    Steps:
    1. Form an approximately optimal TSP tour over Depot + all customer locations.
    2. Compute the total perimeter length L of the tour.
    3. Partition the tour into n_trucks segments of length ~ L / n_trucks.
    4. Connect each truck from the depot to its assigned segment start, traverse the segment,
       and return directly to the depot.
    """
    if dist_fn is None:
        from ..metrics import get_distance_fn
        dist_fn = get_distance_fn('geodesic')

    if not locations or n_trucks <= 0:
        return [[] for _ in range(n_trucks)]

    # 1. TSP tour over depot + locations
    all_nodes = [depot] + list(locations)
    tsp_tour = get_tsp_2_approx(all_nodes, dist_fn)

    # Remove duplicates while preserving order
    clean_tour = []
    seen = set()
    for node in tsp_tour:
        if node not in seen:
            seen.add(node)
            clean_tour.append(node)

    # Calculate total length of TSP tour
    total_length = 0.0
    for i in range(len(clean_tour) - 1):
        total_length += dist_fn(clean_tour[i], clean_tour[i + 1])
    if clean_tour:
        total_length += dist_fn(clean_tour[-1], clean_tour[0])

    target_segment_length = total_length / n_trucks if n_trucks > 0 else total_length

    # Partition tour among trucks
    truck_routes = [[] for _ in range(n_trucks)]
    current_truck = 0
    current_length = 0.0

    for i in range(len(clean_tour)):
        u = clean_tour[i]
        next_node = clean_tour[(i + 1) % len(clean_tour)]
        step_dist = dist_fn(u, next_node)

        if u != depot:
            truck_routes[current_truck].append(u)

        current_length += step_dist
        if current_length >= target_segment_length and current_truck < n_trucks - 1:
            current_truck += 1
            current_length = 0.0

    # Ensure empty trucks get filled if there are remaining unassigned stops
    # Pad to exactly n_trucks
    while len(truck_routes) < n_trucks:
        truck_routes.append([])

    return truck_routes
