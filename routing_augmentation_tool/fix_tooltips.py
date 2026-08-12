import re

with open("app.py", "r") as f:
    content = f.read()

# For lines like popup=f"..."
# We want to replace: popup=f"..." 
# with: tooltip=f"...", popup=f"..."

def replace_popup(match):
    # match.group(0) contains the full matched popup=f"..." string
    s = match.group(0)
    # The string inside starts at popup=f" and ends at "
    return f"tooltip={s[6:]}, {s}"

content = re.sub(r'popup=f".*?"', replace_popup, content)

with open("app.py", "w") as f:
    f.write(content)

