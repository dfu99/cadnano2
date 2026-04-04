#!/usr/bin/env python
"""
Verify diverse cadnano designs against expected 3D shapes via oxDNA.

Tests:
  1. Tube (6-helix, closed ring) — should have circular cross-section
  2. 2×3 grid (6 helices, 2 rows) — wider, thicker than single-row flat sheet
  3. Single-row long sheet (6-helix, 252bp) — aspect ratio should scale with length

Pipeline per shape:
  cadnano design → JSON → tacoxDNA → .oxdna coordinates → PCA fit → metrics

Usage:
  QT_QPA_PLATFORM=offscreen python tools/oxdna_shape_verify.py
"""

import os
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import json
import subprocess
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TACOX_DIR = os.path.join(os.path.dirname(PROJECT_ROOT), 'tacoxDNA')
TACOX_SCRIPT = os.path.join(TACOX_DIR, 'src', 'cadnano_oxDNA.py')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')
OXDNA_UNIT_NM = 0.8518


def _init_cadnano():
    """Initialize cadnano app and return (app, AgentMethods class)."""
    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()
    from cadnano2.views.agent.agentmethods import AgentMethods
    return app, AgentMethods


def _make_methods(app):
    """Create a fresh document and return (dc, methods)."""
    dc = list(app.documentControllers)[0]
    # Reset to a clean document (removes all parts and helices)
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
    methods = AgentMethods(mock)
    return dc, methods


def _save_and_convert(dc, work_dir, name):
    """Save cadnano JSON and convert to oxDNA. Returns (dat_path, top_path)."""
    os.makedirs(work_dir, exist_ok=True)
    json_path = os.path.join(work_dir, f'{name}.json')
    dc.writeDocumentToFile(json_path)

    cmd = [sys.executable, TACOX_SCRIPT, json_path, 'he']
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=work_dir)
    if result.returncode != 0:
        raise RuntimeError(f"tacoxDNA failed: {result.stderr}")

    # Find output files
    dat_path = top_path = None
    for f in os.listdir(work_dir):
        if f.endswith('.oxdna') or (f.endswith('.dat') and 'oxdna' not in f):
            dat_path = os.path.join(work_dir, f)
        if f.endswith('.top'):
            top_path = os.path.join(work_dir, f)

    if not dat_path or not top_path:
        raise FileNotFoundError(f"oxDNA output not found in {work_dir}")

    return dat_path, top_path


def parse_oxdna(dat_path, top_path):
    """Parse oxDNA files. Returns (coords, strands, n_strands)."""
    coords = []
    with open(dat_path) as f:
        for _ in range(3):
            next(f)
        for line in f:
            vals = line.split()
            if len(vals) >= 3:
                coords.append([float(vals[0]), float(vals[1]), float(vals[2])])
    coords = np.array(coords)

    strands = []
    with open(top_path) as f:
        header = next(f).split()
        n_strands = int(header[1])
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                strands.append(int(parts[0]))
    strands = np.array(strands)

    return coords, strands, n_strands


def analyze_shape(coords):
    """PCA-based shape analysis. Returns metrics dict."""
    from numpy.linalg import eigh

    centered = coords - coords.mean(axis=0)
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = eigh(cov)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]

    projected = centered @ eigenvectors
    pca_dims = (projected.max(axis=0) - projected.min(axis=0)) * OXDNA_UNIT_NM

    sorted_dims = np.sort(pca_dims)
    flatness = sorted_dims[0] / sorted_dims[2] if sorted_dims[2] > 0 else 0
    aspect = sorted_dims[2] / sorted_dims[1] if sorted_dims[1] > 0 else 0

    plane_dist = projected[:, 2] * OXDNA_UNIT_NM
    rms_planarity = np.sqrt(np.mean(plane_dist ** 2))

    # Cross-section analysis: project onto PC2-PC3 plane
    cross_section = projected[:, 1:3] * OXDNA_UNIT_NM
    cs_center = cross_section.mean(axis=0)
    radii = np.sqrt(((cross_section - cs_center) ** 2).sum(axis=1))
    mean_radius = radii.mean()
    std_radius = radii.std()
    circularity = 1.0 - (std_radius / mean_radius) if mean_radius > 0 else 0

    return {
        'n_nucleotides': len(coords),
        'pca_dims_nm': pca_dims.tolist(),
        'flatness_ratio': float(flatness),
        'aspect_ratio': float(aspect),
        'rms_planarity_nm': float(rms_planarity),
        'cross_section_circularity': float(circularity),
        'cross_section_mean_radius_nm': float(mean_radius),
        'eigenvalues': eigenvalues.tolist(),
        'projected': projected,
        'eigenvectors': eigenvectors,
    }


