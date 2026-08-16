import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
import io
import base64
from streamlit_folium import st_folium
import matplotlib.pyplot as plt

from analyzer import load_and_preprocess_orders, aggregate_customer_demands, get_available_days, DAYS_ORDER
from heatmap_generator import create_demand_heatmap_map, METRIC_LABELS, METRIC_UNITS
from statistics_reporter import compute_detailed_statistics, generate_distribution_figure, export_distribution_report_files

st.set_page_config(
    page_title="Customer Demand & Order Analytics",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🗺️ Customer Demand & Statistical Distribution Hub")
st.markdown("""
Interactive analytics platform to visualize geographic demand heatmaps, evaluate pallet consumption, 
and explore **means, medians, and distribution bar charts** across days of the week.
""")

# --- SIDEBAR: DATA INPUT & CONFIG ---
st.sidebar.header("📁 Data Source")

SAMPLE_FILES = {
    "6-Month Dataset (orders_6_months_synthetic.csv)": "customer_demand_heatmaps/orders_6_months_synthetic.csv",
    "Sample Orders (sample_orders_routing.csv)": "routing_comparison/sample_orders_routing.csv",
    "Multi-Day Sample (routes_sample.csv)": "routing_comparison/routes_sample.csv",
    "Routed Orders (anon_routed_orders_5_28_26.csv)": "routing_augmentation_tool/anon_routed_orders_5_28_26.csv"
}

data_source = st.sidebar.radio(
    "Choose Data Source:",
    ["Use Repository Sample Dataset", "Upload CSV File"]
)

raw_df = None
file_label = ""

if data_source == "Upload CSV File":
    uploaded_file = st.sidebar.file_uploader("Upload Orders CSV", type=["csv"])
    if uploaded_file is not None:
        file_label = uploaded_file.name
        file_bytes = uploaded_file.getvalue()
        raw_df = load_and_preprocess_orders(io.BytesIO(file_bytes))
else:
    sample_choice = st.sidebar.selectbox("Select Sample Dataset:", list(SAMPLE_FILES.keys()))
    sample_path = SAMPLE_FILES[sample_choice]
    
    # Resolve relative path
    possible_paths = [
        sample_path,
        os.path.join("..", sample_path),
        os.path.join(os.path.dirname(__file__), "..", sample_path)
    ]
    resolved_path = None
    for p in possible_paths:
        if os.path.exists(p):
            resolved_path = p
            break

    if resolved_path:
        file_label = sample_choice
        raw_df = load_and_preprocess_orders(resolved_path)
    else:
        st.error(f"Sample file not found: {sample_path}")

if raw_df is None:
    st.info("👆 Please upload a routing CSV file or select a sample dataset in the sidebar to begin.")
    st.stop()

# --- CONFIGURATION CONTROLS ---
st.sidebar.markdown("---")
st.sidebar.header("⚙️ Calculation & Display Settings")

rounding_mode = st.sidebar.radio(
    "Per-Order Pallet Rounding Method:",
    ["Ceiling (math.ceil - Standard Logistics)", "Nearest Integer (round)"],
    index=0
)
round_key = 'ceil' if 'Ceiling' in rounding_mode else 'round'

with st.sidebar.expander("🎨 Heatmap Map Settings", expanded=False):
    radius = st.slider("Heat Radius", min_value=10, max_value=45, value=25, step=1)
    blur = st.slider("Heat Blur", min_value=5, max_value=35, value=18, step=1)
    min_opacity = st.slider("Min Opacity", min_value=0.1, max_value=0.8, value=0.35, step=0.05)
    show_markers = st.checkbox("Show Customer Markers & Popups", value=True)
    map_tiles = st.selectbox("Map Theme", ["CartoDB positron", "OpenStreetMap", "CartoDB dark_matter"])

# Available Days
available_days = get_available_days(raw_df)

# Tabs
tab_map, tab_stats = st.tabs([
    "🗺️ Interactive Geographic Heatmaps",
    "📊 Statistical Distributions & Charts (Means, Medians, Bar Charts)"
])

# =========================================================================
# TAB 1: INTERACTIVE HEATMAP
# =========================================================================
with tab_map:
    st.markdown("### 🎛️ Heatmap Controls")

    col_day, col_metric = st.columns([1.2, 1])

    with col_day:
        st.markdown("**📅 Day of the Week Filter:**")
        selected_day = st.select_slider(
            "Slide to filter by day of week:",
            options=available_days,
            value="All Days" if "All Days" in available_days else available_days[0],
            label_visibility="collapsed",
            key="heatmap_day_slider"
        )

    with col_metric:
        st.markdown("**📊 Heatmap Display Metric:**")
        metric_options = {
            'total_pallets_unrounded': '1. Total Pallets Consumed (Unrounded)',
            'total_pallets_rounded': '2. Total Rounded Pallets (Per-Order Rounded)',
            'pallets_per_order': '3. Average Pallets per Order',
            'total_orders': '4. Total Number of Orders'
        }
        selected_metric_key = st.selectbox(
            "Select metric for heatmap intensity:",
            options=list(metric_options.keys()),
            format_func=lambda k: metric_options[k],
            label_visibility="collapsed"
        )

    # Aggregate customer demand
    cust_summary = aggregate_customer_demands(raw_df, selected_day=selected_day, rounding_mode=round_key)

    if cust_summary.empty:
        st.warning(f"No delivery orders found for **{selected_day}** in this dataset.")
    else:
        # KPI Cards
        total_unrounded = cust_summary['total_pallets_unrounded'].sum()
        total_rounded = cust_summary['total_pallets_rounded'].sum()
        total_orders = cust_summary['total_orders'].sum()
        active_custs = len(cust_summary)
        avg_ppo = (total_unrounded / total_orders) if total_orders > 0 else 0.0

        st.markdown(f"#### 📈 Summary Overview for **{selected_day}**")
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("📦 Unrounded Pallets", f"{total_unrounded:,.2f}")
        k2.metric("📦 Rounded Pallets", f"{total_rounded:,}")
        k3.metric("🚚 Total Orders", f"{total_orders:,}")
        k4.metric("🏢 Active Customers", f"{active_custs:,}")
        k5.metric("📊 Avg Pallets / Order", f"{avg_ppo:.2f}")

        # Map display
        st.markdown("---")
        st.subheader(f"📍 Geographic Heatmap: {METRIC_LABELS[selected_metric_key]} ({selected_day})")

        heatmap_map = create_demand_heatmap_map(
            cust_summary,
            metric=selected_metric_key,
            selected_day=selected_day,
            radius=radius,
            blur=blur,
            min_opacity=min_opacity,
            show_markers=show_markers,
            tiles=map_tiles
        )

        st_folium(heatmap_map, width="100%", height=580)

        # Customer Data Table & CSV Download
        st.markdown("---")
        st.subheader(f"📋 Customer Demand Data ({selected_day})")

        display_df = cust_summary[[
            'customer_name', 'customer_id', 'city_borough', 'address',
            'total_pallets_unrounded', 'total_pallets_rounded',
            'pallets_per_order', 'total_orders', 'latitude', 'longitude'
        ]].copy()

        display_df.columns = [
            'Customer Name', 'Customer ID', 'City/Borough', 'Address',
            'Total Pallets (Unrounded)', 'Total Pallets (Rounded)',
            'Pallets / Order', 'Total Orders', 'Latitude', 'Longitude'
        ]

        st.dataframe(display_df, use_container_width=True)

        csv_buf = io.StringIO()
        display_df.to_csv(csv_buf, index=False)
        st.download_button(
            label=f"📥 Download {selected_day} Customer CSV",
            data=csv_buf.getvalue().encode('utf-8'),
            file_name=f"customer_demand_{selected_day.lower().replace(' ', '_')}.csv",
            mime="text/csv",
            type="primary"
        )

# =========================================================================
# TAB 2: STATISTICAL DISTRIBUTIONS & BAR CHARTS (MEANS & MEDIANS)
# =========================================================================
with tab_stats:
    st.markdown("### 📊 Comprehensive Statistical Distribution & Breakdown")
    st.markdown("Descriptive statistics including **Means, Medians, Standard Deviations, Quartiles**, and visual distribution charts.")

    # Compute overall customer aggregation
    all_cust_df = aggregate_customer_demands(raw_df, selected_day='All Days', rounding_mode=round_key)
    stats_df = compute_detailed_statistics(all_cust_df)

    # KPI summary for overall dataset
    p_unround = all_cust_df['total_pallets_unrounded']
    p_round = all_cust_df['total_pallets_rounded']
    ppo_s = all_cust_df['pallets_per_order']
    ord_s = all_cust_df['total_orders']

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown("**📦 Unrounded Pallets**")
        st.metric("Mean (Average)", f"{p_unround.mean():.2f} plts")
        st.markdown(f"• **Median (50%):** `{p_unround.median():.2f} plts`  \n• **Std Dev:** `{p_unround.std():.2f}`  \n• **Total:** `{p_unround.sum():,.1f} plts`")

    with c2:
        st.markdown("**📦 Rounded Pallets**")
        st.metric("Mean (Average)", f"{p_round.mean():.2f} plts")
        st.markdown(f"• **Median (50%):** `{p_round.median():.2f} plts`  \n• **Std Dev:** `{p_round.std():.2f}`  \n• **Total:** `{int(p_round.sum()):,} plts`")

    with c3:
        st.markdown("**📊 Pallets per Order**")
        st.metric("Mean (Average)", f"{ppo_s.mean():.2f} plts/ord")
        st.markdown(f"• **Median (50%):** `{ppo_s.median():.2f} plts/ord`  \n• **Std Dev:** `{ppo_s.std():.2f}`  \n• **IQR:** `{ppo_s.quantile(0.75) - ppo_s.quantile(0.25):.2f}`")

    with c4:
        st.markdown("**🚚 Orders per Customer**")
        st.metric("Mean (Average)", f"{ord_s.mean():.2f} orders")
        st.markdown(f"• **Median (50%):** `{ord_s.median():.2f} orders`  \n• **Std Dev:** `{ord_s.std():.2f}`  \n• **Total Orders:** `{int(ord_s.sum()):,}`")

    st.markdown("---")
    st.subheader("📈 Distribution Bar Charts & Histograms")

    # Render Matplotlib Figure
    dist_fig = generate_distribution_figure(all_cust_df, raw_df)
    st.pyplot(dist_fig)

    # Detailed statistics table
    st.markdown("---")
    st.subheader("📋 Descriptive Statistics Table (Means, Medians & Quantiles)")
    st.dataframe(stats_df, use_container_width=True)

    # Export Buttons
    st.markdown("#### 📥 Export Statistical Reports")
    exp_col1, exp_col2, exp_col3 = st.columns(3)

    with exp_col1:
        stat_csv_buf = io.StringIO()
        stats_df.to_csv(stat_csv_buf, index=False)
        st.download_button(
            label="📥 Download Statistical Summary CSV",
            data=stat_csv_buf.getvalue().encode('utf-8'),
            file_name=f"statistical_summary_{file_label.split('.')[0]}.csv",
            mime="text/csv",
            type="primary"
        )

    with exp_col2:
        img_buf = io.BytesIO()
        dist_fig.savefig(img_buf, format='png', dpi=200, bbox_inches='tight')
        st.download_button(
            label="🖼️ Download Distribution Charts (PNG)",
            data=img_buf.getvalue(),
            file_name=f"distribution_charts_{file_label.split('.')[0]}.png",
            mime="image/png"
        )

    with exp_col3:
        # Generate standalone HTML
        html_buf = io.BytesIO()
        chart_b64 = base64.b64encode(img_buf.getvalue()).decode('utf-8')
        from statistics_reporter import generate_html_report
        temp_html_path = "temp_export_report.html"
        generate_html_report(all_cust_df, stats_df, chart_b64, temp_html_path, file_label)
        with open(temp_html_path, "r") as f:
            html_data = f.read().encode('utf-8')
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)

        st.download_button(
            label="🌐 Download Visual HTML Report",
            data=html_data,
            file_name=f"distribution_report_{file_label.split('.')[0]}.html",
            mime="text/html"
        )
