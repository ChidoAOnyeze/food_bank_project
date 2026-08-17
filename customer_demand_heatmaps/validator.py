import os
import re
import math
import pandas as pd
import numpy as np

class DataValidationError(Exception):
    """Custom exception raised when an input CSV has fatal structural or data issues."""
    def __init__(self, message, issues=None):
        super().__init__(message)
        self.message = message
        self.issues = issues or []

    def __str__(self):
        if not self.issues:
            return self.message
        
        issue_lines = []
        for iss in self.issues[:15]: # Show first 15 issues
            issue_lines.append(f"  • Row {iss.get('row_number', '?')} | Column '{iss.get('column', '?')}': {iss.get('description', '')} (Value: {repr(iss.get('value', ''))})")
        
        if len(self.issues) > 15:
            issue_lines.append(f"  ... and {len(self.issues) - 15} more issues.")

        return f"{self.message}\n\nProblematic Locations:\n" + "\n".join(issue_lines)

def detect_csv_delimiter(file_source):
    """Detects comma, semicolon, tab, or pipe delimiters."""
    try:
        if isinstance(file_source, str):
            with open(file_source, 'r', encoding='utf-8-sig', errors='ignore') as f:
                sample = f.read(4096)
        else:
            pos = file_source.tell() if hasattr(file_source, 'tell') else 0
            sample = file_source.read(4096).decode('utf-8-sig', errors='ignore')
            if hasattr(file_source, 'seek'):
                file_source.seek(pos)
        
        delimiters = [',', '\t', ';', '|']
        counts = {d: sample.count(d) for d in delimiters}
        best_delim = max(counts, key=counts.get)
        return best_delim if counts[best_delim] > 0 else ','
    except Exception:
        return ','