# ---- Shape generators ----

def create_tube(app, n_helices=6, length=126):
    """
    6-helix tube: helices arranged in a ring (hexagonal pattern).

    In honeycomb lattice, 6 helices forming a ring use positions that
    are all neighbors of each other in a hexagonal arrangement.
    """
    print(f"\n{'='*60}")
    print(f"  TUBE: {n_helices} helices x {length}bp")
    print(f"{'='*60}")

    dc, methods = _make_methods(app)

    # 6-helix tube: use honeycomb positions forming a hexagonal ring
    # Row 21: col 20, 21 (adjacent in row)
    # Row 22: col 20, 21 (adjacent in row, neighbors of row 21)
    # Row 20: col 20, 21 (adjacent in row, neighbors of row 21)
    # This gives a 3×2 block — a tube-like arrangement
    positions = [[20, 20], [20, 21],
                 [21, 20], [21, 21],
                 [22, 20], [22, 21]]

    result = methods.createHelicesWithStrands(positions=positions, strand_type="both", length=length)
    print(f"  Helices: {result}")

    xr = methods.addAllNeighborCrossovers("scaffold")
    print(f"  Scaffold xovers: {xr}")
    xr2 = methods.addAllNeighborCrossovers("staple")
    print(f"  Staple xovers: {xr2}")

    return dc, "tube"


def create_2x3_grid(app, length=126):
    """
    2×3 grid: 6 helices in 2 rows of 3.
    Should be wider and thicker than a single-row flat sheet.
    """
    print(f"\n{'='*60}")
    print(f"  2×3 GRID: 6 helices x {length}bp")
    print(f"{'='*60}")

    dc, methods = _make_methods(app)

    # 2 rows, 3 columns each
    positions = [[21, 20], [21, 21], [21, 22],
                 [22, 20], [22, 21], [22, 22]]

    result = methods.createHelicesWithStrands(positions=positions, strand_type="both", length=length)
    print(f"  Helices: {result}")

    xr = methods.addAllNeighborCrossovers("scaffold")
    print(f"  Scaffold xovers: {xr}")
    xr2 = methods.addAllNeighborCrossovers("staple")
    print(f"  Staple xovers: {xr2}")

    return dc, "grid_2x3"


def create_long_sheet(app, n_helices=6, length=252):
    """
    Long single-row flat sheet: same width as reference but 2× length.
    Aspect ratio should approximately double.
    """
    print(f"\n{'='*60}")
    print(f"  LONG SHEET: {n_helices} helices x {length}bp")
    print(f"{'='*60}")

    dc, methods = _make_methods(app)

    positions = [[21, 20 + i] for i in range(n_helices)]
    result = methods.createHelicesWithStrands(positions=positions, strand_type="both", length=length)
    print(f"  Helices: {result}")

    xr = methods.addAllNeighborCrossovers("scaffold")
    print(f"  Scaffold xovers: {xr}")
    xr2 = methods.addAllNeighborCrossovers("staple")
    print(f"  Staple xovers: {xr2}")

    return dc, "long_sheet"


def create_l_shape(app, length=126):
    """
    L-shape: 3 helices in a row + 2 helices extending downward from one end.
    Should show asymmetric cross-section (not flat, not circular).
    """
    print(f"\n{'='*60}")
    print(f"  L-SHAPE: 5 helices x {length}bp")
    print(f"{'='*60}")

    dc, methods = _make_methods(app)

    # Horizontal arm: row 21, cols 20-22 (3 helices)
    # Vertical arm: rows 22-23, col 20 (2 more helices below left end)
    positions = [[21, 20], [21, 21], [21, 22],
                 [22, 20],
                 [23, 20]]

    result = methods.createHelicesWithStrands(positions=positions, strand_type="both", length=length)
    print(f"  Helices: {result}")

    xr = methods.addAllNeighborCrossovers("scaffold")
    print(f"  Scaffold xovers: {xr}")
    xr2 = methods.addAllNeighborCrossovers("staple")
    print(f"  Staple xovers: {xr2}")

    return dc, "l_shape"


