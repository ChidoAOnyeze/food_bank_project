import re

with open('app.py', 'r') as f:
    content = f.read()

old_orig = "PolyLineTextPath(pl_orig, '►', repeat=True, offset=7, attributes={'fill': r_color, 'font-weight': 'bold', 'font-size': '18'})"
new_orig = "PolyLineTextPath(pl_orig, '        ►        ', repeat=True, offset=7, attributes={'fill': r_color, 'fill-opacity': '0.3', 'font-weight': 'bold', 'font-size': '18'})"

old_new = "PolyLineTextPath(pl_new, '►', repeat=True, offset=7, attributes={'fill': r_color, 'font-weight': 'bold', 'font-size': '18'})"
new_new = "PolyLineTextPath(pl_new, '        ►        ', repeat=True, offset=7, attributes={'fill': r_color, 'fill-opacity': '1.0', 'font-weight': 'bold', 'font-size': '18'})"

content = content.replace(old_orig, new_orig)
content = content.replace(old_new, new_new)

with open('app.py', 'w') as f:
    f.write(content)

