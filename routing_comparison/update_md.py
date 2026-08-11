import re

with open("routing_research.md", "r") as f:
    content = f.read()

new_section = """### 5.2 Implemented Algorithm: Depth-First Tree Partitioning

**How it works (in simple terms):**
The implemented algorithm balances both makespan and latency in three steps:
1. **Build a Roadmap (Minimum Spanning Tree):** It creates a single "cheapest" roadmap (MST) connecting the depot to all deliveries.
2. **Smart Routing for Latency:** To minimize customer wait times, the algorithm traverses this roadmap. When it reaches an intersection, it asks: *"Which branch has fewer total deliveries?"* It **always visits the "lighter" branches first**. If you drive down a massive branch that takes hours to serve 50 houses, the 3 houses on the smaller branch are forced to wait. By knocking out the smaller branches first, you drastically reduce the total number of people kept waiting, optimizing overall latency.
3. **Slicing for Makespan (Partitioning):** The smart traversal yields one massive, perfectly-ordered list of all locations. To ensure no single truck is overworked (satisfying makespan), the algorithm slices this ordered list into equal-sized chunks based on the exact number of trucks available.

**Pseudo-code for the Implemented Algorithm:**
```text
Algorithm: Bi-Objective-Routing(depot, locations, n_trucks)
1. Let all_nodes = {depot} ∪ locations.
2. Construct a Minimum Spanning Tree (MST) connecting all_nodes.
3. For every node in the tree, calculate its "subtree weight" (the number of 
   descendant nodes in that branch).
4. Perform a Depth-First Search (DFS) starting at the depot. At each node, 
   sort its children by subtree weight (ascending). Visit lighter subtrees first.
5. The DFS traversal yields a single ordered tour of all locations.
6. Slice this ordered tour into exactly n_trucks equal-sized contiguous chunks.
7. Return the resulting sliced routes.
```"""

# Replace the existing section 5.2
content = re.sub(r"### 5.2 Approximation Algorithm: Depth-First Tree Doubling.*?```", new_section, content, flags=re.DOTALL)

with open("routing_research.md", "w") as f:
    f.write(content)
