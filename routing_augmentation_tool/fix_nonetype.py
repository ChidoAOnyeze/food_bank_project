import re
with open("app_valhalla.py", "r") as f:
    content = f.read()

replacement = """
                                orig_i = indices_i[r_idx]
                                orig_j = indices_j[c_idx]
                                k = f"{locations[orig_i][0]},{locations[orig_i][1]}|{locations[orig_j][0]},{locations[orig_j][1]}"
                                
                                if target and target.get('distance') is not None:
                                    cache[k] = int(target['distance'] * 1000)
                                else:
                                    from geopy.distance import geodesic
                                    cache[k] = int(geodesic(locations[orig_i], locations[orig_j]).meters * 1.5) # Penalty for unroutable paths
"""

content = re.sub(
    r"""                                orig_i = indices_i\[r_idx\]
                                orig_j = indices_j\[c_idx\]
                                k = f"\{locations\[orig_i\]\[0\]\},\{locations\[orig_i\]\[1\]\}\|\{locations\[orig_j\]\[0\]\},\{locations\[orig_j\]\[1\]\}"
                                cache\[k\] = int\(target\['distance'\] \* 1000\)""",
    replacement, content
)

with open("app_valhalla.py", "w") as f:
    f.write(content)
