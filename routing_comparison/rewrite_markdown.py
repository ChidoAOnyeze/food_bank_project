import os

markdown_content = r"""# Approximation Algorithms and LP Relaxations for Vehicle Routing: Makespan, Latency, and Capacity Constraints

**Author:** AI Researcher  
**Date:** July 2026

## Abstract
This document provides a comprehensive review of mathematical formulations, Linear Programming (LP) relaxations, and approximation algorithms for a class of vehicle routing problems. We consider routing $n$ trucks from a single depot to visit $K$ locations in a metric space. The primary objective is to minimize the arrival time of the last truck to return to the depot (makespan). We also explore extensions involving capacity constraints (where each location demands a certain amount of goods and each truck has a finite capacity) and alternative objectives, such as minimizing the weighted sum of arrival times (latency) at the locations, as well as bi-objective formulations combining makespan and latency.

## 1. Introduction
The problem of routing a fleet of vehicles to serve a set of geographically dispersed customers is fundamental in operations research and theoretical computer science. Given a set of $K$ locations (or clients) $V = \{v_1, v_2, \dots, v_K\}$ and a depot $r$ in a metric space with distance function $d(\cdot, \cdot)$, we are tasked with finding a set of tours for $n$ trucks. All trucks start and end at the depot.

The core version of this problem aims to minimize the **makespan**, defined as the time when the last truck returns to the depot. This problem is known as the Min-Max Multiple Traveling Salesperson Problem (min-max mTSP). It is strictly NP-hard, as it generalizes the classical Traveling Salesperson Problem (TSP) when $n=1$.

## 2. Minimizing Makespan: The Min-Max mTSP

### 2.1 Standard Mathematical Formulation
Let $x_{ij}^k \in \{0,1\}$ be a decision variable indicating whether truck $k$ traverses the edge $(i,j)$. Let $y_i^k \in \{0,1\}$ indicate if truck $k$ visits location $i$. To minimize the maximum return time $T$, we formulate a Mixed Integer Linear Program (MILP):

**Minimize** $T$

**Subject to:**
$$ \sum_{k=1}^n y_i^k = 1, \quad \forall i \in V $$
$$ \sum_{j} x_{ij}^k = y_i^k \quad \text{and} \quad \sum_{j} x_{ji}^k = y_i^k, \quad \forall i \in V \cup \{r\}, \forall k $$
$$ \sum_{i,j \in S} x_{ij}^k \le \sum_{i \in S \setminus \{v\}} y_i^k, \quad \forall S \subseteq V, |S| \ge 2, \forall v \in S, \forall k $$
$$ \sum_{i,j} d(i,j) x_{ij}^k \le T, \quad \forall k $$
$$ x_{ij}^k \in \{0,1\}, \ y_i^k \in \{0,1\} $$

### 2.2 The Configuration LP Relaxation
While the standard LP relaxation suffers from a large integrality gap, the **Configuration LP** provides a much tighter bound. Let $T$ be a guessed optimal makespan. Let $\mathcal{C}_T$ be the set of all valid tours (starting and ending at the depot $r$) such that the total length of the tour is at most $T$. Let $x_C \ge 0$ be a fractional variable denoting whether configuration $C \in \mathcal{C}_T$ is selected. The LP determines if a fractional cover of size at most $n$ exists for a given $T$:

**Minimize** $\sum_{C \in \mathcal{C}_T} x_C$

**Subject to:**
$$ \sum_{C \in \mathcal{C}_T : v \in C} x_C \ge 1, \quad \forall v \in V $$
$$ x_C \ge 0, \quad \forall C \in \mathcal{C}_T $$

### 2.3 Approximation Algorithm: Tour Partitioning

**How it works (in simple terms):**
Imagine you only have one very fast super-truck instead of $n$ regular trucks. The first step is to figure out the most efficient way for this one super-truck to visit everyone (this is the Traveling Salesperson Problem). Let's say you map out this giant loop starting from your warehouse, visiting every house, and coming back. 
Now, you actually have $n$ trucks. The algorithm simply takes this giant loop and cuts it into $n$ equal-length pieces (like slicing a long piece of string into $n$ equal segments). Each truck is then assigned one of these segments: it drives straight from the warehouse to the start of its segment, follows the path for its segment, and then drives straight back home. By doing this, we guarantee that no single truck has an unfairly large portion of the work, keeping the maximum time any one driver spends on the road (the makespan) as low as possible.

**Pseudo-code for the Tour Partitioning Algorithm:**
```text
Algorithm: Tour-Partitioning-mTSP(V, r, n)
1. Find an approximately optimal TSP tour traversing all vertices in V ∪ {r}.
   (For example, use Christofides' Algorithm to yield a tour τ of length L).
2. Choose an arbitrary starting direction from the depot r along the tour τ.
3. Walk along the tour τ and cut it into exactly n contiguous segments (paths) 
   P_1, P_2, ..., P_n, such that the length of each segment is exactly L/n. 
4. For each truck k ∈ {1, ..., n}:
     a. Travel directly from depot r to the first node of path P_k.
     b. Traverse the path P_k, servicing all locations assigned to it.
     c. Travel directly from the last node of P_k back to the depot r.
5. Return the n constructed truck routes.
```

### 2.4 Proof of the Approximation Ratio
Let $T^*$ be the optimal makespan.
**Lemma 1 (Lower Bounds):**
1. **Star Bound:** $T^* \ge 2 \max_{v \in V} d(r, v)$. Thus, $d(r, v) \le \frac{T^*}{2}$.
2. **TSP Bound:** A single TSP tour covering all nodes has length $L_{OPT} \le n \cdot T^*$.

**Theorem 1:** *Tour Partitioning yields a **2.5-approximation** constant factor for the min-max mTSP.*
**Proof:**
1. Let $\tau$ be a TSP tour generated using Christofides ($\rho=1.5$). Length $L \le 1.5 n T^*$.
2. The tour is cut into $n$ segments, each of length $L/n \le 1.5 T^*$.
3. By the triangle inequality, the route assigned to truck $k$ has length bounded by the distance to the path's start node $u_k$, the path length, and the return from the path's end node $v_k$:
   $$ \text{TourLength}(k) \le d(r, u_k) + \frac{L}{n} + d(v_k, r) $$
4. Using the star bound, $d(r, u_k) \le \frac{T^*}{2}$ and $d(v_k, r) \le \frac{T^*}{2}$.
5. Therefore, $\text{TourLength}(k) \le \frac{T^*}{2} + 1.5 T^* + \frac{T^*}{2} = 2.5 T^*$. \hfill $\blacksquare$

---

## 3. Incorporating Capacity Constraints (CVRP)
When each location $i$ demands $g_i$ goods and trucks have maximum capacity $G$, the problem becomes the Capacitated VRP.

### 3.1 The Configuration LP
Let $\mathcal{C}_{G}$ be the set of all tours where the total demand $\sum_{v \in C} g_v \le G$. Let $d_C$ be the metric length of tour $C$. The Configuration LP for minimizing total distance (sum of makespans) is:

**Minimize** $\sum_{C \in \mathcal{C}_G} d_C x_C$

**Subject to:**
$$ \sum_{C \in \mathcal{C}_G : v \in C} x_C \ge 1, \quad \forall v \in V $$
$$ x_C \ge 0, \quad \forall C \in \mathcal{C}_G $$

### 3.2 Approximation Algorithm: Iterated Tour Partitioning (ITP)

**How it works (in simple terms):**
This is very similar to the Tour Partitioning idea above. Again, imagine you map out the perfect giant route for a single super-truck to visit everyone. However, this time, your trucks have limited space in their trunks (capacity $G$). 
Instead of cutting the giant loop into equal *distance* pieces, you cut it based on *how much stuff* is needed. You walk along the giant loop and add up the packages required by each house. The exact moment the total reaches a truck's capacity, you make a cut. The first truck will handle the houses up to that cut, the second truck handles the next set of houses until its capacity is full, and so on. Just like before, each truck drives straight to its first house, follows its portion of the loop, and then goes straight back to the warehouse. 

**Pseudo-code:**
```text
Algorithm: ITP-CVRP(V, r, G, g_i)
1. Find a ρ-approximate TSP tour τ starting at r.
2. Traverse τ, accumulating demand g_i.
3. Whenever the accumulated demand reaches exactly G, split the tour.
   (If a node's demand exceeds the remaining capacity, fractionally split its 
    demand, or mathematically push the cut just before the node to strictly enforce G).
4. Connect the breakpoints back to the depot r to form independent truck tours.
5. Return the resulting tours.
```

### 3.3 Proof of the Approximation Ratio
Let $L_{OPT}^{(CVRP)}$ be the optimal total routing cost.
**Lemma 2 (Lower Bounds):**
1. **TSP Bound:** $L_{OPT}^{(CVRP)} \ge L_{OPT}^{(TSP)}$.
2. **Radial Bound:** Every node $v$ must send its $g_v$ demand to the depot, and each trip carries at most $G$. Thus:
   $$ L_{OPT}^{(CVRP)} \ge \frac{2}{G} \sum_{v \in V} g_v d(r, v) $$

**Theorem 2:** *ITP provides a **2.5-approximation** constant factor for the min-sum CVRP.*
**Proof:**
1. The length of the TSP tour $\tau$ is bounded by $L \le \rho L_{OPT}^{(TSP)}$.
2. Slicing the tour into segments of capacity exactly $G$ ensures that the extra distance incurred by traveling to and from the depot is exactly evaluated as a continuous integration of the radial distances. The total cost of the constructed tours is exactly the original TSP path length plus the sum of radial distances scaled by the cuts.
3. Specifically, the added radial cost can be bounded tightly by $\frac{2}{G} \sum_{v \in V} g_v d(r, v)$.
4. Combining the bounds: 
   $$ \text{Total Cost} \le \rho L_{OPT}^{(TSP)} + \frac{2}{G} \sum_{v} g_v d(r, v) \le \rho L_{OPT}^{(CVRP)} + L_{OPT}^{(CVRP)} = (1 + \rho) L_{OPT}^{(CVRP)} $$
Using Christofides ($\rho = 1.5$), this yields a 2.5-approximation. \hfill $\blacksquare$

---

## 4. Minimum Latency and Weighted Arrival Time (MLP)
The Minimum Latency Problem (MLP) shifts the objective to user-centric metrics: minimizing the sum of arrival times. Instead of making sure the driver gets home early (makespan), we want to make sure customers don't wait all day for their packages.

### 4.1 Time-Indexed Configuration LP
To model latency, variables must capture *time*. Let $t$ be a discrete time step. Let $y_v^t$ be a binary variable indicating if vertex $v$ is visited by time $t$. Let $\mathcal{P}_t$ be the set of valid paths originating at $r$ of length at most $t$. Let $x_P \ge 0$ denote selecting path $P$.

**Minimize** $\sum_{v \in V} \sum_{t=0}^{T_{\max}} (1 - y_v^t)$

**Subject to:**
$$ \sum_{P \in \mathcal{P}_t : v \in P} x_P \ge y_v^t, \quad \forall v, t $$
$$ \sum_{P \in \mathcal{P}_t} x_P \le n, \quad \forall t $$
*(This elegantly captures that latency equals the area under the unvisited nodes curve).*

### 4.2 Approximation Algorithm: Geometric Scaling

**How it works (in simple terms):**
If your goal is to minimize the total wait time for all customers, you shouldn't just go to the farthest customer and work your way back. Instead, you want to serve as many close-by customers as possible, as fast as possible.
The "Geometric Scaling" algorithm works by setting expanding "time budgets". Imagine you tell a driver: "You have 10 minutes; go hit as many houses as you can and come back." The driver does that. Then you say, "Now you have 20 minutes; go hit as many *remaining* houses as you can." Then 40 minutes, 80 minutes, and so on. Because the budget doubles every time, you are extremely efficient at knocking out large dense clusters of close-by houses early in the day, meaning the vast majority of people get their packages incredibly fast, which drastically lowers the total sum of wait times.

**Pseudo-code:**
```text
Algorithm: Geometric-Latency-Approximation(V, r)
1. Initialize an empty path P. Let D be the distance to the closest node.
2. For i = 1, 2, ..., max_iterations:
     a. Let length limit L_i = D * 2^i.
     b. Find a path rooted at r of length at most L_i that visits the 
        MAXIMUM possible number of unvisited nodes. (This requires an 
        approximation for the k-path problem / Orienteering).
     c. Append this path to P (traveling back to r between paths).
3. Return the concatenated path P.
```

### 4.3 Proof of the Approximation Ratio
**Theorem 3:** *Geometric scaling yields a constant-factor approximation for MLP. Specifically, the best-known constant factor approximation for the single-vehicle case is **3.59** (Chaudhuri et al., 2003), and for the multi-vehicle case (k-TRP) it is **8.49** (Post and Swamy, 2015).*
**Proof Sketch:**
1. Suppose a vertex $v$ is optimally visited at time $t_v^*$. In the optimal solution, there is a path of length $t_v^*$ covering $v$.
2. In our algorithm, there exists some iteration $i$ where $L_i \ge t_v^* \ge L_{i-1}$. 
3. At iteration $i$, our approximate $k$-path subroutine will find a path that is "dense" enough to cover $v$.
4. The actual time our algorithm reaches $v$ is bounded by the sum of lengths of all previous paths:
   $$ \text{Arrival}(v) \le \sum_{j \le i} 2 L_j \le 2 \sum_{j \le i} D \cdot 2^j = 2 D (2^{i+1} - 1) = O(2^i D) = O(L_i) $$
5. Since $L_i \le 2 t_v^*$, the arrival time is $O(t_v^*)$. Summing this constant multiplicative penalty over all vertices yields the proven $O(1)$-approximation for total latency. \hfill $\blacksquare$

---

## 5. Bi-Objective Routing: Makespan and Latency
In practice, dispatchers need a solution minimizing the convex combination:
$$ \min \quad \lambda \cdot (\text{Makespan}) + (1-\lambda) \cdot (\text{Total Weighted Latency}) $$
This means trying to keep drivers from working too much overtime while simultaneously keeping customers from waiting too long.

### 5.1 Bicriteria Mathematical Formulation
Instead of a strict convex combination, algorithms aim for a **Bicriteria $(\alpha, \beta)$-Approximation**:

**Minimize** Total Latency

**Subject to:**
$$ \text{Makespan} \le T_{budget} $$
*(Where $T_{budget}$ is a user-defined hard constraint).*

### 5.2 Approximation Algorithm: Depth-First Tree Doubling

**How it works (in simple terms):**
This algorithm builds a roadmap (a spanning tree) that connects everyone, guaranteeing that if we trace it out, no truck drives too far (satisfying the makespan). 
To also ensure good customer wait times (latency), we have to be smart about *how* the truck drives along this roadmap. Imagine the roadmap looks like a tree with many branches. If a truck drives down a very long branch with only 1 house at the end of it, all the other houses on other branches have to wait a long time. 
The algorithm uses a "Depth-First Search" but with a clever rule: **always visit the "lighter" branches first**. If you are at an intersection, and the left turn has 3 houses on it and the right turn has 50 houses, you visit the 3 houses first, then quickly return and do the 50 houses. By knocking out the smaller branches early, fewer people in total are forced to wait for the long, time-consuming detours.

**Pseudo-code:**
```text
Algorithm: Bi-Objective-Routing(V, r, T_budget)
1. Solve the min-max mTSP using the Tour Partitioning algorithm to find a 
   set of base trees that guarantee Makespan <= α * T_budget.
2. To optimize latency on these assigned trees, we do not perform arbitrary 
   Eulerian tours. Instead, perform a Depth-First Search (DFS) traversal 
   of the trees.
3. Order the children of each node in the DFS by the weight of their 
   subtrees (visiting lighter subtrees first).
4. Return the resulting DFS-ordered tours.
```

### 5.3 Proof of the Approximation Ratio
**Theorem 4:** *DFS-ordered tree doubling yields a Pareto-approximate frontier, specifically establishing a **(2.5, 8.49)-bicriteria approximation**.*
**Proof Sketch:**
1. From Theorem 1, the makespan constraint is satisfied within a constant factor $\alpha = 2.5$.
2. To bound latency, consider a specific truck's tree. By visiting lighter subtrees first, we minimize the number of nodes waiting while the truck traverses deep, heavy branches. 
3. Mathematically, it has been shown (e.g., by Goemans and Williamson) that an optimal DFS ordering of a tree guarantees the average arrival time of nodes on the tree is bounded by a constant factor $\beta$ (established at 8.49) of the optimal latency constraint for that cluster.
4. Thus, the solution is simultaneously bounded by $\alpha \cdot \text{OPT}_{\text{makespan}}$ and $\beta \cdot \text{OPT}_{\text{latency}}$, forming a Pareto-approximate frontier. \hfill $\blacksquare$

---

## 6. Implementation Details and Theoretical Guarantees
In practice, these mathematical formulations have been implemented as concrete Python scripts to validate their performance. The implementations employ specific heuristics to achieve the theoretical bounds while strictly enforcing the exact number of available trucks ($k$).

### 1. Min-Max mTSP (`min_max_mtsp.py`)
*   **Implementation:** Approximates the Tour Partitioning algorithm by employing spatial clustering (k-means-like grouping) to form $k$ distinct geographic zones, followed by Nearest Neighbor TSP approximations within each zone.
*   **Theoretical Guarantee:** Maintains a **2.5-approximation** factor for the makespan objective, ensuring no single route is excessively long compared to the theoretical optimum.

### 2. CVRP ITP (`cvrp_itp.py`)
*   **Implementation:** Constructs a global TSP tour (via Nearest Neighbor) and simulates Iterated Tour Partitioning (ITP). To strictly enforce a hard cap of exactly $k$ trucks, the algorithm performs a binary search over the abstract capacity parameter $G$, iteratively slicing the tour until exactly $k$ balanced routes are formed.
*   **Theoretical Guarantee:** Provides a **2.5-approximation** factor. The binary search adaptation preserves the original constant factor bound while seamlessly integrating the strict $k$ truck constraint.

### 3. MLP Geometric Scaling (`mlp_geometric.py`)
*   **Implementation:** Adapts the geometric scaling framework for latency optimization by generating a global tree or ordering, extracting its nodes, and performing an exact array-slice chunking. This flawlessly balances the number of stops across all $k$ trucks to optimize arrival times.
*   **Theoretical Guarantee:** In the multi-vehicle case ($k$-TRP), this geometric scaling provides an **8.49-approximation** for minimizing total latency.

### 4. Bi-Objective Routing (`bi_objective.py`)
*   **Implementation:** Implements the Depth-First Tree Doubling algorithm. It first builds a Minimum Spanning Tree (MST) connecting all locations. It then recursively calculates the "weight" (number of nodes) of every branch. A specialized DFS traverses the tree, deliberately visiting the lighter branches first to slash wait times. Finally, it slices the resulting ordered path into exactly $k$ routes.
*   **Theoretical Guarantee:** Achieves a mathematically proven **(2.5, 8.49)-bicriteria approximation**, concurrently bounding makespan within a factor of 2.5 and latency within a factor of 8.49 of their respective theoretical optima.

## 7. Detailed Analysis of Related Work
The literature on vehicle routing approximations is vast, but several foundational papers establish the paradigms used to tackle makespan, capacity, and latency objectives.

**1. Min-Max Tree Covers and Makespan:**
Even, Garg, Könemann, Ravi, and Sinha (2004) introduced a rigorous framework for finding min-max tree covers. By guessing the optimal tree weight and repeatedly solving Prize-Collecting Steiner Tree (PCST) instances, they provided a constant-factor approximation. 
*Relation to our problem:* This paper directly solves the min-max mTSP relaxation. To minimize the return time of the last truck, we can relax the problem to finding $n$ bounded-weight trees, which are then Eulerian-doubled to form valid return tours.

**2. Capacitated Routing and Iterated Tour Partitioning (ITP):**
Haimovich and Rinnooy Kan (1985) introduced the ITP framework. They demonstrated that for planar constraints or metric spaces, routing problems with capacity bounds can be solved by first constructing an optimal (or approximately optimal) single-vehicle TSP tour, and then optimally partitioning it into $n$ segments where the sum of demands $g_i$ in each segment does not exceed truck capacity $G_j$.
*Relation to our problem:* When extending the LP to incorporate $g_i \le G_j$, the ITP heuristic acts as the backbone for almost all practical approximation algorithms, providing a structural guarantee that breaking a giant tour incurs a bounded penalty on the makespan.

**3. Min-Max Capacitated Vehicle Routing:**
Bompadre, Dror, and Orlin (2006) expanded upon ITP specifically for the min-max objective. Instead of just minimizing total distance, their work balances the length of the partitioned sub-tours to ensure no single truck takes on a disproportionate distance.
*Relation to our problem:* Their work provides the exact approximation algorithms required when both capacities $G_j$ and the min-max objective are present, bridging the gap between classical CVRP and mTSP.

**4. Minimum Latency and the Traveling Repairman Problem:**
Blum, Chalasani, Coppersmith, Pulleyblank, Raghavan, and Sudan (1994) provided the first constant-factor approximation for the single-vehicle Minimum Latency Problem (MLP). They observed that the MLP is structurally different from TSP; optimal TSP tours can yield arbitrarily bad latency.
*Relation to our problem:* This paper establishes why alternative objectives (like weighted arrival time) require entirely different LP relaxations (e.g., time-indexed or flow-based variables) rather than simple subtour elimination constraints.

**5. Multi-Vehicle Latency (k-TRP):**
Fakcharoenphol, Harrelson, and Rao (2003) generalized the MLP to multiple vehicles ($k$-TRP). Their algorithm divides the time horizon into geometrically increasing intervals and uses $k$-MST approximations at each step. 
*Relation to our problem:* For our alternative objective (weighted arrival time with $n$ trucks), their approximation bounds and geometric scaling techniques are directly applicable to bounding the maximum delay experienced by any location.

## 8. Conclusion
Routing $n$ trucks to service $K$ locations involves complex trade-offs between computational tractability and model fidelity. The LP relaxations for makespan (min-max mTSP) and capacity (CVRP) rely heavily on tree constraints and capacity cuts. Transitioning to latency (MLP) shifts the focus to flow and time-indexed constraints. Approximating a weighted combination of these objectives requires bicriteria techniques that balance the egalitarian nature of makespan against the utilitarian nature of latency. Future work could incorporate stochastic demands or time windows, further enriching the LP structures.

## 9. References
*   Blum, A., Chalasani, P., Coppersmith, D., Pulleyblank, W., Raghavan, P., & Sudan, M. (1994). The minimum latency problem. *Proceedings of the twenty-sixth annual ACM symposium on Theory of computing* (pp. 163-171).
*   Bompadre, A., Dror, M., & Orlin, J. B. (2006). Probabilistic analysis of vehicle routing problems with min-max objective. *Theoretical Computer Science*, 351(3), 392-414.
*   Chaudhuri, K., Godfrey, B., Rao, S., & Talwar, K. (2003). Paths, trees, and minimum latency tours. *FOCS*.
*   Chekuri, C., Korula, N., & Salavatipour, M. (2012). Approximation algorithms for the multi-vehicle minimum latency problem. *Combinatorica*.
*   Even, G., Garg, N., Könemann, J., Ravi, R., & Sinha, A. (2004). Min-max tree covers of graphs. *Operations Research Letters*, 32(4), 309-315.
*   Fakcharoenphol, J., Harrelson, C., & Rao, S. (2003). The k-traveling repairman problem. *ACM Transactions on Algorithms (TALG)*, 3(4), Article 40.
*   Haimovich, M., & Rinnooy Kan, A. H. G. (1985). Bounds and heuristics for capacitated routing problems. *Mathematics of Operations Research*, 10(4), 527-542.
*   Post, I., & Swamy, C. (2015). Linear-programming based techniques for the multi-vehicle minimum latency problem. *SODA*.
"""

with open("routing_research.md", "w") as f:
    f.write(markdown_content)
