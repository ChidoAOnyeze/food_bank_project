import re

with open('app.py', 'r') as f:
    content = f.read()

old_orig = "weight=5, opacity=0.8, popup=f\"Original {truck_names[idx]}\""
new_orig = "weight=6, opacity=0.3, popup=f\"Original {truck_names[idx]}\""

old_new = "weight=4, opacity=0.9, dash_array='5, 10', popup=f\"Improved {truck_names[idx]}\""
new_new = "weight=5, opacity=1.0, dash_array='5, 10', popup=f\"Improved {truck_names[idx]}\""

content = content.replace(old_orig, new_orig)
content = content.replace(old_new, new_new)

with open('app.py', 'w') as f:
    f.write(content)
