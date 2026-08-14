import re

files = ["app_valhalla_road_path.py", "app_valhalla.py"]

for filename in files:
    with open(filename, "r") as f:
        content = f.read()

    # Update the local colors logic for improvement routes
    old_block = """                # Assign collision-free colors for the involved routes
                local_colors = {}
                used_colors = set()
                for idx in changed_route_indices:
                    desired_color = colors[idx % len(colors)]
                    if desired_color in used_colors:
                        for fallback in colors:
                            if fallback not in used_colors:
                                desired_color = fallback
                                break
                    used_colors.add(desired_color)
                    local_colors[idx] = desired_color"""

    new_block = """                # Assign high-visibility collision-free colors for the involved routes (prioritizing red, dark blue, green)
                highlight_colors = ['red', 'darkblue', 'green', 'darkred', 'darkgreen', 'blue', 'purple']
                local_colors = {idx: highlight_colors[i % len(highlight_colors)] for i, idx in enumerate(changed_route_indices)}"""

    if old_block in content:
        content = content.replace(old_block, new_block)
        print(f"Replaced local_colors in {filename}")
    else:
        print(f"Could not find old_block in {filename}")

    # Also update marker_color fallback in changed routes
    old_marker = "marker_color = local_colors.get(orig_route, colors[orig_route % len(colors)])"
    new_marker = "marker_color = local_colors.get(orig_route, highlight_colors[0])"
    if old_marker in content:
        content = content.replace(old_marker, new_marker)
        print(f"Replaced marker fallback in {filename}")

    with open(filename, "w") as f:
        f.write(content)

