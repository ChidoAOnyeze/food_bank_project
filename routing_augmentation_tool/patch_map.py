import re

with open('app.py', 'r') as f:
    content = f.read()

# 1. Update top_moves tuple to include new_routes
content = content.replace("top_moves.append((savings, cost, desc))", "top_moves.append((savings, cost, desc, new_routes))")
content = content.replace("for rank, (imp, c, d) in enumerate(top_moves):", "for rank, (imp, c, d, _) in enumerate(top_moves):")

# 2. Update invocation to use session_state so the selectbox doesn't retrigger the solver
old_invoke = """        st.info("Parsing completed. Running route optimization (this will take ~5 seconds)...")
        
        st.subheader("Live Feed: Top 5 Local Improvements on Initial Route")
        feed_container = st.empty()
        
        with st.spinner("Optimizing routes..."):
            init_cost, top_moves, final_cost, improved_routes = solve_routing(
                locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_weight, latency_weight, ui_container=feed_container
            )"""

new_invoke = """        st.info("Parsing completed. Preparing routing engine...")
        
        # Check if parameters changed to avoid re-running when just interacting with UI
        current_params = (locations, demands, vehicle_capacities, initial_routes, makespan_weight, latency_weight)
        
        if 'last_run_params' not in st.session_state or st.session_state['last_run_params'] != current_params:
            st.subheader("Live Feed: Top 5 Local Improvements on Initial Route")
            feed_container = st.empty()
            
            with st.spinner("Optimizing routes..."):
                results = solve_routing(
                    locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_weight, latency_weight, ui_container=feed_container
                )
            st.session_state['optimization_results'] = results
            st.session_state['last_run_params'] = current_params
        
        init_cost, top_moves, final_cost, improved_routes = st.session_state['optimization_results']"""

content = content.replace(old_invoke, new_invoke)

# 3. Completely replace the Visualization logic at the bottom
# It starts around: st.subheader("Route Visualization")
# and goes to st_folium(m, width=900, height=600)

visualization_start = content.find('            st.subheader("Route Visualization")')

if visualization_start != -1:
    new_vis = """            st.subheader("Route Visualization")
            
            # Selection box for improvements
            if top_moves:
                options = ["Show Full OR-Tools Optimization"] + [f"Move {i+1}: {m[2]}" for i, m in enumerate(top_moves)]
                selected_option = st.selectbox("Visualize a specific route improvement:", options)
            else:
                selected_option = "Show Full OR-Tools Optimization"

            center_lat, center_lng = locations[0]
            m = folium.Map(location=[center_lat, center_lng], zoom_start=13)
            
            colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred',
                      'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue',
                      'darkpurple', 'pink', 'lightblue', 'lightgreen',
                      'gray', 'black', 'lightgray']

            if selected_option == "Show Full OR-Tools Optimization":
                show_proposed = st.toggle("Overlay Proposed Changes (Dotted Line)", value=True)
                
                # Add All Markers
                for idx, (lat, lng) in enumerate(locations):
                    if idx == 0:
                        folium.Marker([lat, lng], popup="Depot", icon=folium.Icon(color="black", icon="star")).add_to(m)
                    else:
                        demand = demands[idx]
                        folium.Marker([lat, lng], popup=f"{node_names[idx]} (Pallets: {demand})", icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)

                # Plot All Original Routes (Always drawn, Solid)
                for route_idx, route in enumerate(initial_routes):
                    if not route:
                        continue
                    route_coords = [locations[0]] + [locations[n] for n in route] + [locations[0]]
                    color = colors[route_idx % len(colors)]
                    folium.PolyLine(
                        route_coords,
                        color=color,
                        weight=5,
                        opacity=0.8,
                        popup=f"Original Route {route_idx} ({truck_names[route_idx]})"
                    ).add_to(m)

                # Plot All Improved Routes (if toggled, Dotted)
                if show_proposed:
                    for route_idx, route in enumerate(improved_routes):
                        if not route:
                            continue
                        route_coords = [locations[0]] + [locations[n] for n in route] + [locations[0]]
                        color = colors[route_idx % len(colors)]
                        folium.PolyLine(
                            route_coords,
                            color=color,
                            weight=4,
                            opacity=0.9,
                            dash_array='5, 10', # Dotted line
                            popup=f"Improved Route {route_idx} ({truck_names[route_idx]})"
                        ).add_to(m)
            else:
                # User selected a specific local move
                move_idx = int(selected_option.split(":")[0].replace("Move ", "")) - 1
                selected_new_routes = top_moves[move_idx][3]
                
                # Identify changed routes
                changed_route_indices = []
                for i in range(len(initial_routes)):
                    if initial_routes[i] != selected_new_routes[i]:
                        changed_route_indices.append(i)
                        
                # Add Markers ONLY for nodes in these routes, plus depot
                nodes_to_draw = {0}
                for idx in changed_route_indices:
                    nodes_to_draw.update(initial_routes[idx])
                    nodes_to_draw.update(selected_new_routes[idx])
                    
                for idx, (lat, lng) in enumerate(locations):
                    if idx in nodes_to_draw:
                        if idx == 0:
                            folium.Marker([lat, lng], popup="Depot", icon=folium.Icon(color="black", icon="star")).add_to(m)
                        else:
                            demand = demands[idx]
                            folium.Marker([lat, lng], popup=f"{node_names[idx]} (Pallets: {demand})", icon=folium.Icon(color="blue", icon="info-sign")).add_to(m)

                # Draw ONLY the affected routes
                for idx in changed_route_indices:
                    # Solid original
                    r_orig = initial_routes[idx]
                    if r_orig:
                        route_coords_orig = [locations[0]] + [locations[n] for n in r_orig] + [locations[0]]
                        folium.PolyLine(route_coords_orig, color=colors[idx % len(colors)], weight=5, opacity=0.8, popup=f"Original {truck_names[idx]}").add_to(m)
                    
                    # Dotted new
                    r_new = selected_new_routes[idx]
                    if r_new:
                        route_coords_new = [locations[0]] + [locations[n] for n in r_new] + [locations[0]]
                        folium.PolyLine(route_coords_new, color=colors[idx % len(colors)], weight=4, opacity=0.9, dash_array='5, 10', popup=f"Improved {truck_names[idx]}").add_to(m)

            st_folium(m, width=900, height=600)"""

    content = content[:visualization_start] + new_vis
    
with open('app.py', 'w') as f:
    f.write(content)

