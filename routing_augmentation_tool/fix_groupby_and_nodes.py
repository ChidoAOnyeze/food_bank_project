import re

for filename in ["app_valhalla_road_path.py", "app_valhalla.py"]:
    with open(filename, "r") as f:
        content = f.read()

    # 1. Update groupby to include 'Rt'
    old_groupby = """        agg_funcs = {
            'Food Pallets': 'sum',
            'Pet Food Pallets': 'sum',
            'Chemical Pallets': 'sum',
            'Rt': 'first',
            'seq': 'min'
        }
        if 'Weight' in df.columns:
            agg_funcs['Weight'] = 'sum'
            
        grouped = df.groupby(['Latitude', 'Longitude', 'Name'], as_index=False).agg(agg_funcs)"""

    new_groupby = """        agg_funcs = {
            'Food Pallets': 'sum',
            'Pet Food Pallets': 'sum',
            'Chemical Pallets': 'sum',
            'seq': 'min'
        }
        if 'Weight' in df.columns:
            agg_funcs['Weight'] = 'sum'
            
        # Group by Latitude, Longitude, Name, AND Rt to ensure separate truck deliveries to the same customer are NOT merged!
        grouped = df.groupby(['Latitude', 'Longitude', 'Name', 'Rt'], as_index=False).agg(agg_funcs)"""

    content = content.replace(old_groupby, new_groupby)

    # 2. Update locations, demands, and initial_routes building to 1-to-1 map grouped rows
    old_locations_block = """        # Build locations and demands lists
        locations = [depot_coords]
        demands = [0]
        node_names = ["Depot"]
        coord_to_node = {depot_coords: 0}
        
        for _, row in grouped.iterrows():
            coord = (row['Latitude'], row['Longitude'])
            if coord not in coord_to_node:
                coord_to_node[coord] = len(locations)
                locations.append(coord)
                demands.append(int(row['Total Pallets']))
                node_names.append(row['Name'])
                
        total_demand = sum(demands)
        total_capacity = sum(vehicle_capacities)
        
        cap_col1, cap_col2 = st.columns(2)
        cap_col1.metric("Total Pallets Needed (Demand)", total_demand)
        
        if total_capacity < total_demand:
            cap_col2.metric("Total Truck Capacity", total_capacity, "-Insufficient Capacity", delta_color="normal")
        else:
            cap_col2.metric("Total Truck Capacity", total_capacity)


        # Build initial routes based on the trucks configuration
        if 'accepted_routes' not in st.session_state:
            initial_routes = [[] for _ in truck_names]
            truck_name_to_idx = {name: idx for idx, name in enumerate(truck_names)}
            
            for _, row in grouped.iterrows():
                coord = (row['Latitude'], row['Longitude'])
                node_id = coord_to_node[coord]
                if node_id == 0:
                    continue
                    
                rt_name = row['Rt']
                if rt_name in rt_to_vehicle:
                    t_name = rt_to_vehicle[rt_name]
                    if t_name in truck_name_to_idx:
                        t_idx = truck_name_to_idx[t_name]
                        # avoid consecutive duplicates
                        if not initial_routes[t_idx] or initial_routes[t_idx][-1] != node_id:
                            initial_routes[t_idx].append(node_id)
            st.session_state['accepted_routes'] = initial_routes
        else:
            initial_routes = st.session_state['accepted_routes']"""

    new_locations_block = """        # Build locations and demands lists directly from grouped rows (1 node per grouped delivery)
        locations = [depot_coords]
        demands = [0]
        node_names = ["Depot"]
        
        for _, row in grouped.iterrows():
            locations.append((row['Latitude'], row['Longitude']))
            demands.append(int(row['Total Pallets']))
            node_names.append(row['Name'])
                
        total_demand = sum(demands)
        total_capacity = sum(vehicle_capacities)
        
        cap_col1, cap_col2 = st.columns(2)
        cap_col1.metric("Total Pallets Needed (Demand)", total_demand)
        
        if total_capacity < total_demand:
            cap_col2.metric("Total Truck Capacity", total_capacity, "-Insufficient Capacity", delta_color="normal")
        else:
            cap_col2.metric("Total Truck Capacity", total_capacity)


        # Build initial routes based on the trucks configuration
        if 'accepted_routes' not in st.session_state:
            initial_routes = [[] for _ in truck_names]
            truck_name_to_idx = {name: idx for idx, name in enumerate(truck_names)}
            
            for row_idx, row in grouped.iterrows():
                node_id = row_idx + 1 # 1-indexed (0 is Depot)
                rt_name = row['Rt']
                if rt_name in rt_to_vehicle:
                    t_name = rt_to_vehicle[rt_name]
                    if t_name in truck_name_to_idx:
                        t_idx = truck_name_to_idx[t_name]
                        initial_routes[t_idx].append(node_id)
            st.session_state['accepted_routes'] = initial_routes
        else:
            initial_routes = st.session_state['accepted_routes']"""

    content = content.replace(old_locations_block, new_locations_block)

    with open(filename, "w") as f:
        f.write(content)

    print(f"Updated {filename}")
