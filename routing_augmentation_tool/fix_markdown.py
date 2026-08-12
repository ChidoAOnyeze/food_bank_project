import re
with open("app.py", "r") as f:
    content = f.read()

content = content.replace(
    "**Required columns**: `Name`, `Longitude`, `Latitude`, `Rt`, `Food Pallets`, `Pet Food Pallets`, `Chemical Pallets`.",
    "**Required columns**: `Name`, `Longitude`, `Latitude`, `Rt`, `seq`, `Food Pallets`, `Pet Food Pallets`, `Chemical Pallets`."
)
content = content.replace(
    "Optional columns: `Weight`, `seq`",
    "Optional columns: `Weight`"
)

with open("app.py", "w") as f:
    f.write(content)
