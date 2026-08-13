#!/usr/bin/env python3
"""Anonymize Routed Orders CSV

Removes sensitive columns, replaces `Name` with a consistent anonymized label,
and maps `OrderType` values: Cold -> A, Dry -> B.

Usage:
  python anonymize_orders.py [input.csv] [output.csv]
If no paths are provided, the script will operate on
`Routed Orders 5.28.26.csv` in the same folder and write
`Routed Orders 5.28.26_anonymized.csv`.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
from pathlib import Path

# Columns to remove (must match CSV header names)
DROP_COLUMNS = [
    "Work Order Number",
    "Customer Number",
    "Memo (Main)",
    "Address",
    "City",
    "State",
    "Zip",
    "FixedTime",
    "OrderDate",
    "Total Quantity",
    "EqCode",
    "Open1",
    "Close1",
    "Pattern1",
    "Filler",
    "Shipment Date",
    "Standing Appointment",
    "County",
    "Delivery Instructions",
    "Static Appointment",
]

def anonymize(input_path: Path, output_path: Path) -> None:
    with input_path.open(newline='', encoding='utf-8-sig') as inf:
        reader = csv.DictReader(inf)
        if reader.fieldnames is None:
            raise SystemExit("Input CSV has no header")

        # Determine output fieldnames preserving original order but dropping unwanted cols
        out_fieldnames = [f for f in reader.fieldnames if f not in DROP_COLUMNS]

        rows = []
        for row in reader:
            name = (row.get("Name") or "").strip()

            # Deterministic anonymization via hashing (no external map file)
            if name:
                h = hashlib.sha1(name.encode('utf-8')).hexdigest()[:8].upper()
                anon_name = f"Site_{h}"
            else:
                anon_name = ""

            # Build anonymized row keeping only allowed fields
            out_row = {k: v for k, v in row.items() if k in out_fieldnames}
            out_row["Name"] = anon_name

            # Map OrderType: Cold -> A, Dry -> B
            ot = (out_row.get("OrderType") or "").strip()
            if ot.lower() == "cold":
                out_row["OrderType"] = "A"
            elif ot.lower() == "dry":
                out_row["OrderType"] = "B"

            rows.append(out_row)

    # Write output
    with output_path.open('w', newline='', encoding='utf-8') as outf:
        writer = csv.DictWriter(outf, fieldnames=out_fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote anonymized CSV: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Anonymize a routed orders CSV")
    parser.add_argument('input_csv', help='Path to input CSV file')
    parser.add_argument('output_csv', nargs='?', help='Optional output CSV path')
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    output_path = Path(args.output_csv) if args.output_csv else input_path.with_name(input_path.stem + "_anonymized.csv")

    if not input_path.exists():
        print(f"Input not found: {input_path}")
        raise SystemExit(2)

    anonymize(input_path, output_path)


if __name__ == '__main__':
    main()
