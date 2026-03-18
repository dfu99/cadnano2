#!/usr/bin/env python
"""
Build a 2×12 rectangular DNA origami with cavity — CORRECT scaffold routing.

The scaffold routing follows this pattern (learned from PI's template):

1. Helices grouped into pairs: (0,1), (2,3), ..., (22,23)
2. INTRA-PAIR crossovers (within each pair):
   - Non-cavity: 4 xovers — left edge, left seam, right seam, right edge
     The seam pair (120,121 in template) is a "full crossover" bisecting the middle
   - Cavity: 4 xovers — left edge, left-of-cavity, right-of-cavity, right edge
     The full crossover is "split" — halves moved apart to create the cavity gap
   - LAST pair: 2 xovers only — left edge, right edge (NO middle seam)
     This connects the left and right halves of the scaffold
3. INTER-PAIR crossovers (H1→H2, H3→H4, etc.):
   - 2 double crossovers per connection (4 positions)

Usage:
  conda activate cn24-agentic
  QT_QPA_PLATFORM=offscreen python tools/build_cavity_correct.py
"""

import os
import sys
import json
from math import ceil

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_p8064_cavity():
    """Build p8064 2×12 cavity design with correct scaffold routing."""
    import cadnano2.cadnano as cadnano

    # ── Parameters (scaled from PI's template) ──
    HELIX_LENGTH = 420  # 20 steps × 21 (scaled from 252 = 12×21)
    SCALE = HELIX_LENGTH / 252  # 1.667x

    # Grid: 2 rows × 12 cols, same positions as PI's template
    ROW_A_POSITIONS = [(12, c) for c in range(20, 8, -1)]  # H0-H11: col 20→9
    ROW_B_POSITIONS = [(13, c) for c in range(9, 21)]       # H12-H23: col 9→20

    # Cavity columns (same as template: cols 13-16)
    CAVITY_COLS = {13, 14, 15, 16}

    # Scaled crossover positions
    # Template intra-pair (non-cavity): [5, 120, 121, 246]
    # Template intra-pair (cavity): [5, 67, 163, 246]
    # Template last pair: [2, 242]

    # Row 12 (even row) intra-pair positions
    R12_EDGE_LEFT = 5           # same offset
    R12_EDGE_RIGHT = int(246 * SCALE)
    R12_SEAM_LEFT = int(120 * SCALE)
    R12_SEAM_RIGHT = int(121 * SCALE)
    R12_CAVITY_LEFT = int(67 * SCALE)
    R12_CAVITY_RIGHT = int(163 * SCALE)

    # Row 13 (odd row) intra-pair positions
    R13_EDGE_LEFT = 2
    R13_EDGE_RIGHT = int(242 * SCALE)
    R13_SEAM_LEFT = int(116 * SCALE)
    R13_SEAM_RIGHT = int(117 * SCALE)
    R13_CAVITY_LEFT = int(74 * SCALE)
    R13_CAVITY_RIGHT = int(170 * SCALE)

    print("=" * 60)
    print("BUILDING p8064 2×12 CAVITY (CORRECT ROUTING)")
    print("=" * 60)
    print(f"  Helix length: {HELIX_LENGTH} bp, scale: {SCALE:.3f}x")

    # ── Initialize cadnano (MUST be before importing Crossovers) ──
    app = cadnano.initAppWithGui()
    from cadnano2.model.parts.honeycombpart import Crossovers
    dc = list(app.documentControllers)[0]
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    # Extend part size
    step = part.stepSize()
    if HELIX_LENGTH - 1 > part.maxBaseIdx():
        delta = int(ceil((HELIX_LENGTH - 1 - part.maxBaseIdx()) / step)) * step
        part.resizeVirtualHelices(0, delta, useUndoStack=True)

    # ── Create helices ──
    all_positions = ROW_A_POSITIONS + ROW_B_POSITIONS
    for r, c in all_positions:
        part.createVirtualHelix(r, c, useUndoStack=True)

    vh_by_num = {}
    for i, (r, c) in enumerate(all_positions):
        vh = part.virtualHelixAtCoord((r, c))
        vh_by_num[i] = vh

    print(f"  Created {len(vh_by_num)} helices")

    # ── Create scaffold strands ──
    # For each helix, create scaffold strand(s)
    # Non-cavity: one full-length strand
    # Cavity: two strands (left and right of gap)
    for i, (r, c) in enumerate(all_positions):
        vh = vh_by_num[i]
        scaf_ss = vh.scaffoldStrandSet()
        is_cavity = c in CAVITY_COLS

        if is_cavity:
            if r == 12:
                gap_start, gap_end = int(68 * SCALE), int(162 * SCALE)
            else:
                gap_start, gap_end = int(75 * SCALE), int(169 * SCALE)

            # Left segment
            lo_left = R12_EDGE_LEFT if r == 12 else R13_EDGE_LEFT
            scaf_ss.createStrand(lo_left, gap_start - 1, useUndoStack=True)
            # Right segment
            hi_right = R12_EDGE_RIGHT if r == 12 else R13_EDGE_RIGHT
            scaf_ss.createStrand(gap_end + 1, hi_right, useUndoStack=True)
        else:
            lo = R12_EDGE_LEFT if r == 12 else R13_EDGE_LEFT
            hi = R12_EDGE_RIGHT if r == 12 else R13_EDGE_RIGHT
            scaf_ss.createStrand(lo, hi, useUndoStack=True)

    print("  Created scaffold strands")

    # ── Place intra-pair crossovers ──
    # Pairs: (0,1), (2,3), ..., (22,23)
    xovers_placed = 0
    for pair_idx in range(12):
        h_a = pair_idx * 2
        h_b = pair_idx * 2 + 1
        vh_a = vh_by_num[h_a]
        vh_b = vh_by_num[h_b]
        r = all_positions[h_a][0]
        c_a = all_positions[h_a][1]
        is_cavity = c_a in CAVITY_COLS
        is_last_pair = (pair_idx == 11)  # H22-H23

        if is_last_pair:
            # Last pair: only edge crossovers (no middle seam)
            positions = [R13_EDGE_LEFT, R13_EDGE_RIGHT]
        elif is_cavity:
            if r == 12:
                positions = [R12_EDGE_LEFT, R12_CAVITY_LEFT,
                             R12_CAVITY_RIGHT, R12_EDGE_RIGHT]
            else:
                positions = [R13_EDGE_LEFT, R13_CAVITY_LEFT,
                             R13_CAVITY_RIGHT, R13_EDGE_RIGHT]
        else:
            if r == 12:
                positions = [R12_EDGE_LEFT, R12_SEAM_LEFT,
                             R12_SEAM_RIGHT, R12_EDGE_RIGHT]
            else:
                positions = [R13_EDGE_LEFT, R13_SEAM_LEFT,
                             R13_SEAM_RIGHT, R13_EDGE_RIGHT]

        for pos in positions:
            try:
                strand_a = vh_a.scaffoldStrandSet().getStrand(pos)
                strand_b = vh_b.scaffoldStrandSet().getStrand(pos)
                if strand_a and strand_b:
                    part.createXover(strand_a, pos, strand_b, pos,
                                     useUndoStack=True)
                    xovers_placed += 1
            except Exception as e:
                print(f"    WARN: xover H{h_a}-H{h_b} at {pos}: {e}")

    print(f"  Intra-pair crossovers: {xovers_placed}")

    # ── Place inter-pair crossovers ──
    # H1→H2, H3→H4, ..., H21→H22, and H11→H12 (cross-row)
    inter_xovers = 0
    inter_pairs = [(1,2), (3,4), (5,6), (7,8), (9,10), (11,12),
                   (13,14), (15,16), (17,18), (19,20), (21,22)]

    for h_a, h_b in inter_pairs:
        vh_a = vh_by_num[h_a]
        vh_b = vh_by_num[h_b]

        # Get valid crossover positions from honeycomb tables
        neighbors = part.getVirtualHelixNeighbors(vh_a)
        if vh_b not in neighbors:
            # Try reverse
            neighbors = part.getVirtualHelixNeighbors(vh_b)
            if vh_a not in neighbors:
                print(f"    WARN: H{h_a} and H{h_b} not neighbors")
                continue
            vh_a, vh_b = vh_b, vh_a

        direction = neighbors.index(vh_b)
        low_offsets = Crossovers.honeycombScafLow[direction]
        high_offsets = Crossovers.honeycombScafHigh[direction]

        # Place 2 double crossovers (scaled from template positions)
        # Template had crossovers roughly at 1/3 and 2/3 of helix length
        target_positions = [int(HELIX_LENGTH * 0.15), int(HELIX_LENGTH * 0.5),
                           int(HELIX_LENGTH * 0.75)]

        for target in target_positions:
            # Find closest valid crossover position
            best = None
            best_dist = 999
            for base in range(0, HELIX_LENGTH, step):
                for lo_off, hi_off in zip(low_offsets, high_offsets):
                    lo_idx = base + lo_off
                    hi_idx = base + hi_off
                    if 0 <= lo_idx < HELIX_LENGTH and 0 <= hi_idx < HELIX_LENGTH:
                        dist = abs(lo_idx - target)
                        if dist < best_dist:
                            best = lo_idx
                            best_dist = dist

            if best is not None:
                try:
                    # Need to get strands at this position
                    sa = vh_a.scaffoldStrandSet().getStrand(best)
                    sb = vh_b.scaffoldStrandSet().getStrand(best)
                    if sa and sb:
                        part.createXover(sa, best, sb, best, useUndoStack=True)
                        inter_xovers += 1
                except Exception as e:
                    pass  # Some positions may not work

    print(f"  Inter-pair crossovers: {inter_xovers}")

    # ── Verify scaffold ──
    scaffold_oligos = [o for o in part.oligos() if not o.isStaple()]
    total_scaf_bp = sum(o.length() for o in scaffold_oligos)
    print(f"\n  Scaffold oligos: {len(scaffold_oligos)} (goal: 1)")
    print(f"  Total scaffold bp: {total_scaf_bp}")

    # ── Save ──
    output_dir = os.path.join(PROJECT_ROOT, 'results', 'from_scratch_corrected')
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, 'p8064_2x12_cavity_corrected.json')
    dc.writeDocumentToFile(json_path)
    print(f"  Saved: {json_path}")

    # ── Generate scaffold routing visualization ──
    visualize_routing(json_path, output_dir)

    return json_path


