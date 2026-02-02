#!/usr/bin/env python3
"""
Generate visual assets for go-optimizr documentation.

Usage:
    pip install matplotlib
    python docs/generate_charts.py

Output:
    docs/worker-scaling.png
    docs/memory-efficiency.png
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Set style
plt.style.use('seaborn-v0_8-whitegrid')
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 11


def create_worker_scaling_chart():
    """Create the worker scaling / diminishing returns chart."""
    workers = [1, 2, 3, 4, 6, 8]
    throughput = [4.12, 5.41, 6.08, 5.89, 5.21, 4.83]

    fig, ax = plt.subplots(figsize=(10, 6))

    # Main line
    ax.plot(workers, throughput, 'b-o', linewidth=2.5, markersize=12,
            label='Measured Throughput', zorder=5)

    # Highlight optimal point
    ax.scatter([3], [6.08], color='green', s=200, zorder=6, marker='*')
    ax.annotate('OPTIMAL\n(w=3, 6.08 img/s)',
                xy=(3, 6.08), xytext=(3.5, 6.5),
                fontsize=11, fontweight='bold', color='green',
                arrowprops=dict(arrowstyle='->', color='green', lw=1.5))

    # Shade diminishing returns region
    ax.axvspan(3, 8.5, alpha=0.15, color='red', label='Diminishing Returns Zone')

    # Shade I/O overlap benefit region
    ax.axvspan(0.5, 3, alpha=0.15, color='green', label='I/O Overlap Benefit')

    # Labels and title
    ax.set_xlabel('Worker Count', fontsize=13, fontweight='bold')
    ax.set_ylabel('Throughput (images/second)', fontsize=13, fontweight='bold')
    ax.set_title('Worker Scaling on 1-Core System\nDiminishing Returns Beyond w=3',
                 fontsize=14, fontweight='bold', pad=15)

    # Set limits
    ax.set_xlim(0.5, 8.5)
    ax.set_ylim(3.5, 7)
    ax.set_xticks(workers)

    # Legend
    ax.legend(loc='lower right', fontsize=10)

    # Add annotation for context switching
    ax.annotate('Context switch\noverhead exceeds\nI/O overlap benefit',
                xy=(6, 5.21), xytext=(6.5, 4.2),
                fontsize=9, style='italic', color='darkred',
                arrowprops=dict(arrowstyle='->', color='darkred', lw=1))

    plt.tight_layout()
    plt.savefig('docs/worker-scaling.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print('Created: docs/worker-scaling.png')
    plt.close()


def create_memory_efficiency_chart():
    """Create the memory efficiency comparison chart."""
    workers = [1, 2, 3, 4, 6, 8]
    peak_memory = [187, 256, 319, 398, 512, 624]
    throughput = [4.12, 5.41, 6.08, 5.89, 5.21, 4.83]

    # Calculate efficiency (img/s per 100MB)
    efficiency = [t / (m / 100) for t, m in zip(throughput, peak_memory)]

    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Bar chart for memory
    bars = ax1.bar(workers, peak_memory, color='steelblue', alpha=0.7,
                   label='Peak Memory (MB)', width=0.6)
    ax1.set_xlabel('Worker Count', fontsize=13, fontweight='bold')
    ax1.set_ylabel('Peak Memory (MB)', fontsize=13, fontweight='bold', color='steelblue')
    ax1.tick_params(axis='y', labelcolor='steelblue')
    ax1.set_ylim(0, 700)

    # Highlight w=3 bar
    bars[2].set_color('green')
    bars[2].set_alpha(0.9)

    # Second y-axis for efficiency
    ax2 = ax1.twinx()
    ax2.plot(workers, efficiency, 'ro-', linewidth=2.5, markersize=10,
             label='Efficiency (img/s per 100MB)')
    ax2.set_ylabel('Efficiency (img/s per 100MB)', fontsize=13,
                   fontweight='bold', color='darkred')
    ax2.tick_params(axis='y', labelcolor='darkred')
    ax2.set_ylim(2.5, 5.5)

    # Highlight optimal efficiency
    ax2.scatter([3], [efficiency[2]], color='green', s=200, zorder=6, marker='*')

    # Title
    plt.title('Memory Usage vs Throughput Efficiency\nw=3 Maximizes Both',
              fontsize=14, fontweight='bold', pad=15)

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right', fontsize=10)

    plt.tight_layout()
    plt.savefig('docs/memory-efficiency.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print('Created: docs/memory-efficiency.png')
    plt.close()


def create_architecture_diagram():
    """Create a simple ASCII architecture for fallback."""
    diagram = """
    ┌─────────────────────────────────────────────────────────────────┐
    │                    GO-OPTIMIZR DATA FLOW                         │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │   ┌──────────┐     ┌──────────┐     ┌──────────┐               │
    │   │  INPUT   │     │  WORKER  │     │  OUTPUT  │               │
    │   │  DIR     │────►│   POOL   │────►│   DIR    │               │
    │   │ (10 GB)  │     │  (w=3)   │     │ (0.4 GB) │               │
    │   └──────────┘     └──────────┘     └──────────┘               │
    │        │                │                │                      │
    │        │         ┌──────┴──────┐         │                      │
    │        │         │             │         │                      │
    │        ▼         ▼             ▼         ▼                      │
    │   ┌─────────────────────────────────────────────┐              │
    │   │              ANALYTICS COLLECTOR             │              │
    │   │   • Memory snapshots (30s interval)         │              │
    │   │   • Atomic counters (lock-free)             │              │
    │   │   • GC pause tracking                       │              │
    │   └─────────────────────────────────────────────┘              │
    │                          │                                      │
    │                          ▼                                      │
    │                   ┌─────────────┐                               │
    │                   │ summary.json│                               │
    │                   │ (46 fields) │                               │
    │                   └─────────────┘                               │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘
    """
    with open('docs/architecture.txt', 'w') as f:
        f.write(diagram)
    print('Created: docs/architecture.txt (ASCII fallback)')


if __name__ == '__main__':
    print('Generating go-optimizr documentation charts...\n')

    try:
        create_worker_scaling_chart()
        create_memory_efficiency_chart()
    except Exception as e:
        print(f'Error generating charts: {e}')
        print('Make sure matplotlib is installed: pip install matplotlib')

    create_architecture_diagram()

    print('\nDone! Add these to your README:')
    print('  ![Worker Scaling](./docs/worker-scaling.png)')
    print('  ![Memory Efficiency](./docs/memory-efficiency.png)')
