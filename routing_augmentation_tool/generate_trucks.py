import csv

trucks = []

# 20 trucks of capacity 10
for i in range(1, 21):
    trucks.append({"Vehicle": f"Truck_Cap10_{i}", "Pallet Capacity": 10})

# 15 trucks of capacity 12
for i in range(1, 16):
    trucks.append({"Vehicle": f"Truck_Cap12_{i}", "Pallet Capacity": 12})

# 4 trucks of capacity 22
for i in range(1, 5):
    trucks.append({"Vehicle": f"Truck_Cap22_{i}", "Pallet Capacity": 22})

with open("test_trucks.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["Vehicle", "Pallet Capacity"])
    writer.writeheader()
    writer.writerows(trucks)
    
print("Updated test_trucks.csv")
