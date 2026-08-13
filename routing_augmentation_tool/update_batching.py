import re
with open("app_valhalla.py", "r") as f:
    content = f.read()

# We need to replace the entire 'if missing_indices:' block
replacement = """
    if missing_indices:
        import streamlit as st
        import time
        # Ask valhalla for a matrix of ONLY the locations that are missing data
        missing_list = list(missing_indices)
        req_locations = [{"lat": locations[idx][0], "lon": locations[idx][1]} for idx in missing_list]
        
        # Max matrix elements is 2500 (e.g. 50x50 = 2500).
        # We chunk into 40x40 batches = 1600 elements per request to be safe.
        chunk_size = 40
        for i in range(0, len(req_locations), chunk_size):
            sources_chunk = req_locations[i : i + chunk_size]
            indices_i = missing_list[i : i + chunk_size]
            
            for j in range(0, len(req_locations), chunk_size):
                targets_chunk = req_locations[j : j + chunk_size]
                indices_j = missing_list[j : j + chunk_size]
                
                payload = {
                    "sources": sources_chunk,
                    "targets": targets_chunk,
                    "costing": "truck",
                    "units": "kilometers"
                }
                
                try:
                    resp = requests.post("https://valhalla1.openstreetmap.de/sources_to_targets", json=payload, timeout=20)
                    if resp.status_code == 200:
                        data = resp.json().get("sources_to_targets", [])
                        for r_idx, row in enumerate(data):
                            for c_idx, target in enumerate(row):
                                orig_i = indices_i[r_idx]
                                orig_j = indices_j[c_idx]
                                k = f"{locations[orig_i][0]},{locations[orig_i][1]}|{locations[orig_j][0]},{locations[orig_j][1]}"
                                cache[k] = int(target['distance'] * 1000)
                    else:
                        error_msg = f"Valhalla API Error {resp.status_code}: {resp.text}"
                        print(error_msg)
                        st.error(error_msg)
                        st.stop()
                except Exception as e:
                    error_msg = f"Valhalla Request Failed: {e}"
                    print(error_msg)
                    st.error(error_msg)
                    st.stop()
                    
                # Brief sleep to respect free API rate limits
                time.sleep(0.5)
                
        # Save cache after all chunks succeed
        with open(VALHALLA_CACHE_FILE, "w") as f:
            json.dump(cache, f)
"""

# Find the block to replace
start_str = "    if missing_indices:"
end_str = "    # Now populate matrix"

start_idx = content.find(start_str)
end_idx = content.find(end_str)

new_content = content[:start_idx] + replacement + "\n" + content[end_idx:]

with open("app_valhalla.py", "w") as f:
    f.write(new_content)

