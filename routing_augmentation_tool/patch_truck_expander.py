import re

with open('app.py', 'r') as f:
    content = f.read()

old_block = """        st.subheader("Trucks Configuration")
        unique_rts = grouped['Rt'].unique()
        
        # Calculate assigned load per route from the grouped data
        route_loads = grouped.groupby('Rt')['Total Pallets'].sum()
        
        truck_df = pd.DataFrame({
            "Name": unique_rts,
            "Initial Load": [int(route_loads.get(rt, 0)) for rt in unique_rts],
            "Capacity in Pallets": [25] * len(unique_rts)
        })
        
        st.markdown("Adjust the capacities for each truck:")
        edited_trucks = st.data_editor(truck_df, num_rows="dynamic", disabled=["Initial Load"])"""

new_block = """        with st.expander("Trucks Configuration", expanded=False):
            unique_rts = grouped['Rt'].unique()
            
            # Calculate assigned load per route from the grouped data
            route_loads = grouped.groupby('Rt')['Total Pallets'].sum()
            
            truck_df = pd.DataFrame({
                "Name": unique_rts,
                "Initial Load": [int(route_loads.get(rt, 0)) for rt in unique_rts],
                "Capacity in Pallets": [25] * len(unique_rts)
            })
            
            st.markdown("Adjust the capacities for each truck:")
            edited_trucks = st.data_editor(truck_df, num_rows="dynamic", disabled=["Initial Load"])"""

content = content.replace(old_block, new_block)

with open('app.py', 'w') as f:
    f.write(content)

