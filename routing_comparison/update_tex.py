with open("routing_research.tex", "r") as f:
    content = f.read()

new_section = r"""\subsection{Implemented Algorithm: Depth-First Tree Partitioning}
\textbf{How it works (in simple terms):}\\
The implemented algorithm balances both makespan and latency in three steps:
1. \textbf{Build a Roadmap (Minimum Spanning Tree):} It creates a single ``cheapest'' roadmap (MST) connecting the depot to all deliveries.
2. \textbf{Smart Routing for Latency:} To minimize customer wait times, the algorithm traverses this roadmap. When it reaches an intersection, it asks: \emph{``Which branch has fewer total deliveries?''} It \textbf{always visits the ``lighter'' branches first}. If you drive down a massive branch that takes hours to serve 50 houses, the 3 houses on the smaller branch are forced to wait. By knocking out the smaller branches first, you drastically reduce the total number of people kept waiting, optimizing overall latency.
3. \textbf{Slicing for Makespan (Partitioning):} The smart traversal yields one massive, perfectly-ordered list of all locations. To ensure no single truck is overworked (satisfying makespan), the algorithm slices this ordered list into equal-sized chunks based on the exact number of trucks available.

\textbf{Mathematical Details:}\\
Finding a single solution that simultaneously approximates both objectives to within a constant factor is challenging because the optimal solutions for the two objectives can be diametrically opposed. However, approximation algorithms exist to approximate the \emph{Pareto frontier}. 
A common technique is the \emph{Bicriteria Approximation}: An algorithm is an $(\alpha, \beta)$-approximation if it produces a solution where the makespan is at most $\alpha$ times the optimal makespan, and the latency is at most $\beta$ times the optimal latency. Constant factor bicriteria approximations for related routing problems (like VRP) leverage modified tree-covers. By optimizing latency subject to a hard constraint on the makespan, rounding the corresponding LP relaxation using lagrangian relaxation techniques yields solutions balancing the two metrics.
"""

start_str = r"\subsection{Approximation Algorithms for Bi-Objective}"
end_str = r"\section{Conclusion}"

start_idx = content.find(start_str)
end_idx = content.find(end_str)

if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_section + "\n" + content[end_idx:]
    with open("routing_research.tex", "w") as f:
        f.write(content)
else:
    print("Could not find the section boundaries.")
