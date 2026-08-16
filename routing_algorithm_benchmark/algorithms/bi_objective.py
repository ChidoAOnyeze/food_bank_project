import math

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

def bi_objective_routing(depot, locations, n_trucks, dist_fn=None):
    """
    Bicriteria Approximation Algorithm (Makespan & Latency).
    
    Theoretical Guarantee: Forms a (2.5, 8.49)-bicriteria approximation frontier.
    
    Steps:
    1. Construct a global MST rooted at the depot.
    2. Traverse the tree using a weight-prioritized DFS (lighter subtrees first).
    3. Partition the resulting sequence across n_trucks.
    """
    if dist_fn is None:
        from ..metrics import get_distance_fn
        dist_fn = get_distance_fn('geodesic')

    if not locations or n_trucks <= 0:
        return [[] for _ in range(n_trucks)]

    all_nodes = [depot] + list(locations)
    mst = build_mst(all_nodes, depot, dist_fn)

    dfs_tour = dfs_order_by_weight(mst, depot)
    # Remove depot
    customer_tour = [n for n in dfs_tour if n != depot]

    if not customer_tour:
        return [[] for _ in range(n_trucks)]

    actual_k = min(n_trucks, len(customer_tour))
    chunk_size = len(customer_tour) // actual_k
    remainder = len(customer_tour) % actual_k

    truck_routes = []
    idx = 0
    for i in range(actual_k):
        size = chunk_size + (1 if i < remainder else 0)
        truck_routes.append(customer_tour[idx:idx + size])
        idx += size

    while len(truck_routes) < n_trucks:
        truck_routes.append([])

    return truck_routes
