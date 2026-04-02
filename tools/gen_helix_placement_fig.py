#!/usr/bin/env python
"""
Generate accepted vs rejected helix placement figures for 1-layer through 4-layer designs.

For each layer count, shows:
  - CORRECT: helices in a single row (flat sheet)
  - WRONG 1: helices in a compact grid (square-ish cross-section)
  - WRONG 2: helices scattered / diagonal / maximally non-flat

Uses tacoxDNA to convert cadnano → oxDNA, then PCA cross-section analysis.
White background, publication-quality figures.

Usage:
    QT_QPA_PLATFORM=offscreen python -m tools.gen_helix_placement_fig
"""

import os
import sys
import json
import subprocess
import tempfile
import shutil

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TACOX_DIR = os.path.join(os.path.dirname(PROJECT_ROOT), 'tacoxDNA')
TACOX_SCRIPT = os.path.join(TACOX_DIR, 'src', 'cadnano_oxDNA.py')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results', 'layer_cross_sections')
OXDNA_UNIT_NM = 0.8518

LENGTH = 126  # bp per helix


# ---------------------------------------------------------------------------
# Core pipeline (from oxdna_geometric_reward.py)
# ---------------------------------------------------------------------------

def convert_cadnano_to_oxdna(json_path, work_dir):
    cmd = [sys.executable, TACOX_SCRIPT, json_path, 'he']
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=work_dir)
    if result.returncode != 0:
        raise RuntimeError(f"tacoxDNA failed: {result.stderr[:500]}")
    dat_path = top_path = None
    for f in os.listdir(work_dir):
        if f.endswith('.oxdna') or (f.endswith('.dat') and 'oxdna' not in f):
            dat_path = os.path.join(work_dir, f)
        if f.endswith('.top'):
            top_path = os.path.join(work_dir, f)
    if not dat_path or not top_path:
        raise FileNotFoundError(f"oxDNA output not found in {work_dir}")
    return dat_path, top_path


def parse_oxdna_coordinates(dat_path):
    coords = []
    with open(dat_path) as f:
        for _ in range(3):
            next(f)
        for line in f:
            vals = line.split()
            if len(vals) >= 3:
                coords.append([float(vals[0]), float(vals[1]), float(vals[2])])
    return np.array(coords)


def pca_cross_section(coords):
    """Return PCA-projected coordinates and dims in nm."""
    from numpy.linalg import eigh
    centered = coords - coords.mean(axis=0)
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = eigh(cov)
    order = np.argsort(eigenvalues)[::-1]
    eigenvectors = eigenvectors[:, order]
    projected = centered @ eigenvectors
    dims = (projected.max(axis=0) - projected.min(axis=0)) * OXDNA_UNIT_NM
    flatness = min(dims) / max(dims) if max(dims) > 0 else 0
    return projected * OXDNA_UNIT_NM, dims, flatness


# ---------------------------------------------------------------------------
# cadnano design creation
# ---------------------------------------------------------------------------

def _init_cadnano():
    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()
    return app


def _make_methods(app):
    dc = list(app.documentControllers)[0]
    dc.newDocument()
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    class MockDC:
        def __init__(self, a, d, p):
            self._app, self._doc, self._part = a, d, p
        def document(self):
            return self._doc
        def activePart(self):
            return self._part
        def undoStack(self):
            return self._doc.undoStack()

    from cadnano2.views.agent.agentmethods import AgentMethods
    mock = MockDC(app, doc, part)
    return dc, AgentMethods(mock)


def create_design(app, positions, name):
    """Create a design with helices at given (row, col) positions."""
    dc, methods = _make_methods(app)
    methods.createHelicesWithStrands(positions=positions, strand_type="both", length=LENGTH)
    methods.addAllNeighborCrossovers("scaffold")
    methods.addAllNeighborCrossovers("staple")
    return dc, methods, name


def verify_scaffold(dc):
    """Count scaffold oligos. Valid routing = 1 scaffold oligo."""
    doc = dc.document()
    part = doc.selectedPart()
    scaffold_oligos = []
    for oligo in part.oligos():
        if oligo.isStaple():
            continue
        scaffold_oligos.append(oligo)
    return len(scaffold_oligos)


def get_cross_section(app, positions, name):
    """Create design → verify scaffold → tacoxDNA → PCA cross-section."""
    dc, methods, name = create_design(app, positions, name)
    n_scaffold = verify_scaffold(dc)
    work_dir = tempfile.mkdtemp(prefix=f'oxdna_{name}_')
    try:
        json_path = os.path.join(work_dir, f'{name}.json')
        dc.writeDocumentToFile(json_path)
        dat_path, _ = convert_cadnano_to_oxdna(json_path, work_dir)
        coords = parse_oxdna_coordinates(dat_path)
        projected, dims, flatness = pca_cross_section(coords)
        return projected, dims, flatness, n_scaffold
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Design definitions: correct vs wrong for each layer count
#
# Honeycomb lattice: row/col positions. Adjacent cols in same row = flat.
# Stacking rows = adding layers (non-flat).
# ---------------------------------------------------------------------------

