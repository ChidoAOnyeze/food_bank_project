import re

with open('app.py', 'r') as f:
    content = f.read()

# 1. Add toggle to sidebar
old_sidebar = """st.sidebar.header("Testing")
test_mode = st.sidebar.toggle("Test Mode (Limit to 200 improvements)", value=False)

uploaded_file = st.file_uploader("Upload Stops CSV", type=["csv"])"""

new_sidebar = """st.sidebar.header("Testing")
test_mode = st.sidebar.toggle("Test Mode (Limit to 200 improvements)", value=False)
allow_overcapacity = st.sidebar.toggle("Allow Over-Capacity (Soft Constraint)", value=False)

uploaded_file = st.file_uploader("Upload Stops CSV", type=["csv"])"""
content = content.replace(old_sidebar, new_sidebar)

# 2. Signature
old_sig = "def solve_routing(locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_coef=0, latency_coef=0, ui_container=None, test_mode=False):"
new_sig = "def solve_routing(locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_coef=0, latency_coef=0, ui_container=None, test_mode=False, allow_overcapacity=False):"
content = content.replace(old_sig, new_sig)

# 3. Constraint logic
old_cap = "    routing.AddDimensionWithVehicleCapacity(demand_callback_index, 0, data['vehicle_capacities'], True, 'Capacity')"
new_cap = """    if allow_overcapacity:
        large_caps = [1000000] * data['num_vehicles']
        routing.AddDimensionWithVehicleCapacity(demand_callback_index, 0, large_caps, True, 'Capacity')
        capacity_dimension = routing.GetDimensionOrDie('Capacity')
        penalty_cost = 1000000  # High penalty per pallet over capacity
        for vehicle_id in range(data['num_vehicles']):
            end_index = routing.End(vehicle_id)
            actual_capacity = data['vehicle_capacities'][vehicle_id]
            capacity_dimension.SetCumulVarSoftUpperBound(end_index, actual_capacity, penalty_cost)
    else:
        routing.AddDimensionWithVehicleCapacity(demand_callback_index, 0, data['vehicle_capacities'], True, 'Capacity')"""
content = content.replace(old_cap, new_cap)

# 4. Invocation
old_inv = """        # Check if parameters changed to avoid re-running when just interacting with UI
        current_params = (locations, demands, vehicle_capacities, initial_routes, makespan_weight, latency_weight, test_mode)
        
        if 'last_run_params' not in st.session_state or st.session_state['last_run_params'] != current_params:
            st.subheader("Live Feed: Top 5 Local Improvements on Initial Route")
            feed_container = st.empty()
            
            with st.spinner("Optimizing routes..."):
                results = solve_routing(
                    locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_weight, latency_weight, ui_container=feed_container, test_mode=test_mode
                )"""
new_inv = """        # Check if parameters changed to avoid re-running when just interacting with UI
        current_params = (locations, demands, vehicle_capacities, initial_routes, makespan_weight, latency_weight, test_mode, allow_overcapacity)
        
        if 'last_run_params' not in st.session_state or st.session_state['last_run_params'] != current_params:
            st.subheader("Live Feed: Top 5 Local Improvements on Initial Route")
            feed_container = st.empty()
            
            with st.spinner("Optimizing routes..."):
                results = solve_routing(
                    locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_weight, latency_weight, ui_container=feed_container, test_mode=test_mode, allow_overcapacity=allow_overcapacity
                )"""
content = content.replace(old_inv, new_inv)


# 5. UI warning for soft violations
old_ui = """        else:
            if init_cost > 0:
                total_pct = ((init_cost - final_cost) / init_cost) * 100"""
new_ui = """        else:
            if allow_overcapacity:
                violations = []
                for i, route in enumerate(improved_routes):
                    if not route: continue
                    truck_name = truck_names[i]
                    capacity = vehicle_capacities[i]
                    load = sum(demands[node] for node in route)
                    if load > capacity:
                        violations.append(f"**{truck_name}**: Load = {load} pallets, Capacity = {capacity} pallets (Over by {load - capacity})")
                if violations:
                    st.warning("### ⚠️ Some trucks are still over capacity (Soft Constraint Active)")
                    for v in violations:
                        st.write(f"- {v}")

            if init_cost > 0:
                # If soft constraint is active, costs include massive penalties, making percentage look weird.
                if not allow_overcapacity:
                    total_pct = ((init_cost - final_cost) / init_cost) * 100"""
content = content.replace(old_ui, new_ui)

# Need to fix the else block to handle the lack of total_pct when allow_overcapacity is true
old_pct = """                total_pct = ((init_cost - final_cost) / init_cost) * 100
                st.metric("Total Route Improvement", f"{total_pct:.1f}%")
            else:"""
new_pct = """                total_pct = ((init_cost - final_cost) / init_cost) * 100
                if not allow_overcapacity:
                    st.metric("Total Route Improvement", f"{total_pct:.1f}%")
                else:
                    st.metric("Penalty Score Improvement (Soft Constraints)", f"{init_cost - final_cost} points")
            else:"""
content = content.replace(old_pct, new_pct)


with open('app.py', 'w') as f:
    f.write(content)
