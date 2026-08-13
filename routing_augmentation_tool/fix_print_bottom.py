import re
with open("app_valhalla.py", "r") as f:
    content = f.read()

replacement = """
            else:
                # Fallback to geodesic if API fails
                print(f"Warning: Cache miss for {locations[i]} to {locations[j]}. Using geodesic fallback.")
                distance_matrix[i][j] = int(geodesic(locations[i], locations[j]).meters)
"""

content = re.sub(
    r"""            else:
                # Fallback to geodesic if API fails
                distance_matrix\[i\]\[j\] = int\(geodesic\(locations\[i\], locations\[j\]\)\.meters\)""",
    replacement, content
)

with open("app_valhalla.py", "w") as f:
    f.write(content)
