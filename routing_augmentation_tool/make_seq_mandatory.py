import re
with open("app.py", "r") as f:
    content = f.read()

# Update required_cols
content = content.replace(
    "required_cols = ['Name', 'Longitude', 'Latitude', 'Rt', 'Food Pallets', 'Pet Food Pallets', 'Chemical Pallets']",
    "required_cols = ['Name', 'Longitude', 'Latitude', 'Rt', 'seq', 'Food Pallets', 'Pet Food Pallets', 'Chemical Pallets']"
)

# Remove the fallback for seq
content = content.replace(
    """        # Pre-process: group by location to merge deliveries
        if 'seq' not in df.columns:
            df['seq'] = df.index""",
    "        # Pre-process: group by location to merge deliveries"
)

with open("app.py", "w") as f:
    f.write(content)
