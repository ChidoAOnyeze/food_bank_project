# Routing Augmentation Tool: Methods for Route Improvement

This document details five industry-standard methods for taking an initial multi-truck route schedule and iteratively improving it. These are collectively known as local search heuristics and metaheuristics for the Vehicle Routing Problem (VRP). Most modern routing engines (such as Google OR-Tools or VRP-REP state-of-the-art solvers) utilize a combination of these exact methods.

## 1. 2-Opt (Intra-Route Improvement)

**Why it works**:
In a metric space, crossing paths always violate the triangle inequality, making the route artificially longer. 2-Opt undoes these crossings by reversing a subsegment of the route, untangling self-intersections without altering which customers are assigned to the truck.

**How it works**:
Given a route sequence `[..., A, B, ..., C, D, ...]`, 2-Opt removes the edges (A, B) and (C, D) and reconnects them as (A, C) and (B, D). To maintain a valid and continuous sequence, the path between B and C must be completely reversed.

**When it is likely to be effective**:
Highly effective as a fast post-processing step on any single route produced by a construction heuristic (like Nearest Neighbor or Clarke-Wright) that might have created self-intersections. It is generally the first heuristic applied.

**Implementation details**:
```python
def two_opt(route, dist_matrix):
    """
    route: list of node IDs, e.g., [depot, A, B, C, depot]
    dist_matrix: 2D array or function returning distance between two nodes
    """
    improvement = True
    best_route = route.copy()
    
    def calc_distance(r):
        return sum(dist_matrix[r[i]][r[i+1]] for i in range(len(r)-1))
        
    best_distance = calc_distance(best_route)
    
    while improvement:
        improvement = False
        # loop through all pairs of edges
        for i in range(1, len(best_route) - 2):
            for j in range(i + 1, len(best_route) - 1):
                if j - i == 1: 
                    continue # Skip adjacent edges
                
                # Try swapping by reversing the segment between i and j
                new_route = best_route[:i] + best_route[i:j+1][::-1] + best_route[j+1:]
                new_distance = calc_distance(new_route)
                
                if new_distance < best_distance:
                    best_route = new_route
                    best_distance = new_distance
                    improvement = True
                    break # Break out to restart the search
            if improvement:
                break
    return best_route
```

---

## 2. Relocate / Shift Operator (Inter-Route Improvement)

**Why it works**:
Sometimes a customer is awkwardly placed in Route A but lies perfectly along the path of Route B. The Relocate operator explores moving a single customer from their current route to any position in any other route.

**How it works**:
For every customer `c` in every Route A, and for every possible insertion position in every Route B (where A != B, or even within A), we calculate the change in cost (`delta`) of removing `c` from A and inserting `c` into B. If the move is valid (respects capacity limits) and `delta < 0`, we accept it.

**When it is likely to be effective**:
Effective for balancing routes and correcting cases where the initial clustering assigned a boundary node to the wrong truck.

**Implementation details**:
```python
def relocate(routes, capacities, demand_dict, dist_matrix):
    improvement = True
    while improvement:
        improvement = False
        best_delta = 0
        best_move = None # (route1_idx, node_index, route2_idx, insert_index)
        
        for r1_idx, route1 in enumerate(routes):
            for i in range(1, len(route1) - 1): # Exclude depots at start/end
                customer = route1[i]
                
                for r2_idx, route2 in enumerate(routes):
                    # Check capacity constraint for route2 if moving to a new route
                    if r1_idx != r2_idx:
                        current_load2 = sum(demand_dict[c] for c in route2[1:-1])
                        if current_load2 + demand_dict[customer] > capacities[r2_idx]:
                            continue
                        
                    for j in range(1, len(route2)):
                        if r1_idx == r2_idx and (j == i or j == i + 1):
                            continue # Moving node to its own exact spot does nothing
                            
                        # Calculate cost delta
                        removal_cost = (dist_matrix[route1[i-1]][route1[i+1]] - 
                                        dist_matrix[route1[i-1]][customer] - 
                                        dist_matrix[customer][route1[i+1]])
                                        
                        insertion_cost = (dist_matrix[route2[j-1]][customer] + 
                                          dist_matrix[customer][route2[j]] - 
                                          dist_matrix[route2[j-1]][route2[j]])
                                          
                        delta = removal_cost + insertion_cost
                        
                        if delta < best_delta:
                            best_delta = delta
                            best_move = (r1_idx, i, r2_idx, j, customer)
                            
        if best_delta < -1e-6:
            r1_idx, i, r2_idx, j, customer = best_move
            routes[r1_idx].pop(i)
            # If inserting into the same route later on, adjust index due to pop
            if r1_idx == r2_idx and j > i: 
                j -= 1
            routes[r2_idx].insert(j, customer)
            improvement = True
            
    return routes
```

