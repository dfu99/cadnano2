#!/usr/bin/env python
"""
Rectilinear prism fit analysis for oxDNA flat sheet structures.

Given a cadnano design converted to oxDNA format, this script answers:
  1. How well do the 3D nucleotide positions fill a rectangular prism?
  2. Where do nucleotides deviate from the ideal prism geometry?
  3. Is the cross-section uniform along the sheet length?

These answers map directly to a continuous geometric reward for the
training pipeline: a perfect flat sheet should have nucleotides that
uniformly fill a thin rectangular slab.

Reads existing oxDNA files from results/oxdna_flat_sheet/.
Outputs figures and report to results/oxdna_flat_sheet/.

Usage:
  python -m tools.oxdna_prism_fit
"""

import json
import os
import sys

import numpy as np
from numpy.linalg import eigh

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK_DIR = os.path.join(PROJECT_ROOT, 'results', 'oxdna_flat_sheet')
OXDNA_UNIT_NM = 0.8518  # 1 oxDNA unit = 0.8518 nm


def parse_oxdna(dat_path, top_path):
    """Parse oxDNA configuration and topology files."""
    # Parse coordinates
    coords = []
    with open(dat_path) as f:
        for _ in range(3):
            next(f)  # skip header
        for line in f:
            vals = line.split()
            if len(vals) >= 9:
                coords.append([float(vals[0]), float(vals[1]), float(vals[2])])

    coords = np.array(coords) * OXDNA_UNIT_NM  # convert to nm immediately

    # Parse topology (strand assignments)
    strand_ids = []
    with open(top_path) as f:
        header = next(f).split()
        n_nuc, n_strands = int(header[0]), int(header[1])
        for line in f:
            parts = line.split()
            if len(parts) >= 4:
                strand_ids.append(int(parts[0]))

    strand_ids = np.array(strand_ids)
    return coords, strand_ids, n_strands


def pca_align(coords):
    """
    Align coordinates to principal axes.
    Returns: aligned coords, eigenvectors, eigenvalues, center.
    PC1 = length (longest), PC2 = width, PC3 = thickness (shortest).
    """
    center = coords.mean(axis=0)
    centered = coords - center
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = eigh(cov)

    # Sort descending: PC1 = most variance = length
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]

    aligned = centered @ eigenvectors
    return aligned, eigenvectors, eigenvalues, center


def fit_prism(aligned):
    """
    Fit an oriented bounding box (rectilinear prism) to PCA-aligned coordinates.

    Returns dict with:
      - dims: [length, width, thickness] in nm
      - min/max along each axis
      - per-nucleotide fractional coordinates (0-1 within prism)
    """
    mins = aligned.min(axis=0)
    maxs = aligned.max(axis=0)
    dims = maxs - mins

    # Fractional coordinates: where each nucleotide sits within the prism [0, 1]
    frac = (aligned - mins) / dims

    return {
        'dims': dims,
        'mins': mins,
        'maxs': maxs,
        'frac': frac,
    }


