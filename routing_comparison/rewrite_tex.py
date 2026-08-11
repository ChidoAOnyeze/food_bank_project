import os

tex_content = r"""\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage{amsmath, amssymb, amsthm}
\usepackage{geometry}
\geometry{a4paper, margin=1in}
\usepackage{hyperref}
\usepackage{cite}
\usepackage{graphicx}

\title{Approximation Algorithms and LP Relaxations for Vehicle Routing: \\ Makespan, Latency, and Capacity Constraints}
\author{AI Researcher}
\date{\today}

\begin{document}

\maketitle

\begin{abstract}
This document provides a comprehensive review of mathematical formulations, Linear Programming (LP) relaxations, and approximation algorithms for a class of vehicle routing problems. We consider routing $n$ trucks from a single depot to visit $K$ locations in a metric space. The primary objective is to minimize the arrival time of the last truck to return to the depot (makespan). We also explore extensions involving capacity constraints (where each location demands a certain amount of goods and each truck has a finite capacity) and alternative objectives, such as minimizing the weighted sum of arrival times (latency) at the locations, as well as bi-objective formulations combining makespan and latency.
\end{abstract}

\section{Introduction}

The problem of routing a fleet of vehicles to serve a set of geographically dispersed customers is fundamental in operations research and theoretical computer science. Given a set of $K$ locations (or clients) $V = \{v_1, v_2, \dots, v_K\}$ and a depot $r$ in a metric space with distance function $d(\cdot, \cdot)$, we are tasked with finding a set of tours for $n$ trucks. All trucks start and end at the depot. 

The core version of this problem aims to minimize the \emph{makespan}, defined as the time when the last truck returns to the depot. This problem is known as the Min-Max Multiple Traveling Salesperson Problem (min-max mTSP). It is strictly NP-hard, as it generalizes the classical Traveling Salesperson Problem (TSP) when $n=1$.

\section{Minimizing Makespan: The Min-Max mTSP}

\subsection{Mathematical Formulation and LP Relaxation}
Let $x_{ij}^k \in \{0,1\}$ be a decision variable indicating whether truck $k$ traverses the edge $(i,j)$. Let $y_i^k \in \{0,1\}$ indicate if truck $k$ visits location $i$. 
To minimize the maximum return time $T$, we can formulate a Mixed Integer Linear Program (MILP):

\begin{align}
\min \quad & T \nonumber \\
\text{s.t.} \quad & \sum_{k=1}^n y_i^k = 1, \quad \forall i \in V \label{eq:visit} \\
& \sum_{j} x_{ij}^k = y_i^k, \quad \forall i \in V \cup \{r\}, \forall k \label{eq:degree1} \\
& \sum_{j} x_{ji}^k = y_i^k, \quad \forall i \in V \cup \{r\}, \forall k \label{eq:degree2} \\
& \sum_{i,j \in S} x_{ij}^k \le \sum_{i \in S \setminus \{v\}} y_i^k, \quad \forall S \subseteq V, |S| \ge 2, \forall v \in S, \forall k \label{eq:subtour} \\
& \sum_{i,j} d(i,j) x_{ij}^k \le T, \quad \forall k \label{eq:makespan} \\
& x_{ij}^k \in \{0,1\}, \ y_i^k \in \{0,1\}. \nonumber
\end{align}
Constraints \eqref{eq:visit} ensure every location is visited exactly once. Constraints \eqref{eq:degree1} and \eqref{eq:degree2} enforce flow conservation. Constraints \eqref{eq:subtour} are the subtour elimination constraints. Constraints \eqref{eq:makespan} bound the total distance traveled by each truck by the makespan $T$.

Relaxing the integrality constraint $x_{ij}^k \in \{0,1\}$ to $0 \le x_{ij}^k \le 1$ yields the standard LP relaxation. However, this relaxation has a large integrality gap for min-max problems. A more powerful relaxation involves the \emph{configuration LP}, which uses a variable for each valid bounded-length tour and has an exponentially large number of variables, solvable via column generation.

\subsection{Approximation Algorithms}
\textbf{How it works (in simple terms):}\\
Imagine you only have one very fast super-truck instead of $n$ regular trucks. The first step is to figure out the most efficient way for this one super-truck to visit everyone (this is the Traveling Salesperson Problem). Let's say you map out this giant loop starting from your warehouse, visiting every house, and coming back. 
Now, you actually have $n$ trucks. The algorithm simply takes this giant loop and cuts it into $n$ equal-length pieces (like slicing a long piece of string into $n$ equal segments). Each truck is then assigned one of these segments: it drives straight from the warehouse to the start of its segment, follows the path for its segment, and then drives straight back home. By doing this, we guarantee that no single truck has an unfairly large portion of the work, keeping the maximum time any one driver spends on the road (the makespan) as low as possible.

\textbf{Mathematical Details:}\\
For the min-max mTSP, Even et al.\ (2004) and Franks et al.\ established approximation frameworks based on tree covers. A common approach yields a $3$-approximation (or better, e.g., $2.5$ using Christofides' heuristic) by guessing the optimal makespan $T^*$ via binary search. For a guessed $T$, the algorithm constructs a graph of edges with weight at most $T$ and attempts to find a set of $n$ trees rooted at the depot that cover all vertices such that the weight of each tree is bounded by $\alpha T$. Doubling the trees gives the tours. The current best approximations for metric min-max mTSP are close to $2$.

\section{Incorporating Capacity Constraints (CVRP)}

When each location $i$ demands $g_i$ goods and each truck has a maximum capacity $G$, the problem becomes the Capacitated Vehicle Routing Problem (CVRP) with a min-max objective.

\subsection{LP Relaxation}
We extend the previous LP by adding a constraint ensuring that a truck's total demand does not exceed $G$:
\begin{equation}
\sum_{i \in V} g_i y_i^k \le G, \quad \forall k=1, \dots, n.
\end{equation}
Furthermore, valid inequalities such as the \emph{Capacity Cut} constraints are heavily utilized in the LP relaxation:
\begin{equation}
\sum_{i \in S, j \notin S} x_{ij} \ge 2 \lceil \frac{\sum_{i \in S} g_i}{G} \rceil, \quad \forall S \subseteq V.
\end{equation}
The term $\lceil \sum_{i \in S} g_i / G \rceil$ provides a lower bound on the number of trucks needed to serve subset $S$.

\subsection{Approximation Algorithms}
\textbf{How it works (in simple terms):}\\
This is very similar to the Tour Partitioning idea above. Again, imagine you map out the perfect giant route for a single super-truck to visit everyone. However, this time, your trucks have limited space in their trunks (capacity $G$). 
Instead of cutting the giant loop into equal \emph{distance} pieces, you cut it based on \emph{how much stuff} is needed. You walk along the giant loop and add up the packages required by each house. The exact moment the total reaches a truck's capacity, you make a cut. The first truck will handle the houses up to that cut, the second truck handles the next set of houses until its capacity is full, and so on. Just like before, each truck drives straight to its first house, follows its portion of the loop, and then goes straight back to the warehouse. 

\textbf{Mathematical Details:}\\
Approximation algorithms for CVRP often use the Iterated Tour Partitioning (ITP) heuristic originally proposed by Haimovich and Rinnooy Kan (1985). This involves:
1. Solving a standard TSP on all nodes.
2. Partitioning the giant tour into feasible sub-tours such that no sub-tour violates the capacity constraint $G$.
For the min-max objective, Bompadre et al.\ (2006) and others have developed approximations that balance the length of the partitioned segments, leading to constant-factor approximation guarantees that depend on the integrality gap of the underlying TSP relaxation and the bin packing problem.

\section{Minimum Latency and Weighted Arrival Time}

An alternative user-centric objective is to minimize the sum of arrival times (or weighted arrival times) at the locations. This is known as the Minimum Latency Problem (MLP) or the Traveling Repairman Problem (TRP). With $n$ vehicles, it is the $k$-TRP. Instead of making sure the driver gets home early (makespan), we want to make sure customers don't wait all day for their packages.

\subsection{LP Relaxation}
Formulating MLP mathematically requires capturing the \emph{arrival time} at each node. Let $t_i$ be the arrival time at node $i$. We use a time-indexed or flow-based LP relaxation. A common flow formulation models the number of vertices left to visit. For the multi-vehicle case, configuration LPs where variables represent paths (with their respective latencies) are often used to achieve bounded integrality gaps.

\subsection{Approximation Algorithms}
\textbf{How it works (in simple terms):}\\
If your goal is to minimize the total wait time for all customers, you shouldn't just go to the farthest customer and work your way back. Instead, you want to serve as many close-by customers as possible, as fast as possible.
The ``Geometric Scaling'' algorithm works by setting expanding ``time budgets''. Imagine you tell a driver: ``You have 10 minutes; go hit as many houses as you can and come back.'' The driver does that. Then you say, ``Now you have 20 minutes; go hit as many \emph{remaining} houses as you can.'' Then 40 minutes, 80 minutes, and so on. Because the budget doubles every time, you are extremely efficient at knocking out large dense clusters of close-by houses early in the day, meaning the vast majority of people get their packages incredibly fast, which drastically lowers the total sum of wait times.

\textbf{Mathematical Details:}\\
The first constant-factor approximation for a single vehicle was given by Blum et al.\ (1994). For multiple vehicles ($n$-TRP), Fakcharoenphol, Harrelson, and Rao (2003) and later Chekuri, Korula, and Salavatipour (2012) provided frameworks that yield constant-factor approximations. These algorithms typically involve guessing the locations of the vehicles at exponentially increasing time intervals and solving Prize-Collecting Steiner Tree (PCST) or $k$-MST problems to connect unvisited nodes, thereby controlling the latency accumulation.

\section{Bi-Objective Routing: Makespan and Latency}

In practice, a dispatcher wants to balance the system's efficiency (makespan) with customer satisfaction (latency). This means trying to keep drivers from working too much overtime while simultaneously keeping customers from waiting too long.

\subsection{Formulation}
We aim to minimize a convex combination:
\begin{equation}
\min \quad \lambda \cdot (\text{Makespan}) + (1-\lambda) \cdot (\text{Total Weighted Latency})
\end{equation}
for some $\lambda \in [0,1]$. Note that minimizing makespan generally creates sparse, long tours, while minimizing latency encourages dense, short ``stars'' radiating from the depot.

\subsection{Approximation Algorithms for Bi-Objective}
\textbf{How it works (in simple terms):}\\
This algorithm builds a roadmap (a spanning tree) that connects everyone, guaranteeing that if we trace it out, no truck drives too far (satisfying the makespan). 
To also ensure good customer wait times (latency), we have to be smart about \emph{how} the truck drives along this roadmap. Imagine the roadmap looks like a tree with many branches. If a truck drives down a very long branch with only 1 house at the end of it, all the other houses on other branches have to wait a long time. 
The algorithm uses a ``Depth-First Search'' but with a clever rule: \textbf{always visit the ``lighter'' branches first}. If you are at an intersection, and the left turn has 3 houses on it and the right turn has 50 houses, you visit the 3 houses first, then quickly return and do the 50 houses. By knocking out the smaller branches early, fewer people in total are forced to wait for the long, time-consuming detours.

\textbf{Mathematical Details:}\\
Finding a single solution that simultaneously approximates both objectives to within a constant factor is challenging because the optimal solutions for the two objectives can be diametrically opposed. However, approximation algorithms exist to approximate the \emph{Pareto frontier}. 
A common technique is the \emph{Bicriteria Approximation}: An algorithm is an $(\alpha, \beta)$-approximation if it produces a solution where the makespan is at most $\alpha$ times the optimal makespan, and the latency is at most $\beta$ times the optimal latency. Constant factor bicriteria approximations for related routing problems (like VRP) leverage modified tree-covers. By optimizing latency subject to a hard constraint on the makespan, rounding the corresponding LP relaxation using lagrangian relaxation techniques yields solutions balancing the two metrics.

\section{Conclusion}

Routing $n$ trucks to service $K$ locations involves complex trade-offs between computational tractability and model fidelity. The LP relaxations for makespan (min-max mTSP) and capacity (CVRP) rely heavily on tree constraints and capacity cuts. Transitioning to latency (MLP) shifts the focus to flow and time-indexed constraints. Approximating a weighted combination of these objectives requires bicriteria techniques that balance the egalitarian nature of makespan against the utilitarian nature of latency. Future work could incorporate stochastic demands or time windows, further enriching the LP structures.

\end{document}
"""

with open("routing_research.tex", "w") as f:
    f.write(tex_content)
