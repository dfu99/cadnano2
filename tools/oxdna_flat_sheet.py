#!/usr/bin/env python
"""
Create a flat sheet rectangle in cadnano, convert to oxDNA, and measure
how well the 3D coordinates fit a rectilinear prism.

Pipeline:
  1. Create a 6-helix flat sheet in cadnano (headless)
  2. Export as cadnano JSON
  3. Convert to oxDNA format using tacoxDNA
  4. Parse 3D coordinates from .dat file
  5. Fit bounding box and rectilinear prism, compute planarity metrics
  6. Generate visualization figures

Usage:
  QT_QPA_PLATFORM=offscreen python -m tools.oxdna_flat_sheet
"""

import os
import sys

# CRITICAL: Must set before any Qt imports — do this FIRST
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import json
import subprocess
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TACOX_DIR = os.path.join(os.path.dirname(PROJECT_ROOT), 'tacoxDNA')
TACOX_SCRIPT = os.path.join(TACOX_DIR, 'src', 'cadnano_oxDNA.py')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')
WORK_DIR = os.path.join(PROJECT_ROOT, 'results', 'oxdna_flat_sheet')

OXDNA_UNIT_NM = 0.8518  # 1 oxDNA unit = 0.8518 nm


def create_flat_sheet_design(n_helices=6, length=126):
    """
    Create a flat sheet rectangle in cadnano and save as JSON.

    Uses a single row of helices in the honeycomb lattice.
    Scaffold routed as a serpentine path with crossovers.

    Returns path to the saved JSON file.
    """
    import cadnano2.cadnano as cadnano

    print(f"Creating {n_helices}-helix flat sheet ({length}bp)...")

    app = cadnano.initAppWithGui()

    # Import AgentMethods AFTER QApplication is created (requires Qt to be initialized)
    from cadnano2.views.agent.agentmethods import AgentMethods

    dc = list(app.documentControllers)[0]
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    class MockDC:
        def __init__(self, app, doc, part):
            self._app = app
            self._doc = doc
            self._part = part
        def document(self):
            return self._doc
        def activePart(self):
            return self._part
        def undoStack(self):
            return self._doc.undoStack()

    mock = MockDC(app, doc, part)
    methods = AgentMethods(mock)

    # Create a single row of helices (flat sheet)
    # Honeycomb lattice: row 21, columns 20, 21, 22, ...
    # Adjacent columns in same row are neighbors
    positions = [[21, 20 + i] for i in range(n_helices)]

    result = methods.createHelicesWithStrands(
        positions=positions,
        strand_type="both",
        length=length
    )
    print(f"  Created helices: {result}")

    # Add scaffold crossovers between all neighbor pairs
    xresult = methods.addAllNeighborCrossovers("scaffold")
    print(f"  Scaffold crossovers: {xresult}")

    # Add staple crossovers too
    xresult2 = methods.addAllNeighborCrossovers("staple")
    print(f"  Staple crossovers: {xresult2}")

    # Save the design as JSON using the encoder directly
    os.makedirs(WORK_DIR, exist_ok=True)
    json_path = os.path.join(WORK_DIR, 'flat_sheet.json')

    dc.writeDocumentToFile(json_path)
    print(f"  Saved: {json_path}")

    return json_path, app


def convert_to_oxdna(json_path):
    """Convert cadnano JSON to oxDNA format using tacoxDNA."""
    print(f"\nConverting to oxDNA...")

    if not os.path.exists(TACOX_SCRIPT):
        raise FileNotFoundError(f"tacoxDNA not found at {TACOX_SCRIPT}")

    # tacoxDNA outputs files in the current working directory
    cmd = [
        sys.executable, TACOX_SCRIPT,
        json_path,
        'he'  # hexagonal/honeycomb lattice
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=WORK_DIR
    )

    if result.returncode != 0:
        print(f"  STDERR: {result.stderr}")
        raise RuntimeError(f"tacoxDNA failed: {result.stderr}")

    print(f"  stdout: {result.stdout[:500]}")

    # Find output files
    dat_path = os.path.join(WORK_DIR, 'flat_sheet.oxdna')
    top_path = os.path.join(WORK_DIR, 'flat_sheet.top')

    # tacoxDNA may name them differently
    if not os.path.exists(dat_path):
        # Try alternative names
        for f in os.listdir(WORK_DIR):
            if f.endswith('.oxdna') or f.endswith('.dat'):
                dat_path = os.path.join(WORK_DIR, f)
            if f.endswith('.top'):
                top_path = os.path.join(WORK_DIR, f)

    print(f"  .dat: {dat_path} (exists: {os.path.exists(dat_path)})")
    print(f"  .top: {top_path} (exists: {os.path.exists(top_path)})")

    return dat_path, top_path