def compute_prism_metrics(aligned, prism):
    """
    Compute how well the nucleotides fill the rectilinear prism.

    Key metrics:
      - uniformity: how evenly nucleotides distribute within the prism
        (1.0 = perfectly uniform, 0.0 = all clustered in one spot)
      - surface_distance_rms: RMS distance of each point to nearest prism face
        (lower = points closer to surface = hollow; higher = more filled)
      - slice_consistency: how similar the cross-section is at different
        positions along the length axis
      - rectangularity: how rectangular the cross-section is (vs. circular
        or irregular)
    """
    dims = prism['dims']
    frac = prism['frac']
    N = len(aligned)

    # --- Uniformity via 3D grid occupancy ---
    # Divide prism into cells. For a flat sheet, most variance is in
    # length and width; thickness has very few cells.
    n_bins_length = max(2, int(np.ceil(dims[0] / 2.0)))  # ~2nm bins
    n_bins_width = max(2, int(np.ceil(dims[1] / 2.0)))
    n_bins_thick = max(2, int(np.ceil(dims[2] / 1.0)))   # ~1nm bins for thin axis
    n_total_bins = n_bins_length * n_bins_width * n_bins_thick

    # Bin each nucleotide
    bin_idx = np.zeros(N, dtype=int)
    for i in range(N):
        bl = min(int(frac[i, 0] * n_bins_length), n_bins_length - 1)
        bw = min(int(frac[i, 1] * n_bins_width), n_bins_width - 1)
        bt = min(int(frac[i, 2] * n_bins_thick), n_bins_thick - 1)
        bin_idx[i] = bl * n_bins_width * n_bins_thick + bw * n_bins_thick + bt

    occupied = len(np.unique(bin_idx))
    uniformity = occupied / n_total_bins

    # --- Distance to nearest prism face ---
    # For each point, distance to the nearest of the 6 faces
    face_dists = np.zeros(N)
    for i in range(N):
        d_faces = []
        for ax in range(3):
            d_faces.append(aligned[i, ax] - prism['mins'][ax])  # dist to min face
            d_faces.append(prism['maxs'][ax] - aligned[i, ax])  # dist to max face
        face_dists[i] = min(d_faces)

    surface_distance_rms = np.sqrt(np.mean(face_dists**2))
    surface_distance_mean = np.mean(face_dists)

    # --- Slice consistency along length axis ---
    # Divide into slices along PC1 and measure cross-section spread in PC2/PC3
    n_slices = 10
    slice_edges = np.linspace(prism['mins'][0], prism['maxs'][0], n_slices + 1)
    slice_widths = []
    slice_thicknesses = []
    slice_counts = []

    for s in range(n_slices):
        mask = (aligned[:, 0] >= slice_edges[s]) & (aligned[:, 0] < slice_edges[s + 1])
        if mask.sum() < 3:
            continue
        sl = aligned[mask]
        slice_widths.append(sl[:, 1].max() - sl[:, 1].min())
        slice_thicknesses.append(sl[:, 2].max() - sl[:, 2].min())
        slice_counts.append(mask.sum())

    slice_widths = np.array(slice_widths)
    slice_thicknesses = np.array(slice_thicknesses)
    slice_counts = np.array(slice_counts)

    # Coefficient of variation of slice widths (lower = more consistent)
    width_cv = np.std(slice_widths) / np.mean(slice_widths) if len(slice_widths) > 1 else 0
    thick_cv = np.std(slice_thicknesses) / np.mean(slice_thicknesses) if len(slice_thicknesses) > 1 else 0

    # --- Rectangularity of cross-section ---
    # Project onto PC2-PC3 plane, compute convex hull area / bounding rect area
    from scipy.spatial import ConvexHull
    cross_section = aligned[:, 1:3]  # PC2-PC3
    hull = ConvexHull(cross_section)
    hull_area = hull.volume  # In 2D, ConvexHull.volume = area
    rect_area = dims[1] * dims[2]
    rectangularity = hull_area / rect_area if rect_area > 0 else 0

    # --- Composite prism fit score ---
    # Combines uniformity, slice consistency, and rectangularity
    # Higher = better fit to rectilinear prism
    consistency_score = 1.0 - min(width_cv, 1.0)
    prism_fit_score = (
        0.4 * uniformity +
        0.3 * rectangularity +
        0.3 * consistency_score
    )

    return {
        'prism_dims_nm': dims.tolist(),
        'uniformity': float(uniformity),
        'grid_bins': [n_bins_length, n_bins_width, n_bins_thick],
        'occupied_bins': int(occupied),
        'total_bins': int(n_total_bins),
        'surface_distance_rms_nm': float(surface_distance_rms),
        'surface_distance_mean_nm': float(surface_distance_mean),
        'slice_width_mean_nm': float(np.mean(slice_widths)),
        'slice_width_cv': float(width_cv),
        'slice_thickness_mean_nm': float(np.mean(slice_thicknesses)),
        'slice_thickness_cv': float(thick_cv),
        'slice_counts': slice_counts.tolist(),
        'rectangularity': float(rectangularity),
        'prism_fit_score': float(prism_fit_score),
        'n_slices': int(n_slices),
        'flatness_ratio': float(dims[2] / dims[0]),
        'aspect_ratio': float(dims[0] / dims[1]),
    }


