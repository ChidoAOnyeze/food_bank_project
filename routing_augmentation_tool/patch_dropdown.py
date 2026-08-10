import re

with open('app.py', 'r') as f:
    content = f.read()

# 1. Update the dropdown option generation
old_dropdown = 'options = ["Show Full OR-Tools Optimization"] + [f"Move {i+1}: {m[2]}" for i, m in enumerate(top_moves)]'
new_dropdown = 'options = ["Show Full OR-Tools Optimization"] + [f"Move {i+1} (Improves by {((m[0] / init_cost) * 100 if init_cost > 0 else 0):.1f}%): {m[2]}" for i, m in enumerate(top_moves)]'
content = content.replace(old_dropdown, new_dropdown)

# 2. Add the seen_states deduplication
old_loop = """    top_moves = []
    total_improvements_found = 0
    
    for new_routes, desc in moves:
        sol = routing.ReadAssignmentFromRoutes(new_routes, True)"""
new_loop = """    top_moves = []
    total_improvements_found = 0
    seen_states = set()
    
    for new_routes, desc in moves:
        state_hash = tuple(tuple(r) for r in new_routes)
        if state_hash in seen_states:
            continue
        seen_states.add(state_hash)
        
        sol = routing.ReadAssignmentFromRoutes(new_routes, True)"""
content = content.replace(old_loop, new_loop)

with open('app.py', 'w') as f:
    f.write(content)

