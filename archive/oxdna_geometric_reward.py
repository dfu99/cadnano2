#!/usr/bin/env python
"""
Geometric reward scorer: cadnano → oxDNA → 3D shape verification → reward signal.

Integrates tacoxDNA conversion with PCA-based shape analysis to produce a
continuous reward signal (0-1) for the RLVR training pipeline. This lets the
agent learn not just structural correctness (crossovers, strand connectivity)
but also geometric correctness (does the design form the intended 3D shape?).

Key idea: cadnano's 2D lattice view does not reveal 3D geometry. A design
can look correct in 2D but have wrong 3D shape (e.g., missing crossovers
cause a flat sheet to curl into a tube). The oxDNA conversion produces
coarse-grained 3D coordinates that let us measure actual geometry.

Target shapes:
  - "flat_sheet": thin, planar rectangle (flatness < 0.1, planarity < 1.0 nm)
  - "tube": cylindrical cross-section (circularity > 0.5)
  - "grid": near-square cross-section (circularity > 0.7)

Usage:
  QT_QPA_PLATFORM=offscreen python -m tools.oxdna_geometric_reward
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
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results', 'oxdna_geometric_reward')
OXDNA_UNIT_NM = 0.8518


# ---------------------------------------------------------------------------
# Core geometric analysis
# ---------------------------------------------------------------------------

def convert_cadnano_to_oxdna(json_path, work_dir):
    """Convert cadnano JSON → oxDNA via tacoxDNA. Returns (dat_path, top_path)."""
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
    """Parse oxDNA .dat file → (N, 3) coordinate array."""
    coords = []
    with open(dat_path) as f:
        for _ in range(3):
            next(f)  # skip header
        for line in f:
            vals = line.split()
            if len(vals) >= 3:
                coords.append([float(vals[0]), float(vals[1]), float(vals[2])])
    return np.array(coords)


def parse_oxdna_topology(top_path):
    """Parse oxDNA .top file → (strand_ids, n_strands)."""
    with open(top_path) as f:
        header = next(f).split()
        n_nucleotides, n_strands = int(header[0]), int(header[1])
        strand_ids = []
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                strand_ids.append(int(parts[0]))
    return np.array(strand_ids), n_strands


def pca_shape_analysis(coords):
    """
    PCA-based shape analysis on oxDNA coordinates.

    Returns dict with:
      - pca_dims_nm: [length, width, thickness] in nm
      - flatness_ratio: thickness/length (0=flat, 1=cube)
      - rms_planarity_nm: RMS distance from best-fit plane
      - cross_section_circularity: 1=circular, 0=elongated
      - projected: PCA-projected coordinates (for plotting)
    """
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

    # Cross-section circularity
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
    }


# ---------------------------------------------------------------------------
# Geometric reward functions
# ---------------------------------------------------------------------------

def reward_flat_sheet(metrics):
    """
    Reward for flat sheet target shape.

    A perfect flat sheet has:
      - Very low flatness ratio (thickness/length ≈ 0.05-0.06)
      - Low planarity RMS (< 1.0 nm, ideally ~0.63 nm for 6-helix)
      - Low cross-section circularity (elongated, not round)

    Returns (reward, breakdown) where reward ∈ [0, 1].
    """
    flatness = metrics['flatness_ratio']
    planarity = metrics['rms_planarity_nm']
    circularity = metrics['cross_section_circularity']

    # Flatness score: ideal ~0.06, penalty above 0.15
    # Uses sigmoid-like scoring: 1.0 at flatness=0.06, drops to 0 at flatness=0.3
    flatness_score = np.clip(1.0 - (flatness - 0.06) / 0.24, 0, 1)

    # Planarity score: ideal ~0.63 nm, penalty above 1.5 nm
    planarity_score = np.clip(1.0 - (planarity - 0.63) / 1.5, 0, 1)

    # Circularity penalty: flat sheets should NOT be circular (want < 0.5)
    # circularity > 0.6 means it's becoming tube-like
    circ_score = np.clip(1.0 - (circularity - 0.4) / 0.4, 0, 1)

    # Weighted combination
    reward = 0.4 * flatness_score + 0.35 * planarity_score + 0.25 * circ_score

    breakdown = {
        'flatness_score': float(flatness_score),
        'planarity_score': float(planarity_score),
        'circularity_score': float(circ_score),
        'total_reward': float(reward),
        'raw_flatness': float(flatness),
        'raw_planarity': float(planarity),
        'raw_circularity': float(circularity),
    }
    return float(reward), breakdown


def reward_tube(metrics):
    """
    Reward for tube/cylinder target shape.

    A good tube has:
      - Higher circularity (> 0.5, ideally > 0.55)
      - Moderate flatness (not as flat as a sheet)
    """
    circularity = metrics['cross_section_circularity']
    flatness = metrics['flatness_ratio']

    # Circularity score: want > 0.5
    circ_score = np.clip((circularity - 0.3) / 0.4, 0, 1)

    # Flatness score: tubes should NOT be very flat (want > 0.07)
    flat_score = np.clip((flatness - 0.03) / 0.07, 0, 1)

    reward = 0.6 * circ_score + 0.4 * flat_score

    breakdown = {
        'circularity_score': float(circ_score),
        'flatness_score': float(flat_score),
        'total_reward': float(reward),
        'raw_circularity': float(circularity),
        'raw_flatness': float(flatness),
    }
    return float(reward), breakdown


def compute_geometric_reward(json_path, target_shape="flat_sheet", work_dir=None):
    """
    End-to-end geometric reward: cadnano JSON → oxDNA → PCA → reward.

    Args:
        json_path: Path to cadnano JSON file
        target_shape: "flat_sheet", "tube", or "grid"
        work_dir: Directory for intermediate files (temp if None)

    Returns:
        (reward, metrics, breakdown) where reward ∈ [0, 1]
    """
    cleanup = False
    if work_dir is None:
        work_dir = tempfile.mkdtemp(prefix='oxdna_reward_')
        cleanup = True

    try:
        # Copy JSON to work dir if not already there
        json_basename = os.path.basename(json_path)
        work_json = os.path.join(work_dir, json_basename)
        if os.path.abspath(json_path) != os.path.abspath(work_json):
            shutil.copy2(json_path, work_json)

        # Convert
        dat_path, top_path = convert_cadnano_to_oxdna(work_json, work_dir)

        # Parse
        coords = parse_oxdna_coordinates(dat_path)
        strand_ids, n_strands = parse_oxdna_topology(top_path)

        if len(coords) == 0:
            return 0.0, {}, {'error': 'no nucleotides in oxDNA output'}

        # Analyze
        metrics = pca_shape_analysis(coords)
        metrics['n_strands'] = n_strands
        metrics['strand_ids'] = strand_ids

        # Score
        reward_fns = {
            'flat_sheet': reward_flat_sheet,
            'tube': reward_tube,
        }
        reward_fn = reward_fns.get(target_shape, reward_flat_sheet)
        reward, breakdown = reward_fn(metrics)

        return reward, metrics, breakdown

    finally:
        if cleanup and os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Test designs: correct vs defective
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


def create_correct_flat_sheet(app, n_helices=6, length=126):
    """Correct flat sheet: single row, all crossovers."""
    dc, methods = _make_methods(app)
    positions = [[21, 20 + i] for i in range(n_helices)]
    methods.createHelicesWithStrands(positions=positions, strand_type="both", length=length)
    methods.addAllNeighborCrossovers("scaffold")
    methods.addAllNeighborCrossovers("staple")
    return dc, f"correct_{n_helices}h_{length}bp"


def create_no_crossovers_sheet(app, n_helices=6, length=126):
    """Defective: helices with strands but NO crossovers at all."""
    dc, methods = _make_methods(app)
    positions = [[21, 20 + i] for i in range(n_helices)]
    methods.createHelicesWithStrands(positions=positions, strand_type="both", length=length)
    # No crossovers — helices are disconnected
    return dc, f"no_xovers_{n_helices}h_{length}bp"


def create_scaffold_only_sheet(app, n_helices=6, length=126):
    """Partial: scaffold crossovers but no staple crossovers."""
    dc, methods = _make_methods(app)
    positions = [[21, 20 + i] for i in range(n_helices)]
    methods.createHelicesWithStrands(positions=positions, strand_type="both", length=length)
    methods.addAllNeighborCrossovers("scaffold")
    # Missing staple crossovers
    return dc, f"scaffold_only_{n_helices}h_{length}bp"


def create_partial_crossovers_sheet(app, n_helices=6, length=126):
    """Partial: only half the neighbor pairs have crossovers."""
    dc, methods = _make_methods(app)
    positions = [[21, 20 + i] for i in range(n_helices)]
    methods.createHelicesWithStrands(positions=positions, strand_type="both", length=length)
    # Only add crossovers for the first half of pairs
    pairs = methods.getNeighborPairs()
    # Parse pairs string to get list
    import re
    pair_matches = re.findall(r'helix (\d+) and helix (\d+)', str(pairs))
    n_pairs = len(pair_matches)
    for i, (h1, h2) in enumerate(pair_matches):
        if i < n_pairs // 2:
            methods.addCrossoversForPair(int(h1), int(h2), "scaffold")
            methods.addCrossoversForPair(int(h1), int(h2), "staple")
    return dc, f"partial_xovers_{n_helices}h_{length}bp"


def create_wrong_shape_grid(app, length=126):
    """Wrong target: 2×3 grid (should NOT score well as flat_sheet target)."""
    dc, methods = _make_methods(app)
    positions = [[21, 20], [21, 21], [21, 22],
                 [22, 20], [22, 21], [22, 22]]
    methods.createHelicesWithStrands(positions=positions, strand_type="both", length=length)
    methods.addAllNeighborCrossovers("scaffold")
    methods.addAllNeighborCrossovers("staple")
    return dc, "wrong_shape_grid_2x3"


def create_correct_tube(app, length=126):
    """Correct tube: hexagonal ring arrangement."""
    dc, methods = _make_methods(app)
    positions = [[20, 20], [20, 21],
                 [21, 20], [21, 21],
                 [22, 20], [22, 21]]
    methods.createHelicesWithStrands(positions=positions, strand_type="both", length=length)
    methods.addAllNeighborCrossovers("scaffold")
    methods.addAllNeighborCrossovers("staple")
    return dc, "correct_tube_6h"


# ---------------------------------------------------------------------------
# Figure generation
# ---------------------------------------------------------------------------

def generate_report_figures(results):
    """
    Generate purposeful figures that demonstrate the geometric reward's
    ability to distinguish correct designs from defective ones.
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    os.makedirs(RESULTS_DIR, exist_ok=True)
    figure_paths = []

    # Separate flat_sheet and tube results
    flat_results = [r for r in results if r['target'] == 'flat_sheet']
    tube_results = [r for r in results if r['target'] == 'tube']

    # ======================================================================
    # FIGURE 1: Reward scores — correct vs defective flat sheet designs
    # Objective: Show that the geometric reward discriminates between
    #            well-formed and defective designs
    # ======================================================================
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5), gridspec_kw={'width_ratios': [2, 1]})
    fig.patch.set_facecolor('#0f172a')

    for ax in [ax1, ax2]:
        ax.set_facecolor('#1e293b')
        ax.tick_params(colors='#e2e8f0')
        ax.xaxis.label.set_color('#e2e8f0')
        ax.yaxis.label.set_color('#e2e8f0')
        ax.title.set_color('#e2e8f0')
        for spine in ax.spines.values():
            spine.set_color('#334155')

    # Left panel: bar chart of total reward by design
    names = [r['name'] for r in flat_results]
    rewards = [r['reward'] for r in flat_results]
    # Color by reward: green for high, red for low
    bar_colors = [plt.cm.RdYlGn(r) for r in rewards]
    bars = ax1.barh(range(len(names)), rewards, color=bar_colors, edgecolor='#475569', height=0.6)

    for i, (bar, r) in enumerate(zip(bars, rewards)):
        ax1.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height() / 2,
                 f'{r:.3f}', va='center', color='#e2e8f0', fontweight='bold', fontsize=10)

    ax1.set_yticks(range(len(names)))
    # Clean up names for display
    display_names = []
    for n in names:
        n = n.replace('_', ' ').replace(' 6h 126bp', '').replace(' 6h 252bp', ' (long)')
        display_names.append(n)
    ax1.set_yticklabels(display_names, fontsize=9, color='#e2e8f0')
    ax1.set_xlabel('Geometric Reward (0 = wrong shape, 1 = perfect)')
    ax1.set_xlim(0, 1.15)
    ax1.set_title('Flat Sheet Target: Reward Discrimination', fontweight='bold', fontsize=12)

    # Add vertical line at threshold
    ax1.axvline(0.7, color='#10b981', linestyle='--', alpha=0.5, linewidth=1)
    ax1.text(0.71, len(names) - 0.5, 'good\nthreshold', color='#10b981', fontsize=8, va='top')

    # Right panel: reward component breakdown for the correct design
    correct_result = flat_results[0]  # first should be "correct"
    breakdown = correct_result['breakdown']
    components = ['flatness_score', 'planarity_score', 'circularity_score']
    comp_labels = ['Flatness\n(40%)', 'Planarity\n(35%)', 'Circularity\n(25%)']
    comp_values = [breakdown[c] for c in components]
    comp_colors = ['#8b5cf6', '#06b6d4', '#f59e0b']

    bars2 = ax2.bar(range(len(comp_labels)), comp_values, color=comp_colors,
                     edgecolor='#475569', width=0.6)
    for bar, v in zip(bars2, comp_values):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                 f'{v:.3f}', ha='center', color='#e2e8f0', fontweight='bold', fontsize=10)
    ax2.set_xticks(range(len(comp_labels)))
    ax2.set_xticklabels(comp_labels, fontsize=9, color='#e2e8f0')
    ax2.set_ylim(0, 1.15)
    ax2.set_ylabel('Component Score')
    ax2.set_title('Reward Components\n(correct 6-helix sheet)', fontweight='bold', fontsize=11)

    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, 'fig1_reward_discrimination.png')
    plt.savefig(path, dpi=150, facecolor='#0f172a', bbox_inches='tight')
    plt.close()
    figure_paths.append(path)
    print(f"  Figure 1: {path}")

    # ======================================================================
    # FIGURE 2: 3D geometry comparison — correct vs defective designs
    # Objective: Show what the agent "sees" in 3D after oxDNA conversion.
    #            The 2D cadnano view cannot reveal these geometric differences.
    # ======================================================================
    # Pick 3 designs to compare: correct, no crossovers, wrong shape
    compare = []
    for r in flat_results:
        if 'correct' in r['name'] and '252' not in r['name']:
            compare.append(('Correct flat sheet', r))
        elif 'no_xovers' in r['name']:
            compare.append(('No crossovers', r))
        elif 'wrong_shape' in r['name']:
            compare.append(('Wrong shape (2×3 grid)', r))

    if len(compare) >= 2:
        fig, axes = plt.subplots(1, len(compare), figsize=(5 * len(compare), 4.5))
        fig.patch.set_facecolor('#0f172a')
        if len(compare) == 1:
            axes = [axes]

        for i, (title, r) in enumerate(compare):
            ax = axes[i]
            ax.set_facecolor('#1e293b')
            ax.tick_params(colors='#e2e8f0')
            ax.xaxis.label.set_color('#e2e8f0')
            ax.yaxis.label.set_color('#e2e8f0')
            ax.title.set_color('#e2e8f0')
            for spine in ax.spines.values():
                spine.set_color('#334155')

            proj = r['metrics']['projected'] * OXDNA_UNIT_NM

            # Cross-section view (PC2 vs PC3) — reveals the shape
            strand_ids = r['metrics'].get('strand_ids', np.ones(len(proj)))
            unique_strands = np.unique(strand_ids)
            colors = plt.cm.tab20(np.linspace(0, 1, max(len(unique_strands), 1)))
            c = [colors[np.where(unique_strands == s)[0][0] % len(colors)]
                 for s in strand_ids]

            ax.scatter(proj[:, 1], proj[:, 2], c=c, s=2, alpha=0.5)
            ax.set_xlabel('PC2 — width (nm)')
            ax.set_ylabel('PC3 — thickness (nm)')
            ax.set_aspect('equal')

            reward = r['reward']
            dims = r['metrics']['pca_dims_nm']
            ax.set_title(f'{title}\nreward = {reward:.3f}\n'
                        f'{dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f} nm',
                        fontweight='bold', fontsize=10, color='#e2e8f0')

        fig.suptitle('Cross-Section Comparison (PC2 vs PC3)\n'
                     'cadnano 2D view cannot reveal these geometric differences',
                     fontsize=12, fontweight='bold', color='#94a3b8', y=1.02)
        plt.tight_layout()
        path = os.path.join(RESULTS_DIR, 'fig2_cross_section_comparison.png')
        plt.savefig(path, dpi=150, facecolor='#0f172a', bbox_inches='tight')
        plt.close()
        figure_paths.append(path)
        print(f"  Figure 2: {path}")

    # ======================================================================
    # FIGURE 3: Reward landscape — how each raw metric maps to reward
    # Objective: Explain the reward function shape to make it interpretable.
    #            Show where each test design falls on the curve.
    # ======================================================================
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    fig.patch.set_facecolor('#0f172a')

    for ax in axes:
        ax.set_facecolor('#1e293b')
        ax.tick_params(colors='#e2e8f0')
        ax.xaxis.label.set_color('#e2e8f0')
        ax.yaxis.label.set_color('#e2e8f0')
        ax.title.set_color('#e2e8f0')
        for spine in ax.spines.values():
            spine.set_color('#334155')

    # Panel A: Flatness ratio → flatness_score
    x_flat = np.linspace(0, 0.35, 200)
    y_flat = np.clip(1.0 - (x_flat - 0.06) / 0.24, 0, 1)
    axes[0].plot(x_flat, y_flat, color='#8b5cf6', linewidth=2)
    axes[0].fill_between(x_flat, y_flat, alpha=0.15, color='#8b5cf6')
    for r in flat_results:
        raw = r['breakdown']['raw_flatness']
        score = r['breakdown']['flatness_score']
        label = r['name'].replace('_6h_126bp', '').replace('_6h_252bp', '(L)')
        marker = 'o' if 'correct' in r['name'] else 'x'
        color = '#10b981' if score > 0.7 else '#ef4444'
        axes[0].plot(raw, score, marker, color=color, markersize=8, markeredgewidth=2)
        axes[0].annotate(label.replace('_', ' '), (raw, score),
                        textcoords='offset points', xytext=(5, 5),
                        fontsize=7, color='#94a3b8')
    axes[0].set_xlabel('Flatness ratio (thickness / length)')
    axes[0].set_ylabel('Score (weight: 40%)')
    axes[0].set_title('Flatness Reward Curve', fontweight='bold')

    # Panel B: Planarity RMS → planarity_score
    x_plan = np.linspace(0, 3.0, 200)
    y_plan = np.clip(1.0 - (x_plan - 0.63) / 1.5, 0, 1)
    axes[1].plot(x_plan, y_plan, color='#06b6d4', linewidth=2)
    axes[1].fill_between(x_plan, y_plan, alpha=0.15, color='#06b6d4')
    for r in flat_results:
        raw = r['breakdown']['raw_planarity']
        score = r['breakdown']['planarity_score']
        label = r['name'].replace('_6h_126bp', '').replace('_6h_252bp', '(L)')
        marker = 'o' if 'correct' in r['name'] else 'x'
        color = '#10b981' if score > 0.7 else '#ef4444'
        axes[1].plot(raw, score, marker, color=color, markersize=8, markeredgewidth=2)
        axes[1].annotate(label.replace('_', ' '), (raw, score),
                        textcoords='offset points', xytext=(5, 5),
                        fontsize=7, color='#94a3b8')
    axes[1].set_xlabel('RMS planarity (nm)')
    axes[1].set_ylabel('Score (weight: 35%)')
    axes[1].set_title('Planarity Reward Curve', fontweight='bold')

    # Panel C: Circularity → circularity_score (inverted — want LOW circularity)
    x_circ = np.linspace(0, 1.0, 200)
    y_circ = np.clip(1.0 - (x_circ - 0.4) / 0.4, 0, 1)
    axes[2].plot(x_circ, y_circ, color='#f59e0b', linewidth=2)
    axes[2].fill_between(x_circ, y_circ, alpha=0.15, color='#f59e0b')
    for r in flat_results:
        raw = r['breakdown']['raw_circularity']
        score = r['breakdown']['circularity_score']
        label = r['name'].replace('_6h_126bp', '').replace('_6h_252bp', '(L)')
        marker = 'o' if 'correct' in r['name'] else 'x'
        color = '#10b981' if score > 0.7 else '#ef4444'
        axes[2].plot(raw, score, marker, color=color, markersize=8, markeredgewidth=2)
        axes[2].annotate(label.replace('_', ' '), (raw, score),
                        textcoords='offset points', xytext=(5, 5),
                        fontsize=7, color='#94a3b8')
    axes[2].set_xlabel('Cross-section circularity')
    axes[2].set_ylabel('Score (weight: 25%)')
    axes[2].set_title('Circularity Penalty Curve', fontweight='bold')

    fig.suptitle('Reward Function Shape: How Raw Metrics Map to Scores\n'
                 '○ = correct designs, × = defective designs',
                 fontsize=12, fontweight='bold', color='#94a3b8', y=1.05)
    plt.tight_layout()
    path = os.path.join(RESULTS_DIR, 'fig3_reward_landscape.png')
    plt.savefig(path, dpi=150, facecolor='#0f172a', bbox_inches='tight')
    plt.close()
    figure_paths.append(path)
    print(f"  Figure 3: {path}")

    return figure_paths


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(RESULTS_DIR, exist_ok=True)

    app = _init_cadnano()

    # Define test cases: (creator_fn, target_shape, description)
    test_cases = [
        (lambda a: create_correct_flat_sheet(a, 6, 126), "flat_sheet",
         "Correct 6-helix flat sheet with all crossovers"),
        (lambda a: create_correct_flat_sheet(a, 6, 252), "flat_sheet",
         "Correct 6-helix long flat sheet (252bp)"),
        (lambda a: create_scaffold_only_sheet(a, 6, 126), "flat_sheet",
         "Missing staple crossovers"),
        (lambda a: create_partial_crossovers_sheet(a, 6, 126), "flat_sheet",
         "Only half the crossover pairs wired"),
        (lambda a: create_no_crossovers_sheet(a, 6, 126), "flat_sheet",
         "No crossovers at all (disconnected helices)"),
        (lambda a: create_wrong_shape_grid(a, 126), "flat_sheet",
         "Wrong shape: 2×3 grid scored as flat sheet target"),
        (lambda a: create_correct_tube(a, 126), "tube",
         "Correct tube scored against tube target"),
    ]

    results = []
    for i, (creator, target, desc) in enumerate(test_cases):
        print(f"\n{'='*60}")
        print(f"  Test {i+1}/{len(test_cases)}: {desc}")
        print(f"{'='*60}")

        try:
            dc, name = creator(app)

            # Save JSON
            work_dir = os.path.join(RESULTS_DIR, name)
            os.makedirs(work_dir, exist_ok=True)
            json_path = os.path.join(work_dir, f'{name}.json')
            dc.writeDocumentToFile(json_path)

            # Compute geometric reward
            reward, metrics, breakdown = compute_geometric_reward(
                json_path, target_shape=target, work_dir=work_dir
            )

            dims = metrics['pca_dims_nm']
            print(f"  Dimensions: {dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f} nm")
            print(f"  Flatness: {metrics['flatness_ratio']:.4f}")
            print(f"  Planarity RMS: {metrics['rms_planarity_nm']:.2f} nm")
            print(f"  Circularity: {metrics['cross_section_circularity']:.4f}")
            print(f"  → REWARD: {reward:.4f}")

            results.append({
                'name': name,
                'description': desc,
                'target': target,
                'reward': reward,
                'metrics': metrics,
                'breakdown': breakdown,
            })

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'name': name if 'name' in dir() else f'test_{i}',
                'description': desc,
                'target': target,
                'reward': 0.0,
                'metrics': {},
                'breakdown': {'error': str(e)},
            })

    # Generate figures
    print(f"\n{'='*60}")
    print("  Generating figures...")
    print(f"{'='*60}")
    figure_paths = generate_report_figures(results)

    # Save report
    report = {
        'summary': {
            'n_designs': len(results),
            'n_figures': len(figure_paths),
            'pipeline': 'cadnano JSON → tacoxDNA → oxDNA .dat/.top → PCA → geometric reward',
        },
        'results': [],
    }
    for r in results:
        entry = {
            'name': r['name'],
            'description': r['description'],
            'target_shape': r['target'],
            'reward': r['reward'],
            'breakdown': r['breakdown'],
        }
        # Include metrics but exclude large arrays
        if r.get('metrics'):
            entry['pca_dims_nm'] = r['metrics'].get('pca_dims_nm')
            entry['flatness_ratio'] = r['metrics'].get('flatness_ratio')
            entry['rms_planarity_nm'] = r['metrics'].get('rms_planarity_nm')
            entry['cross_section_circularity'] = r['metrics'].get('cross_section_circularity')
            entry['n_nucleotides'] = r['metrics'].get('n_nucleotides')
        report['results'].append(entry)

    report['figure_paths'] = figure_paths

    report_path = os.path.join(RESULTS_DIR, 'geometric_reward_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n  Report: {report_path}")

    # Print summary table
    print(f"\n{'='*70}")
    print(f"  GEOMETRIC REWARD SUMMARY")
    print(f"{'='*70}")
    print(f"  {'Design':<35} {'Target':<12} {'Reward':>8}")
    print(f"  {'-'*35} {'-'*12} {'-'*8}")
    for r in results:
        name = r['name'][:35]
        print(f"  {name:<35} {r['target']:<12} {r['reward']:>8.4f}")
    print(f"{'='*70}")

    return results


if __name__ == '__main__':
    main()
