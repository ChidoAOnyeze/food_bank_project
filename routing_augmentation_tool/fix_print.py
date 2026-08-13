import re
with open("app_valhalla.py", "r") as f:
    content = f.read()

replacement = """
                                if target and target.get('distance') is not None:
                                    cache[k] = int(target['distance'] * 1000)
                                else:
                                    from geopy.distance import geodesic
                                    print(f"Warning: Unroutable path between {locations[orig_i]} and {locations[orig_j]}. Using penalized fallback.")
                                    cache[k] = int(geodesic(locations[orig_i], locations[orig_j]).meters * 1.5) # Penalty for unroutable paths
"""

content = re.sub(
    r"""                                if target and target\.get\('distance'\) is not None:
                                    cache\[k\] = int\(target\['distance'\] \* 1000\)
                                else:
                                    from geopy\.distance import geodesic
                                    cache\[k\] = int\(geodesic\(locations\[orig_i\], locations\[orig_j\]\)\.meters \* 1\.5\) # Penalty for unroutable paths""",
    replacement, content
)

with open("app_valhalla.py", "w") as f:
    f.write(content)
