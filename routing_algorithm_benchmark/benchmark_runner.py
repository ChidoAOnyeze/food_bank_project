import argparse
import os
import sys
import pandas as pd

pkg_dir = os.path.dirname(os.path.abspath(__file__))
if pkg_dir not in sys.path:
    sys.path.insert(0, pkg_dir)

try:
    from .loader import load_route_instances, DEFAULT_DEPOT
    from .metrics import create_instance_distance_matrix, evaluate_routes
    from .algorithms.min_max_mtsp import tour_partitioning_mtsp
    from .algorithms.cvrp_itp import cvrp_itp
    from .algorithms.mlp_geometric import mlp_geometric_scaling
    from .algorithms.bi_objective import bi_objective_routing
    from .algorithms.ortools_solver import ortools_routing
except (ImportError, ValueError):
    from loader import load_route_instances, DEFAULT_DEPOT
    from metrics import create_instance_distance_matrix, evaluate_routes
    from algorithms.min_max_mtsp import tour_partitioning_mtsp
    from algorithms.cvrp_itp import cvrp_itp
    from algorithms.mlp_geometric import mlp_geometric_scaling
    from algorithms.bi_objective import bi_objective_routing
    from algorithms.ortools_solver import ortools_routing

def run_benchmark(input_file, output_csv=None, depot=None, metric='valhalla', include_ortools=True, trucks_file=None):
    """
    Executes the multi-algorithm routing benchmark on an input CSV route file using Valhalla road network.
    """
    depot = depot or DEFAULT_DEPOT
    unit_label = "km" if metric in ['valhalla', 'geodesic', 'wgs84'] else "units"
    metric_name = "Valhalla OSM Truck Driving Distance (km)" if metric == 'valhalla' else f"{metric.upper()} ({unit_label})"

    print(f"\n=======================================================")
    print(f"  Routing Algorithm Multi-Objective Benchmark Suite")
    print(f"=======================================================")
    print(f"Input File:       {input_file}")
    print(f"Depot Location:   Lat {depot[0]:.6f}, Lon {depot[1]:.6f}")
    print(f"Distance Metric:  {metric_name}")
    
    if trucks_file:
        print(f"Trucks File:      {trucks_file}")
    instances = load_route_instances(input_file, depot=depot, trucks_file=trucks_file)
    print(f"Found {len(instances)} routing instance(s) to evaluate.\n")

    summary_rows = []

    for idx, inst in enumerate(instances, 1):
        print(f"-------------------------------------------------------")
        print(f"[{idx}/{len(instances)}] Evaluating Instance: {inst.name} | Date: {inst.date}")
        print(f"    Stops: {inst.num_stops} | Fleet Size (Trucks): {inst.num_trucks}")
        print(f"-------------------------------------------------------")

        # Fast in-memory distance matrix for this instance's nodes
        all_inst_nodes = [depot] + list(inst.locations)
        dist_matrix = create_instance_distance_matrix(all_inst_nodes, metric=metric)
        demands_map = inst.demands_map

        # 1. Original / Actual Routes
        actual_eval = evaluate_routes(depot, inst.actual_routes, demands_map, dist_matrix)
        base_dist = actual_eval['total_distance']
        base_makespan = actual_eval['makespan']
        base_latency = actual_eval['total_latency']

        def make_row(algo_name, eval_res, is_base=False):
            t_dist = eval_res['total_distance']
            m_span = eval_res['makespan']
            t_lat = eval_res['total_latency']
            avg_lat = eval_res['avg_latency']

            # Percentage improvements vs base (positive = reduction / improvement)
            dist_imp = 0.0 if is_base or base_dist == 0 else ((base_dist - t_dist) / base_dist) * 100.0
            make_imp = 0.0 if is_base or base_makespan == 0 else ((base_makespan - m_span) / base_makespan) * 100.0
            lat_imp = 0.0 if is_base or base_latency == 0 else ((base_latency - t_lat) / base_latency) * 100.0

            # Competitive Ratios (Realized / Algo)
            dist_ratio = 1.0 if is_base or t_dist == 0 else base_dist / t_dist
            make_ratio = 1.0 if is_base or m_span == 0 else base_makespan / m_span
            lat_ratio = 1.0 if is_base or t_lat == 0 else base_latency / t_lat

            return {
                'Instance': inst.name,
                'Date': inst.date,
                'Algorithm': algo_name,
                'Total Stops': inst.num_stops,
                'Trucks': inst.num_trucks,
                f'Total Distance ({unit_label})': t_dist,
                f'Makespan ({unit_label})': m_span,
                f'Total Latency ({unit_label}-stops)': t_lat,
                f'Avg Latency ({unit_label})': avg_lat,
                'Max Load': eval_res['max_load'],
                'Load StdDev': eval_res['load_std'],
                'Dist Imprv (%)': round(dist_imp, 1),
                'Makespan Imprv (%)': round(make_imp, 1),
                'Latency Imprv (%)': round(lat_imp, 1),
                'Dist Ratio (Orig/Algo)': round(dist_ratio, 3),
                'Makespan Ratio (Orig/Algo)': round(make_ratio, 3),
                'Latency Ratio (Orig/Algo)': round(lat_ratio, 3)
            }

        summary_rows.append(make_row('Original / Realized Routes', actual_eval, is_base=True))

        # 2. Min-Max mTSP (Tour Partitioning)
        try:
            mtsp_routes = tour_partitioning_mtsp(depot, inst.locations, inst.num_trucks, dist_matrix, demands=inst.demands, vehicle_capacities=inst.vehicle_capacities)
            mtsp_eval = evaluate_routes(depot, mtsp_routes, demands_map, dist_matrix)
            summary_rows.append(make_row('Min-Max mTSP (Tour Partitioning)', mtsp_eval))
            print("  ✓ Min-Max mTSP completed")
        except Exception as e:
            print(f"  ✗ Min-Max mTSP failed: {e}")

        # 3. CVRP ITP (Iterated Tour Partitioning)
        try:
            cvrp_routes = cvrp_itp(depot, inst.locations, inst.demands, inst.num_trucks, dist_matrix, vehicle_capacities=inst.vehicle_capacities)
            cvrp_eval = evaluate_routes(depot, cvrp_routes, demands_map, dist_matrix)
            summary_rows.append(make_row('CVRP ITP (Iterated Partitioning)', cvrp_eval))
            print("  ✓ CVRP ITP completed")
        except Exception as e:
            print(f"  ✗ CVRP ITP failed: {e}")

        # 4. MLP Geometric Scaling (Minimum Latency)
        try:
            mlp_routes = mlp_geometric_scaling(depot, inst.locations, inst.num_trucks, dist_matrix, demands=inst.demands, vehicle_capacities=inst.vehicle_capacities)
            mlp_eval = evaluate_routes(depot, mlp_routes, demands_map, dist_matrix)
            summary_rows.append(make_row('MLP Geometric Scaling (Latency)', mlp_eval))
            print("  ✓ MLP Geometric Scaling completed")
        except Exception as e:
            print(f"  ✗ MLP Geometric Scaling failed: {e}")

        # 5. Bi-Objective (Makespan & Latency)
        try:
            bi_routes = bi_objective_routing(depot, inst.locations, inst.num_trucks, dist_matrix, demands=inst.demands, vehicle_capacities=inst.vehicle_capacities)
            bi_eval = evaluate_routes(depot, bi_routes, demands_map, dist_matrix)
            summary_rows.append(make_row('Bi-Objective (Makespan & Latency)', bi_eval))
            print("  ✓ Bi-Objective Routing completed")
        except Exception as e:
            print(f"  ✗ Bi-Objective Routing failed: {e}")

        # 6. OR-Tools Metaheuristic
        if include_ortools:
            try:
                ortools_routes = ortools_routing(depot, inst.locations, inst.demands, inst.num_trucks, dist_matrix, time_limit_seconds=2, vehicle_capacities=inst.vehicle_capacities)
                ortools_eval = evaluate_routes(depot, ortools_routes, demands_map, dist_matrix)
                summary_rows.append(make_row('OR-Tools (Guided Local Search)', ortools_eval))
                print("  ✓ OR-Tools Guided Local Search completed")
            except Exception as e:
                print(f"  ✗ OR-Tools Solver failed: {e}")

        print()

    # Convert to DataFrame
    df_summary = pd.DataFrame(summary_rows)

    # Save to CSV
    if output_csv is None:
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_csv = f"benchmark_summary_{base_name}.csv"

    df_summary.to_csv(output_csv, index=False)
    print(f"=======================================================")
    print(f"  Benchmark Summary Results saved to: {output_csv}")
    print(f"=======================================================\n")

    # Display detailed table (show first/last rows if large)
    display_cols = [
        'Instance', 'Date', 'Algorithm', f'Total Distance ({unit_label})',
        f'Makespan ({unit_label})', f'Total Latency ({unit_label}-stops)',
        'Dist Imprv (%)', 'Makespan Imprv (%)', 'Latency Imprv (%)'
    ]
    
    num_dates = df_summary['Date'].nunique()
    if num_dates <= 5:
        try:
            print(df_summary[display_cols].to_markdown(index=False))
        except Exception:
            print(df_summary[display_cols].to_string(index=False))
    else:
        print(f"Showing sample of {len(df_summary)} instance rows (full day-by-day table saved to {output_csv}):")
        try:
            print(pd.concat([df_summary[display_cols].head(12), df_summary[display_cols].tail(12)]).to_markdown(index=False))
        except Exception:
            print(pd.concat([df_summary[display_cols].head(12), df_summary[display_cols].tail(12)]).to_string(index=False))

    # Compute and display Cross-Date Aggregated Summary if multiple dates
    if num_dates > 1:
        agg_df = df_summary.groupby('Algorithm').agg(
            Avg_Distance=(f'Total Distance ({unit_label})', 'mean'),
            Avg_Makespan=(f'Makespan ({unit_label})', 'mean'),
            Avg_Latency=(f'Total Latency ({unit_label}-stops)', 'mean'),
            Mean_Dist_Improvement_Pct=('Dist Imprv (%)', 'mean'),
            Mean_Makespan_Improvement_Pct=('Makespan Imprv (%)', 'mean'),
            Mean_Latency_Improvement_Pct=('Latency Imprv (%)', 'mean'),
            Days_Evaluated=('Date', 'count')
        ).reset_index()

        agg_df.columns = [
            'Algorithm', f'Avg Distance ({unit_label})', f'Avg Makespan ({unit_label})',
            f'Avg Latency ({unit_label}-stops)', 'Mean Dist Imprv (%)',
            'Mean Makespan Imprv (%)', 'Mean Latency Imprv (%)', 'Delivery Days'
        ]

        # Round values for display
        agg_display = agg_df.copy()
        for col in [f'Avg Distance ({unit_label})', f'Avg Makespan ({unit_label})', f'Avg Latency ({unit_label}-stops)', 'Mean Dist Imprv (%)', 'Mean Makespan Imprv (%)', 'Mean Latency Imprv (%)']:
            agg_display[col] = agg_display[col].round(2)

        base_name = os.path.splitext(os.path.basename(input_file))[0]
        agg_output_csv = f"benchmark_aggregated_{base_name}.csv"
        agg_df.to_csv(agg_output_csv, index=False)

        print("\n=======================================================")
        print(f"  CROSS-DATE AGGREGATED BENCHMARK SUMMARY ({num_dates} Delivery Days)")
        print(f"  Saved to: {agg_output_csv}")
        print("=======================================================")
        try:
            print(agg_display.to_markdown(index=False))
        except Exception:
            print(agg_display.to_string(index=False))
        print()

    return df_summary