def parse_oxdna_dat(dat_path):
    """
    Parse oxDNA .dat file to extract 3D coordinates.

    Returns:
        coords: np.array shape (N, 3) — center-of-mass positions
        a1_vecs: np.array shape (N, 3) — base/backbone direction vectors
        a3_vecs: np.array shape (N, 3) — stacking/normal direction vectors
    """
    coords = []
    a1_vecs = []
    a3_vecs = []

    with open(dat_path) as f:
        # Skip 3 header lines (timestep, box, energy)
        for _ in range(3):
            header_line = next(f)
            print(f"  Header: {header_line.strip()}")

        for line in f:
            vals = line.split()
            if len(vals) >= 9:
                coords.append([float(vals[0]), float(vals[1]), float(vals[2])])
                a1_vecs.append([float(vals[3]), float(vals[4]), float(vals[5])])
                a3_vecs.append([float(vals[6]), float(vals[7]), float(vals[8])])

    coords = np.array(coords)
    a1_vecs = np.array(a1_vecs)
    a3_vecs = np.array(a3_vecs)

    print(f"\n  Parsed {len(coords)} nucleotides")
    print(f"  Coordinate range: X [{coords[:,0].min():.2f}, {coords[:,0].max():.2f}]")
    print(f"                    Y [{coords[:,1].min():.2f}, {coords[:,1].max():.2f}]")
    print(f"                    Z [{coords[:,2].min():.2f}, {coords[:,2].max():.2f}]")

    return coords, a1_vecs, a3_vecs


def parse_oxdna_top(top_path):
    """Parse oxDNA .top file to extract strand assignments."""
    strands = []
    bases = []

    with open(top_path) as f:
        header = next(f).split()
        n_nucleotides = int(header[0])
        n_strands = int(header[1])
        print(f"\n  Topology: {n_nucleotides} nucleotides, {n_strands} strands")

        for line in f:
            parts = line.split()
            if len(parts) >= 4:
                strands.append(int(parts[0]))
                bases.append(parts[1])

    return np.array(strands), bases


def fit_rectilinear_prism(coords):
    """
    Fit a rectilinear prism (axis-aligned bounding box) and a
    PCA-aligned bounding box to the coordinates.

    Returns metrics about how well the structure fits a flat sheet.
    """
    from numpy.linalg import eigh

    # 1. Axis-aligned bounding box
    aabb_min = coords.min(axis=0)
    aabb_max = coords.max(axis=0)
    aabb_dims = aabb_max - aabb_min
    aabb_dims_nm = aabb_dims * OXDNA_UNIT_NM

    print(f"\n  Axis-aligned bounding box (oxDNA units):")
    print(f"    X: {aabb_dims[0]:.2f}  Y: {aabb_dims[1]:.2f}  Z: {aabb_dims[2]:.2f}")
    print(f"  In nm:")
    print(f"    X: {aabb_dims_nm[0]:.1f}  Y: {aabb_dims_nm[1]:.1f}  Z: {aabb_dims_nm[2]:.1f}")

    # 2. PCA to find principal axes
    centered = coords - coords.mean(axis=0)
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = eigh(cov)

    # Sort by eigenvalue descending (largest spread first)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]

    # Project onto principal axes
    projected = centered @ eigenvectors
    pca_min = projected.min(axis=0)
    pca_max = projected.max(axis=0)
    pca_dims = pca_max - pca_min
    pca_dims_nm = pca_dims * OXDNA_UNIT_NM

    print(f"\n  PCA-aligned bounding box (oxDNA units):")
    print(f"    PC1: {pca_dims[0]:.2f}  PC2: {pca_dims[1]:.2f}  PC3: {pca_dims[2]:.2f}")
    print(f"  In nm:")
    print(f"    PC1: {pca_dims_nm[0]:.1f}  PC2: {pca_dims_nm[1]:.1f}  PC3: {pca_dims_nm[2]:.1f}")

    # 3. Flatness metric: ratio of smallest to largest dimension
    # A perfect flat sheet would have PC3 << PC1, PC2
    sorted_dims = np.sort(pca_dims)
    flatness_ratio = sorted_dims[0] / sorted_dims[2]  # thickness / length
    aspect_ratio = sorted_dims[2] / sorted_dims[1]  # length / width

    print(f"\n  Flatness ratio (thickness/length): {flatness_ratio:.4f}")
    print(f"  Aspect ratio (length/width): {aspect_ratio:.2f}")

    # 4. Planarity: RMS distance from best-fit plane
    # The best-fit plane is the plane spanned by PC1 and PC2
    # Distance from plane = projection onto PC3
    plane_distances = projected[:, 2]  # projection onto thinnest axis
    rms_planarity = np.sqrt(np.mean(plane_distances**2))
    rms_planarity_nm = rms_planarity * OXDNA_UNIT_NM

    print(f"  RMS planarity (dist from best-fit plane): {rms_planarity:.4f} oxDNA = {rms_planarity_nm:.2f} nm")

    # 5. Rectilinear prism fit: how much of the PCA bounding box is filled
    pca_volume = np.prod(pca_dims)
    # Convex hull volume approximation
    try:
        from scipy.spatial import ConvexHull
        hull = ConvexHull(coords)
        hull_volume = hull.volume
        fill_fraction = hull_volume / pca_volume if pca_volume > 0 else 0
        print(f"  Fill fraction (convex hull / PCA bbox): {fill_fraction:.3f}")
    except ImportError:
        hull_volume = None
        fill_fraction = None
        print(f"  (scipy not available for convex hull)")

    return {
        'aabb_dims_nm': aabb_dims_nm.tolist(),
        'pca_dims_nm': pca_dims_nm.tolist(),
        'flatness_ratio': float(flatness_ratio),
        'aspect_ratio': float(aspect_ratio),
        'rms_planarity_nm': float(rms_planarity_nm),
        'fill_fraction': float(fill_fraction) if fill_fraction else None,
        'eigenvalues': eigenvalues.tolist(),
        'eigenvectors': eigenvectors.tolist(),
        'n_nucleotides': len(coords),
    }


