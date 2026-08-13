import re
with open("app_valhalla.py", "r") as f:
    content = f.read()

replacement = """
            # Sort the truck list by capacity descending, then by initial load descending
            truck_df = truck_df.sort_values(by=["Capacity in Pallets", "Initial Load"], ascending=[False, False]).reset_index(drop=True)
"""

content = re.sub(
    r"""            # Sort the truck list by capacity descending
            truck_df = truck_df\.sort_values\(by="Capacity in Pallets", ascending=False\)\.reset_index\(drop=True\)""",
    replacement, content
)

with open("app_valhalla.py", "w") as f:
    f.write(content)
