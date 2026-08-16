import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse
import os
import sys

from analyzer import load_and_preprocess_orders, aggregate_customer_demands, get_available_days
from heatmap_generator import create_demand_heatmap_map, save_heatmap_html, METRIC_LABELS

METRIC_CLI_MAP = {
    'unrounded': 'total_pallets_unrounded',
    'rounded': 'total_pallets_rounded',
    'pallets_per_order': 'pallets_per_order',
    'ppo': 'pallets_per_order',
    'orders': 'total_orders',
    'total_orders': 'total_orders'
}

def main():
    parser = argparse.ArgumentParser(
        description="Customer Demand & Order Heatmap Generator CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        help="Path to input orders/routing CSV file"
    )
    parser.add_argument(
        '-d', '--day',
        default='All Days',
        help="Day of the week filter (e.g. Monday, Tuesday, Wednesday, ..., or 'All Days')"
    )
    parser.add_argument(
        '-m', '--metric',
        choices=list(METRIC_CLI_MAP.keys()),
        default='unrounded',
        help="Heatmap metric intensity (unrounded, rounded, pallets_per_order, orders)"
    )
    parser.add_argument(
        '-r', '--rounding',
        choices=['ceil', 'round'],
        default='ceil',
        help="Per-order pallet rounding method"
    )
    parser.add_argument(
        '-o', '--html-out',
        default=None,
        help="Path to save output interactive HTML heatmap"
    )
    parser.add_argument(
        '--csv-out',
        default=None,
        help="Path to save output customer aggregation CSV summary"
    )

    args = parser.parse_args()

    print(f"Loading order data from: {args.input}")
    raw_df = load_and_preprocess_orders(args.input, rounding_mode=args.rounding)
    available_days = get_available_days(raw_df)
    print(f"Available days in dataset: {', '.join(available_days)}")

    selected_day = args.day
    if selected_day not in available_days and selected_day != 'All Days':
        print(f"Warning: Selected day '{selected_day}' not found in dataset. Using 'All Days'.")
        selected_day = 'All Days'

    metric_key = METRIC_CLI_MAP[args.metric]
    cust_summary = aggregate_customer_demands(raw_df, selected_day=selected_day, rounding_mode=args.rounding)

    print(f"\n=======================================================")
    print(f"  Customer Demand Summary for {selected_day}")
    print(f"=======================================================")
    print(f"Active Customers:       {len(cust_summary)}")
    print(f"Total Orders:           {cust_summary['total_orders'].sum()}")
    print(f"Total Unrounded Pallets:{cust_summary['total_pallets_unrounded'].sum():.2f}")
    print(f"Total Rounded Pallets:  {cust_summary['total_pallets_rounded'].sum()}")
    print(f"Average Pallets/Order:  {(cust_summary['total_pallets_unrounded'].sum() / cust_summary['total_orders'].sum()):.2f}")
    print(f"=======================================================\n")

    # Generate map
    m = create_demand_heatmap_map(
        cust_summary,
        metric=metric_key,
        selected_day=selected_day
    )

    base_name = os.path.splitext(os.path.basename(args.input))[0]
    clean_day = selected_day.lower().replace(" ", "_")

    html_out = args.html_out or f"heatmap_{base_name}_{clean_day}_{args.metric}.html"
    save_heatmap_html(m, html_out)

    if args.csv_out or not args.html_out:
        csv_out = args.csv_out or f"customer_summary_{base_name}_{clean_day}.csv"
        cust_summary.to_csv(csv_out, index=False)
        print(f"Saved customer summary CSV to {csv_out}")

if __name__ == '__main__':
    main()
