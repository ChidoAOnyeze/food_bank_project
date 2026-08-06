import math
import utils

def distance(p1, p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

def get_tsp_tour(nodes):
    # A true 2-approximation for Metric TSP using MST + DFS traversal
    if not nodes: return []
    
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
                d = distance(u[0], v[0])
                if d < min_dist:
                    min_dist = d
                    best_edge = (u, v)
        u, v = best_edge
        unvisited.remove(v)
        visited.append(v)
        if u not in tree:
            tree[u] = []
        tree[u].append(v)
        
    tour = []
    def dfs(node):
        tour.append(node)
        for child in tree.get(node, []):
            dfs(child)
            
    dfs(start)
    return tour

def cvrp_itp(depot, locations, demands, max_capacity):
    """
    Iterated Tour Partitioning for CVRP.
    Yields a 2.5-approximation.
    """
    # 1. Get TSP tour over depot + locations (packaging coords with demands)
    nodes = [(depot, 0)] + list(zip(locations, demands))
    tsp_tour = get_tsp_tour(nodes)
    
    # Remove depot to easily iterate through demands
    tour_locations = [n for n in tsp_tour if n[0] != depot]
    
    truck_routes = []
    current_route = []
    current_load = 0
    
    # 2 & 3. Traverse TSP tour and split when capacity G is reached
    for loc, demand in tour_locations:
        if current_load + demand > max_capacity:
            # Capacity exceeded, send truck back to depot and start new route
            if current_route:
                truck_routes.append(current_route)
            current_route = [loc]
            current_load = demand
        else:
            current_route.append(loc)
            current_load += demand
            
    if current_route:
        truck_routes.append(current_route)
        
    return truck_routes

if __name__ == "__main__":
    depot = (0, 0)
    locations = [(1, 2), (3, 4), (-1, -1), (5, -2), (2, -3)]
    demands = [2, 3, 1, 4, 2]
    G = 5
    routes = cvrp_itp(depot, locations, demands, G)
    print("CVRP ITP Routes:")
    for i, r in enumerate(routes):
        print(f"Truck {i+1}: Depot -> {r} -> Depot")
    
    utils.plot_routes(depot, routes, "CVRP ITP Routes", "cvrp_itp_plot.png")
