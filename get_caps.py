import csv
from cvrp_itp import cvrp_itp

def get_cap(stops, k):
    demands = [float(s['Weight'].replace(',', '')) if s['Weight'] else 1.0 for s in stops]
    low, high = max(demands) if demands else 1, sum(demands) if demands else 10
    best_cap = high
    for _ in range(50):
        mid = (low + high) / 2
        r = cvrp_itp((0,0), [ (0,0) for _ in demands ], demands, mid) # dummy locations
        best_cap = mid
        if len(r) == k: break
        elif len(r) > k: low = mid
        else: high = mid
    return best_cap

with open('sample_orders_routing.csv', 'r', encoding='utf-8') as f:
    data = list(csv.DictReader(f))
    
m = [r for r in data if r.get('Open1') == '0830' and r.get('Close1') == '1230']
a = [r for r in data if r.get('Open1') == '1230' and r.get('Close1') == '1630']

# Morning actual k was 30. Afternoon actual k was 8.
print("Morning Capacity:", get_cap(m, 30))
print("Afternoon Capacity:", get_cap(a, 8))