---

## 3. Exchange / Swap Operator (Inter-Route Improvement)

**Why it works**:
Instead of just moving a node, two routes might have each "stolen" a node that belongs to the other. Swapping them can drastically reduce routing cost while often having a smaller net effect on truck capacity than Relocate.

**How it works**:
Pick customer `c1` from Route A and `c2` from Route B. Compute the cost of replacing `c1` with `c2` and vice versa. Check if the swapped capacities are valid. If the overall cost improves, perform the swap.

**When it is likely to be effective**:
Very effective when trucks are near full capacity, because Relocate often fails due to capacity limits. Exchanging customers of similar weights bypasses this strict limit.

**Implementation details**:
```python
def exchange(routes, capacities, demand_dict, dist_matrix):
    improvement = True
    while improvement:
        improvement = False
        best_delta = 0
        best_move = None
        
        for r1_idx, route1 in enumerate(routes):
            for i in range(1, len(route1) - 1):
                c1 = route1[i]
                
                for r2_idx in range(r1_idx + 1, len(routes)): # Avoid symmetric checks
                    route2 = routes[r2_idx]
                    for j in range(1, len(route2) - 1):
                        c2 = route2[j]
                        
                        load1 = sum(demand_dict[c] for c in route1[1:-1])
                        load2 = sum(demand_dict[c] for c in route2[1:-1])
                        
                        # Check capacity constraints
                        if load1 - demand_dict[c1] + demand_dict[c2] > capacities[r1_idx]: continue
                        if load2 - demand_dict[c2] + demand_dict[c1] > capacities[r2_idx]: continue
                        
                        # Calculate cost delta
                        delta1 = (dist_matrix[route1[i-1]][c2] + dist_matrix[c2][route1[i+1]]) - \
                                 (dist_matrix[route1[i-1]][c1] + dist_matrix[c1][route1[i+1]])
                                 
                        delta2 = (dist_matrix[route2[j-1]][c1] + dist_matrix[c1][route2[j+1]]) - \
                                 (dist_matrix[route2[j-1]][c2] + dist_matrix[c2][route2[j+1]])
                                 
                        delta = delta1 + delta2
                        
                        if delta < best_delta:
                            best_delta = delta
                            best_move = (r1_idx, i, r2_idx, j)
                            
        if best_delta < -1e-6:
            r1_idx, i, r2_idx, j = best_move
            # Perform swap
            routes[r1_idx][i], routes[r2_idx][j] = routes[r2_idx][j], routes[r1_idx][i]
            improvement = True
            
    return routes
```

---

## 4. Cross-Exchange (Inter-Route Segment Swap)

**Why it works**:
Single node swaps (Relocate/Exchange) can get stuck in local optima. Sometimes an entire segment of stops should be transferred or swapped with another segment to see a benefit. 

**How it works**:
It identifies a sub-segment in Route A (e.g., length 1 to L) and a sub-segment in Route B. It swaps these entire segments. 

**When it is likely to be effective**:
Extremely effective at breaking out of local minima where individual node movements are forbidden by cost or capacity constraints, but moving a cluster of adjacent nodes is highly beneficial.

**Implementation details**:
```python
def cross_exchange(routes, capacities, demand_dict, dist_matrix, max_seg_len=3):
    improvement = True
    while improvement:
        improvement = False
        best_delta = 0
        best_move = None
        
        for r1_idx, route1 in enumerate(routes):
            for i in range(1, len(route1) - 1):
                for l1 in range(1, min(max_seg_len + 1, len(route1) - i)):
                    seg1 = route1[i:i+l1]
                    
                    for r2_idx in range(r1_idx + 1, len(routes)):
                        route2 = routes[r2_idx]
                        for j in range(1, len(route2) - 1):
                            for l2 in range(1, min(max_seg_len + 1, len(route2) - j)):
                                seg2 = route2[j:j+l2]
                                
                                # Capacity checks
                                d1 = sum(demand_dict[c] for c in seg1)
                                d2 = sum(demand_dict[c] for c in seg2)
                                load1 = sum(demand_dict[c] for c in route1[1:-1])
                                load2 = sum(demand_dict[c] for c in route2[1:-1])
                                
                                if load1 - d1 + d2 > capacities[r1_idx]: continue
                                if load2 - d2 + d1 > capacities[r2_idx]: continue
                                
                                # Delta calculation
                                cost_rem1 = dist_matrix[route1[i-1]][seg1[0]] + dist_matrix[seg1[-1]][route1[i+l1]]
                                cost_rem2 = dist_matrix[route2[j-1]][seg2[0]] + dist_matrix[seg2[-1]][route2[j+l2]]
                                
                                cost_add1 = dist_matrix[route1[i-1]][seg2[0]] + dist_matrix[seg2[-1]][route1[i+l1]]
                                cost_add2 = dist_matrix[route2[j-1]][seg1[0]] + dist_matrix[seg1[-1]][route2[j+l2]]
                                
                                delta = (cost_add1 + cost_add2) - (cost_rem1 + cost_rem2)
                                
                                if delta < best_delta:
                                    best_delta = delta
                                    best_move = (r1_idx, i, l1, r2_idx, j, l2)
                                    
        if best_delta < -1e-6:
            r1_idx, i, l1, r2_idx, j, l2 = best_move
            seg1 = routes[r1_idx][i:i+l1]
            seg2 = routes[r2_idx][j:j+l2]
            
            # Perform swap
            routes[r1_idx] = routes[r1_idx][:i] + seg2 + routes[r1_idx][i+l1:]
            routes[r2_idx] = routes[r2_idx][:j] + seg1 + routes[r2_idx][j+l2:]
            improvement = True
            
    return routes
```

