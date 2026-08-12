import re

with open("app.py", "r") as f:
    content = f.read()

# 1. Modify solve_routing signature
content = content.replace(
    "def solve_routing(locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_coef=0, latency_coef=0, ui_container=None, test_mode=False, allow_overcapacity=False):",
    "def solve_routing(locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_coef=0, latency_coef=0, ui_container=None, test_mode=False, allow_overcapacity=False, rejected_moves=None):"
)

# 2. Add rejected_moves filter
replace_moves_loop = """
    for new_routes, desc in moves:
        if rejected_moves and desc in rejected_moves:
            continue
            
        # Quick validation"""
content = content.replace("""
    for new_routes, desc in moves:
        # Quick validation""", replace_moves_loop)


# 3. Add file hash logic
replace_upload = """
uploaded_file = st.file_uploader("Upload Stops CSV", type=["csv"])

if uploaded_file is not None:
    import io
    file_bytes = uploaded_file.getvalue()
    file_hash = hash(file_bytes)
    
    if 'current_file_hash' not in st.session_state or st.session_state['current_file_hash'] != file_hash:
        st.session_state['current_file_hash'] = file_hash
        if 'accepted_routes' in st.session_state:
            del st.session_state['accepted_routes']
        if 'rejected_moves' in st.session_state:
            del st.session_state['rejected_moves']
            
    if 'rejected_moves' not in st.session_state:
        st.session_state['rejected_moves'] = set()
        
    df = pd.read_csv(io.BytesIO(file_bytes))
"""
content = re.sub(
    r'uploaded_file = st\.file_uploader\("Upload Stops CSV", type=\["csv"\]\)\s+if uploaded_file is not None:\s+df = pd\.read_csv\(uploaded_file\)',
    replace_upload, content
)


# 4. Use accepted_routes instead of rebuilding
replace_initial_routes = """
        # Build initial routes based on the trucks configuration
        if 'accepted_routes' not in st.session_state:
            initial_routes = [[] for _ in truck_names]
            truck_name_to_idx = {name: idx for idx, name in enumerate(truck_names)}
            
            for _, row in grouped.iterrows():
                coord = (row['Latitude'], row['Longitude'])
                node_id = coord_to_node[coord]
                if node_id == 0:
                    continue
                    
                t_name = row['Rt']
                if t_name in truck_name_to_idx:
                    t_idx = truck_name_to_idx[t_name]
                    # avoid consecutive duplicates
                    if not initial_routes[t_idx] or initial_routes[t_idx][-1] != node_id:
                        initial_routes[t_idx].append(node_id)
            st.session_state['accepted_routes'] = initial_routes
        else:
            initial_routes = st.session_state['accepted_routes']
"""
content = re.sub(
    r'        # Build initial routes based on the trucks configuration.*?initial_routes\[t_idx\]\.append\(node_id\)',
    replace_initial_routes, content, flags=re.DOTALL
)

# 5. Add rejected_moves to solve_routing call
content = content.replace(
    "allow_overcapacity=allow_overcapacity",
    "allow_overcapacity=allow_overcapacity, rejected_moves=st.session_state.get('rejected_moves', set())"
)

# 6. Add buttons to accept/reject
replace_buttons = """
                # User selected a specific local move
                move_idx = int(selected_option.split(" ")[1]) - 1
                selected_new_routes = top_moves[move_idx][3]
                
                # --- NEW BUTTONS ---
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
                st.write("---")
                # -------------------
"""
content = re.sub(
    r'                # User selected a specific local move\s+move_idx = int\(selected_option\.split\(" "\)\[1\]\) - 1\s+selected_new_routes = top_moves\[move_idx\]\[3\]',
    replace_buttons, content
)


# 7. Add export CSV button at the end
replace_export = """
            st_folium(m, width=900, height=600)
            
            st.markdown("### Export Updated Routes")
            export_rows = []
            for t_idx, route in enumerate(initial_routes):
                truck_name = truck_names[t_idx]
                for seq_idx, node in enumerate(route):
                    lat, lng = locations[node]
                    name = node_names[node]
                    
                    match = grouped[(grouped['Latitude'] == lat) & (grouped['Longitude'] == lng) & (grouped['Name'] == name)]
                    if not match.empty:
                        row_dict = match.iloc[0].to_dict()
                        row_dict['Rt'] = truck_name
                        row_dict['seq'] = seq_idx + 1
                        export_rows.append(row_dict)
                    else:
                        export_rows.append({
                            "Name": name, "Latitude": lat, "Longitude": lng, "Rt": truck_name, "seq": seq_idx + 1
                        })
                        
            export_df = pd.DataFrame(export_rows)
            csv_str = export_df.to_csv(index=False)
            st.download_button(
                label="Download Updated Routes CSV",
                data=csv_str,
                file_name="updated_routes.csv",
                mime="text/csv"
            )
"""
content = content.replace("            st_folium(m, width=900, height=600)", replace_export)

with open("app.py", "w") as f:
    f.write(content)

