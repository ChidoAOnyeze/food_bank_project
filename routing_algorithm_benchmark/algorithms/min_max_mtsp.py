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

def tour_partitioning_mtsp(depot, locations, n_trucks, dist_fn=None, demands=None, vehicle_capacities=None):
    """
    Tour Partitioning Algorithm for Min-Max mTSP (Makespan & Capacity Optimization).
    
    -----------------------------------------------------------------------------------------
    1. WITHOUT TRUCK CAPACITY CONSTRAINTS:
    -----------------------------------------------------------------------------------------
    - Objective: Minimizes Makespan (max_k D_k), the driving distance of the single longest route.
    - Mechanism (Frederickson et al. 2.5-approximation):
      1. Builds a 2-approximation metric TSP tour over Depot + all customer stops using Prim's MST.
      2. Computes the total perimeter length L of the global TSP tour.
      3. Sets a target segment length per truck: L_target = L / n_trucks.
      4. Partitions the tour into n_trucks equal continuous segments, connecting each truck from 
         the depot to its assigned segment start, traversing the segment, and returning to the depot.

    -----------------------------------------------------------------------------------------
    2. HOW TRUCK CAPACITIES WERE INCORPORATED:
    -----------------------------------------------------------------------------------------
    - As the algorithm traces along the perimeter of the global TSP tour, it tracks both:
        * current_length (cumulative distance)
        * current_load (cumulative pallet demand)
    - Capacitated Cut Boundary: For each customer stop with demand d_i:
        * If adding d_i exceeds the assigned truck's capacity (current_load + d_i > capacity_k),
          the route for truck k is immediately closed at the previous stop, and the remaining 
          stops advance to the next available truck.
        * If within capacity, the route continues until reaching L_target to maintain makespan balance.
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
        avg_cap = max(max(demands) if demands else 1.0, (sum(demands) / n_trucks) * 1.35)
        vehicle_capacities = [avg_cap] * n_trucks

    # 1. TSP tour over depot + locations
    all_nodes = [depot] + list(locations)
    tsp_tour = get_tsp_2_approx(all_nodes, dist_fn)

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

    # Partition tour among trucks respecting both target distance and capacity
    customer_nodes = [u for u in clean_tour if u != depot]
    truck_routes = [[] for _ in range(n_trucks)]
    current_truck = 0
    current_length = 0.0
    current_load = 0.0

    for i, u in enumerate(customer_nodes):
        d_val = demands_dict.get(u, 1.0)
        cap = vehicle_capacities[current_truck]
        next_node = customer_nodes[(i + 1) % len(customer_nodes)]
        step_dist = dist_fn(u, next_node)

        # If adding this node exceeds capacity and we have another truck available, advance truck
        if current_load + d_val > cap and current_truck < n_trucks - 1 and len(truck_routes[current_truck]) > 0:
            current_truck += 1
            current_length = 0.0
            current_load = 0.0
            cap = vehicle_capacities[current_truck]

        truck_routes[current_truck].append(u)
        current_load += d_val
        current_length += step_dist

        # If reached target length and within capacity, advance to next truck for makespan balance
        if current_length >= target_segment_length and current_truck < n_trucks - 1 and i < len(customer_nodes) - 1:
            current_truck += 1
            current_length = 0.0
            current_load = 0.0

    while len(truck_routes) < n_trucks:
        truck_routes.append([])

    return truck_routes
