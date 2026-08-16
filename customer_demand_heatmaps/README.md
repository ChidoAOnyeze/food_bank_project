# 🗺️ Customer Demand & Order Heatmap Analysis Tool

An interactive visualization tool to analyze geographic customer demand patterns, order densities, and pallet consumption across days of the week.

---

## 📌 Features

1. **Four Customer Metrics Computed per Location:**
   * **1. Total Pallets Consumed (Unrounded):** Exact float sum of pallet demands ($\sum \text{pallets}_i$).
   * **2. Total Rounded Pallets (Per-Order Rounded):** Sum of rounded order pallets ($\sum \lceil \text{pallets}_i \rceil$).
   * **3. Average Pallets per Order:** Mean delivery size per customer ($\frac{\text{Total Unrounded Pallets}}{\text{Total Orders}}$).
   * **4. Total Number of Orders:** Total count of orders received by that customer.

2. **Interactive Day-of-the-Week Slider:**
   * Slide between **Monday**, **Tuesday**, **Wednesday**, **Thursday**, **Friday**, **Saturday**, **Sunday**, or **All Days** to dynamically observe day-by-day spatial shifts in demand.

3. **Multi-Metric Heatmap Layers:**
   * Smooth, high-resolution Folium / Leaflet heat gradient weighted by any of the 4 customer metrics.
   * Interactive customer circle markers with detailed popups showing customer name, ID, address, and demand breakdown.

4. **Data Table & CSV Export:**
   * Export the aggregated customer summary table to CSV for any selected day or the full dataset.

---

## 🚀 Running the Streamlit Web Application

Launch the interactive web interface:

```bash
streamlit run customer_demand_heatmaps/app.py
```

---

## 💻 Running the Command-Line Interface (CLI)

Generate static HTML heatmaps and aggregated CSV summaries directly from the terminal:

```bash
# Generate heatmap for Wednesday (Unrounded Pallets)
python customer_demand_heatmaps/cli.py -i routing_comparison/sample_orders_routing.csv -d Wednesday -m unrounded -o heatmap_wednesday.html --csv-out summary_wednesday.csv

# Generate heatmap for All Days (Total Number of Orders)
python customer_demand_heatmaps/cli.py -i routing_comparison/routes_sample.csv -d "All Days" -m orders -o heatmap_orders_all.html
```

### CLI Metric Options:
* `-m unrounded`: Total Pallets Consumed (Unrounded)
* `-m rounded`: Total Rounded Pallets (Per-order rounded)
* `-m pallets_per_order`: Average Pallets per Order
* `-m orders`: Total Number of Orders