# 1-layer designs (1 row of helices = flat)
# Wrong shapes: stack rows vertically so cross-section is tall, not wide
DESIGNS_1LAYER = {
    'correct': {
        'label': '1-Layer Flat\n(1×6 row)',
        'positions': [[15, 10+i] for i in range(6)],
    },
    'wrong1': {
        'label': 'Wrong: 3×2 Block',
        'positions': [[14, 10], [14, 11],
                       [15, 10], [15, 11],
                       [16, 10], [16, 11]],
    },
    'wrong2': {
        'label': 'Wrong: 6×1 Column',
        'positions': [[12, 10],
                       [13, 10],
                       [14, 10],
                       [15, 10],
                       [16, 10],
                       [17, 10]],
    },
}

# 2-layer designs (2 rows = flat rectangle)
DESIGNS_2LAYER = {
    'correct': {
        'label': '2-Layer Flat\n(2×6 rectangle)',
        'positions': [[14, 10+i] for i in range(6)] +
                     [[15, 10+i] for i in range(6)],
    },
    'wrong1': {
        'label': 'Wrong: 4×3 Block',
        'positions': [[13, 10], [13, 11], [13, 12],
                       [14, 10], [14, 11], [14, 12],
                       [15, 10], [15, 11], [15, 12],
                       [16, 10], [16, 11], [16, 12]],
    },
    'wrong2': {
        'label': 'Wrong: 12×1 Column',
        'positions': [[9, 10],
                       [10, 10],
                       [11, 10],
                       [12, 10],
                       [13, 10],
                       [14, 10],
                       [15, 10],
                       [16, 10],
                       [17, 10],
                       [18, 10],
                       [19, 10],
                       [20, 10]],
    },
}

# 3-layer designs (3 rows)
DESIGNS_3LAYER = {
    'correct': {
        'label': '3-Layer Flat\n(3×6 rectangle)',
        'positions': [[13, 10+i] for i in range(6)] +
                     [[14, 10+i] for i in range(6)] +
                     [[15, 10+i] for i in range(6)],
    },
    'wrong1': {
        'label': 'Wrong: 6×3 Tower',
        'positions': [[12, 10], [12, 11], [12, 12],
                       [13, 10], [13, 11], [13, 12],
                       [14, 10], [14, 11], [14, 12],
                       [15, 10], [15, 11], [15, 12],
                       [16, 10], [16, 11], [16, 12],
                       [17, 10], [17, 11], [17, 12]],
    },
    'wrong2': {
        'label': 'Wrong: 9×2 Tower',
        'positions': [[10, 10], [10, 11],
                       [11, 10], [11, 11],
                       [12, 10], [12, 11],
                       [13, 10], [13, 11],
                       [14, 10], [14, 11],
                       [15, 10], [15, 11],
                       [16, 10], [16, 11],
                       [17, 10], [17, 11],
                       [18, 10], [18, 11]],
    },
}

# 4-layer designs (4 rows)
DESIGNS_4LAYER = {
    'correct': {
        'label': '4-Layer Flat\n(4×6 rectangle)',
        'positions': [[12, 10+i] for i in range(6)] +
                     [[13, 10+i] for i in range(6)] +
                     [[14, 10+i] for i in range(6)] +
                     [[15, 10+i] for i in range(6)],
    },
    'wrong1': {
        'label': 'Wrong: 8×3 Tower',
        'positions': [[10, 10], [10, 11], [10, 12],
                       [11, 10], [11, 11], [11, 12],
                       [12, 10], [12, 11], [12, 12],
                       [13, 10], [13, 11], [13, 12],
                       [14, 10], [14, 11], [14, 12],
                       [15, 10], [15, 11], [15, 12],
                       [16, 10], [16, 11], [16, 12],
                       [17, 10], [17, 11], [17, 12]],
    },
    'wrong2': {
        'label': 'Wrong: Cross/Plus',
        'positions': (
            # vertical bar (8 rows × 2 cols)
            [[10, 12], [10, 13],
             [11, 12], [11, 13],
             [12, 12], [12, 13],
             [13, 12], [13, 13],
             [14, 12], [14, 13],
             [15, 12], [15, 13],
             [16, 12], [16, 13],
             [17, 12], [17, 13]] +
            # horizontal bar wings
            [[13, 10], [13, 11], [13, 14], [13, 15],
             [14, 10], [14, 11], [14, 14], [14, 15]]
        ),
    },
}

