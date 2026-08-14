import re

for filename in ["app_valhalla_road_path.py", "app_valhalla.py"]:
    with open(filename, "r") as f:
        content = f.read()

    # 1. Expand pool size in solve_routing to 50
    content = content.replace(
        "if len(top_moves) < 5 or savings > top_moves[-1][0]:\n                    top_moves.append((savings, cost, desc, new_routes))\n                    top_moves.sort(key=lambda x: x[0], reverse=True)\n                    top_moves = top_moves[:5]",
        "if len(top_moves) < 50 or savings > top_moves[-1][0]:\n                    top_moves.append((savings, cost, desc, new_routes))\n                    top_moves.sort(key=lambda x: x[0], reverse=True)\n                    top_moves = top_moves[:50]"
    )

    # 2. Filter top_moves in session state without re-running solver
    old_unpack = """        if not needs_optimization:
            init_cost, top_moves, final_cost, improved_routes = st.session_state['optimization_results']"""

    new_unpack = """        if not needs_optimization:
            init_cost, all_top_moves, final_cost, improved_routes = st.session_state['optimization_results']
            rejected_set = st.session_state.get('rejected_moves', set())
            top_moves = [m for m in all_top_moves if m[2] not in rejected_set][:5]"""

    content = content.replace(old_unpack, new_unpack)

    # 3. In Reject button, don't delete last_run_params
    old_reject = """                with b_col2:
                    if st.button("Reject Improvement"):
                        st.session_state['rejected_moves'].add(top_moves[move_idx][2])
                        if 'last_run_params' in st.session_state:
                            del st.session_state['last_run_params']
                        st.rerun()"""

    new_reject = """                with b_col2:
                    if st.button("Reject Improvement"):
                        st.session_state['rejected_moves'].add(top_moves[move_idx][2])
                        st.rerun()"""

    content = content.replace(old_reject, new_reject)

    with open(filename, "w") as f:
        f.write(content)

    print(f"Updated {filename} successfully.")

