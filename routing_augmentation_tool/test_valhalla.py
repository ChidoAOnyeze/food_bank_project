import requests
import json
import pandas as pd

print("1. Reading test_input.csv...")
df = pd.read_csv("test_input.csv")
print(f"Loaded {len(df)} locations.")

# The Valhalla API expects locations as a list of dicts: {"lat": x, "lon": y}
# We use the same points for both 'sources' and 'targets' to create an NxN matrix
locations = []
for _, row in df.iterrows():
    locations.append({
        "lat": row['Latitude'],
        "lon": row['Longitude']
    })

# Add the depot as the first point
depot = {"lat": 40.80594755, "lon": -73.87299938}
locations.insert(0, depot)

# 2. Build the API Request Payload
# We use costing="truck" to ensure it respects parkways, bridges, and commercial bans
valhalla_payload = {
    "sources": locations,
    "targets": locations,
    "costing": "truck",
    "units": "miles"
}

# 3. Hit the free public Valhalla server hosted by OpenStreetMap Germany
url = "https://valhalla1.openstreetmap.de/sources_to_targets"

print("\n2. Sending Matrix Request to Valhalla (costing='truck')...")
response = requests.post(url, json=valhalla_payload)

if response.status_code == 200:
    data = response.json()
    matrix = data.get("sources_to_targets", [])
    
    print("\n3. Successfully received Distance & Time Matrix!")
    print(f"Matrix size: {len(matrix)}x{len(matrix[0])} (Total {len(matrix)*len(matrix[0])} routing combinations)\n")
    
    # Let's print out the distances from the Depot to all stops
    print("--- Driving Distances from the Depot (Truck Routing) ---")
    depot_to_others = matrix[0] # First row corresponds to Depot -> Others
    
    for i, target in enumerate(depot_to_others):
        if i == 0:
            continue
        stop_name = df.iloc[i-1]['Name']
        distance_miles = target['distance']
        time_minutes = target['time'] / 60
        print(f"Depot to {stop_name}: {distance_miles:.2f} miles ({time_minutes:.1f} minutes)")
else:
    print(f"Error: {response.status_code}")
    print(response.text)