---

## 5. Large Neighborhood Search (LNS) / Ruin and Recreate

**Why it works**:
Traditional local searches (like the ones above) explore very small, adjacent neighborhoods. LNS is a metaheuristic that makes massive changes ("ruining" up to 10-20% of the routes) and rebuilding them to easily escape deep local minima.

**How it works**:
1. **Destroy Phase**: Remove `q` customers using heuristics (e.g., random removal, worst-cost removal, or spatial removal—removing a bunch of customers close to each other).
2. **Repair Phase**: Re-insert the removed customers using a greedy heuristic or regret heuristic (placing a customer in a route where failing to do so now would severely hurt later).
3. **Acceptance**: Accept the new route if it is better.

**When it is likely to be effective**:
This is the modern industry standard for vehicle routing. When local search stops yielding improvements, LNS jumps the algorithm to entirely new configurations.

**Implementation details**:
```python
import random
import copy

def large_neighborhood_search(routes, capacities, demand_dict, dist_matrix, iterations=1000):
    def calc_total_cost(rts):
        cost = 0
        for r in rts:
            cost += sum(dist_matrix[r[i]][r[i+1]] for i in range(len(r)-1))
        return cost
        
    best_routes = copy.deepcopy(routes)
    best_cost = calc_total_cost(routes)
    current_routes = copy.deepcopy(routes)
    
    total_customers = sum(len(r)-2 for r in routes)
    
    for _ in range(iterations):
        # 1. Destroy: Remove q random customers
        q = max(2, int(0.1 * total_customers)) # Ruin 10% of customers
        removed_customers = []
        
        for _ in range(q):
            valid_routes = [idx for idx, r in enumerate(current_routes) if len(r) > 2]
            if not valid_routes: break
            
            r_idx = random.choice(valid_routes)
            c_idx = random.randint(1, len(current_routes[r_idx]) - 2)
            removed_customers.append(current_routes[r_idx].pop(c_idx))
            
        # 2. Repair: Greedy insertion
        # Sort removed customers by demand descending (hardest to fit first)
        removed_customers.sort(key=lambda c: demand_dict[c], reverse=True)
        
        repair_failed = False
        for customer in removed_customers:
            best_insert_cost = float('inf')
            best_insert_pos = None
            
            for r_idx, route in enumerate(current_routes):
                load = sum(demand_dict[c] for c in route[1:-1])
                if load + demand_dict[customer] > capacities[r_idx]: 
                    continue
                
                for i in range(1, len(route)):
                    cost = (dist_matrix[route[i-1]][customer] + 
                            dist_matrix[customer][route[i]] - 
                            dist_matrix[route[i-1]][route[i]])
                            
                    if cost < best_insert_cost:
                        best_insert_cost = cost
                        best_insert_pos = (r_idx, i)
                        
            if best_insert_pos:
                r_idx, i = best_insert_pos
                current_routes[r_idx].insert(i, customer)
            else:
                repair_failed = True
                break
                
        # 3. Acceptance (Simple Hill Climbing)
        if not repair_failed:
            new_cost = calc_total_cost(current_routes)
            if new_cost < best_cost:
                best_routes = copy.deepcopy(current_routes)
                best_cost = new_cost
                
        # Revert for the next iteration (unless we use Simulated Annealing)
        current_routes = copy.deepcopy(best_routes)
            
    return best_routes
```
