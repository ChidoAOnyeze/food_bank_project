import folium
from folium.plugins import HeatMap
import pandas as pd
import numpy as np

METRIC_LABELS = {
    'total_pallets_unrounded': 'Total Pallets Consumed (Unrounded)',
    'total_pallets_rounded': 'Total Rounded Pallets (Per-Order Rounded)',
    'pallets_per_order': 'Average Pallets per Order',
    'total_orders': 'Total Number of Orders'
}

METRIC_UNITS = {
    'total_pallets_unrounded': 'pallets',
    'total_pallets_rounded': 'rounded pallets',
    'pallets_per_order': 'pallets / order',
    'total_orders': 'orders'
}

def create_demand_heatmap_map(
    customer_df,
    metric='total_pallets_unrounded',
    selected_day='All Days',
    radius=22,
    blur=18,
    min_opacity=0.35,
    max_zoom=14,
    show_markers=True,
    tiles='CartoDB positron'
):
    """
    Creates an interactive Folium map with a weighted HeatMap layer and
    informative customer location markers.
    """
    if customer_df.empty:
        # Default NYC center
        m = folium.Map(location=[40.758896, -73.985130], zoom_start=11, tiles=tiles)
        return m

    # Center map on customer centroid
    center_lat = float(customer_df['latitude'].mean())
    center_lon = float(customer_df['longitude'].mean())
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles=tiles)

    metric_title = METRIC_LABELS.get(metric, metric)
    unit_label = METRIC_UNITS.get(metric, '')

    # Prepare HeatMap weighted data
    heat_data = []
    max_val = customer_df[metric].max() if not customer_df.empty else 1.0
    if max_val <= 0:
        max_val = 1.0

    for _, row in customer_df.iterrows():
        lat = float(row['latitude'])
        lon = float(row['longitude'])
        val = float(row[metric])
        # Normalized weight between 0.1 and 1.0 for folium heatmap
        norm_weight = max(val / max_val, 0.05)
        heat_data.append([lat, lon, norm_weight])

    # Add HeatMap Layer
    gradient = {
        0.2: '#3b82f6', # Blue
        0.4: '#10b981', # Green
        0.6: '#eab308', # Yellow
        0.8: '#f97316', # Orange
        1.0: '#ef4444'  # Red
    }

    HeatMap(
        heat_data,
        radius=radius,
        blur=blur,
        min_opacity=min_opacity,
        max_zoom=max_zoom,
        gradient=gradient,
        name=f"Heatmap: {metric_title}"
    ).add_to(m)

    # Add Customer Circle Markers with rich popups
    if show_markers:
        marker_group = folium.FeatureGroup(name="Customer Markers")
        for _, row in customer_df.iterrows():
            lat = float(row['latitude'])
            lon = float(row['longitude'])
            val = row[metric]
            cust_name = row['customer_name']
            cust_id = row['customer_id']
            addr = row['address']
            city = row['city_borough']
            
            unrounded = row['total_pallets_unrounded']
            rounded = row['total_pallets_rounded']
            orders_cnt = row['total_orders']
            ppo = row['pallets_per_order']

            popup_html = f"""
            <div style="font-family: Arial, sans-serif; font-size: 12px; width: 230px; line-height: 1.4;">
                <div style="font-size: 14px; font-weight: bold; color: #1e293b; border-bottom: 2px solid #3b82f6; padding-bottom: 4px; margin-bottom: 6px;">
                    🏢 {cust_name}
                </div>
                <div style="color: #64748b; margin-bottom: 6px; font-size: 11px;">
                    <strong>ID:</strong> {cust_id} {f"| {addr}, {city}" if addr else ""}
                </div>
                <div style="background-color: #f1f5f9; padding: 6px 8px; border-radius: 4px; margin-bottom: 4px;">
                    <div style="color: #0f172a; font-weight: bold; margin-bottom: 2px;">
                        📌 Selected: <span style="color: #2563eb;">{val} {unit_label}</span>
                    </div>
                </div>
                <table style="width: 100%; font-size: 11px; margin-top: 4px;">
                    <tr><td style="color: #64748b;">• Total Unrounded:</td><td style="text-align: right; font-weight: bold;">{unrounded} plts</td></tr>
                    <tr><td style="color: #64748b;">• Total Rounded:</td><td style="text-align: right; font-weight: bold;">{rounded} plts</td></tr>
                    <tr><td style="color: #64748b;">• Total Orders:</td><td style="text-align: right; font-weight: bold;">{orders_cnt}</td></tr>
                    <tr><td style="color: #64748b;">• Pallets / Order:</td><td style="text-align: right; font-weight: bold;">{ppo}</td></tr>
                </table>
                <div style="font-size: 10px; color: #94a3b8; margin-top: 6px; text-align: right;">
                    Day Filter: {selected_day}
                </div>
            </div>
            """

            # Size circle by metric value
            marker_radius = max(min(int(val / max_val * 10) + 3, 14), 3)

            folium.CircleMarker(
                location=[lat, lon],
                radius=marker_radius,
                color='#1e293b',
                weight=1,
                fill=True,
                fill_color='#3b82f6',
                fill_opacity=0.75,
                tooltip=f"{cust_name} ({val} {unit_label})",
                popup=folium.Popup(popup_html, max_width=260)
            ).add_to(marker_group)

        marker_group.add_to(m)

    folium.LayerControl().add_to(m)
    return m

def save_heatmap_html(m, output_path):
    m.save(output_path)
    print(f"Saved interactive heatmap to {output_path}")