def visualize_routing(json_path, output_dir):
    """Draw scaffold routing from the JSON."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    with open(json_path) as f:
        data = json.load(f)

    vs_list = data['vstrands']
    fig, ax = plt.subplots(figsize=(16, 10))
    y_spacing = 2.0

    for di, vs in enumerate(vs_list):
        num = vs['num']
        scaf = vs['scaf']
        y = -di * y_spacing

        ax.text(-15, y, f'H{num}\n({vs["row"]},{vs["col"]})', fontsize=6,
                ha='right', va='center', fontfamily='monospace')

        # Draw scaffold segments
        seg_start = None
        for idx, entry in enumerate(scaf):
            if entry != [-1,-1,-1,-1]:
                if seg_start is None:
                    seg_start = idx
            else:
                if seg_start is not None:
                    ax.plot([seg_start, idx-1], [y, y], '-', color='steelblue',
                            linewidth=3, solid_capstyle='round', alpha=0.8)
                    seg_start = None
        if seg_start is not None:
            ax.plot([seg_start, len(scaf)-1], [y, y], '-', color='steelblue',
                    linewidth=3, solid_capstyle='round', alpha=0.8)

        # Draw crossovers
        for idx, (vh5p, idx5p, vh3p, idx3p) in enumerate(scaf):
            if vh3p != -1 and vh3p != num:
                target_di = next(i for i, v in enumerate(vs_list) if v['num'] == vh3p)
                y_target = -target_di * y_spacing
                ax.plot([idx, idx3p], [y, y_target], '-', color='red',
                        linewidth=1, alpha=0.6)

    ax.set_xlabel('Base pair index', fontsize=10)
    ax.set_title('Corrected From-Scratch — Scaffold Routing (p8064)',
                 fontsize=12, fontweight='bold')
    ax.set_xlim(-20, len(vs_list[0]['scaf']) + 5)
    plt.tight_layout()
    path = os.path.join(output_dir, 'scaffold_routing.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {path}")


if __name__ == '__main__':
    build_p8064_cavity()
