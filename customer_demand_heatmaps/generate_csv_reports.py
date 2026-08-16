import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os
import sys
import pandas as pd

from analyzer import load_and_preprocess_orders, aggregate_customer_demands, get_available_days

def generate_all_customer_csvs(input_file, output_prefix=None):
    if output_prefix is None:
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_dir = os.path.dirname(os.path.abspath(__file__))
        output_prefix = os.path.join(output_dir, f"customer_summary_{base_name}")

    print(f"\n=======================================================")
    print(f"  Generating Customer CSV Reports for: {input_file}")
    print(f"=======================================================")

    raw_df = load_and_preprocess_orders(input_file)
    available_days = get_available_days(raw_df)

    # 1. Combined All Days Summary
    all_days_df = aggregate_customer_demands(raw_df, selected_day='All Days')
    all_days_csv = f"{output_prefix}_all_days.csv"
    all_days_df.to_csv(all_days_csv, index=False)
    print(f"  ✓ Saved overall summary: {all_days_csv} ({len(all_days_df)} customers)")

    # 2. Detailed Per-Day Summary (stacked)
    per_day_records = []
    for day in available_days:
        if day == 'All Days':
            continue
        day_df = aggregate_customer_demands(raw_df, selected_day=day)
        per_day_records.append(day_df)

    if per_day_records:
        stacked_day_df = pd.concat(per_day_records, ignore_index=True)
        by_day_csv = f"{output_prefix}_by_day_of_week.csv"
        stacked_day_df.to_csv(by_day_csv, index=False)
        print(f"  ✓ Saved day-by-day breakdown: {by_day_csv} ({len(stacked_day_df)} customer-day rows)")

    # 3. Pivot View (Customer x Day Pallets)
    if 'day_of_week' in raw_df.columns and raw_df['day_of_week'].nunique() > 1:
        pivot_df = raw_df.pivot_table(
            index=['customer_id', 'customer_name', 'latitude', 'longitude'],
            columns='day_of_week',
            values='order_pallets',
            aggfunc='sum',
            fill_value=0.0
        ).reset_index()
        pivot_df['Total_Pallets'] = pivot_df.drop(columns=['customer_id', 'customer_name', 'latitude', 'longitude'], errors='ignore').sum(axis=1).round(2)
        pivot_csv = f"{output_prefix}_day_pivot_table.csv"
        pivot_df.to_csv(pivot_csv, index=False)
        print(f"  ✓ Saved customer day-of-week pivot table: {pivot_csv}")

    print("=======================================================\n")
    return all_days_df

if __name__ == '__main__':
    # Generate for all datasets
    datasets = [
        "routing_comparison/sample_orders_routing.csv",
        "routing_comparison/routes_sample.csv",
        "routing_augmentation_tool/anon_routed_orders_5_28_26.csv"
    ]
    for ds in datasets:
        if os.path.exists(ds):
            generate_all_customer_csvs(ds)
