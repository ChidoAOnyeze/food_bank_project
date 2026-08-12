import re
with open("app.py", "r") as f:
    content = f.read()

replace_str = """
        needs_optimization = ('last_run_params' not in st.session_state or st.session_state['last_run_params'] != current_params)
        
        selected_option = "Show Full OR-Tools Optimization"
        show_proposed = False
        top_moves = []
        improved_routes = []
        init_cost = 0 # Prevent NameError, but avoid triggering init_cost > 0 logic
        final_cost = 0
        
        if not needs_optimization:
            init_cost, top_moves, final_cost, improved_routes = st.session_state['optimization_results']
"""
content = re.sub(
    r"        needs_optimization = \('last_run_params' not in st\.session_state or st\.session_state\['last_run_params'\] != current_params\).*?if not needs_optimization:\s+init_cost, top_moves, final_cost, improved_routes = st\.session_state\['optimization_results'\]",
    replace_str, content, flags=re.DOTALL
)

with open("app.py", "w") as f:
    f.write(content)
