import re
with open("app_valhalla.py", "r") as f:
    content = f.read()

replacement = """
            # Sort the truck list by capacity descending
            truck_df = truck_df.sort_values(by="Capacity in Pallets", ascending=False).reset_index(drop=True)
            
            st.markdown("Adjust the assignments and capacities:")
            edited_trucks = st.data_editor(truck_df, num_rows="dynamic", disabled=["Initial Load", "Rt"])
"""

content = re.sub(
    r"""            st\.markdown\("Adjust the assignments and capacities:"\)
            edited_trucks = st\.data_editor\(truck_df, num_rows="dynamic", disabled=\["Initial Load", "Rt"\]\)""",
    replacement, content
)

with open("app_valhalla.py", "w") as f:
    f.write(content)
