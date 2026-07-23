import matplotlib.pyplot as plt

def plot_routes(depot, routes, title, filename):
    plt.figure(figsize=(8, 6))
    
    # Plot depot
    plt.scatter([depot[0]], [depot[1]], c='red', marker='s', s=100, label='Depot')
    plt.text(depot[0]+0.1, depot[1]+0.1, 'Depot', fontsize=10, weight='bold')
    
    # Check if routes is a single list of tuples (single path)
    if routes and isinstance(routes[0], tuple):
        routes = [routes]
        
    colors = plt.get_cmap('tab10')
    
    for i, route in enumerate(routes):
        if not route: continue
        # Extract x and y including depot at start and end
        xs = [depot[0]] + [p[0] for p in route] + [depot[0]]
        ys = [depot[1]] + [p[1] for p in route] + [depot[1]]
        
        plt.plot(xs, ys, marker='o', color=colors(i % 10), linewidth=2, label=f'Route {i+1}')
        
        # Plot locations
        for p in route:
            if p != depot:
                plt.text(p[0]+0.1, p[1]+0.1, f'{p}', fontsize=9)
            
    plt.title(title)
    plt.xlabel('X Coordinate')
    plt.ylabel('Y Coordinate')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.savefig(filename, bbox_inches='tight')
    plt.close()
    print(f"Saved plot to {filename}")
