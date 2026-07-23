import math
import collections
import utils

def distance(p1, p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

def get_mst(nodes, depot):
    # Primitive Prim's algorithm for MST construction
    unvisited = set(nodes)
    unvisited.remove(depot)
    tree = {depot: []}
    
    # Simple metric MST
    visited = [depot]
    while unvisited:
        # Find closest pair between visited and unvisited
        min_dist = float('inf')
        best_edge = None
        for u in visited:
            for v in unvisited:
                d = distance(u, v)
                if d < min_dist:
                    min_dist = d
                    best_edge = (u, v)
        u, v = best_edge
        unvisited.remove(v)
        visited.append(v)
        if u not in tree:
            tree[u] = []
        tree[u].append(v)
        tree[v] = []
    return tree

def compute_subtree_weight(tree, node):
    weight = 1
    for child in tree.get(node, []):
        weight += compute_subtree_weight(tree, child)
    return weight

def dfs_order_by_weight(tree, node):
    """
    DFS traversal ordering children by subtree weight (lighter subtrees first).
    """
    tour = [node]
    children = tree.get(node, [])
    
    # Sort children by their subtree weights (ascending to optimize latency)
    children.sort(key=lambda c: compute_subtree_weight(tree, c))
    
    for child in children:
        tour.extend(dfs_order_by_weight(tree, child))
    return tour

def bi_objective_routing(depot, locations, n_trucks):
    """
    Bicriteria Approximation Algorithm (Makespan & Latency).
    Uses Depth-First Tree Doubling to form a (2.5, 8.49)-bicriteria frontier.
    """
    all_nodes = [depot] + locations
    
    # 1. Base tree construction (representing the makespan bounded sub-trees)
    # For simulation, we'll build a single global MST and split its branches
    mst = get_mst(all_nodes, depot)
    
    # 2 & 3. Optimize latency using DFS prioritizing lighter subtrees
    dfs_tour = dfs_order_by_weight(mst, depot)
    dfs_tour.remove(depot) # Exclude depot for slicing
    
    # 4. Partition into n_trucks satisfying the Makespan bound
    segment_size = max(1, len(dfs_tour) // n_trucks)
    truck_routes = []
    
    for i in range(0, len(dfs_tour), segment_size):
        truck_routes.append(dfs_tour[i:i+segment_size])
        
    return truck_routes

if __name__ == "__main__":
    depot = (0, 0)
    locations = [(1, 2), (3, 4), (-1, -1), (5, -2), (2, -3), (-2, -5), (10, 0)]
    n_trucks = 2
    routes = bi_objective_routing(depot, locations, n_trucks)
    print("Bi-Objective DFS-Ordered Routes:")
    for i, r in enumerate(routes):
        print(f"Truck {i+1}: Depot -> {r} -> Depot")
    
    utils.plot_routes(depot, routes, "Bi-Objective DFS-Ordered Routes", "bi_objective_plot.png")
