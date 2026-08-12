import re

with open("app.py", "r") as f:
    content = f.read()

# 1. We need to extract the optimization block from the middle.
# It looks like:
#        if 'last_run_params' not in st.session_state or st.session_state['last_run_params'] != current_params:
#            st.subheader("Live Feed: Top 5 Local Improvements on Initial Route")
#            feed_container = st.empty()
#            
#            with st.spinner("Optimizing routes..."):
#                results = solve_routing(...)
#            st.session_state['optimization_results'] = results
#            st.session_state['last_run_params'] = current_params
#        
#        init_cost, top_moves, final_cost, improved_routes = st.session_state['optimization_results']

# We will replace it with `needs_optimization` flag and logic
optimization_setup_replace = """
        needs_optimization = ('last_run_params' not in st.session_state or st.session_state['last_run_params'] != current_params)
        
        selected_option = "Show Full OR-Tools Optimization"
        show_proposed = False
        top_moves = []
        improved_routes = []
        
        if not needs_optimization:
            init_cost, top_moves, final_cost, improved_routes = st.session_state['optimization_results']
"""
content = re.sub(
    r"        if 'last_run_params' not in st\.session_state.*?init_cost, top_moves, final_cost, improved_routes = st\.session_state\['optimization_results'\]",
    optimization_setup_replace, content, flags=re.DOTALL
)


# 2. Add the optimization execution block to the VERY BOTTOM of the file (after the download button)
# The end of the file currently is:
#            st.download_button(
#                label="Download Updated Routes CSV",
#                data=csv_str,
#                file_name="updated_routes.csv",
#                mime="text/csv"
#            )
optimization_execution = """
            st.download_button(
                label="Download Updated Routes CSV",
                data=csv_str,
                file_name="updated_routes.csv",
                mime="text/csv"
            )
            
            if needs_optimization:
                st.subheader("Searching for Improvements...")
                feed_container = st.empty()
                
                with st.spinner("Optimizing routes (map is usable while this runs)..."):
                    results = solve_routing(
                        locations, demands, vehicle_capacities, initial_routes, truck_names, node_names, makespan_weight, latency_weight, ui_container=feed_container, test_mode=test_mode, allow_overcapacity=allow_overcapacity, rejected_moves=st.session_state.get('rejected_moves', set())
                    )
                st.session_state['optimization_results'] = results
                st.session_state['last_run_params'] = current_params
                st.rerun()
"""
content = content.replace(
"""            st.download_button(
                label="Download Updated Routes CSV",
                data=csv_str,
                file_name="updated_routes.csv",
                mime="text/csv"
            )""", optimization_execution)

with open("app.py", "w") as f:
    f.write(content)