def inspect_and_diagnose_csv(file_source, raise_on_fatal=True):
    """
    Performs deep structural and cell-level validation on a routing CSV.
    
    Returns:
    - is_valid (bool)
    - fatal_errors (list of dicts)
    - row_warnings (list of dicts with exact row_number, column, value, issue_type, description)
    - cleaned_df (pandas.DataFrame)
    """
    issues = []
    fatal_errors = []
    
    # 1. Read Raw CSV
    try:
        delim = detect_csv_delimiter(file_source)
        if isinstance(file_source, str):
            if not os.path.exists(file_source):
                raise DataValidationError(f"File not found: {file_source}")
            if os.path.getsize(file_source) == 0:
                raise DataValidationError(f"File is completely empty (0 bytes): {file_source}")
            raw_df = pd.read_csv(file_source, sep=delim, dtype=str)
        else:
            raw_df = pd.read_csv(file_source, sep=delim, dtype=str)
    except DataValidationError:
        raise
    except Exception as e:
        msg = f"Failed to parse CSV file. Error: {str(e)}"
        if raise_on_fatal:
            raise DataValidationError(msg)
        return False, [{'row_number': 1, 'column': 'FILE', 'description': msg, 'value': ''}], [], None

    if raw_df.empty or len(raw_df.columns) == 0:
        msg = "CSV contains no data rows or columns."
        if raise_on_fatal:
            raise DataValidationError(msg)
        return False, [{'row_number': 1, 'column': 'HEADER', 'description': msg, 'value': ''}], [], None

    # Clean column headers
    raw_df.columns = [str(c).strip() for c in raw_df.columns]
    cols_lower = {str(c).strip().lower(): c for c in raw_df.columns}

    def get_col(candidates):
        for cand in candidates:
            if cand.lower() in cols_lower:
                return cols_lower[cand.lower()]
        return None

    lat_col = get_col(['latitude', 'lat', 'y'])
    lon_col = get_col(['longitude', 'lon', 'lng', 'long', 'x'])
    name_col = get_col(['name', 'customer name', 'address name', 'stop name', 'client'])
    id_col = get_col(['customer number', 'customer id', 'customer_id', 'cust id', 'stop id', 'address id'])
    date_col = get_col(['date', 'orderdate', 'shipment date', 'delivery date', 'order_date'])

    # Check fatal missing coordinates headers
    if not lat_col or not lon_col:
        msg = (
            f"Missing required Latitude/Longitude columns in CSV.\n"
            f"Found columns: {list(raw_df.columns)}\n"
            f"Expected columns matching: 'latitude', 'lat', 'y' and 'longitude', 'lon', 'lng', 'x'."
        )
        fatal_errors.append({
            'row_number': 1,
            'column': 'HEADER',
            'issue_type': 'MISSING_COORDINATE_COLUMNS',
            'description': msg,
            'value': str(list(raw_df.columns))
        })
        if raise_on_fatal:
            raise DataValidationError(msg, fatal_errors)
        return False, fatal_errors, [], None

    # 2. Row-by-Row Cell Validation (Row numbers are 2-indexed in CSV for header + 1-based index)
    valid_row_indices = []
    
    # Pallet / Demand columns
    food_p = get_col(['food pallets'])
    pet_p = get_col(['pet food pallets'])
    chem_p = get_col(['chemical pallets'])
    weight_col = get_col(['weight', 'total weight nh', 'quantity', 'demand', 'pallets'])

    for idx, row in raw_df.iterrows():
        csv_row_num = idx + 2 # Header is Row 1
        cust_desc = str(row[name_col]) if name_col and pd.notna(row[name_col]) else (str(row[id_col]) if id_col and pd.notna(row[id_col]) else f"Row {csv_row_num}")
        
        row_has_fatal = False

        # --- A. Check Latitude & Longitude ---
        lat_val = row[lat_col]
        lon_val = row[lon_col]

        parsed_lat = None
        parsed_lon = None

        if pd.isna(lat_val) or str(lat_val).strip() in ['', 'nan', 'null', 'none', 'n/a']:
            issues.append({
                'row_number': csv_row_num,
                'customer': cust_desc,
                'column': lat_col,
                'value': str(lat_val),
                'issue_type': 'MISSING_LATITUDE',
                'description': f"Missing Latitude coordinate for customer '{cust_desc}'. Row will be skipped.",
                'severity': 'HIGH'
            })
            row_has_fatal = True
        else:
            try:
                parsed_lat = float(str(lat_val).strip())
            except ValueError:
                issues.append({
                    'row_number': csv_row_num,
                    'customer': cust_desc,
                    'column': lat_col,
                    'value': str(lat_val),
                    'issue_type': 'INVALID_LATITUDE_FORMAT',
                    'description': f"Latitude value '{lat_val}' cannot be parsed as a numeric coordinate. Row will be skipped.",
                    'severity': 'HIGH'
                })
                row_has_fatal = True

        if pd.isna(lon_val) or str(lon_val).strip() in ['', 'nan', 'null', 'none', 'n/a']:
            issues.append({
                'row_number': csv_row_num,
                'customer': cust_desc,
                'column': lon_col,
                'value': str(lon_val),
                'issue_type': 'MISSING_LONGITUDE',
                'description': f"Missing Longitude coordinate for customer '{cust_desc}'. Row will be skipped.",
                'severity': 'HIGH'
            })
            row_has_fatal = True
        else:
            try:
                parsed_lon = float(str(lon_val).strip())
            except ValueError:
                issues.append({
                    'row_number': csv_row_num,
                    'customer': cust_desc,
                    'column': lon_col,
                    'value': str(lon_val),
                    'issue_type': 'INVALID_LONGITUDE_FORMAT',
                    'description': f"Longitude value '{lon_val}' cannot be parsed as a numeric coordinate. Row will be skipped.",
                    'severity': 'HIGH'
                })
                row_has_fatal = True

        # Check bounds & swapped lat/lon
        if parsed_lat is not None and parsed_lon is not None:
            # Swapped coordinates detection (e.g. lat = -73.9, lon = 40.8)
            if parsed_lat < 0 and parsed_lon > 0:
                issues.append({
                    'row_number': csv_row_num,
                    'customer': cust_desc,
                    'column': f"{lat_col}, {lon_col}",
                    'value': f"Lat: {parsed_lat}, Lon: {parsed_lon}",
                    'issue_type': 'SWAPPED_COORDINATES',
                    'description': f"Latitude ({parsed_lat}) and Longitude ({parsed_lon}) appear to be swapped. Auto-corrected.",
                    'severity': 'MEDIUM'
                })
                # Auto-correct swapped coordinates
                parsed_lat, parsed_lon = parsed_lon, parsed_lat
                raw_df.at[idx, lat_col] = str(parsed_lat)
                raw_df.at[idx, lon_col] = str(parsed_lon)

            # Bounds check
            if not (-90.0 <= parsed_lat <= 90.0) or not (-180.0 <= parsed_lon <= 180.0):
                issues.append({
                    'row_number': csv_row_num,
                    'customer': cust_desc,
                    'column': f"{lat_col}, {lon_col}",
                    'value': f"Lat: {parsed_lat}, Lon: {parsed_lon}",
                    'issue_type': 'OUT_OF_BOUNDS_COORDINATES',
                    'description': f"Coordinates out of geographic range [-90,90], [-180,180]. Row will be skipped.",
                    'severity': 'HIGH'
                })
                row_has_fatal = True
            elif abs(parsed_lat) < 0.001 and abs(parsed_lon) < 0.001:
                issues.append({
                    'row_number': csv_row_num,
                    'customer': cust_desc,
                    'column': f"{lat_col}, {lon_col}",
                    'value': f"Lat: {parsed_lat}, Lon: {parsed_lon}",
                    'issue_type': 'ZERO_COORDINATES',
                    'description': f"Coordinates are located at (0, 0) [Null Island]. Row will be skipped.",
                    'severity': 'HIGH'
                })
                row_has_fatal = True

        # --- B. Check Demands / Pallets ---
        demand_cols_to_check = [c for c in [food_p, pet_p, chem_p, weight_col] if c is not None]
        for d_col in demand_cols_to_check:
            d_val = row[d_col]
            if pd.notna(d_val) and str(d_val).strip() != '':
                clean_d = str(d_val).replace(',', '').strip()
                try:
                    num_d = float(clean_d)
                    if num_d < 0:
                        issues.append({
                            'row_number': csv_row_num,
                            'customer': cust_desc,
                            'column': d_col,
                            'value': str(d_val),
                            'issue_type': 'NEGATIVE_DEMAND',
                            'description': f"Negative demand '{d_val}' found. Replaced with 0.0.",
                            'severity': 'LOW'
                        })
                        raw_df.at[idx, d_col] = '0.0'
                except ValueError:
                    issues.append({
                        'row_number': csv_row_num,
                        'customer': cust_desc,
                        'column': d_col,
                        'value': str(d_val),
                        'issue_type': 'NON_NUMERIC_DEMAND',
                        'description': f"Non-numeric demand value '{d_val}' found. Treated as 0.0.",
                        'severity': 'MEDIUM'
                    })
                    raw_df.at[idx, d_col] = '0.0'

        # --- C. Check Date Parsing ---
        if date_col and pd.notna(row[date_col]) and str(row[date_col]).strip() != '':
            date_val = str(row[date_col]).strip()
            try:
                pd.to_datetime(date_val)
            except Exception:
                issues.append({
                    'row_number': csv_row_num,
                    'customer': cust_desc,
                    'column': date_col,
                    'value': date_val,
                    'issue_type': 'UNPARSEABLE_DATE',
                    'description': f"Could not parse date '{date_val}'. Day of week defaulted to 'Unknown'.",
                    'severity': 'LOW'
                })

        if not row_has_fatal:
            valid_row_indices.append(idx)

    # Filter clean rows
    cleaned_df = raw_df.loc[valid_row_indices].copy()

    if cleaned_df.empty:
        msg = f"All {len(raw_df)} rows in the CSV failed validation due to corrupted or missing coordinates."
        if raise_on_fatal:
            raise DataValidationError(msg, issues)
        return False, [{'row_number': 'ALL', 'column': 'DATA', 'description': msg, 'value': ''}], issues, None

    return True, [], issues, cleaned_df
