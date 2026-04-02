#!/usr/bin/env python
"""Generate individual XZ front-view panels for each cavity variant (initial + relaxed)."""
import os
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

plt.rcParams['font.family'] = 'Arial'

UNIT_NM = 0.8518  # oxDNA length unit


def parse_oxdna_conf(conf_path):
    """Parse oxDNA .conf file, return Nx3 array of positions in nm."""
    positions = []
    with open(conf_path) as f:
        # Skip header (3 lines: timestep, box, energy)
        for _ in range(3):
            f.readline()
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 3:
                positions.append([float(parts[0]), float(parts[1]), float(parts[2])])
    return np.array(positions) * UNIT_NM


def plot_xz_front(coords, ax, title, color='steelblue'):
    """Plot XZ front view (index 0=X, 2=Z)."""
    ax.scatter(coords[:, 0], coords[:, 2], s=0.3, alpha=0.4, c=color, edgecolors='none')
    ax.set_xlabel('X (nm)', fontsize=8)
    ax.set_ylabel('Z (nm)', fontsize=8)
    ax.set_title(title, fontsize=9, fontweight='bold')
    ax.set_aspect('equal')
    ax.tick_params(labelsize=7)
    # Compute bounding box dimensions
    xspan = coords[:, 0].max() - coords[:, 0].min()
    zspan = coords[:, 2].max() - coords[:, 2].min()
    return f'{xspan:.0f}x{zspan:.0f}nm'


def main():
    variants = [
        ('20nm', 'results/cavity_variants/oxdna_20nm'),
        ('30nm', 'results/cavity_variants/oxdna_30nm'),
        ('40nm', 'results/cavity_variants/oxdna_40nm'),
    ]

    os.makedirs('results/paper_figure_assets', exist_ok=True)

    for name, work_dir in variants:
        initial = parse_oxdna_conf(os.path.join(work_dir, 'start.conf'))
        relaxed = parse_oxdna_conf(os.path.join(work_dir, 'relaxed2.conf'))

        # Individual initial panel
        fig, ax = plt.subplots(figsize=(4, 6))
        dims = plot_xz_front(initial, ax, f'{name} Initial (tacoxDNA)', color='steelblue')
        plt.tight_layout()
        p1 = f'results/paper_figure_assets/cavity_{name}_initial.png'
        fig.savefig(p1, dpi=200, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        print(f'Saved: {p1} ({dims})')

        # Individual relaxed panel
        fig, ax = plt.subplots(figsize=(4, 6))
        dims = plot_xz_front(relaxed, ax, f'{name} Relaxed (oxDNA 20M steps)', color='green')
        plt.tight_layout()
        p2 = f'results/paper_figure_assets/cavity_{name}_relaxed.png'
        fig.savefig(p2, dpi=200, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        print(f'Saved: {p2} ({dims})')


if __name__ == '__main__':
    main()
