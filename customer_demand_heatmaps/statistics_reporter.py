import os
import io
import base64
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg') # Non-interactive headless backend
import matplotlib.pyplot as plt

DAYS_ORDER = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

def compute_detailed_statistics(cust_df, group_by_col=None):
    """
    Computes rigorous descriptive statistics (Mean, Median, Std, IQR, Min, Max, Quantiles)
    for each customer metric.
    """
    metrics = [
        ('total_pallets_unrounded', 'Unrounded Pallets'),
        ('total_pallets_rounded', 'Rounded Pallets'),
        ('total_food_pallets', 'Food Pallets'),
        ('total_pet_food_pallets', 'Pet Food Pallets'),
        ('total_chemical_pallets', 'Chemical Pallets'),
        ('total_weight', 'Total Weight (lbs)'),
        ('pallets_per_order', 'Pallets per Order'),
        ('total_orders', 'Total Orders')
    ]

    records = []

    def calc_stats_for_slice(sub_df, slice_name, slice_val):
        for col_name, label in metrics:
            if col_name not in sub_df.columns or sub_df[col_name].empty:
                continue
            series = sub_df[col_name].dropna().astype(float)
            if series.empty or (series == 0).all() and col_name in ['total_food_pallets', 'total_pet_food_pallets', 'total_chemical_pallets', 'total_weight']:
                continue
            
            n = len(series)
            s_sum = series.sum()
            s_mean = series.mean()
            s_median = series.median()
            s_std = series.std(ddof=1) if n > 1 else 0.0
            s_min = series.min()
            q25 = series.quantile(0.25)
            q75 = series.quantile(0.75)
            s_max = series.max()
            iqr = q75 - q25

            records.append({
                'Grouping': slice_name,
                'Category': str(slice_val),
                'Metric': label,
                'Metric_Key': col_name,
                'Count (Customers)': n,
                'Total Sum': round(s_sum, 2) if 'order' not in col_name else round(s_sum, 2),
                'Mean (Average)': round(s_mean, 2),
                'Median (50%)': round(s_median, 2),
                'Std Dev': round(s_std, 2),
                'Min': round(s_min, 2),
                'Q1 (25%)': round(q25, 2),
                'Q3 (75%)': round(q75, 2),
                'IQR': round(iqr, 2),
                'Max': round(s_max, 2)
            })

    # Overall Summary
    calc_stats_for_slice(cust_df, 'Overall', 'All Customers')

    # Grouped Summary (e.g. by Day of Week or Borough)
    if group_by_col and group_by_col in cust_df.columns:
        for group_val, group_sub in cust_df.groupby(group_by_col):
            calc_stats_for_slice(group_sub, group_by_col, group_val)

    return pd.DataFrame(records)

