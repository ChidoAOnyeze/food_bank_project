import math
import statistics
from geopy.distance import geodesic
try:
    from .valhalla_matrix import build_valhalla_matrix
except (ImportError, ValueError):
    from valhalla_matrix import build_valhalla_matrix

def haversine_km(p1, p2):
    """
    Fast analytical Haversine distance in kilometers.
    """
    lat1, lon1 = p1
    lat2, lon2 = p2
    if lat1 == lat2 and lon1 == lon2:
        return 0.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    return 6371.0088 * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

def get_distance_fn(metric='valhalla'):
    """
    Returns a distance function between two (lat, lon) or (x, y) coordinates.
    """
    if metric == 'geodesic':
        return haversine_km
    elif metric == 'wgs84':
        def dist_geo(p1, p2):
            if p1 == p2:
                return 0.0
            return geodesic((p1[0], p1[1]), (p2[0], p2[1])).kilometers
        return dist_geo
    else:
        def dist_euc(p1, p2):
            return math.hypot(p1[0] - p2[0], p1[1] - p2[1])
        return dist_euc

def create_instance_distance_matrix(all_nodes, metric='valhalla', fetch_missing=True):
    """
    Creates an optimized distance matrix lookup for an instance:
    - 'valhalla': OpenStreetMap turn-by-turn truck road distances in km.
    - 'geodesic': Haversine great-circle distance in km.
    - 'euclidean': Geometric Euclidean distances.
    """
    if metric == 'valhalla':
        return build_valhalla_matrix(all_nodes, fetch_missing=fetch_missing)
    else:
        return DistanceMatrix(all_nodes, metric=metric)

class DistanceMatrix:
    """
    Fast O(1) in-memory cached distance lookup for an instance's locations.
    """
    def __init__(self, all_nodes, metric='geodesic'):
        self.dist_fn = get_distance_fn(metric)
        self.node_to_idx = {node: idx for idx, node in enumerate(all_nodes)}
        n = len(all_nodes)
        self.matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                d = self.dist_fn(all_nodes[i], all_nodes[j])
                self.matrix[i][j] = d
                self.matrix[j][i] = d

    def __call__(self, p1, p2):
        if p1 == p2:
            return 0.0
        i = self.node_to_idx.get(p1)
        j = self.node_to_idx.get(p2)
        if i is not None and j is not None:
            return self.matrix[i][j]
        return self.dist_fn(p1, p2)

def evaluate_routes(depot, routes, demands_map=None, dist_fn=None):
    """
    Evaluates a set of vehicle routes across multiple objectives.
    """
    if dist_fn is None:
        dist_fn = get_distance_fn('geodesic')
        
    if not routes:
        return {
            'total_distance': 0.0,
            'makespan': 0.0,
            'total_latency': 0.0,
            'avg_latency': 0.0,
            'num_trucks_used': 0,
            'max_load': 0.0,
            'total_demand': 0.0,
            'load_std': 0.0,
            'route_stops_count': []
        }

    if routes and isinstance(routes[0], tuple):
        routes = [routes]

    total_dist = 0.0
    makespan = 0.0
    total_latency = 0.0
    total_stops = 0
    route_loads = []
    route_stops_count = []
    used_trucks = 0

    for route in routes:
        if not route:
            route_loads.append(0.0)
            route_stops_count.append(0)
            continue

        used_trucks += 1
        route_stops_count.append(len(route))
        
        curr_loc = depot
        curr_cumul_dist = 0.0
        route_demand = 0.0

        for stop in route:
            d = dist_fn(curr_loc, stop)
            curr_cumul_dist += d
            total_latency += curr_cumul_dist
            total_stops += 1
            curr_loc = stop

            if demands_map and stop in demands_map:
                route_demand += demands_map[stop]

        # Return to depot
        return_dist = dist_fn(curr_loc, depot)
        curr_cumul_dist += return_dist
        
        total_dist += curr_cumul_dist
        makespan = max(makespan, curr_cumul_dist)
        route_loads.append(route_demand)

    avg_latency = total_latency / total_stops if total_stops > 0 else 0.0
    load_std = statistics.stdev(route_loads) if len(route_loads) > 1 else 0.0
    max_load = max(route_loads) if route_loads else 0.0
    total_demand = sum(route_loads)

    return {
        'total_distance': round(total_dist, 4),
        'makespan': round(makespan, 4),
        'total_latency': round(total_latency, 4),
        'avg_latency': round(avg_latency, 4),
        'num_trucks_used': used_trucks,
        'max_load': round(max_load, 2),
        'total_demand': round(total_demand, 2),
        'load_std': round(load_std, 2),
        'route_stops_count': route_stops_count
    }