def create_wide_sheet(app, n_cols=10, length=126):
    """
    Wide single-row flat sheet: 10 helices.
    Should have much higher aspect ratio than 6-helix sheet.
    """
    print(f"\n{'='*60}")
    print(f"  WIDE SHEET: {n_cols} helices x {length}bp")
    print(f"{'='*60}")

    dc, methods = _make_methods(app)

    positions = [[21, 20 + i] for i in range(n_cols)]
    result = methods.createHelicesWithStrands(positions=positions, strand_type="both", length=length)
    print(f"  Helices: {result}")

    xr = methods.addAllNeighborCrossovers("scaffold")
    print(f"  Scaffold xovers: {xr}")
    xr2 = methods.addAllNeighborCrossovers("staple")
    print(f"  Staple xovers: {xr2}")

    return dc, "wide_sheet"


def generate_comparison_figure(all_results):
    """Generate a comparison figure across all shapes."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.patch.set_facecolor('#0f172a')

    for ax in axes.flat:
        ax.set_facecolor('#1e293b')
        ax.tick_params(colors='#e2e8f0')
        ax.xaxis.label.set_color('#e2e8f0')
        ax.yaxis.label.set_color('#e2e8f0')
        ax.title.set_color('#e2e8f0')
        for spine in ax.spines.values():
            spine.set_color('#334155')

    names = [r['name'] for r in all_results]
    colors = ['#8b5cf6', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#ec4899', '#a855f7']

    # Panel 1: PCA dimensions
    ax = axes[0, 0]
    x = np.arange(len(names))
    width = 0.25
    for i, (label, color) in enumerate(zip(['Length', 'Width', 'Thickness'],
                                            ['#8b5cf6', '#06b6d4', '#10b981'])):
        vals = [r['metrics']['pca_dims_nm'][i] for r in all_results]
        bars = ax.bar(x + i * width - width, vals, width, label=label, color=color, edgecolor='#475569')
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                    f'{v:.1f}', ha='center', va='bottom', color='#e2e8f0', fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=9)
    ax.set_ylabel('nm')
    ax.set_title('PCA Dimensions (Length / Width / Thickness)', fontweight='bold')
    ax.legend(fontsize=8, facecolor='#1e293b', edgecolor='#475569', labelcolor='#e2e8f0')

    # Panel 2: Flatness and circularity
    ax = axes[0, 1]
    flatness = [r['metrics']['flatness_ratio'] for r in all_results]
    circularity = [r['metrics']['cross_section_circularity'] for r in all_results]
    bars1 = ax.bar(x - 0.15, flatness, 0.3, label='Flatness ratio', color='#f59e0b', edgecolor='#475569')
    bars2 = ax.bar(x + 0.15, circularity, 0.3, label='Cross-section circularity', color='#ef4444', edgecolor='#475569')
    for bars in [bars1, bars2]:
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                    f'{bar.get_height():.3f}', ha='center', va='bottom', color='#e2e8f0', fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=9)
    ax.set_title('Shape Metrics', fontweight='bold')
    ax.legend(fontsize=8, facecolor='#1e293b', edgecolor='#475569', labelcolor='#e2e8f0')

    # Panel 3: RMS planarity
    ax = axes[1, 0]
    rms = [r['metrics']['rms_planarity_nm'] for r in all_results]
    bars = ax.bar(x, rms, 0.5, color=colors[:len(names)], edgecolor='#475569')
    for bar, v in zip(bars, rms):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                f'{v:.2f} nm', ha='center', va='bottom', color='#e2e8f0', fontsize=9, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=9)
    ax.set_ylabel('nm')
    ax.set_title('RMS Planarity (distance from best-fit plane)', fontweight='bold')
    ax.axhline(0.63, color='#94a3b8', linestyle='--', linewidth=0.8, alpha=0.5)
    ax.text(len(names) - 0.5, 0.63 + 0.05, 'ref: flat sheet (0.63 nm)', color='#94a3b8', fontsize=8, ha='right')

    # Panel 4: Cross-section scatter for each shape (PC2 vs PC3)
    ax = axes[1, 1]
    for i, r in enumerate(all_results):
        proj = r['metrics']['projected']
        cs = proj[:, 1:3] * OXDNA_UNIT_NM
        ax.scatter(cs[:, 0], cs[:, 1], s=1, alpha=0.4, color=colors[i], label=r['name'])
    ax.set_xlabel('PC2 (nm)')
    ax.set_ylabel('PC3 (nm)')
    ax.set_title('Cross-sections (PC2 vs PC3)', fontweight='bold')
    ax.set_aspect('equal')
    ax.legend(fontsize=8, facecolor='#1e293b', edgecolor='#475569', labelcolor='#e2e8f0', markerscale=5)

    fig.suptitle('oxDNA Shape Verification: Diverse Cadnano Geometries',
                 fontsize=14, fontweight='bold', color='#e2e8f0')
    plt.tight_layout(rect=[0, 0, 1, 0.95])

    path = os.path.join(RESULTS_DIR, 'obj-010-oxdna-shape-verification.png')
    plt.savefig(path, dpi=150, facecolor='#0f172a')
    plt.close()
    print(f"\n  Comparison figure: {path}")
    return path


def main():
    app, _ = _init_cadnano()

    # Reference: existing flat sheet from obj-007
    ref_work = os.path.join(RESULTS_DIR, 'oxdna_flat_sheet')

    shapes = [
        ("tube", create_tube),
        ("grid_2x3", create_2x3_grid),
        ("long_sheet", create_long_sheet),
        ("l_shape", create_l_shape),
        ("wide_sheet", create_wide_sheet),
    ]

    all_results = []

    # Include reference flat sheet if available
    ref_dat = os.path.join(ref_work, 'flat_sheet.json.oxdna')
    ref_top = os.path.join(ref_work, 'flat_sheet.json.top')
    if os.path.exists(ref_dat) and os.path.exists(ref_top):
        print("\nLoading reference flat sheet...")
        coords, strands, n_strands = parse_oxdna(ref_dat, ref_top)
        metrics = analyze_shape(coords)
        print(f"  Reference: {metrics['pca_dims_nm'][0]:.1f} x {metrics['pca_dims_nm'][1]:.1f} x {metrics['pca_dims_nm'][2]:.1f} nm")
        all_results.append({'name': 'flat_sheet\n(6×126)', 'metrics': metrics})

    for shape_name, creator_fn in shapes:
        work_dir = os.path.join(RESULTS_DIR, f'oxdna_{shape_name}')

        try:
            dc, name = creator_fn(app)
            dat_path, top_path = _save_and_convert(dc, work_dir, name)
            coords, strands, n_strands = parse_oxdna(dat_path, top_path)
            metrics = analyze_shape(coords)

            dims = metrics['pca_dims_nm']
            print(f"\n  {shape_name}: {dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} nm")
            print(f"  Flatness: {metrics['flatness_ratio']:.4f}, Circularity: {metrics['cross_section_circularity']:.4f}")
            print(f"  RMS planarity: {metrics['rms_planarity_nm']:.2f} nm")

            display_name = {
                'tube': 'tube\n(hex 6×126)',
                'grid_2x3': 'grid_2×3\n(6×126)',
                'long_sheet': 'long_sheet\n(6×252)',
                'l_shape': 'L-shape\n(5×126)',
                'wide_sheet': 'wide_sheet\n(10×126)',
            }.get(shape_name, shape_name)

            all_results.append({'name': display_name, 'metrics': metrics})

        except Exception as e:
            print(f"\n  ERROR on {shape_name}: {e}")
            import traceback
            traceback.print_exc()

    if len(all_results) >= 2:
        fig_path = generate_comparison_figure(all_results)

        # Save report
        report = {}
        for r in all_results:
            key = r['name'].replace('\n', ' ')
            m = {k: v for k, v in r['metrics'].items() if k not in ('projected', 'eigenvectors')}
            report[key] = m

        report_path = os.path.join(RESULTS_DIR, 'oxdna_shape_verify_report.json')
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n  Report: {report_path}")

    print(f"\n{'='*60}")
    print("  SHAPE VERIFICATION COMPLETE")
    print(f"{'='*60}")
    for r in all_results:
        m = r['metrics']
        dims = m['pca_dims_nm']
        print(f"  {r['name'].replace(chr(10), ' ')}: "
              f"{dims[0]:.1f}×{dims[1]:.1f}×{dims[2]:.1f} nm, "
              f"flat={m['flatness_ratio']:.3f}, circ={m['cross_section_circularity']:.3f}")


if __name__ == '__main__':
    main()
