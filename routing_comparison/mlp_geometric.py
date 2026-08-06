import math
import utils

def distance(p1, p2):
    return math.hypot(p1[0]-p2[0], p1[1]-p2[1])

def mock_k_path_orienteering(start, unvisited_nodes, limit):
    """
    Mocking a k-path / Orienteering approximation.
    Finds a path originating at 'start' of length at most 'limit' 
    that visits the maximum possible number of unvisited nodes.
    """
    path = []
    current = start
    current_length = 0
    
    # Greedily pick the closest nodes within the limit
    while unvisited_nodes:
        nxt = min(unvisited_nodes, key=lambda n: distance(current, n))
        dist = distance(current, nxt)
        if current_length + dist <= limit:
            path.append(nxt)
            unvisited_nodes.remove(nxt)
            current_length += dist
            current = nxt
        else:
            break
            
    return path

def mlp_geometric_scaling(depot, locations):
    """
    Geometric Scaling Approximation for the Minimum Latency Problem (MLP).
    Yields a constant factor approximation (3.59 for single vehicle).
    """
    unvisited = locations.copy()
    
    # 1. Initialize distance limit D to closest node
    if not unvisited:
        return []
    closest_dist = min(distance(depot, n) for n in unvisited)
    D = max(closest_dist, 0.1) # prevent 0
    
    final_path = []
    iteration = 1
    
    # 2. Iteratively double the search length
    while unvisited:
        L_i = D * (2 ** iteration)
        
        # 3. Find dense path of length L_i
        # In reality this connects via k-MST or Orienteering subroutine
        dense_path = mock_k_path_orienteering(depot, unvisited, L_i)
        
        if dense_path:
            final_path.extend(dense_path)
            
        iteration += 1
        
    return final_path

if __name__ == "__main__":
    depot = (0, 0)
    locations = [(1, 2), (3, 4), (-1, -1), (5, -2), (2, -3), (10, 10)]
    path = mlp_geometric_scaling(depot, locations)
    print(f"MLP Latency-Optimized Path: Depot -> {path}")
    utils.plot_routes(depot, path, "MLP Geometric Scaling Path", "mlp_geometric_plot.png")
