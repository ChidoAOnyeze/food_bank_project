import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
import io
import base64
from streamlit_folium import st_folium
from validator import DataValidationError
from analyzer import load_and_preprocess_orders, aggregate_customer_demands, get_available_days
from heatmap_generator import create_demand_heatmap_map, METRIC_LABELS, METRIC_UNITS
from statistics_reporter import compute_detailed_statistics, generate_distribution_figure, generate_html_report

st.set_page_config(
    page_title="Customer Demand & Order Analytics",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS: Replace animated running/biking/swimming icons with a clean circular spinner
st.markdown("""
<style>
[data-testid="stStatusWidget"] svg,
.stStatusWidget svg {
    display: none !important;
}

[data-testid="stStatusWidget"],
.stStatusWidget {
    display: inline-flex !important;
    align-items: center !important;
    gap: 8px !important;
}

[data-testid="stStatusWidget"]::before,
.stStatusWidget::before {
    content: "" !important;
    display: inline-block !important;
    width: 16px !important;
    height: 16px !important;
    border: 2.5px solid #cbd5e1 !important;
    border-top-color: #2563eb !important;
    border-radius: 50% !important;
    animation: customSpinner 0.75s linear infinite !important;
}

@keyframes customSpinner {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}
</style>
""", unsafe_allow_html=True)


# --- CACHED HELPER FUNCTIONS FOR INSTANT DAY SWITCHING ---
@st.cache_data(show_spinner="Loading and validating orders dataset...", ttl=3600)
def get_cached_orders_from_bytes(file_bytes, file_name, rounding_mode):
    return load_and_preprocess_orders(io.BytesIO(file_bytes), file_name=file_name, rounding_mode=rounding_mode, raise_on_fatal=False)

@st.cache_data(show_spinner="Loading and validating orders dataset...", ttl=3600)
def get_cached_orders_from_path(file_path, rounding_mode):
    return load_and_preprocess_orders(file_path, file_name=file_path, rounding_mode=rounding_mode, raise_on_fatal=False)

@st.cache_data(show_spinner=False)
def get_cached_customer_summary(df, selected_day, rounding_mode):
    return aggregate_customer_demands(df, selected_day=selected_day, rounding_mode=rounding_mode)

@st.cache_data(show_spinner=False)
def get_cached_stats(cust_df):
    return compute_detailed_statistics(cust_df)

st.title("Customer Demand & Statistical Distribution Hub")
st.markdown("""
Interactive analytics platform to visualize geographic demand heatmaps, evaluate pallet consumption, 
and explore **means, medians, and distribution bar charts** across days of the week.
""")

# --- SIDEBAR: DATA INPUT & CONFIG ---
st.sidebar.header("Data Source")

SAMPLE_FILES = {
    "6-Month Dataset (orders_6_months_synthetic.csv)": "dataset/orders_6_months_synthetic.csv",
    "Sample Orders (sample_orders_routing.csv)": "dataset/sample_orders_routing.csv",
    "Multi-Day Sample (routes_sample.csv)": "dataset/routes_sample.csv",
    "Routed Orders (Routed Orders 5.28.26_anonymized.csv)": "dataset/Routed Orders 5.28.26_anonymized.csv"
}

data_source = st.sidebar.radio(
    "Choose Data Source:",
    ["Use Repository Sample Dataset", "Upload CSV File"]
)

raw_df = None
file_label = ""
load_error = None

# Pallet rounding method
st.sidebar.markdown("---")
st.sidebar.header("Calculation & Display Settings")

rounding_mode = st.sidebar.radio(
    "Per-Order Pallet Rounding Method:",
    ["Ceiling (math.ceil - Standard Logistics)", "Nearest Integer (round)"],
    index=0
)
round_key = 'ceil' if 'Ceiling' in rounding_mode else 'round'

if data_source == "Upload CSV File":
    uploaded_file = st.sidebar.file_uploader("Upload Orders CSV", type=["csv"])
    if uploaded_file is not None:
        file_label = uploaded_file.name
        file_bytes = uploaded_file.getvalue()
        try:
            raw_df = get_cached_orders_from_bytes(file_bytes, file_label, round_key)
        except DataValidationError as e:
            load_error = e
        except Exception as e:
            load_error = DataValidationError(f"Unexpected error while reading CSV: {str(e)}")
else:
    sample_choice = st.sidebar.selectbox("Select Sample Dataset:", list(SAMPLE_FILES.keys()))
    sample_path = SAMPLE_FILES[sample_choice]
    filename = os.path.basename(sample_path)
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    possible_paths = [
        sample_path,
        os.path.join(parent_dir, "dataset", filename),
        os.path.join(parent_dir, sample_path),
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
        try:
            raw_df = get_cached_orders_from_path(resolved_path, round_key)
        except DataValidationError as e:
            load_error = e
    else:
        st.error(f"Sample file not found: {sample_path}")

# Handle Fatal Load Errors
if load_error is not None:
    st.error(f"**Data Validation Error:** {load_error.message}")
    if hasattr(load_error, 'issues') and load_error.issues:
        st.markdown("#### Problematic Locations in CSV:")
        err_df = pd.DataFrame(load_error.issues)
        st.dataframe(err_df)
    st.stop()

if raw_df is None:
    st.info("Please upload a routing CSV file or select a sample dataset in the sidebar to begin.")
    st.stop()

# --- DIAGNOSTICS & DATA QUALITY BANNER ---
validation_issues = raw_df.attrs.get('validation_issues', [])
if validation_issues:
    with st.expander(f"**Data Quality & Anomaly Report ({len(validation_issues)} issues detected & handled)**", expanded=False):
        st.markdown("""
        The validator detected malformed or missing values in your CSV. 
        Invalid coordinate rows were skipped, and bad demand values were auto-corrected so clean data could still be visualized.
        """)
        issues_display = []
        for iss in validation_issues:
            issues_display.append({
                'CSV Row #': iss.get('row_number'),
                'Customer / ID': iss.get('customer'),
                'Column': iss.get('column'),
                'Cell Value': iss.get('value'),
                'Issue Type': iss.get('issue_type'),
                'Diagnostic Details': iss.get('description'),
                'Severity': iss.get('severity', 'MEDIUM')
            })
        st.dataframe(pd.DataFrame(issues_display))

with st.sidebar.expander("Heatmap Map Settings", expanded=False):
    radius = st.slider("Heat Radius", min_value=10, max_value=45, value=25, step=1)
    blur = st.slider("Heat Blur", min_value=5, max_value=35, value=18, step=1)
    min_opacity = st.slider("Min Opacity", min_value=0.1, max_value=0.8, value=0.35, step=0.05)
    show_markers = st.checkbox("Show Customer Markers & Popups", value=True)
    map_tiles = st.selectbox("Map Theme", ["CartoDB positron", "OpenStreetMap", "CartoDB dark_matter"])

# Available Days
available_days = get_available_days(raw_df)

# Tabs
tab_map, tab_stats = st.tabs([
    "Geographic Heatmaps",
    "Statistical Distributions & Charts"
])

# =========================================================================
# TAB 1: INTERACTIVE HEATMAP
# =========================================================================
with tab_map:
    st.markdown("### Heatmap Controls")

    col_day, col_metric = st.columns([1.2, 1])

    with col_day:
        st.markdown("**Day of the Week Filter:**")
        selected_day = st.select_slider(
            "Slide to filter by day of week:",
            options=available_days,
            value="All Days" if "All Days" in available_days else available_days[0],
            label_visibility="collapsed",
            key="heatmap_day_slider"
        )

    with col_metric:
        st.markdown("**Heatmap Display Metric:**")
        metric_options = {
            'total_pallets_unrounded': '1. Total Pallets Consumed (Unrounded)',
            'total_pallets_rounded': '2. Total Rounded Pallets (Per-Order Rounded)',
        }
        if 'food_pallets' in raw_df.columns and raw_df['food_pallets'].sum() > 0:
            metric_options['total_food_pallets'] = f"{len(metric_options)+1}. Food Pallets"
        if 'pet_food_pallets' in raw_df.columns and raw_df['pet_food_pallets'].sum() > 0:
            metric_options['total_pet_food_pallets'] = f"{len(metric_options)+1}. Pet Food Pallets"
        if 'chemical_pallets' in raw_df.columns and raw_df['chemical_pallets'].sum() > 0:
            metric_options['total_chemical_pallets'] = f"{len(metric_options)+1}. Chemical Pallets"
        if 'order_weight' in raw_df.columns and raw_df['order_weight'].sum() > 0:
            metric_options['total_weight'] = f"{len(metric_options)+1}. Total Weight (lbs)"
            
        metric_options['pallets_per_order'] = f"{len(metric_options)+1}. Average Pallets per Order"
        metric_options['total_orders'] = f"{len(metric_options)+1}. Total Number of Orders"

        selected_metric_key = st.selectbox(
            "Select metric for heatmap intensity:",
            options=list(metric_options.keys()),
            format_func=lambda k: metric_options[k],
            label_visibility="collapsed"
        )

    # Fast cached customer aggregation (Instant switch)
    cust_summary = get_cached_customer_summary(raw_df, selected_day, round_key)

    if cust_summary.empty:
        st.warning(f"No delivery orders found for **{selected_day}** in this dataset.")
    else:
        # KPI Cards
        total_unrounded = cust_summary['total_pallets_unrounded'].sum()
        total_rounded = cust_summary['total_pallets_rounded'].sum()
        total_orders = cust_summary['total_orders'].sum()
        active_custs = len(cust_summary)
        avg_ppo = (total_unrounded / total_orders) if total_orders > 0 else 0.0

        st.markdown(f"#### Summary Overview for **{selected_day}**")
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("Unrounded Pallets", f"{total_unrounded:,.2f}")
        k2.metric("Rounded Pallets", f"{total_rounded:,}")
        k3.metric("Total Orders", f"{total_orders:,}")
        k4.metric("Active Customers", f"{active_custs:,}")
        k5.metric("Avg Pallets / Order", f"{avg_ppo:.2f}")

        # Map display
        st.markdown("---")
        st.subheader(f"Geographic Heatmap: {METRIC_LABELS.get(selected_metric_key, selected_metric_key)} ({selected_day})")

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

        st_folium(
            heatmap_map,
            width="100%",
            height=580,
            returned_objects=[],
            key=f"heatmap_{file_label}_{selected_day}_{selected_metric_key}_{round_key}_{radius}_{blur}"
        )

        # Customer Data Table & CSV Download
        st.markdown("---")
        st.subheader(f"Customer Demand Data ({selected_day})")

        display_cols = ['customer_name', 'customer_id', 'city_borough', 'address']
        for c in ['total_pallets_unrounded', 'total_pallets_rounded', 'total_food_pallets', 'total_pet_food_pallets', 'total_chemical_pallets', 'total_weight', 'pallets_per_order', 'total_orders']:
            if c in cust_summary.columns and (cust_summary[c] > 0).any():
                display_cols.append(c)
        display_cols.extend(['latitude', 'longitude'])

        display_df = cust_summary[[c for c in display_cols if c in cust_summary.columns]].copy()
        st.dataframe(display_df)

        csv_buf = io.StringIO()
        display_df.to_csv(csv_buf, index=False)
        st.download_button(
            label=f"Download {selected_day} Customer CSV",
            data=csv_buf.getvalue().encode('utf-8'),
            file_name=f"customer_demand_{selected_day.lower().replace(' ', '_')}.csv",
            mime="text/csv",
            type="primary"
        )

# =========================================================================
# TAB 2: STATISTICAL DISTRIBUTIONS & BAR CHARTS (MEANS & MEDIANS)
# =========================================================================
with tab_stats:
    st.markdown("### Comprehensive Statistical Distribution & Breakdown")
    st.markdown("Descriptive statistics including **Means, Medians, Standard Deviations, Quartiles**, and visual distribution charts.")

    # Control bar for Statistical Charts
    stat_col_metric, stat_col_day = st.columns([1.2, 1])
    
    with stat_col_metric:
        st.markdown("**Quantity / Metric to Graph:**")
        stat_metric_options = {
            'total_pallets_unrounded': '1. Total Pallets Consumed (Unrounded)',
            'total_pallets_rounded': '2. Total Rounded Pallets (Per-Order Rounded)',
        }
        if 'food_pallets' in raw_df.columns and raw_df['food_pallets'].sum() > 0:
            stat_metric_options['total_food_pallets'] = f"{len(stat_metric_options)+1}. Food Pallets"
        if 'pet_food_pallets' in raw_df.columns and raw_df['pet_food_pallets'].sum() > 0:
            stat_metric_options['total_pet_food_pallets'] = f"{len(stat_metric_options)+1}. Pet Food Pallets"
        if 'chemical_pallets' in raw_df.columns and raw_df['chemical_pallets'].sum() > 0:
            stat_metric_options['total_chemical_pallets'] = f"{len(stat_metric_options)+1}. Chemical Pallets"
        if 'order_weight' in raw_df.columns and raw_df['order_weight'].sum() > 0:
            stat_metric_options['total_weight'] = f"{len(stat_metric_options)+1}. Total Weight (lbs)"
            
        stat_metric_options['pallets_per_order'] = f"{len(stat_metric_options)+1}. Average Pallets per Order"
        stat_metric_options['total_orders'] = f"{len(stat_metric_options)+1}. Total Number of Orders"

        selected_stat_metric = st.selectbox(
            "Select quantity for distribution graphs:",
            options=list(stat_metric_options.keys()),
            format_func=lambda k: stat_metric_options[k],
            label_visibility="collapsed",
            key="stats_metric_select"
        )

    with stat_col_day:
        st.markdown("**Day of Week Filter for Stats:**")
        selected_stat_day = st.selectbox(
            "Filter stats by day:",
            options=available_days,
            index=0,
            label_visibility="collapsed",
            key="stats_day_select"
        )

    # Compute customer aggregation for selected day
    all_cust_df = get_cached_customer_summary(raw_df, selected_stat_day, round_key)
    stats_df = get_cached_stats(all_cust_df)

    # Dynamic KPI summary for chosen metric
    actual_col = selected_stat_metric if selected_stat_metric in all_cust_df.columns else 'total_pallets_unrounded'
    metric_series = all_cust_df[actual_col].dropna().astype(float) if not all_cust_df.empty else pd.Series([0.0])

    m_mean = metric_series.mean()
    m_med = metric_series.median()
    m_std = metric_series.std() if len(metric_series) > 1 else 0.0
    m_min = metric_series.min()
    m_max = metric_series.max()
    m_q25 = metric_series.quantile(0.25)
    m_q75 = metric_series.quantile(0.75)
    m_iqr = m_q75 - m_q25
    m_sum = metric_series.sum()
    
    m_unit = METRIC_UNITS.get(selected_stat_metric, 'units')
    m_title = METRIC_LABELS.get(selected_stat_metric, 'Quantity')

    st.markdown(f"#### Summary Key Performance Indicators: **{m_title}** ({selected_stat_day})")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Mean (Average)", f"{m_mean:,.2f} {m_unit}")
        st.caption(f"**Total Sum:** `{m_sum:,.1f} {m_unit}`")
    with c2:
        st.metric("Median (50%)", f"{m_med:,.2f} {m_unit}")
        st.caption(f"**Standard Dev:** `{m_std:,.2f}`")
    with c3:
        st.metric("IQR (Q3 - Q1)", f"{m_iqr:,.2f} {m_unit}")
        st.caption(f"**Q1:** `{m_q25:,.2f}` | **Q3:** `{m_q75:,.2f}`")
    with c4:
        st.metric("Min Value", f"{m_min:,.2f} {m_unit}")
        st.caption(f"**Active Customers:** `{len(metric_series):,}`")
    with c5:
        st.metric("Max Peak", f"{m_max:,.2f} {m_unit}")
        total_ords = int(all_cust_df['total_orders'].sum()) if 'total_orders' in all_cust_df.columns else 0
        st.caption(f"**Total Orders:** `{total_ords:,}`")

    st.markdown("---")
    st.subheader(f"Distribution Bar Charts & Histograms: {m_title}")

    # Render Matplotlib Figure for the chosen quantity
    dist_fig = generate_distribution_figure(all_cust_df, raw_df, selected_day=selected_stat_day, selected_metric=selected_stat_metric)
    st.pyplot(dist_fig)

    # Detailed statistics table
    st.markdown("---")
    st.subheader("Descriptive Statistics Table (Means, Medians & Quantiles)")
    st.dataframe(stats_df)

    # Export Buttons
    st.markdown("#### Export Statistical Reports")
    clean_label = os.path.splitext(os.path.basename(file_label or "dataset"))[0]
    exp_col1, exp_col2, exp_col3 = st.columns(3)

    with exp_col1:
        stat_csv_buf = io.StringIO()
        stats_df.to_csv(stat_csv_buf, index=False)
        st.download_button(
            label="Download Statistical Summary CSV",
            data=stat_csv_buf.getvalue().encode('utf-8'),
            file_name=f"statistical_summary_{clean_label}.csv",
            mime="text/csv",
            type="primary"
        )

    with exp_col2:
        img_buf = io.BytesIO()
        dist_fig.savefig(img_buf, format='png', dpi=200, bbox_inches='tight')
        st.download_button(
            label=f"Download {m_title} Charts (PNG)",
            data=img_buf.getvalue(),
            file_name=f"distribution_{selected_stat_metric}_{clean_label}.png",
            mime="image/png"
        )

    with exp_col3:
        chart_b64 = base64.b64encode(img_buf.getvalue()).decode('utf-8')
        html_content = generate_html_report(all_cust_df, stats_df, chart_b64, None, f"{file_label or 'Dataset'} - {m_title}")
        st.download_button(
            label="Download Visual HTML Report",
            data=html_content.encode('utf-8'),
            file_name=f"distribution_report_{clean_label}.html",
            mime="text/html"
        )