def generate_figures(aligned, strand_ids, prism, metrics):
    """
    Generate 3 purposeful figures.

    Fig 1 — Prism wireframe overlay on 3D structure
      Objective: Visually verify the oriented bounding box captures the
      structure. Shows whether the prism is tight-fitting or has dead space.

    Fig 2 — Cross-sectional slices along the sheet length
      Objective: Reveal whether the sheet maintains uniform rectangular
      cross-section or warps/narrows at the ends. This is the key
      diagnostic for structural integrity.

    Fig 3 — Nucleotide density heatmap within the prism
      Objective: Show how uniformly nucleotides fill the prism volume.
      Dense clusters vs. voids indicate where the design departs from
      the intended geometry. Directly maps to the training reward.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

    figure_paths = []
    dims = prism['dims']
    mins = prism['mins']
    maxs = prism['maxs']

    # ================================================================
    # Fig 1: 3D structure with rectilinear prism wireframe
    # ================================================================
    fig = plt.figure(figsize=(10, 7))
    ax = fig.add_subplot(111, projection='3d')

    # Plot nucleotides colored by helix (strand)
    unique_strands = np.unique(strand_ids)
    # Find the scaffold (strand 1, usually the longest)
    strand_counts = {s: (strand_ids == s).sum() for s in unique_strands}
    scaffold_id = max(strand_counts, key=strand_counts.get)

    scaffold_mask = strand_ids == scaffold_id
    staple_mask = ~scaffold_mask

    ax.scatter(aligned[scaffold_mask, 0], aligned[scaffold_mask, 1],
               aligned[scaffold_mask, 2], c='royalblue', s=2, alpha=0.4,
               label=f'Scaffold ({scaffold_mask.sum()} nt)')
    ax.scatter(aligned[staple_mask, 0], aligned[staple_mask, 1],
               aligned[staple_mask, 2], c='tomato', s=2, alpha=0.3,
               label=f'Staples ({staple_mask.sum()} nt)')

    # Draw prism wireframe
    # 8 corners of the bounding box
    corners = np.array([
        [mins[0], mins[1], mins[2]],
        [maxs[0], mins[1], mins[2]],
        [maxs[0], maxs[1], mins[2]],
        [mins[0], maxs[1], mins[2]],
        [mins[0], mins[1], maxs[2]],
        [maxs[0], mins[1], maxs[2]],
        [maxs[0], maxs[1], maxs[2]],
        [mins[0], maxs[1], maxs[2]],
    ])
    # 12 edges
    edges = [
        [0, 1], [1, 2], [2, 3], [3, 0],  # bottom face
        [4, 5], [5, 6], [6, 7], [7, 4],  # top face
        [0, 4], [1, 5], [2, 6], [3, 7],  # verticals
    ]
    edge_lines = [[corners[e[0]], corners[e[1]]] for e in edges]
    lc = Line3DCollection(edge_lines, colors='black', linewidths=1.2,
                          linestyles='--', alpha=0.7)
    ax.add_collection3d(lc)

    # Semi-transparent faces for the prism
    faces = [
        [corners[0], corners[1], corners[5], corners[4]],  # front
        [corners[2], corners[3], corners[7], corners[6]],  # back
        [corners[0], corners[3], corners[7], corners[4]],  # left
        [corners[1], corners[2], corners[6], corners[5]],  # right
        [corners[0], corners[1], corners[2], corners[3]],  # bottom
        [corners[4], corners[5], corners[6], corners[7]],  # top
    ]
    face_coll = Poly3DCollection(faces, alpha=0.05, facecolor='gray',
                                  edgecolor='none')
    ax.add_collection3d(face_coll)

    ax.set_xlabel('PC1 — length (nm)')
    ax.set_ylabel('PC2 — width (nm)')
    ax.set_zlabel('PC3 — thickness (nm)')
    ax.legend(loc='upper right', fontsize=8, markerscale=3)

    # Annotate dimensions
    ax.set_title(
        f'Flat sheet in rectilinear prism: '
        f'{dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f} nm\n'
        f'Prism fit score = {metrics["prism_fit_score"]:.3f}   '
        f'Rectangularity = {metrics["rectangularity"]:.3f}',
        fontsize=11
    )

    # Set equal-ish aspect by padding the thin axis
    max_range = max(dims) / 2
    mid = [(mins[i] + maxs[i]) / 2 for i in range(3)]
    ax.set_xlim(mid[0] - max_range * 1.1, mid[0] + max_range * 1.1)
    ax.set_ylim(mid[1] - max_range * 0.3, mid[1] + max_range * 0.3)
    ax.set_zlim(mid[2] - max_range * 0.3, mid[2] + max_range * 0.3)

    # Good viewing angle for a flat sheet
    ax.view_init(elev=25, azim=-60)

    plt.tight_layout()
    path = os.path.join(WORK_DIR, 'fig1_prism_wireframe.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    figure_paths.append(path)
    print(f"  Saved: {path}")

    # ================================================================
    # Fig 2: Cross-sectional slices along the sheet length
    # ================================================================
    n_slices = 5
    slice_edges = np.linspace(mins[0], maxs[0], n_slices + 1)

    fig, axes = plt.subplots(1, n_slices, figsize=(3 * n_slices, 3.5),
                              sharey=True)
    fig.suptitle(
        'Cross-sectional slices along sheet length (PC1)\n'
        'Objective: verify uniform rectangular cross-section',
        fontsize=11, y=1.02
    )

    for s in range(n_slices):
        ax = axes[s]
        mask = (aligned[:, 0] >= slice_edges[s]) & (aligned[:, 0] < slice_edges[s + 1])
        sl = aligned[mask]

        if len(sl) < 2:
            ax.set_title(f'Slice {s+1}\n(empty)')
            continue

        # Color by scaffold vs staple
        sl_scaffold = scaffold_mask[np.where(mask)[0]] if mask.sum() > 0 else []
        colors = ['royalblue' if sc else 'tomato'
                  for sc in (strand_ids[mask] == scaffold_id)]

        ax.scatter(sl[:, 1], sl[:, 2], c=colors, s=8, alpha=0.6)

        # Draw the expected prism cross-section
        rect = plt.Rectangle(
            (mins[1], mins[2]), dims[1], dims[2],
            fill=False, edgecolor='black', linestyle='--', linewidth=1
        )
        ax.add_patch(rect)

        # Annotate width/thickness of this slice
        w = sl[:, 1].max() - sl[:, 1].min()
        t = sl[:, 2].max() - sl[:, 2].min()
        pos_start = slice_edges[s]
        pos_end = slice_edges[s + 1]
        ax.set_title(
            f'{pos_start:.0f}–{pos_end:.0f} nm\n'
            f'{len(sl)} nt, {w:.1f}×{t:.1f} nm',
            fontsize=9
        )
        ax.set_xlabel('PC2 — width (nm)', fontsize=8)
        if s == 0:
            ax.set_ylabel('PC3 — thickness (nm)', fontsize=8)
        ax.set_aspect('equal')
        # Pad to show prism boundary
        ax.set_xlim(mins[1] - 1, maxs[1] + 1)
        ax.set_ylim(mins[2] - 1, maxs[2] + 1)

    plt.tight_layout()
    path = os.path.join(WORK_DIR, 'fig2_cross_sections.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    figure_paths.append(path)
    print(f"  Saved: {path}")

    # ================================================================
    # Fig 3: Nucleotide density heatmap — how uniformly is the prism filled?
    # ================================================================
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    fig.suptitle(
        'Nucleotide density within the rectilinear prism\n'
        'Objective: identify voids and clusters that reduce the prism fit score',
        fontsize=11, y=1.02
    )

    # Panel A: Length vs Width heatmap (top-down density)
    ax = axes[0]
    h, xedges, yedges = np.histogram2d(
        aligned[:, 0], aligned[:, 1],
        bins=[20, max(5, int(dims[1] / 1.5))],
        range=[[mins[0], maxs[0]], [mins[1], maxs[1]]]
    )
    im = ax.imshow(
        h.T, origin='lower', aspect='auto',
        extent=[mins[0], maxs[0], mins[1], maxs[1]],
        cmap='YlOrRd', interpolation='nearest'
    )
    ax.set_xlabel('PC1 — length (nm)')
    ax.set_ylabel('PC2 — width (nm)')
    ax.set_title('Top-down density\n(length × width)')
    plt.colorbar(im, ax=ax, label='Nucleotide count', shrink=0.8)

    # Panel B: Length vs Thickness heatmap (side-view density)
    ax = axes[1]
    h, xedges, yedges = np.histogram2d(
        aligned[:, 0], aligned[:, 2],
        bins=[20, max(3, int(dims[2] / 0.5))],
        range=[[mins[0], maxs[0]], [mins[2], maxs[2]]]
    )
    im = ax.imshow(
        h.T, origin='lower', aspect='auto',
        extent=[mins[0], maxs[0], mins[2], maxs[2]],
        cmap='YlOrRd', interpolation='nearest'
    )
    ax.set_xlabel('PC1 — length (nm)')
    ax.set_ylabel('PC3 — thickness (nm)')
    ax.set_title('Side-view density\n(length × thickness)')
    plt.colorbar(im, ax=ax, label='Nucleotide count', shrink=0.8)

    # Panel C: Width vs Thickness heatmap (end-on cross-section density)
    ax = axes[2]
    h, xedges, yedges = np.histogram2d(
        aligned[:, 1], aligned[:, 2],
        bins=[max(5, int(dims[1] / 1.5)), max(3, int(dims[2] / 0.5))],
        range=[[mins[1], maxs[1]], [mins[2], maxs[2]]]
    )
    im = ax.imshow(
        h.T, origin='lower', aspect='auto',
        extent=[mins[1], maxs[1], mins[2], maxs[2]],
        cmap='YlOrRd', interpolation='nearest'
    )
    ax.set_xlabel('PC2 — width (nm)')
    ax.set_ylabel('PC3 — thickness (nm)')
    ax.set_title('End-on density\n(width × thickness)')
    plt.colorbar(im, ax=ax, label='Nucleotide count', shrink=0.8)

    # Draw prism boundary on each panel
    for i, ax in enumerate(axes):
        ax.tick_params(labelsize=8)

    plt.tight_layout()
    path = os.path.join(WORK_DIR, 'fig3_density_heatmap.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    figure_paths.append(path)
    print(f"  Saved: {path}")

    return figure_paths


def main():
    # Load existing oxDNA files
    dat_path = os.path.join(WORK_DIR, 'flat_sheet.json.oxdna')
    top_path = os.path.join(WORK_DIR, 'flat_sheet.json.top')

    if not os.path.exists(dat_path):
        print(f"ERROR: oxDNA file not found: {dat_path}")
        print("Run 'python -m tools.oxdna_flat_sheet' first to generate it.")
        sys.exit(1)

    print("=" * 60)
    print("  RECTILINEAR PRISM FIT ANALYSIS")
    print("=" * 60)

    # Parse
    print("\n1. Parsing oxDNA files...")
    coords, strand_ids, n_strands = parse_oxdna(dat_path, top_path)
    print(f"   {len(coords)} nucleotides, {n_strands} strands")

    # PCA align
    print("\n2. PCA alignment...")
    aligned, eigvecs, eigvals, center = pca_align(coords)
    print(f"   Eigenvalues: {eigvals[0]:.1f}, {eigvals[1]:.1f}, {eigvals[2]:.3f}")
    print(f"   Variance explained: "
          f"{eigvals[0]/sum(eigvals)*100:.1f}%, "
          f"{eigvals[1]/sum(eigvals)*100:.1f}%, "
          f"{eigvals[2]/sum(eigvals)*100:.1f}%")

    # Fit prism
    print("\n3. Fitting rectilinear prism...")
    prism = fit_prism(aligned)
    dims = prism['dims']
    print(f"   Prism dimensions: {dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f} nm")
    print(f"   Volume: {np.prod(dims):.1f} nm³")

    # Compute metrics
    print("\n4. Computing prism fit metrics...")
    metrics = compute_prism_metrics(aligned, prism)
    print(f"   Flatness ratio:       {metrics['flatness_ratio']:.4f} (thickness/length)")
    print(f"   Aspect ratio:         {metrics['aspect_ratio']:.2f} (length/width)")
    print(f"   Uniformity:           {metrics['uniformity']:.3f} ({metrics['occupied_bins']}/{metrics['total_bins']} bins)")
    print(f"   Rectangularity:       {metrics['rectangularity']:.3f} (hull area / rect area)")
    print(f"   Slice width CV:       {metrics['slice_width_cv']:.4f} (lower = more uniform)")
    print(f"   Slice thickness CV:   {metrics['slice_thickness_cv']:.4f}")
    print(f"   Surface dist RMS:     {metrics['surface_distance_rms_nm']:.2f} nm")
    print(f"   PRISM FIT SCORE:      {metrics['prism_fit_score']:.3f}")

    # Generate figures
    print("\n5. Generating figures...")
    figure_paths = generate_figures(aligned, strand_ids, prism, metrics)

    # Save report
    report = {
        'description': (
            'Rectilinear prism fit analysis for a 6-helix flat sheet DNA origami. '
            'The design was created in cadnano (honeycomb lattice), converted to '
            'oxDNA format via tacoxDNA, and the 3D nucleotide positions were analyzed '
            'to quantify how well the structure fills a rectangular prism. This metric '
            'serves as a continuous geometric reward signal for the training pipeline.'
        ),
        'design': {
            'n_helices': 6,
            'length_bp': 126,
            'lattice': 'honeycomb',
            'converter': 'tacoxDNA (cadnano_oxDNA.py, lattice=he)',
        },
        'structure': {
            'n_nucleotides': int(len(coords)),
            'n_strands': int(n_strands),
            'center_of_mass_nm': center.tolist(),
        },
        'pca': {
            'eigenvalues': eigvals.tolist(),
            'variance_explained_pct': (eigvals / eigvals.sum() * 100).tolist(),
            'note': 'PC1=length, PC2=width, PC3=thickness (sorted by descending variance)',
        },
        'prism': {
            'dimensions_nm': dims.tolist(),
            'volume_nm3': float(np.prod(dims)),
            'flatness_ratio': metrics['flatness_ratio'],
            'aspect_ratio': metrics['aspect_ratio'],
        },
        'quality_metrics': {
            'prism_fit_score': metrics['prism_fit_score'],
            'uniformity': metrics['uniformity'],
            'rectangularity': metrics['rectangularity'],
            'slice_width_cv': metrics['slice_width_cv'],
            'slice_thickness_cv': metrics['slice_thickness_cv'],
            'surface_distance_rms_nm': metrics['surface_distance_rms_nm'],
        },
        'interpretation': {
            'prism_fit_score': (
                f'{metrics["prism_fit_score"]:.3f} — composite score (0-1) combining '
                f'uniformity ({metrics["uniformity"]:.3f}), rectangularity '
                f'({metrics["rectangularity"]:.3f}), and slice consistency '
                f'({1.0 - min(metrics["slice_width_cv"], 1.0):.3f}). '
                'Higher = better fit to a rectangular prism.'
            ),
            'flatness': (
                f'Thickness/length = {metrics["flatness_ratio"]:.4f}. '
                f'The structure is {1/metrics["flatness_ratio"]:.0f}× longer than '
                f'it is thick, confirming a flat sheet geometry.'
            ),
            'uniformity': (
                f'{metrics["occupied_bins"]}/{metrics["total_bins"]} grid cells occupied. '
                'Values near 1.0 indicate nucleotides fill the prism volume evenly '
                'rather than clustering at helix positions.'
            ),
            'cross_section': (
                f'Width CV = {metrics["slice_width_cv"]:.4f}, '
                f'Thickness CV = {metrics["slice_thickness_cv"]:.4f}. '
                'Low CV means the cross-section shape is consistent along '
                'the sheet length — no tapering or warping at the ends.'
            ),
        },
        'figures': {
            'fig1_prism_wireframe': {
                'path': figure_paths[0],
                'objective': 'Visually verify the oriented bounding box captures the structure tightly.',
            },
            'fig2_cross_sections': {
                'path': figure_paths[1],
                'objective': 'Show whether cross-section shape is uniform along the sheet length.',
            },
            'fig3_density_heatmap': {
                'path': figure_paths[2],
                'objective': 'Identify voids and clusters within the prism volume.',
            },
        },
        'training_integration': {
            'reward_signal': (
                'prism_fit_score can be used directly as a geometric reward (0-1). '
                'It complements the existing connectivity-based reward from DesignVerifier. '
                'A correct flat sheet should score >0.7; a disconnected or misshapen '
                'structure will score lower.'
            ),
            'pipeline': [
                '1. Agent creates cadnano design via AgentMethods',
                '2. Design exported as JSON',
                '3. tacoxDNA converts JSON → oxDNA (.oxdna + .top)',
                '4. This script computes prism_fit_score from 3D coordinates',
                '5. Score fed back as shaped reward for RLVR training',
            ],
        },
    }

    report_path = os.path.join(WORK_DIR, 'prism_fit_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n   Report: {report_path}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  RESULTS SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Prism:  {dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f} nm")
    print(f"  Score:  {metrics['prism_fit_score']:.3f}")
    print(f"  The structure is {1/metrics['flatness_ratio']:.0f}× longer than thick")
    print(f"  Cross-section uniformity (width CV): {metrics['slice_width_cv']:.4f}")
    print(f"  Figures: {len(figure_paths)} saved to {WORK_DIR}/")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
