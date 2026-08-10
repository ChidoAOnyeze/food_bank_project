import re

with open('app.py', 'r') as f:
    content = f.read()

old_block = """            if init_cost > 0:
                # If soft constraint is active, costs include massive penalties, making percentage look weird.
                if not allow_overcapacity:
                    total_pct = ((init_cost - final_cost) / init_cost) * 100
                if not allow_overcapacity:
                    st.metric("Total Route Improvement", f"{total_pct:.1f}%")
                else:
                    st.metric("Penalty Score Improvement (Soft Constraints)", f"{init_cost - final_cost} points")"""

new_block = """            if init_cost > 0:
                # Check if the initial routes actually had any capacity violations
                initial_violations = False
                for i, route in enumerate(initial_routes):
                    if not route: continue
                    if sum(demands[node] for node in route) > vehicle_capacities[i]:
                        initial_violations = True
                        break
                        
                had_penalties = allow_overcapacity and initial_violations

                if not had_penalties:
                    total_pct = ((init_cost - final_cost) / init_cost) * 100
                    st.metric("Total Route Improvement", f"{total_pct:.1f}%")
                else:
                    st.metric("Penalty Score Improvement (Soft Constraints)", f"{init_cost - final_cost} points")"""

content = content.replace(old_block, new_block)

with open('app.py', 'w') as f:
    f.write(content)
