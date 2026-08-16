# Multi-Objective Routing Algorithm Benchmark Suite

A modular, high-performance benchmarking framework that takes any customer routing dataset, executes classical approximation and metaheuristic algorithms, and outputs a comparative CSV analysis across multiple operational objectives.

---

## 🚀 Quick Start

Run the benchmark from the terminal against any CSV route file:

```bash
# Run on standard delivery orders file
python routing_algorithm_benchmark/run_benchmark.py -i routing_augmentation_tool/anon_routed_orders_5_28_26.csv

# Save results to a custom CSV file
python routing_algorithm_benchmark/run_benchmark.py -i routing_comparison/routes_sample.csv -o comparison_summary.csv

# Specify a custom depot latitude/longitude and distance metric
python routing_algorithm_benchmark/run_benchmark.py \
  -i routing_augmentation_tool/anon_routed_orders_5_28_26.csv \
  --depot-lat 40.805948 \
  --depot-lon -73.872999 \
  --metric geodesic \
  -o benchmark_results.csv
```

---

## 📊 Evaluated Objectives

For each algorithm and the original/actual route baseline, the benchmark calculates:

1. **Total Distance ($km$):** Total distance traveled by all fleet vehicles combined ($\sum_{k} \text{dist}_k$).
2. **Makespan ($km$):** Longest distance / return time of any single vehicle ($\max_k \text{dist}_k$).
3. **Total Latency ($km \cdot \text{stops}$):** Cumulative sum of customer arrival times/distances ($\sum_{i} \text{arrival\_time}_i$).
4. **Average Latency ($km$):** Mean customer wait distance per stop ($\frac{\text{Total Latency}}{N}$).
5. **Max Load & Load StdDev:** Maximum demand on any truck and load balance across the fleet.
6. **Improvement Percentages (%):** Percentage savings vs. original realized routes across Distance, Makespan, and Latency.
7. **Competitive Ratios ($\frac{\text{Realized}}{\text{Algorithm}}$):** Standard operations research benchmark multiplier.

---

## 🧠 Algorithms Implemented

| Algorithm | Focus Objective | Theoretical Framework |
| :--- | :--- | :--- |
| **Original / Realized Routes** | Baseline | Actual historical dispatcher route assignments |
| **Min-Max mTSP (Tour Partitioning)** | Minimizes Makespan ($\max_k \text{dist}_k$) | 2.5-approximation via Metric TSP perimeter partitioning |
| **CVRP ITP (Iterated Partitioning)** | Minimizes Total Distance with Capacity | 2.5-approximation via demand-accumulating TSP tour cuts |
| **MLP Geometric Scaling** | Minimizes Total Customer Latency | Constant-factor approximation via geometric radius doubling ($L_i = D \cdot 2^i$) |
| **Bi-Objective Routing** | Balances Makespan + Latency | (2.5, 8.49)-bicriteria approximation via weight-prioritized MST DFS |
| **OR-Tools Metaheuristic** | Multi-Constraint Local Search | Google OR-Tools Guided Local Search with capacity & span penalties |

---

## 📁 Package Structure

```
routing_algorithm_benchmark/
├── algorithms/
│   ├── __init__.py
│   ├── min_max_mtsp.py      # Min-Max Multiple TSP (Tour Partitioning)
│   ├── cvrp_itp.py          # Capacitated VRP (Iterated Tour Partitioning)
│   ├── mlp_geometric.py     # Minimum Latency Problem (Geometric Scaling)
│   ├── bi_objective.py      # Makespan + Latency (Weight-Ordered DFS Tree)
│   └── ortools_solver.py    # Google OR-Tools Guided Local Search Solver
├── loader.py                # Universal CSV route loader (single-day & multi-day)
├── metrics.py               # Multi-objective metrics evaluator & DistanceMatrix
├── benchmark_runner.py      # Core CLI benchmark runner
├── run_benchmark.py         # Entry-point script
└── README.md                # Documentation & usage guide
```

---

## 📄 Output CSV Summary Format

The output CSV (e.g. `benchmark_summary_5_28_26.csv`) contains:

```csv
Instance,Algorithm,Total Stops,Trucks,Total Distance (km),Makespan (km),Total Latency (km-stops),Avg Latency (km),Max Load,Load StdDev,Dist Imprv (%),Makespan Imprv (%),Latency Imprv (%),Dist Ratio (Orig/Algo),Makespan Ratio (Orig/Algo),Latency Ratio (Orig/Algo)
```
