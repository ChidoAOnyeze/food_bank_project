import csv
import collections
import os
import re
import pandas as pd

DEFAULT_DEPOT = (40.80594755, -73.87299938) # (Lat, Lon) of Food Bank for NYC

class RoutingInstance:
    """
    Standardized Routing Instance data container.
    """
    def __init__(self, name, date, depot, locations, demands, actual_routes, truck_names=None, node_names=None):
        self.name = name
        self.date = date # Date string (e.g. "2026-05-28", "12/2/2025")
        self.depot = depot # (lat, lon)
        self.locations = locations # [(lat, lon), ...]
        self.demands = demands # [float, ...]
        self.actual_routes = actual_routes # [[(lat, lon), ...], ...]
        self.truck_names = truck_names or [f"Truck {i+1}" for i in range(len(actual_routes))]
        self.node_names = node_names or {}

    @property
    def num_trucks(self):
        return len(self.actual_routes)

    @property
    def num_stops(self):
        return len(self.locations)

    @property
    def demands_map(self):
        return dict(zip(self.locations, self.demands))

def find_column(df_columns, candidates):
    cols_lower = {str(c).strip().lower(): c for c in df_columns}
    for cand in candidates:
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    return None

def extract_date_from_filename(filename):
    """
    Extracts date if embedded in filename (e.g. anon_routed_orders_5_28_26.csv -> 5/28/2026).
    """
    base = os.path.basename(filename)
    m = re.search(r'(\d{1,2})[._-](\d{1,2})[._-](\d{2,4})', base)
    if m:
        m1, d1, y1 = m.groups()
        if len(y1) == 2:
            y1 = "20" + y1
        return f"{m1}/{d1}/{y1}"
    return "N/A"

def load_route_instances(file_path, depot=None):
    """
    Intelligently parses any route CSV file into one or more RoutingInstance objects.
    Supports single-day files, multi-day files, and time-window partitioned files.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input route file not found: {file_path}")

    depot = depot or DEFAULT_DEPOT

    # Read CSV
    df = pd.read_csv(file_path)
    df.columns = [str(c).strip() for c in df.columns]

    # Detect Lat/Lon columns
    lat_col = find_column(df.columns, ['latitude', 'lat', 'y'])
    lon_col = find_column(df.columns, ['longitude', 'lon', 'lng', 'long', 'x'])
    route_col = find_column(df.columns, ['rt', 'route name', 'route', 'truck', 'truck name', 'route_name', 'vehicle'])
    seq_col = find_column(df.columns, ['seq', 'stop sequence id (index)', 'stop sequence', 'sequence', 'stop_seq'])
    name_col = find_column(df.columns, ['name', 'address name', 'customer name', 'stop id', 'customer number'])
    date_col = find_column(df.columns, ['date', 'orderdate', 'shipment date', 'delivery date'])
    
    if not lat_col or not lon_col:
        raise ValueError(f"Could not identify Latitude and Longitude columns in {file_path}. Found columns: {list(df.columns)}")

    # Demand columns detection
    food_p = find_column(df.columns, ['food pallets'])
    pet_p = find_column(df.columns, ['pet food pallets'])
    chem_p = find_column(df.columns, ['chemical pallets'])
    weight_col = find_column(df.columns, ['weight', 'total weight nh', 'quantity', 'demand', 'pallets'])

    def compute_demand(row):
        total_p = 0.0
        found = False
        if food_p and pd.notna(row[food_p]):
            total_p += float(row[food_p])
            found = True
        if pet_p and pd.notna(row[pet_p]):
            total_p += float(row[pet_p])
            found = True
        if chem_p and pd.notna(row[chem_p]):
            total_p += float(row[chem_p])
            found = True
        if found:
            return round(total_p, 2)
        if weight_col and pd.notna(row[weight_col]):
            try:
                val = str(row[weight_col]).replace(',', '').strip()
                return float(val)
            except Exception:
                return 1.0
        return 1.0

    # Grouping logic
    time_window_col = find_column(df.columns, ['open1'])
    instances = []

    if date_col and df[date_col].nunique() > 1:
        grouped_by_instance = df.groupby(date_col)
    elif time_window_col and df[time_window_col].nunique() > 1:
        grouped_by_instance = df.groupby(time_window_col)
    else:
        grouped_by_instance = [(os.path.basename(file_path), df)]

    for inst_key, sub_df in grouped_by_instance:
        sub_df = sub_df.dropna(subset=[lat_col, lon_col])
        if sub_df.empty:
            continue

        # Extract explicit date string
        if date_col and sub_df[date_col].notna().any():
            raw_date = str(sub_df[date_col].dropna().iloc[0]).strip()
            date_str = raw_date.split(' ')[0]
        else:
            date_str = extract_date_from_filename(file_path)

        # Build routes
        actual_routes = []
        truck_names = []
        node_names = {}
        all_locations = []
        all_demands = []

        if route_col:
            for rt_name, rt_group in sub_df.groupby(route_col):
                if seq_col:
                    try:
                        rt_group = rt_group.sort_values(by=seq_col)
                    except Exception:
                        pass

                curr_route = []
                for _, row in rt_group.iterrows():
                    lat = float(row[lat_col])
                    lon = float(row[lon_col])
                    loc = (lat, lon)
                    
                    # Skip depot if explicitly in row
                    if abs(lat - depot[0]) < 0.0005 and abs(lon - depot[1]) < 0.0005:
                        continue

                    curr_route.append(loc)
                    all_locations.append(loc)
                    demand = compute_demand(row)
                    all_demands.append(demand)

                    if name_col and pd.notna(row[name_col]):
                        node_names[loc] = str(row[name_col])
                    else:
                        node_names[loc] = f"Stop ({lat:.4f}, {lon:.4f})"

                if curr_route:
                    actual_routes.append(curr_route)
                    truck_names.append(str(rt_name))
        else:
            curr_route = []
            for _, row in sub_df.iterrows():
                lat = float(row[lat_col])
                lon = float(row[lon_col])
                loc = (lat, lon)
                if abs(lat - depot[0]) < 0.0005 and abs(lon - depot[1]) < 0.0005:
                    continue
                curr_route.append(loc)
                all_locations.append(loc)
                all_demands.append(compute_demand(row))
                if name_col and pd.notna(row[name_col]):
                    node_names[loc] = str(row[name_col])
                else:
                    node_names[loc] = f"Stop ({lat:.4f}, {lon:.4f})"
            if curr_route:
                actual_routes.append(curr_route)
                truck_names.append("Truck 1")

        if not all_locations or not actual_routes:
            continue

        base_fname = os.path.splitext(os.path.basename(file_path))[0]
        instance_name = f"{base_fname} [{date_str}]" if date_str != "N/A" else f"{base_fname} [{inst_key}]"
        
        inst = RoutingInstance(
            name=instance_name,
            date=date_str,
            depot=depot,
            locations=all_locations,
            demands=all_demands,
            actual_routes=actual_routes,
            truck_names=truck_names,
            node_names=node_names
        )
        instances.append(inst)

    return instances
