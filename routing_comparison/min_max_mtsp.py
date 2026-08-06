import math
import utils

def distance(p1, p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

def get_tsp_2_approx(nodes):
    # A true 2-approximation for Metric TSP using MST + DFS traversal
    if not nodes: return []
    
    # 1. Build MST using Prim's Algorithm
    unvisited = set(nodes)
    start = nodes[0]
    unvisited.remove(start)
    tree = {start: []}
    visited = [start]
    
    while unvisited:
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
        
    # 2. DFS Preorder Traversal to shortcut Eulerian tour
    tour = []
    def dfs(node):
        tour.append(node)
        for child in tree.get(node, []):
            dfs(child)
            
    dfs(start)
    return tour

def tour_partitioning_mtsp(depot, locations, n_trucks):
    """
    Approximation Algorithm for Min-Max mTSP.
    Yields a 2.5-approximation if using Christofides (using 2-approx here).
    """
    # 1. Get TSP tour over depot + locations
    all_nodes = [depot] + locations
    tsp_tour = get_tsp_2_approx(all_nodes)
    
    # Calculate total length of TSP tour
    total_length = 0
    for i in range(len(tsp_tour)-1):
        total_length += distance(tsp_tour[i], tsp_tour[i+1])
    
    segment_length = total_length / n_trucks
    
    # 3 & 4. Partition tour and assign to trucks
    truck_routes = [[] for _ in range(n_trucks)]
    current_truck = 0
    current_length = 0
    
    for i in range(len(tsp_tour)-1):
        u = tsp_tour[i]
        v = tsp_tour[i+1]
        dist = distance(u, v)
        
        # Skip the depot if it's strictly in the interior of the path mapping
        if u != depot:
            truck_routes[current_truck].append(u)
            
        current_length += dist
        if current_length >= segment_length and current_truck < n_trucks - 1:
            current_truck += 1
            current_length = 0
            
    # Add final node
    if tsp_tour[-1] != depot:
        truck_routes[-1].append(tsp_tour[-1])
        
    return truck_routes

if __name__ == "__main__":
    depot = (0, 0)
    locations = [(1, 2), (3, 4), (-1, -1), (5, -2), (2, -3)]
    n_trucks = 2
    routes = tour_partitioning_mtsp(depot, locations, n_trucks)
    print("Min-Max mTSP Routes:")
    for i, r in enumerate(routes):
        print(f"Truck {i+1}: Depot -> {r} -> Depot")
    
    utils.plot_routes(depot, routes, "Min-Max mTSP Routes", "min_max_mtsp_plot.png")
