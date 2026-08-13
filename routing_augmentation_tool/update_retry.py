import re
with open("app_valhalla.py", "r") as f:
    content = f.read()

start_str = "        # Max matrix elements is 2500"
end_str = "        print(f\"Valhalla API Summary"

start_idx = content.find(start_str)
end_idx = content.find(end_str)

replacement = """        def fetch_chunk_with_retry(s_chunk, t_chunk, idx_i, idx_j, allow_halving=True):
            s_count = 0
            f_count = 0
            delays = [0, 5, 10, 15] # 0 for the first attempt
            
            for attempt, delay in enumerate(delays):
                if delay > 0:
                    print(f"Retrying in {delay} seconds (Attempt {attempt + 1})...")
                    time.sleep(delay)
                    
                payload = {
                    "sources": s_chunk,
                    "targets": t_chunk,
                    "costing": "truck",
                    "units": "kilometers"
                }
                
                try:
                    resp = requests.post("https://valhalla1.openstreetmap.de/sources_to_targets", json=payload, timeout=20)
                    if resp.status_code == 200:
                        data = resp.json().get("sources_to_targets", [])
                        for r_idx, row in enumerate(data):
                            for c_idx, target in enumerate(row):
                                orig_i = idx_i[r_idx]
                                orig_j = idx_j[c_idx]
                                k = f"{locations[orig_i][0]},{locations[orig_i][1]}|{locations[orig_j][0]},{locations[orig_j][1]}"
                                
                                if target and target.get('distance') is not None:
                                    cache[k] = int(target['distance'] * 1000)
                                    s_count += 1
                                else:
                                    from geopy.distance import geodesic
                                    print(f"Warning: Unroutable path between {locations[orig_i]} and {locations[orig_j]}. Using penalized fallback.")
                                    cache[k] = int(geodesic(locations[orig_i], locations[orig_j]).meters * 1.5)
                                    f_count += 1
                        time.sleep(0.5) # Rate limit respect
                        return True, s_count, f_count
                    else:
                        print(f"Valhalla API Error {resp.status_code}: {resp.text}")
                except Exception as e:
                    print(f"Valhalla Request Failed: {e}")
                    
            # All 4 attempts failed
            if allow_halving:
                print("All 4 attempts failed. Halving batch size and repeating once...")
                mid_s = len(s_chunk) // 2
                mid_t = len(t_chunk) // 2
                
                s_chunks = [(s_chunk[:mid_s], idx_i[:mid_s]), (s_chunk[mid_s:], idx_i[mid_s:])] if mid_s > 0 else [(s_chunk, idx_i)]
                t_chunks = [(t_chunk[:mid_t], idx_j[:mid_t]), (t_chunk[mid_t:], idx_j[mid_t:])] if mid_t > 0 else [(t_chunk, idx_j)]
                
                for sc, i_i in s_chunks:
                    if not sc: continue
                    for tc, i_j in t_chunks:
                        if not tc: continue
                        success, scount, fcount = fetch_chunk_with_retry(sc, tc, i_i, i_j, allow_halving=False)
                        s_count += scount
                        f_count += fcount
                        if not success:
                            return False, s_count, f_count
                return True, s_count, f_count
            else:
                return False, s_count, f_count

        # Max matrix elements is 2500 (e.g. 50x50 = 2500).
        # We chunk into 40x40 batches = 1600 elements per request to be safe.
        chunk_size = 40
        for i in range(0, len(req_locations), chunk_size):
            sources_chunk = req_locations[i : i + chunk_size]
            indices_i = missing_list[i : i + chunk_size]
            
            for j in range(0, len(req_locations), chunk_size):
                targets_chunk = req_locations[j : j + chunk_size]
                indices_j = missing_list[j : j + chunk_size]
                
                success, s_count, f_count = fetch_chunk_with_retry(sources_chunk, targets_chunk, indices_i, indices_j, allow_halving=True)
                api_success_count += s_count
                api_fail_count += f_count
                
                if not success:
                    error_msg = "Valhalla API permanently failed after all retries and halving."
                    print(error_msg)
                    st.error(error_msg)
                    st.stop()
                    
"""

new_content = content[:start_idx] + replacement + content[end_idx:]

with open("app_valhalla.py", "w") as f:
    f.write(new_content)
