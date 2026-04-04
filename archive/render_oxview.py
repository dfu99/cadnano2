#!/usr/bin/env python
"""Render an oxview JSON file as a 3D visualization using matplotlib."""
import json
import sys
import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

plt.rcParams['font.family'] = 'Arial'

# oxDNA length unit = 0.8518 nm
UNIT_NM = 0.8518

# Staple color palette (similar to cadnano)
STAPLE_COLORS = [
    '#cc0000', '#f74308', '#f7931e', '#aaaa00', '#57bb00',
    '#007200', '#03b6a2', '#1700de', '#7300de', '#b8056c',
    '#333333', '#888888', '#cc6600', '#00cc99', '#6666ff',
]


def load_oxview(path):
    """Load oxview JSON, return list of strands with 3D coordinates."""
    with open(path) as f:
        data = json.load(f)
    strands = []
    for strand in data['systems'][0]['strands']:
        is_scaffold = len(strand['monomers']) > 500
        coords = np.array([m['p'] for m in strand['monomers']]) * UNIT_NM
        strands.append({
            'coords': coords,
            'is_scaffold': is_scaffold,
            'n_monomers': len(strand['monomers']),
            'id': strand['id'],
        })
    return strands


def render(strands, output_png, title=''):
    """Render strands as 3D plot — single large perspective view."""
    scaffold = [s for s in strands if s['is_scaffold']]
    staples = [s for s in strands if not s['is_scaffold']]

    # Compute global bounds
    all_coords = np.vstack([s['coords'] for s in strands])
    center = all_coords.mean(axis=0)
    span = (all_coords.max(axis=0) - all_coords.min(axis=0)).max() / 2 * 1.15

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')

    # Draw staples with varied colors
    for i, s in enumerate(staples):
        c = s['coords']
        color = STAPLE_COLORS[i % len(STAPLE_COLORS)]
        # Subsample long staples for speed
        if len(c) > 100:
            idx = np.linspace(0, len(c) - 1, 100, dtype=int)
            c = c[idx]
        ax.plot(c[:, 0], c[:, 1], c[:, 2],
                linewidth=0.4, alpha=0.6, color=color, zorder=1)

    # Draw scaffold in blue, thicker
    for s in scaffold:
        c = s['coords']
        if len(c) > 3000:
            idx = np.linspace(0, len(c) - 1, 3000, dtype=int)
            c = c[idx]
        ax.plot(c[:, 0], c[:, 1], c[:, 2],
                linewidth=0.8, alpha=0.95, color='#1565C0', zorder=2)

    ax.set_xlim(center[0] - span, center[0] + span)
    ax.set_ylim(center[1] - span, center[1] + span)
    ax.set_zlim(center[2] - span, center[2] + span)
    ax.view_init(elev=20, azim=-55)

    if title:
        ax.set_title(title, fontsize=11, fontweight='bold', pad=10)

    ax.set_xlabel('X (nm)', fontsize=8, labelpad=5)
    ax.set_ylabel('Y (nm)', fontsize=8, labelpad=5)
    ax.set_zlabel('Z (nm)', fontsize=8, labelpad=5)
    ax.tick_params(labelsize=7)

    # Clean panes
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.xaxis.pane.set_edgecolor('lightgray')
    ax.yaxis.pane.set_edgecolor('lightgray')
    ax.zaxis.pane.set_edgecolor('lightgray')

    # Add stats annotation
    n_scaf = len(scaffold)
    n_stap = len(staples)
    scaf_bp = sum(s['n_monomers'] for s in scaffold)
    dims = all_coords.max(axis=0) - all_coords.min(axis=0)
    stats = (f'{scaf_bp}bp scaffold, {n_stap} staples\n'
             f'{dims[0]*UNIT_NM:.0f} x {dims[1]*UNIT_NM:.0f} x {dims[2]*UNIT_NM:.0f} nm')
    ax.text2D(0.02, 0.02, stats, transform=ax.transAxes,
              fontsize=7, color='#555555', fontstyle='italic')

    plt.tight_layout()
    os.makedirs(os.path.dirname(output_png) or '.', exist_ok=True)
    fig.savefig(output_png, dpi=250, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f'Saved: {output_png}')


def main():
    if len(sys.argv) < 3:
        print(f'Usage: {sys.argv[0]} <input.oxview> <output.png> [title]')
        sys.exit(1)

    oxview_path = sys.argv[1]
    output_png = sys.argv[2]
    title = sys.argv[3] if len(sys.argv) > 3 else ''

    strands = load_oxview(oxview_path)
    n_scaf = sum(1 for s in strands if s['is_scaffold'])
    n_stap = sum(1 for s in strands if not s['is_scaffold'])
    total_nt = sum(s['n_monomers'] for s in strands)
    print(f'Loaded: {len(strands)} strands ({n_scaf} scaffold, {n_stap} staples), {total_nt} nucleotides')

    render(strands, output_png, title)


if __name__ == '__main__':
    main()
