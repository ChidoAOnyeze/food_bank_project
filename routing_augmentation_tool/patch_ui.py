import re

with open('app.py', 'r') as f:
    content = f.read()

# Update invocation
old_invoke = """        st.info("Parsing completed. Running route optimization (this will take ~5 seconds)...")
        
        with st.spinner("Optimizing routes..."):
            init_cost, top_moves, final_cost, improved_routes = solve_routing(
                locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_weight, latency_weight
            )"""

new_invoke = """        st.info("Parsing completed. Running route optimization (this will take ~5 seconds)...")
        
        st.subheader("Live Feed: Top 5 Local Improvements on Initial Route")
        feed_container = st.empty()
        
        with st.spinner("Optimizing routes..."):
            init_cost, top_moves, final_cost, improved_routes = solve_routing(
                locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_weight, latency_weight, ui_container=feed_container
            )"""

content = content.replace(old_invoke, new_invoke)

# Remove the old static top 5
old_static = """            st.subheader("Top 5 Local Improvements on Initial Route")
            if top_moves:
                for i, (imp, cost, desc) in enumerate(top_moves):
                    pct = (imp / init_cost) * 100 if init_cost > 0 else 0
                    st.write(f"**{i+1}.** {desc} (Improves by {pct:.1f}%)")
            else:
                st.write("No single-node moves improve the objective.")"""

new_static = """            if not top_moves:
                feed_container.write("No single-node moves improve the objective.")"""

content = content.replace(old_static, new_static)

with open('app.py', 'w') as f:
    f.write(content)
