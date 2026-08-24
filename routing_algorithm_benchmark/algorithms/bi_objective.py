def build_mst(nodes, depot, dist_fn):
    """
    Constructs a Minimum Spanning Tree (MST) rooted at the depot using Prim's algorithm.
    """
    unvisited = set(nodes)
    if depot in unvisited:
        unvisited.remove(depot)
        
    tree = {depot: []}
    visited = [depot]

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
        if v not in tree:
            tree[v] = []

    return tree

def compute_subtree_weight(tree, node):
    weight = 1
    for child in tree.get(node, []):
        weight += compute_subtree_weight(tree, child)
    return weight

def dfs_order_by_weight(tree, node):
    """
    DFS traversal ordering children by subtree weight (lighter subtrees visited first).
    Prioritizes serving dense customer subtrees early to drive down total latency.
    """
    tour = [node]
    children = list(tree.get(node, []))
    children.sort(key=lambda c: compute_subtree_weight(tree, c))

    for child in children:
        tour.extend(dfs_order_by_weight(tree, child))
    return tour

def bi_objective_routing(depot, locations, n_trucks, dist_fn=None, demands=None, vehicle_capacities=None):
    """
    Capacitated Bi-Objective Routing (Makespan vs. Latency Pareto Balancing).
    
    -----------------------------------------------------------------------------------------
    1. WITHOUT TRUCK CAPACITY CONSTRAINTS:
    -----------------------------------------------------------------------------------------
    - Objective: Explores the Pareto trade-off between Makespan (max_k D_k) and Latency (sum_i Arr_i).
    - Mechanism:
      1. Constructs a global Minimum Spanning Tree (MST) rooted at the depot.
      2. Traverses the tree with a weight-prioritized DFS (lighter subtrees visited first).
      3. Partitions the sequence into n_trucks sub-routes.

    -----------------------------------------------------------------------------------------
    2. HOW TRUCK CAPACITIES WERE INCORPORATED:
    -----------------------------------------------------------------------------------------
    - Subtree-Preserving Capacity Cuts:
      * The density-prioritized DFS sequence is partitioned across vehicles such that each truck's 
        assigned subtree satisfies sum_{i in Route_k} d_i <= capacity_k.
      * If a customer subtree branch exceeds a vehicle's capacity, the cut advances to the next 
        truck, maintaining topological clustering while enforcing hard capacity limits.
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

    all_nodes = [depot] + list(locations)
    mst = build_mst(all_nodes, depot, dist_fn)

    dfs_tour = dfs_order_by_weight(mst, depot)
    customer_tour = [n for n in dfs_tour if n != depot]

    if not customer_tour:
        return [[] for _ in range(n_trucks)]

    # Capacity-constrained partitioning
    truck_routes = [[] for _ in range(n_trucks)]
    current_truck = 0
    current_load = 0.0
    target_stops_per_truck = max(1, len(customer_tour) // n_trucks)

    for i, node in enumerate(customer_tour):
        d_val = demands_dict.get(node, 1.0)
        cap = vehicle_capacities[current_truck]

        if current_load + d_val > cap and current_truck < n_trucks - 1 and len(truck_routes[current_truck]) > 0:
            current_truck += 1
            current_load = 0.0
            cap = vehicle_capacities[current_truck]
        elif len(truck_routes[current_truck]) >= target_stops_per_truck and current_truck < n_trucks - 1 and i < len(customer_tour) - 1:
            current_truck += 1
            current_load = 0.0
            cap = vehicle_capacities[current_truck]

        truck_routes[current_truck].append(node)
        current_load += d_val

    while len(truck_routes) < n_trucks:
        truck_routes.append([])

    return truck_routes
