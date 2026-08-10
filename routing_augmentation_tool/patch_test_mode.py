import re

with open('app.py', 'r') as f:
    content = f.read()

# 1. Add sidebar toggle
old_sidebar = """makespan_weight = makespan_ui * 10
latency_weight = latency_ui * 10

uploaded_file = st.file_uploader("Upload Stops CSV", type=["csv"])"""

new_sidebar = """makespan_weight = makespan_ui * 10
latency_weight = latency_ui * 10

st.sidebar.header("Testing")
test_mode = st.sidebar.toggle("Test Mode (Limit to 200 improvements)", value=False)

uploaded_file = st.file_uploader("Upload Stops CSV", type=["csv"])"""

content = content.replace(old_sidebar, new_sidebar)


# 2. Update solve_routing signature
old_sig = "def solve_routing(locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_coef=0, latency_coef=0, ui_container=None):"
new_sig = "def solve_routing(locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_coef=0, latency_coef=0, ui_container=None, test_mode=False):"

content = content.replace(old_sig, new_sig)


# 3. Add break condition in loop
old_loop_end = """                            pct = (imp / initial_cost) * 100 if initial_cost > 0 else 0
                            st.write(f"**{rank+1}.** {d} (Improves by {pct:.1f}%)")
                            
    # Final flush to UI"""

new_loop_end = """                            pct = (imp / initial_cost) * 100 if initial_cost > 0 else 0
                            st.write(f"**{rank+1}.** {d} (Improves by {pct:.1f}%)")
                            
                if test_mode and total_improvements_found >= 200:
                    break
                            
    # Final flush to UI"""

content = content.replace(old_loop_end, new_loop_end)


# 4. Update solve_routing invocation and current_params
old_invoke = """        # Check if parameters changed to avoid re-running when just interacting with UI
        current_params = (locations, demands, vehicle_capacities, initial_routes, makespan_weight, latency_weight)
        
        if 'last_run_params' not in st.session_state or st.session_state['last_run_params'] != current_params:
            st.subheader("Live Feed: Top 5 Local Improvements on Initial Route")
            feed_container = st.empty()
            
            with st.spinner("Optimizing routes..."):
                results = solve_routing(
                    locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_weight, latency_weight, ui_container=feed_container
                )"""

new_invoke = """        # Check if parameters changed to avoid re-running when just interacting with UI
        current_params = (locations, demands, vehicle_capacities, initial_routes, makespan_weight, latency_weight, test_mode)
        
        if 'last_run_params' not in st.session_state or st.session_state['last_run_params'] != current_params:
            st.subheader("Live Feed: Top 5 Local Improvements on Initial Route")
            feed_container = st.empty()
            
            with st.spinner("Optimizing routes..."):
                results = solve_routing(
                    locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_weight, latency_weight, ui_container=feed_container, test_mode=test_mode
                )"""

content = content.replace(old_invoke, new_invoke)

with open('app.py', 'w') as f:
    f.write(content)