def generate_figures(coords, strands, metrics, a3_vecs):
    """Generate visualization figures."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D

    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Convert to nm
    coords_nm = coords * OXDNA_UNIT_NM

    # ---- Figure 1: 3D scatter colored by strand ----
    fig = plt.figure(figsize=(12, 5))

    # Left: 3D view
    ax1 = fig.add_subplot(121, projection='3d')
    unique_strands = np.unique(strands)
    colors = plt.cm.tab20(np.linspace(0, 1, len(unique_strands)))
    strand_color_map = {s: colors[i] for i, s in enumerate(unique_strands)}
    c = [strand_color_map[s] for s in strands]
    ax1.scatter(coords_nm[:, 0], coords_nm[:, 1], coords_nm[:, 2],
                c=c, s=1, alpha=0.6)
    ax1.set_xlabel('X (nm)')
    ax1.set_ylabel('Y (nm)')
    ax1.set_zlabel('Z (nm)')
    ax1.set_title(f'3D Structure ({len(coords)} nucleotides, {len(unique_strands)} strands)')

    # Right: top-down view (XY projection) to show flat sheet shape
    ax2 = fig.add_subplot(122)
    ax2.scatter(coords_nm[:, 0], coords_nm[:, 1], c=c, s=1, alpha=0.6)
    ax2.set_xlabel('X (nm)')
    ax2.set_ylabel('Y (nm)')
    ax2.set_title('Top-down view (XY projection)')
    ax2.set_aspect('equal')

    plt.tight_layout()
    path1 = os.path.join(RESULTS_DIR, 'oxdna_flat_sheet_3d.png')
    plt.savefig(path1, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {path1}")

    # ---- Figure 2: Planarity analysis ----
    # Shows the distribution of distances from the best-fit plane
    # and the PCA-aligned cross sections
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))

    # PCA projection
    centered = coords_nm - coords_nm.mean(axis=0)
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    order = np.argsort(eigenvalues)[::-1]
    eigenvectors = eigenvectors[:, order]
    projected = centered @ eigenvectors

    # PC1 vs PC2 (sheet plane)
    axes[0].scatter(projected[:, 0], projected[:, 1], c=c, s=1, alpha=0.5)
    axes[0].set_xlabel('PC1 (nm) — length')
    axes[0].set_ylabel('PC2 (nm) — width')
    axes[0].set_title('Sheet plane (PC1 vs PC2)')
    axes[0].set_aspect('equal')

    # PC1 vs PC3 (side view — shows thickness)
    axes[1].scatter(projected[:, 0], projected[:, 2], c=c, s=1, alpha=0.5)
    axes[1].set_xlabel('PC1 (nm) — length')
    axes[1].set_ylabel('PC3 (nm) — thickness')
    axes[1].set_title('Side view (PC1 vs PC3)')
    axes[1].set_aspect('equal')

    # Histogram of distances from best-fit plane
    axes[2].hist(projected[:, 2], bins=50, color='steelblue', edgecolor='black', linewidth=0.5)
    axes[2].axvline(0, color='red', linestyle='--', linewidth=1, label='Best-fit plane')
    rms = metrics['rms_planarity_nm']
    axes[2].axvline(rms, color='orange', linestyle=':', linewidth=1, label=f'RMS = {rms:.2f} nm')
    axes[2].axvline(-rms, color='orange', linestyle=':', linewidth=1)
    axes[2].set_xlabel('Distance from best-fit plane (nm)')
    axes[2].set_ylabel('Count')
    axes[2].set_title(f'Planarity distribution\nRMS = {rms:.2f} nm')
    axes[2].legend(fontsize=8)

    plt.tight_layout()
    path2 = os.path.join(RESULTS_DIR, 'oxdna_flat_sheet_planarity.png')
    plt.savefig(path2, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {path2}")

    # ---- Figure 3: Prism fit comparison ----
    fig, ax = plt.subplots(figsize=(8, 5))
    dims = metrics['pca_dims_nm']
    labels = ['PC1\n(length)', 'PC2\n(width)', 'PC3\n(thickness)']
    bars = ax.bar(labels, dims, color=['steelblue', 'coral', 'seagreen'],
                  edgecolor='black', linewidth=0.5)
    for bar, val in zip(bars, dims):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f'{val:.1f} nm', ha='center', va='bottom', fontsize=11)
    ax.set_ylabel('Dimension (nm)')
    ax.set_title(f'Rectilinear Prism Dimensions\n'
                 f'Flatness ratio = {metrics["flatness_ratio"]:.4f}, '
                 f'Aspect ratio = {metrics["aspect_ratio"]:.2f}')
    ax.set_ylim(0, max(dims) * 1.3)

    plt.tight_layout()
    path3 = os.path.join(RESULTS_DIR, 'oxdna_flat_sheet_prism_dims.png')
    plt.savefig(path3, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {path3}")

    return [path1, path2, path3]


def main():
    os.makedirs(WORK_DIR, exist_ok=True)

    # Step 1: Create the flat sheet design
    json_path, app = create_flat_sheet_design(n_helices=6, length=126)

    # Step 2: Convert to oxDNA
    dat_path, top_path = convert_to_oxdna(json_path)

    # Step 3: Parse coordinates
    print("\nParsing oxDNA coordinates...")
    coords, a1_vecs, a3_vecs = parse_oxdna_dat(dat_path)
    strands, bases = parse_oxdna_top(top_path)

    # Step 4: Fit rectilinear prism
    print("\nFitting rectilinear prism...")
    metrics = fit_rectilinear_prism(coords)

    # Step 5: Generate figures
    print("\nGenerating figures...")
    figure_paths = generate_figures(coords, strands, metrics, a3_vecs)

    # Step 6: Save report
    report = {
        'design': {
            'n_helices': 6,
            'length_bp': 126,
            'lattice': 'honeycomb',
        },
        'oxdna': {
            'n_nucleotides': int(metrics['n_nucleotides']),
            'n_strands': int(len(np.unique(strands))),
        },
        'prism_fit': metrics,
        'figures': figure_paths,
    }

    report_path = os.path.join(RESULTS_DIR, 'oxdna_flat_sheet_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report: {report_path}")

    # Print summary
    print(f"\n{'='*60}")
    print(f"  FLAT SHEET ANALYSIS SUMMARY")
    print(f"{'='*60}")
    print(f"  Design: 6 helices x 126bp (honeycomb lattice)")
    print(f"  Nucleotides: {metrics['n_nucleotides']}")
    print(f"  PCA dimensions: {metrics['pca_dims_nm'][0]:.1f} x "
          f"{metrics['pca_dims_nm'][1]:.1f} x "
          f"{metrics['pca_dims_nm'][2]:.1f} nm")
    print(f"  Flatness ratio: {metrics['flatness_ratio']:.4f} "
          f"(0 = perfectly flat, 1 = cube)")
    print(f"  RMS planarity: {metrics['rms_planarity_nm']:.2f} nm")
    if metrics['fill_fraction']:
        print(f"  Fill fraction: {metrics['fill_fraction']:.3f}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
