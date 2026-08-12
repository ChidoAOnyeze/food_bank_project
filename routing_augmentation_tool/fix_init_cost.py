import re
with open("app.py", "r") as f:
    content = f.read()

replace_str = """
        needs_optimization = ('last_run_params' not in st.session_state or st.session_state['last_run_params'] != current_params)
        
        selected_option = "Show Full OR-Tools Optimization"
        show_proposed = False
        top_moves = []
        improved_routes = []
        init_cost = 1 # Dummy value to prevent NameError before optimization runs
        
        if not needs_optimization:
            init_cost, top_moves, final_cost, improved_routes = st.session_state['optimization_results']
"""
content = content.replace("""
        needs_optimization = ('last_run_params' not in st.session_state or st.session_state['last_run_params'] != current_params)
        
        selected_option = "Show Full OR-Tools Optimization"
        show_proposed = False
        top_moves = []
        improved_routes = []
        
        if not needs_optimization:
            init_cost, top_moves, final_cost, improved_routes = st.session_state['optimization_results']
""", replace_str)

with open("app.py", "w") as f:
    f.write(content)
