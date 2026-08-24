import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re
import math
import pandas as pd

from validator import inspect_and_diagnose_csv, DataValidationError

DAYS_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

def find_column(df_columns, candidates):
    cols_lower = {str(c).strip().lower(): c for c in df_columns}
    for cand in candidates:
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    return None

def extract_date_from_filename(filename):
    base = os.path.basename(filename)
    m = re.search(r'(\d{1,2})[._-](\d{1,2})[._-](\d{2,4})', base)
    if m:
        m1, d1, y1 = m.groups()
        if len(y1) == 2:
            y1 = "20" + y1
        return f"{m1}/{d1}/{y1}"
    return None

def load_and_preprocess_orders(file_source, rounding_mode='ceil', raise_on_fatal=True):
    """
    Loads order/routing CSV file, performs comprehensive cell-level validation,
    pinpoints and logs bad inputs with row numbers, and computes customer demands.
    
    rounding_mode: 'ceil' (math.ceil) or 'round' (round to nearest int).
    """
    file_name = file_source if isinstance(file_source, str) else getattr(file_source, 'name', 'uploaded_file.csv')

    # 1. Run deep validation & diagnostics
    is_valid, fatal_errors, row_issues, cleaned_df = inspect_and_diagnose_csv(file_source, raise_on_fatal=raise_on_fatal)

    if not is_valid or cleaned_df is None:
        err_msg = fatal_errors[0]['description'] if fatal_errors else "CSV Validation Failed."
        raise DataValidationError(err_msg, fatal_errors)

    df = cleaned_df.copy()

    # Detect Columns
    lat_col = find_column(df.columns, ['latitude', 'lat', 'y'])
    lon_col = find_column(df.columns, ['longitude', 'lon', 'lng', 'long', 'x'])
    cust_id_col = find_column(df.columns, ['customer number', 'customer id', 'customer_id', 'cust id', 'stop id', 'address id'])
    name_col = find_column(df.columns, ['name', 'customer name', 'address name', 'stop name', 'client'])
    addr_col = find_column(df.columns, ['address', 'street', 'location'])
    city_col = find_column(df.columns, ['city', 'borough', 'county'])
    date_col = find_column(df.columns, ['date', 'orderdate', 'shipment date', 'delivery date', 'order_date'])

    # Convert coordinates to float
    df['latitude'] = pd.to_numeric(df[lat_col], errors='coerce')
    df['longitude'] = pd.to_numeric(df[lon_col], errors='coerce')

    # Date parsing
    if date_col and df[date_col].notna().any():
        df['parsed_date'] = pd.to_datetime(df[date_col], errors='coerce')
    else:
        # Check filename
        file_date_str = extract_date_from_filename(file_name)
        if file_date_str:
            df['parsed_date'] = pd.to_datetime(file_date_str, errors='coerce')
        else:
            df['parsed_date'] = pd.NaT

    df['day_of_week'] = df['parsed_date'].dt.day_name().fillna('Unknown')

    # Pallet demands
    food_p = find_column(df.columns, ['food pallets'])
    pet_p = find_column(df.columns, ['pet food pallets'])
    chem_p = find_column(df.columns, ['chemical pallets'])
    weight_col = find_column(df.columns, ['weight', 'total weight nh', 'quantity', 'demand', 'pallets'])

    food_vals = pd.to_numeric(df[food_p], errors='coerce').fillna(0.0) if food_p else 0.0
    pet_vals = pd.to_numeric(df[pet_p], errors='coerce').fillna(0.0) if pet_p else 0.0
    chem_vals = pd.to_numeric(df[chem_p], errors='coerce').fillna(0.0) if chem_p else 0.0
    
    has_pallet_cols = (food_p is not None or pet_p is not None or chem_p is not None)
    
    if has_pallet_cols:
        order_pallets = food_vals + pet_vals + chem_vals
    elif weight_col:
        raw_wt = df[weight_col].astype(str).str.replace(',', '').str.strip()
        order_pallets = pd.to_numeric(raw_wt, errors='coerce').fillna(1.0)
    else:
        order_pallets = pd.Series(1.0, index=df.index)

    df['order_pallets'] = order_pallets.clip(lower=0.0)

    # Rounded pallets per order
    if rounding_mode == 'ceil':
        df['order_pallets_rounded'] = df['order_pallets'].apply(lambda x: math.ceil(x) if pd.notna(x) else 0)
    else:
        df['order_pallets_rounded'] = df['order_pallets'].round()

    # Customer identifiers
    if cust_id_col:
        df['customer_id'] = df[cust_id_col].astype(str).str.replace('.0', '', regex=False).str.strip()
    else:
        df['customer_id'] = "CUST_" + df.index.astype(str)

    if name_col:
        df['customer_name'] = df[name_col].fillna('Unknown Customer').astype(str).str.strip()
    else:
        df['customer_name'] = df['customer_id']

    df['address_full'] = df[addr_col].fillna('') if addr_col else ''
    df['city_borough'] = df[city_col].fillna('') if city_col else ''

    # Attach diagnostic issues to DataFrame metadata
    df.attrs['validation_issues'] = row_issues
    df.attrs['fatal_errors'] = fatal_errors

    return df

def aggregate_customer_demands(df, selected_day='All Days', rounding_mode='ceil'):
    """
    Aggregates orders by customer location for a specific day of the week (or 'All Days').
    """
    filtered_df = df.copy()
    if selected_day != 'All Days':
        filtered_df = filtered_df[filtered_df['day_of_week'] == selected_day]

    if filtered_df.empty:
        empty_df = pd.DataFrame(columns=[
            'customer_id', 'customer_name', 'latitude', 'longitude',
            'address', 'city_borough', 'day_of_week',
            'total_pallets_unrounded', 'total_pallets_rounded',
            'pallets_per_order', 'total_orders'
        ])
        empty_df.attrs['validation_issues'] = df.attrs.get('validation_issues', [])
        return empty_df

    grouped = filtered_df.groupby(['customer_id', 'customer_name', 'latitude', 'longitude']).agg(
        total_pallets_unrounded=('order_pallets', 'sum'),
        total_pallets_rounded=('order_pallets_rounded', 'sum'),
        total_orders=('order_pallets', 'count'),
        address=('address_full', 'first'),
        city_borough=('city_borough', 'first')
    ).reset_index()

    grouped['total_pallets_unrounded'] = grouped['total_pallets_unrounded'].round(2)
    grouped['total_pallets_rounded'] = grouped['total_pallets_rounded'].astype(int)
    grouped['pallets_per_order'] = (grouped['total_pallets_unrounded'] / grouped['total_orders']).round(2)
    grouped['day_of_week'] = selected_day

    # Sort descending by total unrounded pallets
    grouped = grouped.sort_values(by='total_pallets_unrounded', ascending=False).reset_index(drop=True)
    grouped.attrs['validation_issues'] = df.attrs.get('validation_issues', [])

    return grouped

def get_available_days(df):
    """
    Returns unique days of the week present in the dataset, ordered Monday through Sunday.
    """
    present_days = df['day_of_week'].unique()
    ordered_days = [d for d in DAYS_ORDER if d in present_days]
    remaining = [d for d in present_days if d not in DAYS_ORDER and d != 'Unknown']
    if 'Unknown' in present_days and len(present_days) == 1:
        return ['All Days']
    return ['All Days'] + ordered_days + remaining
