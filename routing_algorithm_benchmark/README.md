# Multi-Objective Routing Algorithm Benchmark Suite

A modular, high-performance benchmarking framework that takes any customer routing dataset, executes classical approximation and metaheuristic algorithms, and outputs a comparative CSV analysis across multiple operational objectives (Distance, Makespan, Latency, and Vehicle Capacities).

---

## Quick Start

Run the benchmark from the terminal against any CSV route file:

```bash
# Run on standard delivery orders file
python3 routing_algorithm_benchmark/benchmark_runner.py -i dataset/routes_sample.csv

# Pass a custom trucks fleet capacity file (e.g. dataset/trucks.csv)
python3 routing_algorithm_benchmark/benchmark_runner.py -i dataset/routes_sample.csv -t dataset/trucks.csv

# Save results to a custom CSV file
python3 routing_algorithm_benchmark/benchmark_runner.py -i dataset/routes_sample.csv -o benchmark_results.csv
```

---

## Algorithms Implemented & Capacity Integration

### 1. Min-Max $k$-mTSP (`min_max_mtsp.py`)
* **Without Capacity:** Minimizes Makespan (distance of longest route) via 2.5-approximation metric TSP perimeter partitioning ($L_{\text{target}} = L / k$).
* **With Capacity:** Monitors cumulative pallet load along the tour perimeter and cuts route boundaries when either $L_{\text{target}}$ or $\text{capacity}_k$ is reached.

### 2. CVRP ITP (`cvrp_itp.py`)
* **Without Capacity:** Minimizes Total Distance via single-tour partitioning (Haimovich & Rinnooy Kan 2.5-approximation).
* **With Capacity:** Binds exact vehicle capacity vectors $[c_1, c_2, \dots, c_k]$, packing vehicles along the metric tour until cumulative pallets reach capacity.

### 3. MLP Geometric Scaling (`mlp_geometric.py`)
* **Without Capacity:** Minimizes Cumulative Customer Arrival Latency via exponential ring doubling ($L_i = D \cdot 2^i$).
* **With Capacity:** Traverses dense customer clusters in strict latency priority order, allocating stops to the earliest available truck with remaining capacity.

### 4. Bi-Objective Balancing (`bi_objective.py`)
* **Without Capacity:** Explores Pareto trade-offs between Makespan and Latency via subtree weight-prioritized DFS traversal over the global MST.
* **With Capacity:** Preserves subtree branch clustering while partitioning stops subject to hard truck pallet limits.

### 5. Google OR-Tools Metaheuristic (`ortools_solver.py`)
* **Without Capacity:** Solves integer mTSP for distance and span-cost balance.
* **With Capacity:** Enforces `routing.AddDimensionWithVehicleCapacity` with Guided Local Search (GLS) neighborhood operators.
