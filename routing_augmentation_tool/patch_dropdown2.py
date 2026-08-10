import re

with open('app.py', 'r') as f:
    content = f.read()

old_block = """            # Selection box for improvements
            if top_moves:
                options = ["Show Full OR-Tools Optimization"] + [f"Move {i+1} (Improves by {((m[0] / init_cost) * 100 if init_cost > 0 else 0):.1f}%): {m[2]}" for i, m in enumerate(top_moves)]"""

new_block = """            # Selection box for improvements
            if top_moves:
                if not locals().get('had_penalties', False):
                    options = ["Show Full OR-Tools Optimization"] + [f"Move {i+1} (Improves by {((m[0] / init_cost) * 100 if init_cost > 0 else 0):.1f}%): {m[2]}" for i, m in enumerate(top_moves)]
                else:
                    options = ["Show Full OR-Tools Optimization"] + [f"Move {i+1} (Fixes Capacity Penalty): {m[2]}" for i, m in enumerate(top_moves)]"""

content = content.replace(old_block, new_block)

with open('app.py', 'w') as f:
    f.write(content)
