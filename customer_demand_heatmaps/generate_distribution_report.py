import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse

from analyzer import load_and_preprocess_orders, aggregate_customer_demands
from statistics_reporter import export_distribution_report_files

def main():
    parser = argparse.ArgumentParser(
        description="Generate Statistical Distribution Reports & Bar Charts",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        help="Path to input orders/routing CSV file"
    )
    parser.add_argument(
        '-o', '--output-prefix',
        default=None,
        help="Prefix path for generated files (defaults to customer_demand_heatmaps/distribution_summary_<name>)"
    )

    args = parser.parse_args()

    print(f"Loading order data from: {args.input}")
    raw_df = load_and_preprocess_orders(args.input)
    cust_df = aggregate_customer_demands(raw_df, selected_day='All Days')

    base_name = os.path.splitext(os.path.basename(args.input))[0]
    out_prefix = args.output_prefix
    if out_prefix is None:
        out_dir = os.path.dirname(os.path.abspath(__file__))
        out_prefix = os.path.join(out_dir, f"distribution_summary_{base_name}")

    print(f"\n=======================================================")
    print(f"  Generating Statistical Distribution Report for: {base_name}")
    print(f"=======================================================")

    results = export_distribution_report_files(cust_df, raw_df, output_prefix=out_prefix, dataset_name=base_name)

    print("\n=======================================================")
    print("  Report Generation Complete!")
    print(f"  1) CSV Summary:  {results['csv_path']}")
    print(f"  2) Charts Image: {results['png_path']}")
    print(f"  3) HTML Report:  {results['html_path']}")
    print("=======================================================\n")

if __name__ == '__main__':
    main()