def generate_distribution_figure(cust_df, raw_df=None, selected_day='All Days', selected_metric='total_pallets_unrounded'):
    """
    Generates a dynamic 4-panel distribution visualization figure for the chosen metric containing:
    1. Day of the Week Demand & Order Distribution Bar Chart
    2. Customer Demand Distribution Histogram & KDE (with Mean/Median markers)
    3. Regional / Borough Distribution or Pallets per Order Distribution
    4. Top 15 Highest-Demand Customers Bar Chart
    """
    fig, axes = plt.subplots(2, 2, figsize=(16, 11), facecolor='#ffffff')
    plt.subplots_adjust(hspace=0.38, wspace=0.28)

    # Metric label and unit mapping
    label_map = {
        'total_pallets_unrounded': ('Total Pallets (Unrounded)', 'pallets', 'order_pallets'),
        'total_pallets_rounded': ('Total Pallets (Rounded)', 'rounded plts', 'order_pallets_rounded'),
        'total_food_pallets': ('Food Pallets', 'food plts', 'food_pallets'),
        'total_pet_food_pallets': ('Pet Food Pallets', 'pet plts', 'pet_food_pallets'),
        'total_chemical_pallets': ('Chemical Pallets', 'chem plts', 'chemical_pallets'),
        'total_weight': ('Total Weight', 'lbs', 'order_weight'),
        'pallets_per_order': ('Average Pallets per Order', 'plts/order', 'order_pallets'),
        'total_orders': ('Total Orders', 'orders', 'order_pallets')
    }

    metric_name, metric_unit, raw_col_name = label_map.get(selected_metric, (selected_metric.replace('_', ' ').title(), 'units', 'order_pallets'))

    # Styling settings
    mean_color = '#ef4444'
    median_color = '#8b5cf6'

    # Fallback to total_pallets_unrounded if selected column not present in cust_df
    actual_col = selected_metric if selected_metric in cust_df.columns else 'total_pallets_unrounded'

    # --- PANEL 1: DAY OF THE WEEK DEMAND DISTRIBUTION (BAR CHART) ---
    ax1 = axes[0, 0]
    if raw_df is not None and 'day_of_week' in raw_df.columns:
        agg_raw_col = raw_col_name if raw_col_name in raw_df.columns else 'order_pallets'
        day_stats = raw_df.groupby('day_of_week').agg(
            total_vol=(agg_raw_col, 'sum'),
            total_orders=('order_pallets', 'count')
        ).reindex([d for d in DAYS_ORDER if d in raw_df['day_of_week'].unique()]).dropna()

        if not day_stats.empty:
            x_indices = np.arange(len(day_stats))
            width = 0.38
            
            bars1 = ax1.bar(x_indices - width/2, day_stats['total_vol'], width, label=f'Total {metric_name}', color='#2563eb', edgecolor='#1d4ed8')
            ax1_twin = ax1.twinx()
            bars2 = ax1_twin.bar(x_indices + width/2, day_stats['total_orders'], width, label='Order Count', color='#10b981', edgecolor='#059669')

            ax1.set_title(f'{metric_name} & Order Volume by Day of Week', fontsize=12, fontweight='bold', pad=10)
            ax1.set_xticks(x_indices)
            ax1.set_xticklabels(day_stats.index, rotation=15, fontsize=10)
            ax1.set_ylabel(f'Total {metric_name} ({metric_unit})', color='#2563eb', fontweight='bold')
            ax1_twin.set_ylabel('Total Orders', color='#10b981', fontweight='bold')
            ax1.grid(axis='y', linestyle='--', alpha=0.3)

            # Data labels
            for b in bars1:
                h = b.get_height()
                ax1.annotate(f'{h:,.1f}' if h >= 1000 else f'{h:.1f}', (b.get_x() + b.get_width()/2, h), ha='center', va='bottom', fontsize=8, xytext=(0, 2), textcoords='offset points')
            for b in bars2:
                h = b.get_height()
                ax1_twin.annotate(f'{int(h)}', (b.get_x() + b.get_width()/2, h), ha='center', va='bottom', fontsize=8, xytext=(0, 2), textcoords='offset points')
        else:
            ax1.text(0.5, 0.5, 'Single Day Dataset', ha='center', va='center', fontsize=12)
    else:
        ax1.text(0.5, 0.5, 'Day of week data not available', ha='center', va='center', fontsize=12)

    # --- PANEL 2: CUSTOMER DEMAND HISTOGRAM (WITH MEAN & MEDIAN) ---
    ax2 = axes[0, 1]
    series_data = cust_df[actual_col].dropna()
    s_mean = series_data.mean()
    s_median = series_data.median()

    counts, bins, patches = ax2.hist(series_data, bins=15, color='#60a5fa', edgecolor='#1e40af', alpha=0.85)
    ax2.axvline(s_mean, color=mean_color, linestyle='--', linewidth=2, label=f'Mean: {s_mean:.2f} {metric_unit}')
    ax2.axvline(s_median, color=median_color, linestyle='-', linewidth=2, label=f'Median: {s_median:.2f} {metric_unit}')

    ax2.set_title(f'Customer {metric_name} Distribution ({selected_day})', fontsize=12, fontweight='bold', pad=10)
    ax2.set_xlabel(f'{metric_name} ({metric_unit})', fontsize=10)
    ax2.set_ylabel('Number of Customers', fontsize=10)
    ax2.legend(loc='upper right', frameon=True, fontsize=9)
    ax2.grid(axis='y', linestyle='--', alpha=0.3)

    # --- PANEL 3: REGIONAL / BOROUGH BREAKDOWN OR PALLETS PER ORDER ---
    ax3 = axes[1, 0]
    has_boroughs = 'city_borough' in cust_df.columns and cust_df['city_borough'].str.strip().replace('', np.nan).dropna().nunique() > 1
    
    if has_boroughs:
        borough_stats = cust_df.groupby('city_borough')[actual_col].sum().sort_values(ascending=True)
        # Filter top 10 regions
        borough_stats = borough_stats.tail(10)
        y_pos = np.arange(len(borough_stats))
        bars_b = ax3.barh(y_pos, borough_stats.values, color='#0ea5e9', edgecolor='#0369a1', alpha=0.9)
        ax3.set_yticks(y_pos)
        ax3.set_yticklabels(borough_stats.index, fontsize=9)
        ax3.set_xlabel(f'Total {metric_name} ({metric_unit})', fontsize=10)
        ax3.set_title(f'{metric_name} by Region / Borough ({selected_day})', fontsize=12, fontweight='bold', pad=10)
        ax3.grid(axis='x', linestyle='--', alpha=0.3)
        for b in bars_b:
            w = b.get_width()
            ax3.annotate(f'{w:,.1f}' if w >= 1000 else f'{w:.1f}', (w, b.get_y() + b.get_height()/2), ha='left', va='center', fontsize=8, xytext=(3, 0), textcoords='offset points')
    else:
        ppo_data = cust_df['pallets_per_order'].dropna() if 'pallets_per_order' in cust_df.columns else series_data
        ppo_m = ppo_data.mean()
        ppo_med = ppo_data.median()
        ax3.hist(ppo_data, bins=15, color='#34d399', edgecolor='#065f46', alpha=0.85)
        ax3.axvline(ppo_m, color=mean_color, linestyle='--', linewidth=2, label=f'Mean: {ppo_m:.2f} plts/ord')
        ax3.axvline(ppo_med, color=median_color, linestyle='-', linewidth=2, label=f'Median: {ppo_med:.2f} plts/ord')
        ax3.set_title(f'Average Pallets per Order Distribution ({selected_day})', fontsize=12, fontweight='bold', pad=10)
        ax3.set_xlabel('Pallets per Order (Average Order Size)', fontsize=10)
        ax3.set_ylabel('Number of Customers', fontsize=10)
        ax3.legend(loc='upper right', frameon=True, fontsize=9)
        ax3.grid(axis='y', linestyle='--', alpha=0.3)

    # --- PANEL 4: TOP 15 CUSTOMERS RANKING FOR CHOSEN METRIC ---
    ax4 = axes[1, 1]
    top15 = cust_df.sort_values(by=actual_col, ascending=False).head(15)
    y_pos = np.arange(len(top15))

    names = [n[:22] + '..' if len(n) > 22 else n for n in top15['customer_name']]
    bars_top = ax4.barh(y_pos, top15[actual_col], color='#f59e0b', edgecolor='#b45309', alpha=0.9)
    ax4.set_yticks(y_pos)
    ax4.set_yticklabels(names, fontsize=8)
    ax4.invert_yaxis() # Top customer on top
    ax4.set_xlabel(f'Total {metric_name} ({metric_unit})', fontsize=10)
    ax4.set_title(f'Top 15 Customer Ranking by {metric_name} ({selected_day})', fontsize=12, fontweight='bold', pad=10)
    ax4.grid(axis='x', linestyle='--', alpha=0.3)

    for b in bars_top:
        w = b.get_width()
        ax4.annotate(f'{w:,.1f}' if w >= 1000 else f'{w:.1f}', (w, b.get_y() + b.get_height()/2), ha='left', va='center', fontsize=8, xytext=(3, 0), textcoords='offset points')

    return fig

