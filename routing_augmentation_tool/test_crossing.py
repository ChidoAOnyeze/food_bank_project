from app import solve_routing

locations = [
    (40.7128, -74.0060), # Depot
    (40.7150, -74.0020),
    (40.7180, -74.0000),
    (40.7190, -73.9980),
    (40.7110, -74.0080),
    (40.7080, -74.0120)
]
initial_routes = [[1, 2, 3], [4, 5]]
# The initial route is quite straight: 0->1->2->3->0 and 0->4->5->0.
# Let's create a crossing by changing initial route:
initial_routes_cross = [[2, 1, 3], [5, 4]]

init, moves, final, improved = solve_routing(locations, initial_routes_cross)
print("Improved:", improved)
