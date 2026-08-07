import re

with open('app.py', 'r') as f:
    content = f.read()

# 1. Update generators
new_generators = """def generate_relocate_moves(routes, truck_names, node_names):
    moves = []
    num_routes = len(routes)
    for r1 in range(num_routes):
        for i in range(len(routes[r1])):
            node = routes[r1][i]
            for r2 in range(num_routes):
                insert_positions = len(routes[r2]) if r1 == r2 else len(routes[r2]) + 1
                for j in range(insert_positions):
                    if r1 == r2 and j == i:
                        continue
                    new_routes = [list(r) for r in routes]
                    new_routes[r1].pop(i)
                    new_routes[r2].insert(j, node)
                    
                    target_truck = truck_names[r2] if r1 != r2 else f"{truck_names[r2]} (different position)"
                    desc = f"Move '{node_names[node]}' from {truck_names[r1]} to {target_truck}"
                    moves.append((new_routes, desc))
    return moves

def generate_swap_moves(routes, truck_names, node_names):
    moves = []
    num_routes = len(routes)
    for r1 in range(num_routes):
        for i in range(len(routes[r1])):
            for r2 in range(r1, num_routes):
                start_j = i + 1 if r1 == r2 else 0
                for j in range(start_j, len(routes[r2])):
                    node1 = routes[r1][i]
                    node2 = routes[r2][j]
                    new_routes = [list(r) for r in routes]
                    new_routes[r1][i] = node2
                    new_routes[r2][j] = node1
                    desc = f"Swap the deliveries for '{node_names[node1]}' (on {truck_names[r1]}) and '{node_names[node2]}' (on {truck_names[r2]})"
                    moves.append((new_routes, desc))
    return moves

def generate_2opt_moves(routes, truck_names, node_names):
    moves = []
    num_routes = len(routes)
    for r in range(num_routes):
        route = routes[r]
        n = len(route)
        for i in range(n - 1):
            for j in range(i + 1, n):
                if j - i == 1:
                    continue # Already covered by adjacent swap
                new_routes = [list(rt) for rt in routes]
                new_routes[r] = route[:i] + route[i:j+1][::-1] + route[j+1:]
                desc = f"Reorder the stops on {truck_names[r]} (reverse the sequence between '{node_names[route[i]]}' and '{node_names[route[j]]}') to uncross the route"
                moves.append((new_routes, desc))
    return moves

def generate_cross_exchange_moves(routes, truck_names, node_names):
    moves = []
    num_routes = len(routes)
    for r1 in range(num_routes):
        for r2 in range(r1 + 1, num_routes):
            # Try swapping tails
            for i in range(len(routes[r1]) + 1):
                for j in range(len(routes[r2]) + 1):
                    # Skip if both tails are empty or both are full (just swaps whole routes)
                    if (i == 0 and j == 0) or (i == len(routes[r1]) and j == len(routes[r2])):
                        continue
                        
                    new_routes = [list(rt) for rt in routes]
                    tail1 = routes[r1][i:]
                    tail2 = routes[r2][j:]
                    
                    new_routes[r1] = routes[r1][:i] + tail2
                    new_routes[r2] = routes[r2][:j] + tail1
                    
                    n1 = f"'{node_names[routes[r1][i-1]]}'" if i > 0 else "the start"
                    n2 = f"'{node_names[routes[r2][j-1]]}'" if j > 0 else "the start"
                    
                    desc = f"Exchange the end-portions of {truck_names[r1]} (after {n1}) and {truck_names[r2]} (after {n2}) to untangle them"
                    moves.append((new_routes, desc))
    return moves

def solve_routing(locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_coef=0, latency_coef=0):"""

# regex replace from def generate_relocate_moves to def solve_routing(...):
pattern = re.compile(r'def generate_relocate_moves\(routes\):.*?def solve_routing\(locations, demands, vehicle_capacities, initial_routes, makespan_coef=0, latency_coef=0\):', re.DOTALL)
content = pattern.sub(new_generators, content)

# 2. Update the calls in solve_routing
new_calls = """moves = (generate_relocate_moves(initial_routes, truck_names, node_names) + 
             generate_swap_moves(initial_routes, truck_names, node_names) + 
             generate_2opt_moves(initial_routes, truck_names, node_names) + 
             generate_cross_exchange_moves(initial_routes, truck_names, node_names))"""
pattern2 = re.compile(r'moves = \(generate_relocate_moves\(initial_routes\) \+ \n             generate_swap_moves\(initial_routes\) \+ \n             generate_2opt_moves\(initial_routes\) \+ \n             generate_cross_exchange_moves\(initial_routes\)\)')
content = pattern2.sub(new_calls, content)

# 3. Update build locations
new_build = """# Build locations and demands lists
        locations = [depot_coords]
        demands = [0]
        node_names = ["Depot"]
        coord_to_node = {depot_coords: 0}
        
        for _, row in grouped.iterrows():
            coord = (row['Latitude'], row['Longitude'])
            if coord not in coord_to_node:
                coord_to_node[coord] = len(locations)
                locations.append(coord)
                demands.append(int(row['Total Pallets']))
                node_names.append(row['Name'])"""
pattern3 = re.compile(r'# Build locations and demands lists\n        locations = \[depot_coords\]\n        demands = \[0\]\n        coord_to_node = \{depot_coords: 0\}\n        \n        for _, row in grouped.iterrows\(\):\n            coord = \(row\[\'Latitude\'\], row\[\'Longitude\'\]\)\n            if coord not in coord_to_node:\n                coord_to_node\[coord\] = len\(locations\)\n                locations.append\(coord\)\n                demands.append\(int\(row\[\'Total Pallets\'\]\)\)')
content = pattern3.sub(new_build, content)

# 4. Update solve_routing call
new_call = """init_cost, top_moves, final_cost, improved_routes = solve_routing(
                locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_weight, latency_weight
            )"""
pattern4 = re.compile(r'init_cost, top_moves, final_cost, improved_routes = solve_routing\(\n                locations, demands, vehicle_capacities, initial_routes, makespan_weight, latency_weight\n            \)')
content = pattern4.sub(new_call, content)

with open('app.py', 'w') as f:
    f.write(content)

