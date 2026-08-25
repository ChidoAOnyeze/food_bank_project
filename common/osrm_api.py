"""
OSRM (Open Source Routing Machine) API Client
----------------------------------------------
Provides modular abstractions for querying OSRM services:
- Road Route Geometry (/route/v1/driving/...) with polyline6 decoding.
- Multi-coordinate path navigation.
- Distance & Duration Matrix Table API (/table/v1/driving/...).
"""

import json
import requests
from geopy.distance import geodesic

DEFAULT_OSRM_URL = "https://router.project-osrm.org"


def decode_polyline(encoded: str, precision: int = 6):
    """
    Decodes an encoded polyline string (precision 6 for OSRM polyline6)
    into a list of (latitude, longitude) float tuples.
    """
    if not encoded:
        return []
    inv = 1.0 / (10 ** precision)
    decoded = []
    lat = 0
    lng = 0
    index = 0
    length = len(encoded)
    while index < length:
        shift = 0
        result = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat

        shift = 0
        result = 0
        while True:
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng
        decoded.append((lat * inv, lng * inv))
    return decoded


class OSRMClient:
    """
    Client for interacting with OSRM Routing and Table APIs.
    """
    def __init__(self, base_url: str = DEFAULT_OSRM_URL, profile: str = "driving", default_timeout: float = 3.0):
        self.base_url = base_url.rstrip("/")
        self.profile = profile
        self.default_timeout = default_timeout

    def _format_coords(self, points):
        """
        Formats points as '{lon},{lat};{lon},{lat};...' for OSRM URL path.
        Points can be list of (lat, lon) or list of dicts.
        """
        formatted = []
        for p in points:
            if isinstance(p, (list, tuple)):
                lat, lon = p[0], p[1]
            elif isinstance(p, dict):
                lat, lon = p.get("lat"), p.get("lon", p.get("lng"))
            else:
                raise ValueError(f"Unsupported coordinate format: {p}")
            formatted.append(f"{lon},{lat}")
        return ";".join(formatted)

    def fetch_route(self, points, overview: str = "full", geometries: str = "polyline6", steps: bool = False, timeout: float = None):
        """
        Calls OSRM Route service: /route/v1/{profile}/{coordinates}
        Returns the parsed JSON response.
        """
        if len(points) < 2:
            return {}
        coords_str = self._format_coords(points)
        timeout = timeout or self.default_timeout
        url = f"{self.base_url}/route/v1/{self.profile}/{coords_str}?overview={overview}&geometries={geometries}&steps={'true' if steps else 'false'}"
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def fetch_leg_geometry(self, p1, p2, timeout: float = None):
        """
        Fetches the turn-by-turn road geometry between two points p1 and p2 using OSRM.
        Returns decoded coordinates [(lat, lon), ...].
        """
        if p1 == p2:
            return [p1, p2]
        try:
            data = self.fetch_route([p1, p2], overview="full", geometries="polyline6", timeout=timeout)
            routes = data.get("routes", [])
            if routes and "geometry" in routes[0]:
                coords = decode_polyline(routes[0]["geometry"], precision=6)
                if coords and len(coords) >= 2:
                    print(f"[OSRM API] Received {len(coords)} road curve points for leg ({p1[0]:.5f}, {p1[1]:.5f}) -> ({p2[0]:.5f}, {p2[1]:.5f})")
                    return coords
        except Exception as e:
            print(f"[OSRM API Warning] Leg ({p1[0]:.5f}, {p1[1]:.5f}) -> ({p2[0]:.5f}, {p2[1]:.5f}): {e}")
        return [p1, p2]

    def fetch_route_geometry(self, points, timeout: float = None):
        """
        Fetches the full turn-by-turn road geometry across an ordered sequence of stops.
        Returns decoded coordinates [(lat, lon), ...].
        """
        if len(points) < 2:
            return points
        try:
            data = self.fetch_route(points, overview="full", geometries="polyline6", timeout=timeout)
            routes = data.get("routes", [])
            if routes and "geometry" in routes[0]:
                coords = decode_polyline(routes[0]["geometry"], precision=6)
                if coords and len(coords) >= 2:
                    return coords
        except Exception as e:
            print(f"[OSRM API Error] Route query failed: {e}")
        return points

    def fetch_table(self, locations, annotations: str = "distance,duration", timeout: float = 10.0):
        """
        Calls OSRM Table service: /table/v1/{profile}/{coordinates}
        Returns a dictionary with 'distances' (meters) and/or 'durations' (seconds).
        """
        if not locations:
            return {}
        coords_str = self._format_coords(locations)
        url = f"{self.base_url}/table/v1/{self.profile}/{coords_str}?annotations={annotations}"
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def get_distance_matrix(self, locations, chunk_size: int = 50, timeout: float = 15.0):
        """
        Builds a full distance matrix (in meters) for locations using the OSRM Table API.
        """
        num_nodes = len(locations)
        matrix = [[0] * num_nodes for _ in range(num_nodes)]
        
        # If total stops fits in single query (e.g. <= 100)
        if num_nodes <= chunk_size:
            try:
                data = self.fetch_table(locations, annotations="distance", timeout=timeout)
                distances = data.get("distances", [])
                if distances and len(distances) == num_nodes:
                    for i in range(num_nodes):
                        for j in range(num_nodes):
                            if distances[i][j] is not None:
                                matrix[i][j] = int(distances[i][j])
                            else:
                                matrix[i][j] = int(geodesic(locations[i], locations[j]).meters * 1.5)
                    return matrix
            except Exception as e:
                print(f"[OSRM API Error] Table query failed: {e}")

        # Fallback pairwise or chunked
        for i in range(num_nodes):
            for j in range(num_nodes):
                if i == j:
                    continue
                matrix[i][j] = int(geodesic(locations[i], locations[j]).meters * 1.5)
        return matrix


# Default singleton instance
default_osrm_client = OSRMClient()

def fetch_osrm_leg_geometry(p1, p2, client=None):
    """
    Convenience function to fetch leg road geometry from OSRM.
    """
    c = client or default_osrm_client
    return c.fetch_leg_geometry(p1, p2)

def fetch_osrm_route_geometry(points, client=None):
    """
    Convenience function to fetch route geometry across stops from OSRM.
    """
    c = client or default_osrm_client
    return c.fetch_route_geometry(points)

def fetch_osrm_table(locations, annotations="distance,duration", client=None):
    """
    Convenience function to query OSRM table service.
    """
    c = client or default_osrm_client
    return c.fetch_table(locations, annotations=annotations)
