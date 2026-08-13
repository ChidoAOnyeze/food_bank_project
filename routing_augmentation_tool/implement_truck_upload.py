import re
with open("app_valhalla.py", "r") as f:
    content = f.read()

start_str = """        with st.expander("Trucks Configuration", expanded=False):
            unique_rts = grouped['Rt'].unique()
            
            # Calculate assigned load per route from the grouped data
            route_loads = grouped.groupby('Rt')['Total Pallets'].sum()
            
            truck_df = pd.DataFrame({
                "Name": unique_rts,
                "Initial Load": [int(route_loads.get(rt, 0)) for rt in unique_rts],
                "Capacity in Pallets": [25] * len(unique_rts)
            })
            
            st.markdown("Adjust the capacities for each truck:")
            edited_trucks = st.data_editor(truck_df, num_rows="dynamic", disabled=["Initial Load"])
        truck_names = edited_trucks["Name"].tolist()
        vehicle_capacities = [int(c) for c in edited_trucks["Capacity in Pallets"].tolist()]"""

replacement1 = """        with st.expander("Trucks Configuration", expanded=False):
            unique_rts = sorted(grouped['Rt'].dropna().unique())
            route_loads = grouped.groupby('Rt')['Total Pallets'].sum()
            
            uploaded_trucks = st.file_uploader("Upload Trucks CSV (Optional)", type=["csv"], key="truck_uploader")
            
            if uploaded_trucks is not None:
                try:
                    tdf = pd.read_csv(uploaded_trucks)
                    if 'Vehicle' in tdf.columns and 'Pallet Capacity' in tdf.columns:
                        tdf = tdf.sort_values(by='Pallet Capacity', ascending=True)
                        available_trucks = tdf.to_dict('records')
                        
                        assigned_names = []
                        assigned_caps = []
                        
                        rts_by_load = sorted(unique_rts, key=lambda r: int(route_loads.get(r, 0)), reverse=True)
                        assignment_map = {}
                        
                        for rt in rts_by_load:
                            load = int(route_loads.get(rt, 0))
                            assigned = False
                            for i, t in enumerate(available_trucks):
                                if int(t['Pallet Capacity']) >= load:
                                    assignment_map[rt] = (t['Vehicle'], int(t['Pallet Capacity']))
                                    available_trucks.pop(i)
                                    assigned = True
                                    break
                            
                            if not assigned:
                                if available_trucks:
                                    t = available_trucks.pop(-1)
                                    assignment_map[rt] = (t['Vehicle'], int(t['Pallet Capacity']))
                                else:
                                    assignment_map[rt] = (f"Unassigned_Truck_for_{rt}", 25)
                                    
                        for rt in unique_rts:
                            assigned_names.append(assignment_map[rt][0])
                            assigned_caps.append(assignment_map[rt][1])
                            
                        truck_df = pd.DataFrame({
                            "Rt": unique_rts,
                            "Vehicle Name": assigned_names,
                            "Initial Load": [int(route_loads.get(rt, 0)) for rt in unique_rts],
                            "Capacity in Pallets": assigned_caps
                        })
                    else:
                        st.error("Trucks CSV must contain 'Vehicle' and 'Pallet Capacity' columns.")
                        truck_df = pd.DataFrame({
                            "Rt": unique_rts,
                            "Vehicle Name": unique_rts,
                            "Initial Load": [int(route_loads.get(rt, 0)) for rt in unique_rts],
                            "Capacity in Pallets": [25] * len(unique_rts)
                        })
                except Exception as e:
                    st.error(f"Error reading trucks CSV: {e}")
                    truck_df = pd.DataFrame({
                        "Rt": unique_rts,
                        "Vehicle Name": unique_rts,
                        "Initial Load": [int(route_loads.get(rt, 0)) for rt in unique_rts],
                        "Capacity in Pallets": [25] * len(unique_rts)
                    })
            else:
                truck_df = pd.DataFrame({
                    "Rt": unique_rts,
                    "Vehicle Name": unique_rts,
                    "Initial Load": [int(route_loads.get(rt, 0)) for rt in unique_rts],
                    "Capacity in Pallets": [25] * len(unique_rts)
                })
            
            st.markdown("Adjust the assignments and capacities:")
            edited_trucks = st.data_editor(truck_df, num_rows="dynamic", disabled=["Initial Load", "Rt"])
            
        truck_names = edited_trucks["Vehicle Name"].tolist()
        vehicle_capacities = [int(c) for c in edited_trucks["Capacity in Pallets"].tolist()]
        rt_to_vehicle = dict(zip(edited_trucks["Rt"], edited_trucks["Vehicle Name"]))"""

content = content.replace(start_str, replacement1)

# Fix initial route building logic since I previously did it but wait I did it wrongly because I had NameErrors!
start_str2 = """                rt_name = row['Rt']
                if rt_name in rt_to_vehicle:
                    t_name = rt_to_vehicle[rt_name]
                    if t_name in truck_name_to_idx:
                        t_idx = truck_name_to_idx[t_name]
                    # avoid consecutive duplicates
                    if not initial_routes[t_idx] or initial_routes[t_idx][-1] != node_id:
                        initial_routes[t_idx].append(node_id)"""
# actually, wait, the `rt_name in rt_to_vehicle` replacement DID successfully happen previously? Let's check!