def export_distribution_report_files(cust_df, raw_df, output_prefix=None, dataset_name="Dataset"):
    """
    Generates and saves:
    1. CSV Summary of Descriptive Statistics (Means, Medians, Quartiles)
    2. High-res Distribution PNG Image
    3. Self-contained HTML Visual Distribution Report
    """
    if output_prefix is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
        output_prefix = os.path.join(output_dir, f"distribution_summary_{dataset_name}")

    # 1. Compute stats table
    stats_df = compute_detailed_statistics(cust_df, group_by_col='city_borough' if 'city_borough' in cust_df.columns else None)
    csv_path = f"{output_prefix}_statistics.csv"
    stats_df.to_csv(csv_path, index=False)
    print(f"  ✓ Saved statistical summary CSV: {csv_path}")

    # 2. Generate and save chart PNG
    fig = generate_distribution_figure(cust_df, raw_df)
    png_path = f"{output_prefix}_charts.png"
    fig.savefig(png_path, dpi=200, bbox_inches='tight')
    print(f"  ✓ Saved distribution charts image: {png_path}")

    # 3. Generate HTML report with base64 embedded chart
    img_buf = io.BytesIO()
    fig.savefig(img_buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    img_base64 = base64.b64encode(img_buf.getvalue()).decode('utf-8')

    html_path = f"{output_prefix}_report.html"
    generate_html_report(cust_df, stats_df, img_base64, html_path, dataset_name)
    print(f"  ✓ Saved standalone HTML distribution report: {html_path}")

    return {
        'csv_path': csv_path,
        'png_path': png_path,
        'html_path': html_path,
        'stats_df': stats_df
    }

def generate_html_report(cust_df, stats_df, chart_base64, html_path, title):
    overall_stats = stats_df[stats_df['Grouping'] == 'Overall']
    
    def get_metric_val(m_key, stat_name):
        row = overall_stats[overall_stats['Metric_Key'] == m_key]
        if not row.empty:
            return row[stat_name].values[0]
        return 0.0

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Statistical Distribution Summary - {title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f8fafc;
            color: #1e293b;
            margin: 0;
            padding: 30px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 12px;
            padding: 32px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        }}
        h1 {{
            color: #0f172a;
            font-size: 26px;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 12px;
            margin-top: 0;
        }}
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            margin: 24px 0;
        }}
        .kpi-card {{
            background: #f1f5f9;
            border-radius: 8px;
            padding: 16px;
            border-left: 4px solid #3b82f6;
        }}
        .kpi-title {{
            font-size: 12px;
            text-transform: uppercase;
            color: #64748b;
            font-weight: 600;
            margin-bottom: 6px;
        }}
        .kpi-value {{
            font-size: 22px;
            font-weight: 700;
            color: #0f172a;
        }}
        .kpi-sub {{
            font-size: 11px;
            color: #64748b;
            margin-top: 4px;
        }}
        .chart-section {{
            text-align: center;
            margin: 32px 0;
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 16px;
        }}
        .chart-section img {{
            max-width: 100%;
            height: auto;
            border-radius: 6px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 16px;
            font-size: 13px;
        }}
        th, td {{
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}
        th {{
            background-color: #f8fafc;
            color: #475569;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f1f5f9;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            background: #e2e8f0;
            color: #334155;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Customer Demand Distribution & Statistical Report</h1>
        <p style="color: #64748b;">Dataset: <strong>{title}</strong> | Active Customers: <strong>{len(cust_df)}</strong></p>

        <!-- KPI SUMMARY CARDS (MEANS & MEDIANS) -->
        <div class="kpi-grid">
            <div class="kpi-card" style="border-color: #3b82f6;">
                <div class="kpi-title">Total Pallets (Unrounded)</div>
                <div class="kpi-value">{get_metric_val('total_pallets_unrounded', 'Total Sum'):,.1f}</div>
                <div class="kpi-sub">Mean: <strong>{get_metric_val('total_pallets_unrounded', 'Mean (Average)'):.2f}</strong> | Median: <strong>{get_metric_val('total_pallets_unrounded', 'Median (50%)'):.2f}</strong></div>
            </div>
            <div class="kpi-card" style="border-color: #10b981;">
                <div class="kpi-title">Total Pallets (Rounded)</div>
                <div class="kpi-value">{int(get_metric_val('total_pallets_rounded', 'Total Sum')):,}</div>
                <div class="kpi-sub">Mean: <strong>{get_metric_val('total_pallets_rounded', 'Mean (Average)'):.2f}</strong> | Median: <strong>{get_metric_val('total_pallets_rounded', 'Median (50%)'):.2f}</strong></div>
            </div>
            <div class="kpi-card" style="border-color: #8b5cf6;">
                <div class="kpi-title">Avg Pallets / Order</div>
                <div class="kpi-value">{get_metric_val('pallets_per_order', 'Mean (Average)'):.2f}</div>
                <div class="kpi-sub">Median: <strong>{get_metric_val('pallets_per_order', 'Median (50%)'):.2f}</strong> | Std Dev: <strong>{get_metric_val('pallets_per_order', 'Std Dev'):.2f}</strong></div>
            </div>
            <div class="kpi-card" style="border-color: #f59e0b;">
                <div class="kpi-title">Total Orders Serviced</div>
                <div class="kpi-value">{int(get_metric_val('total_orders', 'Total Sum')):,}</div>
                <div class="kpi-sub">Mean: <strong>{get_metric_val('total_orders', 'Mean (Average)'):.2f}</strong> | Median: <strong>{get_metric_val('total_orders', 'Median (50%)'):.2f}</strong></div>
            </div>
        </div>

        <!-- DISTRIBUTION CHARTS IMAGE -->
        <div class="chart-section">
            <h2 style="font-size: 18px; color: #1e293b; margin-top: 0; text-align: left;">Distribution Visualizations (Means, Medians & Day-of-Week)</h2>
            <img src="data:image/png;base64,{chart_base64}" alt="Distribution Charts">
        </div>

        <!-- DETAILED STATISTICAL SUMMARY TABLE -->
        <h2>Detailed Statistical Metrics (Means, Medians, Quartiles)</h2>
        <table>
            <thead>
                <tr>
                    <th>Grouping</th>
                    <th>Category</th>
                    <th>Metric</th>
                    <th>Count</th>
                    <th>Total Sum</th>
                    <th>Mean</th>
                    <th>Median (50%)</th>
                    <th>Std Dev</th>
                    <th>Min</th>
                    <th>Q1 (25%)</th>
                    <th>Q3 (75%)</th>
                    <th>Max</th>
                </tr>
            </thead>
            <tbody>
                {"".join([f'''<tr>
                    <td><span class="badge">{row['Grouping']}</span></td>
                    <td><strong>{row['Category']}</strong></td>
                    <td>{row['Metric']}</td>
                    <td>{row['Count (Customers)']}</td>
                    <td>{row['Total Sum']}</td>
                    <td><strong>{row['Mean (Average)']}</strong></td>
                    <td><strong style="color: #8b5cf6;">{row['Median (50%)']}</strong></td>
                    <td>{row['Std Dev']}</td>
                    <td>{row['Min']}</td>
                    <td>{row['Q1 (25%)']}</td>
                    <td>{row['Q3 (75%)']}</td>
                    <td>{row['Max']}</td>
                </tr>''' for _, row in stats_df.iterrows()])}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
    if html_path:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    return html_content
