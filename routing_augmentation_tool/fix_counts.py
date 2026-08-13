import re
with open("app_valhalla.py", "r") as f:
    content = f.read()

# 1. Initialize counts before chunk loop
replacement1 = """        req_locations = [{"lat": locations[idx][0], "lon": locations[idx][1]} for idx in missing_list]
        
        api_success_count = 0
        api_fail_count = 0
        
        # Max matrix elements is 2500 (e.g. 50x50 = 2500)."""

content = content.replace("""        req_locations = [{"lat": locations[idx][0], "lon": locations[idx][1]} for idx in missing_list]
        
        # Max matrix elements is 2500 (e.g. 50x50 = 2500).""", replacement1)


# 2. Increment counts inside the loop
replacement2 = """                                if target and target.get('distance') is not None:
                                    cache[k] = int(target['distance'] * 1000)
                                    api_success_count += 1
                                else:
                                    from geopy.distance import geodesic
                                    print(f"Warning: Unroutable path between {locations[orig_i]} and {locations[orig_j]}. Using penalized fallback.")
                                    cache[k] = int(geodesic(locations[orig_i], locations[orig_j]).meters * 1.5) # Penalty for unroutable paths
                                    api_fail_count += 1"""

content = re.sub(
    r"""                                if target and target\.get\('distance'\) is not None:
                                    cache\[k\] = int\(target\['distance'\] \* 1000\)
                                else:
                                    from geopy\.distance import geodesic
                                    print\(f"Warning: Unroutable path between \{locations\[orig_i\]\} and \{locations\[orig_j\]\}\. Using penalized fallback\."\)
                                    cache\[k\] = int\(geodesic\(locations\[orig_i\], locations\[orig_j\]\)\.meters \* 1\.5\) # Penalty for unroutable paths""",
    replacement2, content
)


# 3. Print counts at the end of the API calls
replacement3 = """                time.sleep(0.5)
                
        print(f"Valhalla API Summary -> Successful Routes: {api_success_count} | Failed/Fallback Routes: {api_fail_count}")
                
        # Save cache after all chunks succeed"""

content = content.replace("""                time.sleep(0.5)
                
        # Save cache after all chunks succeed""", replacement3)

with open("app_valhalla.py", "w") as f:
    f.write(content)