ALL_DESIGNS = [
    ('1-Layer', DESIGNS_1LAYER),
    ('2-Layer', DESIGNS_2LAYER),
    ('3-Layer', DESIGNS_3LAYER),
    ('4-Layer', DESIGNS_4LAYER),
]


# ---------------------------------------------------------------------------
# Figure generation
# ---------------------------------------------------------------------------

def draw_bounding_box(ax, points_2d, color, pad=0.3):
    """Draw an axis-aligned dotted bounding box around 2D points."""
    from matplotlib.patches import Rectangle
    xmin, xmax = points_2d[:, 0].min(), points_2d[:, 0].max()
    ymin, ymax = points_2d[:, 1].min(), points_2d[:, 1].max()
    rect = Rectangle(
        (xmin - pad, ymin - pad),
        (xmax - xmin) + 2 * pad,
        (ymax - ymin) + 2 * pad,
        linewidth=3.5, edgecolor=color, facecolor='none',
        linestyle=(0, (4, 2)), zorder=5,
    )
    ax.add_patch(rect)


def _plot_panel(ax, proj, is_correct):
    """Plot cross-section scatter with dotted bounding box."""
    color = '#2563eb' if is_correct else '#dc2626'
    cs = proj[:, 1:3]  # PC2, PC3
    ax.scatter(cs[:, 0], cs[:, 1], c=color, s=4, alpha=0.5, edgecolors='none')
    draw_bounding_box(ax, cs, color)
    ax.set_aspect('equal')
    ax.axis('off')


def generate_figure(all_results):
    """
    Generate a 4×3 grid of clean cross-section plots for Illustrator import.
    No annotations, axes, or titles — just scatter points with dotted bounding boxes.
    Also saves each panel as an individual PNG.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    os.makedirs(RESULTS_DIR, exist_ok=True)
    n_layers = len(all_results)
    n_variants = 3

    # --- Individual panels ---
    panel_paths = []
    for row_idx, (layer_name, variants) in enumerate(all_results):
        for col_idx, (variant_key, data) in enumerate(variants.items()):
            proj = data['projected']
            is_correct = (variant_key == 'correct')

            fig, ax = plt.subplots(figsize=(4, 4))
            fig.patch.set_facecolor('white')
            ax.set_facecolor('white')
            _plot_panel(ax, proj, is_correct)

            panel_name = f'{layer_name}_{variant_key}'.replace('-', '').replace(' ', '_')
            panel_path = os.path.join(RESULTS_DIR, f'panel_{panel_name}.png')
            plt.savefig(panel_path, dpi=300, facecolor='white', bbox_inches='tight',
                        pad_inches=0.05)
            plt.close()
            panel_paths.append(panel_path)

    # --- Combined grid ---
    fig, axes = plt.subplots(n_layers, n_variants, figsize=(12, 16))
    fig.patch.set_facecolor('white')

    for row_idx, (layer_name, variants) in enumerate(all_results):
        for col_idx, (variant_key, data) in enumerate(variants.items()):
            ax = axes[row_idx, col_idx]
            ax.set_facecolor('white')
            _plot_panel(ax, data['projected'], variant_key == 'correct')

    plt.subplots_adjust(wspace=0.05, hspace=0.05)

    path = os.path.join(RESULTS_DIR, 'helix_placement_accepted_rejected.png')
    plt.savefig(path, dpi=300, facecolor='white', bbox_inches='tight', pad_inches=0.1)
    plt.close()
    print(f"\nCombined figure: {path}")
    print(f"Individual panels: {len(panel_paths)} files in {RESULTS_DIR}/")
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    app = _init_cadnano()

    all_results = []

    for layer_name, designs in ALL_DESIGNS:
        print(f"\n{'='*60}")
        print(f"  {layer_name} designs")
        print(f"{'='*60}")

        variants = {}
        for variant_key in ['correct', 'wrong1', 'wrong2']:
            d = designs[variant_key]
            name = f"{layer_name}_{variant_key}".replace('-', '').replace(' ', '_')
            print(f"  {variant_key}: {d['label'].replace(chr(10), ' ')} "
                  f"({len(d['positions'])} helices)...")

            projected, dims, flatness, n_scaffold = get_cross_section(app, d['positions'], name)
            routing_ok = "VALID (1 oligo)" if n_scaffold == 1 else f"INVALID ({n_scaffold} oligos)"
            print(f"    dims: {dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f} nm, "
                  f"flatness: {flatness:.3f}, scaffold: {routing_ok}")

            variants[variant_key] = {
                'projected': projected,
                'dims': dims,
                'flatness': flatness,
                'n_scaffold': n_scaffold,
                'label': d['label'],
            }

        all_results.append((layer_name, variants))

    path = generate_figure(all_results)
    print(f"\nDone. Output: {path}")


if __name__ == '__main__':
    main()
