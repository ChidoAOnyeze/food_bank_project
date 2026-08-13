import re
with open("app_valhalla.py", "r") as f:
    content = f.read()

replacement = """                            if not assigned:
                                if available_trucks:
                                    # Pop index 0 to get the largest remaining truck (since the list is sorted descending)
                                    t = available_trucks.pop(0)
                                    assignment_map[rt] = (t['Vehicle'], int(t['Pallet Capacity']))"""

content = re.sub(
    r"""                            if not assigned:
                                if available_trucks:
                                    t = available_trucks\.pop\(-1\)
                                    assignment_map\[rt\] = \(t\['Vehicle'\], int\(t\['Pallet Capacity'\]\)\)""",
    replacement, content
)

with open("app_valhalla.py", "w") as f:
    f.write(content)
