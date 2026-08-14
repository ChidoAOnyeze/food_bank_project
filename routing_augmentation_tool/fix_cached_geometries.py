import json
import time
import requests

with open('valhalla_geom_cache.json', 'r') as f:
    cache = json.load(f)

straight_keys = [k for k, v in cache.items() if len(v) <= 2]
print(f"Found {len(straight_keys)} straight-line keys to fix.")

def decode_polyline(encoded, precision=6):
    inv = 1.0 / (10 ** precision)
    decoded = []
    lat = 0
    lng = 0
    index = 0
    length = len(encoded)
    while index < length:
        shift = 0; result = 0
        while True:
            byte = ord(encoded[index]) - 63; index += 1
            result |= (byte & 0x1f) << shift; shift += 5
            if byte < 0x20: break
        dlat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += dlat
        
        shift = 0; result = 0
        while True:
            byte = ord(encoded[index]) - 63; index += 1
            result |= (byte & 0x1f) << shift; shift += 5
            if byte < 0x20: break
        dlng = ~(result >> 1) if (result & 1) else (result >> 1)
        lng += dlng
        decoded.append((lat * inv, lng * inv))
    return decoded

fixed_count = 0
for i, k in enumerate(straight_keys):
    p1_str, p2_str = k.split('|')
    p1 = [float(x) for x in p1_str.split(',')]
    p2 = [float(x) for x in p2_str.split(',')]
    
    # Try truck, then auto
    success = False
    for costing in ['truck', 'auto']:
        payload = {
            'locations': [{'lat': p1[0], 'lon': p1[1]}, {'lat': p2[0], 'lon': p2[1]}],
            'costing': costing,
            'units': 'kilometers'
        }
        try:
            resp = requests.post('https://valhalla1.openstreetmap.de/route', json=payload, timeout=10)
            if resp.status_code == 200:
                legs = resp.json().get('trip', {}).get('legs', [])
                if legs and 'shape' in legs[0]:
                    coords = decode_polyline(legs[0]['shape'])
                    if len(coords) > 2:
                        cache[k] = coords
                        fixed_count += 1
                        success = True
                        break
        except Exception as e:
            pass
        time.sleep(0.1)

    if not success:
        # Delete from cache so it doesn't trick the app into thinking it's cached
        del cache[k]

with open('valhalla_geom_cache.json', 'w') as f:
    json.dump(cache, f)

print(f"Fixed {fixed_count} legs. Removed {len(straight_keys) - fixed_count} failed straight lines from cache.")
