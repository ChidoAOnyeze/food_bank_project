import folium
import webbrowser
import os

def plot_routes_on_map(locations, routes, output_file="routes_map.html"):
    """
    Generates an interactive HTML map with the given locations and routes.
    
    :param locations: List of (latitude, longitude) tuples.
                      The index in the list serves as the node ID.
    :param routes: List of routes. Each route is a list of node IDs.
                   e.g., [[0, 1, 3, 0], [0, 2, 4, 0]]
    :param output_file: Name of the output HTML file.
    """
    if not locations:
        print("No locations provided to plot.")
        return

    # Center the map at the first location (usually the depot)
    center_lat, center_lng = locations[0]
    m = folium.Map(location=[center_lat, center_lng], zoom_start=13)

    # A palette of colors for different routes
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred',
              'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue',
              'darkpurple', 'white', 'pink', 'lightblue', 'lightgreen',
              'gray', 'black', 'lightgray']

    # 1. Plot all locations as markers
    for idx, (lat, lng) in enumerate(locations):
        if idx == 0:
            # Depot gets a special marker
            folium.Marker(
                location=[lat, lng],
                popup="Depot (Node 0)",
                icon=folium.Icon(color="black", icon="star")
            ).add_to(m)
        else:
            # Standard locations
            folium.Marker(
                location=[lat, lng],
                popup=f"Node {idx}",
                icon=folium.Icon(color="blue", icon="info-sign")
            ).add_to(m)

    # 2. Plot the routes as lines
    for route_idx, route in enumerate(routes):
        route_coords = []
        for node_idx in route:
            route_coords.append(locations[node_idx])
            
        color = colors[route_idx % len(colors)]
        
        folium.PolyLine(
            route_coords,
            color=color,
            weight=3,
            opacity=0.8,
            popup=f"Route {route_idx}"
        ).add_to(m)

    # 3. Save to HTML and open in the user's default browser
    m.save(output_file)
    print(f"Map successfully generated and saved to '{output_file}'.")
    
    # Automatically open the generated HTML file in the web browser
    file_path = f"file://{os.path.abspath(output_file)}"
    webbrowser.open(file_path)

if __name__ == "__main__":
    # Demo data to test the visualizer
    # Simulated coordinates around a city center
    sample_locations = [
        (40.7128, -74.0060),  # 0: Depot
        (40.7150, -74.0020),  # 1
        (40.7110, -74.0080),  # 2
        (40.7180, -74.0000),  # 3
        (40.7080, -74.0120),  # 4
        (40.7190, -73.9980),  # 5
    ]
    
    # Routes representing paths taken by vehicles
    sample_routes = [
        [0, 1, 3, 5, 0], # Vehicle 1 route
        [0, 2, 4, 0]     # Vehicle 2 route
    ]

    print("Generating demo map...")
    plot_routes_on_map(sample_locations, sample_routes)
