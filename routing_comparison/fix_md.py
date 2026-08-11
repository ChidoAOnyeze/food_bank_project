import re

with open("routing_research.md", "r") as f:
    content = f.read()

# Fix the duplicate block
content = re.sub(r"```text\nAlgorithm: Bi-Objective-Routing\(V, r, T_budget\).*?```\n", "", content, flags=re.DOTALL)

with open("routing_research.md", "w") as f:
    f.write(content)