def main():
    parser = argparse.ArgumentParser(
        description="Multi-Objective Routing Algorithm Benchmark & Comparison Tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '-i', '--input',
        required=True,
        help="Path to input CSV route file (e.g. anon_routed_orders_5_28_26.csv or routes_sample.csv)"
    )
    parser.add_argument(
        '-t', '--trucks',
        default=None,
        help="Path to trucks CSV file defining custom vehicle capacities (e.g. trucks.csv)"
    )
    parser.add_argument(
        '-o', '--output',
        default=None,
        help="Path to output summary CSV file. Defaults to benchmark_summary_<input_name>.csv"
    )
    parser.add_argument(
        '--depot-lat',
        type=float,
        default=DEFAULT_DEPOT[0],
        help="Depot latitude coordinate"
    )
    parser.add_argument(
        '--depot-lon',
        type=float,
        default=DEFAULT_DEPOT[1],
        help="Depot longitude coordinate"
    )
    parser.add_argument(
        '--metric',
        choices=['valhalla', 'geodesic', 'euclidean', 'wgs84'],
        default='valhalla',
        help="Distance computation metric (valhalla = OpenStreetMap truck road distance, geodesic = Haversine km)"
    )
    parser.add_argument(
        '--no-ortools',
        action='store_true',
        help="Skip OR-Tools solver metaheuristic baseline"
    )

    args = parser.parse_args()
    depot = (args.depot_lat, args.depot_lon)
    
    run_benchmark(
        input_file=args.input,
        output_csv=args.output,
        depot=depot,
        metric=args.metric,
        include_ortools=not args.no_ortools,
        trucks_file=args.trucks
    )

if __name__ == '__main__':
    main()
