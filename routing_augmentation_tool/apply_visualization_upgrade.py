import re

# 1. Upgrade app_valhalla_road_path.py
with open("app_valhalla_road_path.py", "r") as f:
    content = f.read()

# Define the old block to replace from `colors = ['red', 'blue', ...` to `st_folium(m, width=900, height=600, returned_objects=[])`
old_pattern = r"colors = \['red', 'blue',[\s\S]*?st_folium\(m, width=900, height=600, returned_objects=\[\]\)"

new_block_road_path = """colors = ['#2563eb', '#16a34a', '#dc2626', '#9333ea', '#ea580c', '#0891b2',
                      '#db2777', '#4f46e5', '#ca8a04', '#059669', '#6366f1', '#0284c7',
                      '#b91c1c', '#475569', '#1e293b']

            # Helper function for edge-level diffing
            def diff_route_legs(r_orig, r_new):
                seq_orig = [0] + r_orig + [0] if r_orig else []
                seq_new = [0] + r_new + [0] if r_new else []
                legs_orig = [(seq_orig[i], seq_orig[i+1]) for i in range(len(seq_orig) - 1)]
                legs_new = [(seq_new[i], seq_new[i+1]) for i in range(len(seq_new) - 1)]
                set_orig = set(legs_orig)
                set_new = set(legs_new)
                
                common = [leg for leg in legs_orig if leg in set_new]
                removed = [leg for leg in legs_orig if leg not in set_new]
                added = [leg for leg in legs_new if leg not in set_orig]
                return common, removed, added

            if selected_option == "Show Full OR-Tools Optimization":
                show_proposed = st.toggle("Overlay Proposed Changes (Dotted Line)", value=True)
                # Prefetch all missing legs across both initial and improved routes in one super-batch call
                prefetch_and_cache_routes_geometry(initial_routes + improved_routes, locations)
                
                # Map each node to its route and sequence position
                node_to_route_info = {}
                for route_idx, route in enumerate(initial_routes):
                    for seq_idx, n in enumerate(route):
                        node_to_route_info[n] = (route_idx, seq_idx + 1)

                # Add All Markers with Numbered Badges
                for idx, (lat, lng) in enumerate(locations):
                    if idx == 0:
                        folium.Marker(
                            [lat, lng],
                            tooltip="Depot (Start & End)",
                            popup="Depot (Start & End)",
                            icon=folium.DivIcon(
                                html='''<div style="background-color: #0f172a; color: #facc15; border: 2px solid white; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-size: 15px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.6);">★</div>''',
                                icon_size=(28, 28),
                                icon_anchor=(14, 14)
                            )
                        ).add_to(m)
                    else:
                        demand = demands[idx]
                        orig_route, seq_num = node_to_route_info.get(idx, (0, 1))
                        marker_color = colors[orig_route % len(colors)]
                        tooltip_text = f"{node_names[idx]} | Stop #{seq_num} on Route {truck_names[orig_route]} | Pallets: {demand}"
                        folium.Marker(
                            [lat, lng],
                            tooltip=tooltip_text,
                            popup=tooltip_text,
                            icon=folium.DivIcon(
                                html=f'''<div style="background-color: {marker_color}; color: white; border: 2px solid white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.4);">{seq_num}</div>''',
                                icon_size=(24, 24),
                                icon_anchor=(12, 12)
                            )
                        ).add_to(m)

                # Plot All Original Routes (Always drawn, Solid, Real Road Paths)
                for route_idx, route in enumerate(initial_routes):
                    if not route:
                        continue
                    stop_sequence = [locations[0]] + [locations[n] for n in route] + [locations[0]]
                    route_coords = get_full_route_geometry(stop_sequence)
                    color = colors[route_idx % len(colors)]
                    pl = folium.PolyLine(
                        route_coords,
                        color=color,
                        weight=5,
                        opacity=0.75,
                        tooltip=f"Original Route {route_idx} ({truck_names[route_idx]})",
                        popup=f"Original Route {route_idx} ({truck_names[route_idx]})"
                    )
                    pl.add_to(m)
                    PolyLineTextPath(pl, '        ►        ', repeat=True, offset=6, attributes={'fill': color, 'fill-opacity': '0.8', 'font-weight': 'bold', 'font-size': '14'}).add_to(m)

                # Plot All Improved Routes (if toggled, Dotted, Real Road Paths)
                if show_proposed:
                    for route_idx, route in enumerate(improved_routes):
                        if not route:
                            continue
                        stop_sequence = [locations[0]] + [locations[n] for n in route] + [locations[0]]
                        route_coords = get_full_route_geometry(stop_sequence)
                        color = colors[route_idx % len(colors)]
                        pl = folium.PolyLine(
                            route_coords,
                            color=color,
                            weight=4,
                            opacity=0.9,
                            dash_array='6, 8',
                            tooltip=f"Improved Route {route_idx} ({truck_names[route_idx]})",
                            popup=f"Improved Route {route_idx} ({truck_names[route_idx]})"
                        )
                        pl.add_to(m)
                        PolyLineTextPath(pl, '        ►        ', repeat=True, offset=6, attributes={'fill': color, 'fill-opacity': '0.9', 'font-weight': 'bold', 'font-size': '14'}).add_to(m)
            else:
                # User selected a specific local move
                move_idx = int(selected_option.split(" ")[1]) - 1
                selected_new_routes = top_moves[move_idx][3]
                
                # --- ACCEPT / REJECT BUTTONS ---
                b_col1, b_col2 = st.columns(2)
                with b_col1:
                    if st.button("Accept Improvement", type="primary"):
                        st.session_state['accepted_routes'] = selected_new_routes
                        if 'last_run_params' in st.session_state:
                            del st.session_state['last_run_params']
                        st.rerun()
                with b_col2:
                    if st.button("Reject Improvement"):
                        st.session_state['rejected_moves'].add(top_moves[move_idx][2])
                        if 'last_run_params' in st.session_state:
                            del st.session_state['last_run_params']
                        st.rerun()
                
                # Identify changed routes
                changed_route_indices = []
                for i in range(len(initial_routes)):
                    if initial_routes[i] != selected_new_routes[i]:
                        changed_route_indices.append(i)
                        
                # Prefetch affected routes geometry in one batched call
                prefetch_and_cache_routes_geometry([initial_routes[i] for i in changed_route_indices] + [selected_new_routes[i] for i in changed_route_indices], locations)
                        
                # Assign distinct bold base colors for each involved route
                highlight_colors = ['#2563eb', '#16a34a', '#dc2626', '#9333ea', '#ea580c', '#0891b2']
                local_colors = {idx: highlight_colors[i % len(highlight_colors)] for i, idx in enumerate(changed_route_indices)}

                # Display Visual Breadcrumb & Diff Summary Cards
                st.markdown("#### 🔄 Route Improvement Sequence Comparison")
                for idx in changed_route_indices:
                    t_name = truck_names[idx]
                    r_orig = initial_routes[idx]
                    r_new = selected_new_routes[idx]
                    r_color = local_colors[idx]
                    
                    orig_names = ["🏠 Depot"] + [f"{node_names[n]} (#{i+1})" for i, n in enumerate(r_orig)] + ["🏠 Depot"]
                    new_names = ["🏠 Depot"] + [f"{node_names[n]} (#{i+1})" for i, n in enumerate(r_new)] + ["🏠 Depot"]
                    
                    orig_str = " ➔ ".join(orig_names)
                    new_str = " ➔ ".join(new_names)
                    
                    orig_pallets = sum(demands[n] for n in r_orig)
                    new_pallets = sum(demands[n] for n in r_new)
                    
                    st.markdown(f'''
                    <div style="border-left: 5px solid {r_color}; padding: 8px 12px; margin-bottom: 10px; background-color: #f8fafc; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        <div style="font-size: 15px; font-weight: bold; color: {r_color}; margin-bottom: 4px;">
                            🚚 Truck {t_name}
                            <span style="font-size: 12px; font-weight: normal; color: #64748b; margin-left: 8px;">
                                Load: {orig_pallets}p ➔ <strong>{new_pallets}p</strong> | Stops: {len(r_orig)} ➔ <strong>{len(r_new)}</strong>
                            </span>
                        </div>
                        <div style="font-size: 13px; color: #334155; line-height: 1.5;">
                            <span style="color: #64748b;"><strong>Original:</strong></span> {orig_str}<br/>
                            <span style="color: #059669;"><strong>Improved:</strong></span> {new_str}
                        </div>
                    </div>
                    ''', unsafe_allow_html=True)
                st.write("---")

                # Map nodes to their before & after routes and sequences
                orig_node_info = {}
                for r_idx in changed_route_indices:
                    for s_idx, n in enumerate(initial_routes[r_idx]):
                        orig_node_info[n] = (r_idx, s_idx + 1)
                        
                new_node_info = {}
                for r_idx in changed_route_indices:
                    for s_idx, n in enumerate(selected_new_routes[r_idx]):
                        new_node_info[n] = (r_idx, s_idx + 1)

                # Nodes to draw: all nodes in affected routes + depot
                nodes_to_draw = {0}
                for idx in changed_route_indices:
                    nodes_to_draw.update(initial_routes[idx])
                    nodes_to_draw.update(selected_new_routes[idx])

                # Draw Markers
                for idx in nodes_to_draw:
                    lat, lng = locations[idx]
                    if idx == 0:
                        folium.Marker(
                            [lat, lng],
                            tooltip="Depot (Start & End)",
                            popup="Depot (Start & End)",
                            icon=folium.DivIcon(
                                html='''<div style="background-color: #0f172a; color: #facc15; border: 2px solid white; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; font-size: 15px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.6);">★</div>''',
                                icon_size=(28, 28),
                                icon_anchor=(14, 14)
                            )
                        ).add_to(m)
                    else:
                        demand = demands[idx]
                        orig_rt, orig_seq = orig_node_info.get(idx, (None, None))
                        new_rt, new_seq = new_node_info.get(idx, (None, None))
                        
                        target_rt = new_rt if new_rt is not None else orig_rt
                        bg_color = local_colors.get(target_rt, '#2563eb')
                        
                        if orig_rt is not None and new_rt is not None and orig_rt != new_rt:
                            # Transferred between trucks
                            badge_text = f"#{orig_seq}➔#{new_seq}"
                            tooltip_text = f"🔄 {node_names[idx]} | Transferred: Truck {truck_names[orig_rt]} (Stop #{orig_seq}) ➔ Truck {truck_names[new_rt]} (Stop #{new_seq}) | Pallets: {demand}"
                            html = f'''<div style="background-color: {bg_color}; color: white; border: 2px solid #f59e0b; border-radius: 12px; padding: 0 5px; height: 24px; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.5); white-space: nowrap;">{badge_text}</div>'''
                            icon = folium.DivIcon(html=html, icon_size=(54, 24), icon_anchor=(27, 12))
                        elif orig_seq is not None and new_seq is not None and orig_seq != new_seq:
                            # Re-sequenced / Inverted / Reversed on same truck
                            badge_text = f"#{orig_seq}➔#{new_seq}"
                            tooltip_text = f"🔄 {node_names[idx]} | Position Changed: Stop #{orig_seq} ➔ Stop #{new_seq} on Truck {truck_names[target_rt]} | Pallets: {demand}"
                            html = f'''<div style="background-color: {bg_color}; color: white; border: 2px solid #f59e0b; border-radius: 12px; padding: 0 5px; height: 24px; display: inline-flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; box-shadow: 0 2px 5px rgba(0,0,0,0.5); white-space: nowrap;">{badge_text}</div>'''
                            icon = folium.DivIcon(html=html, icon_size=(54, 24), icon_anchor=(27, 12))
                        else:
                            # Unchanged sequence position
                            seq_display = new_seq if new_seq is not None else orig_seq
                            badge_text = f"{seq_display}"
                            tooltip_text = f"{node_names[idx]} | Stop #{seq_display} on Truck {truck_names[target_rt]} | Pallets: {demand}"
                            html = f'''<div style="background-color: {bg_color}; color: white; border: 2px solid white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; box-shadow: 0 2px 4px rgba(0,0,0,0.4);">{badge_text}</div>'''
                            icon = folium.DivIcon(html=html, icon_size=(24, 24), icon_anchor=(12, 12))
                            
                        folium.Marker([lat, lng], tooltip=tooltip_text, popup=tooltip_text, icon=icon).add_to(m)

                # Draw Route Legs by Type (Unchanged Common, Cut Removed, Added Improved)
                for idx in changed_route_indices:
                    r_color = local_colors[idx]
                    t_name = truck_names[idx]
                    r_orig = initial_routes[idx]
                    r_new = selected_new_routes[idx]
                    
                    legs_common, legs_removed, legs_added = diff_route_legs(r_orig, r_new)
                    
                    # 1. Unchanged Legs: Faint gray-tinted line
                    for u, v in legs_common:
                        leg_coords = get_full_route_geometry([locations[u], locations[v]])
                        pl = folium.PolyLine(
                            leg_coords,
                            color='#94a3b8',
                            weight=3,
                            opacity=0.4,
                            tooltip=f"Unchanged: {node_names[u]} ➔ {node_names[v]} (Truck {t_name})"
                        )
                        pl.add_to(m)
                        PolyLineTextPath(pl, '        ►        ', repeat=True, offset=5, attributes={'fill': '#94a3b8', 'fill-opacity': '0.4', 'font-weight': 'bold', 'font-size': '12'}).add_to(m)
                    
                    # 2. Removed Legs: Solid line in route's color (opacity 0.45)
                    for u, v in legs_removed:
                        leg_coords = get_full_route_geometry([locations[u], locations[v]])
                        pl = folium.PolyLine(
                            leg_coords,
                            color=r_color,
                            weight=5,
                            opacity=0.45,
                            tooltip=f"Original (Cut): {node_names[u]} ➔ {node_names[v]} (Truck {t_name})"
                        )
                        pl.add_to(m)
                        PolyLineTextPath(pl, '        ►        ', repeat=True, offset=6, attributes={'fill': r_color, 'fill-opacity': '0.45', 'font-weight': 'bold', 'font-size': '15'}).add_to(m)

                    # 3. Added Improved Legs: Thick Dotted line with bold directional arrows in route's color
                    for u, v in legs_added:
                        leg_coords = get_full_route_geometry([locations[u], locations[v]])
                        pl = folium.PolyLine(
                            leg_coords,
                            color=r_color,
                            weight=6,
                            opacity=1.0,
                            dash_array='6, 8',
                            tooltip=f"Improved (New): {node_names[u]} ➔ {node_names[v]} (Truck {t_name})"
                        )
                        pl.add_to(m)
                        PolyLineTextPath(pl, '        ►        ', repeat=True, offset=7, attributes={'fill': r_color, 'fill-opacity': '1.0', 'font-weight': 'bold', 'font-size': '18'}).add_to(m)

            st_folium(m, width=900, height=600, returned_objects=[])"""

new_content = re.sub(old_pattern, new_block_road_path, content, count=1)
if new_content != content:
    with open("app_valhalla_road_path.py", "w") as f:
        f.write(new_content)
    print("Successfully updated app_valhalla_road_path.py")
else:
    print("Failed to match pattern in app_valhalla_road_path.py")


# 2. Upgrade app_valhalla.py
with open("app_valhalla.py", "r") as f:
    content_v = f.read()

old_pattern_v = r"colors = \['red', 'blue',[\s\S]*?st_folium\(m, width=900, height=600\)"

new_block_v = new_block_road_path.replace("get_full_route_geometry([locations[u], locations[v]])", "[locations[u], locations[v]]").replace("get_full_route_geometry(stop_sequence)", "stop_sequence").replace(", returned_objects=[]", "")

new_content_v = re.sub(old_pattern_v, new_block_v, content_v, count=1)
if new_content_v != content_v:
    with open("app_valhalla.py", "w") as f:
        f.write(new_content_v)
    print("Successfully updated app_valhalla.py")
else:
    print("Failed to match pattern in app_valhalla.py")

