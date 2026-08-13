import re
with open("app_valhalla.py", "r") as f:
    content = f.read()

replacement = """                    if 'Vehicle' in tdf.columns and 'Pallet Capacity' in tdf.columns:
                        # Sort by capacity DESCENDING to assign the absolute largest trucks to the largest loads, maximizing slack
                        tdf = tdf.sort_values(by='Pallet Capacity', ascending=False)
                        available_trucks = tdf.to_dict('records')"""

content = re.sub(
    r"""                    if 'Vehicle' in tdf\.columns and 'Pallet Capacity' in tdf\.columns:
                        tdf = tdf\.sort_values\(by='Pallet Capacity', ascending=True\)
                        available_trucks = tdf\.to_dict\('records'\)""",
    replacement, content
)

with open("app_valhalla.py", "w") as f:
    f.write(content)
