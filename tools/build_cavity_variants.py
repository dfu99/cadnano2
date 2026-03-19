#!/usr/bin/env python
"""
Build 2×12 cavity designs with variable gap sizes — correct scaffold routing.

Combines:
  - Correct routing topology from build_cavity_correct.py (1 scaffold oligo)
  - Variable gap widths parameterized by nm

The routing pattern (from PI's template):
  1. Helices in pairs: (0,1)...(22,23)
  2. Intra-pair: 4 xovers (edges + seam/cavity boundaries)
  3. Last pair: 2 xovers only (edges, no seam)
  4. Inter-pair: 2 double xovers per connection

Crossover positions are scaled from the 252bp template to the target
helix length, with cavity boundary positions adjusted for the target
gap width (snapped to valid lattice positions).

Usage:
  conda activate cn24-agentic
  QT_QPA_PLATFORM=offscreen python tools/build_cavity_variants.py <gap_nm> <output_png>
  QT_QPA_PLATFORM=offscreen python tools/build_cavity_variants.py   # dispatch all 3
"""

import os
import sys
import subprocess
from math import ceil

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'results', 'cavity_variants')
MAX_DIM = 1800
NM_PER_BP = 0.34
STEP = 21
SCAFFOLD_TARGET = 8064

# ── Template reference positions (252bp helices) ──
# These are the exact crossover positions in the PI's template.
# Intra-pair crossovers:
#   Non-cavity row 12: [5, 120, 121, 246]   (edges + seam)
#   Non-cavity row 13: [2, 116, 117, 242]   (edges + seam)
#   Cavity row 12:     [5, 67, 163, 246]    (edges + gap boundaries)
#   Cavity row 13:     [2, 74, 170, 242]    (edges + gap boundaries)
#   Last pair (H22-H23): [2, 242]           (edges only)
#
# Inter-pair crossovers (double xovers, 2 positions each):
#   H1-H2:   [64, 65, 200, 201]
#   H3-H4:   [32, 33, 200, 201]
#   H5-H6:   [32, 33, 200, 201]
#   H7-H8:   [32, 33, 211, 212]
#   H9-H10:  [53, 54, 211, 212]
#   H11-H12: [50, 51, 207, 208]
#   H13-H14: [36, 37, 204, 205]
#   H15-H16: [36, 37, 204, 205]
#   H17-H18: [36, 37, 204, 205]
#   H19-H20: [36, 37, 204, 205]
#   H21-H22: [36, 37, 183, 184]

TEMPLATE_LEN = 252
TEMPLATE_R12_GAP = (68, 162)  # inclusive occupied range is [5..67] + [163..246]
TEMPLATE_R13_GAP = (75, 169)

# Valid crossover offsets per direction (from honeycomb tables)
# Row 12 intra-pair (direction p2): offsets 4, 5, 15, 16  (mod 21)
# Row 13 intra-pair (direction p0): offsets 1, 2, 11, 12  (mod 21)
R12_INTRA_OFFSETS = [4, 5, 15, 16]
R13_INTRA_OFFSETS = [1, 2, 11, 12]


def snap_to_lattice(target, offsets, helix_len):
    """Find the valid lattice position closest to target."""
    best = None
    for k in range(helix_len // STEP + 1):
        for off in offsets:
            pos = k * STEP + off
            if 0 <= pos < helix_len:
                if best is None or abs(pos - target) < abs(best - target):
                    best = pos
    return best


def scale_pos(template_pos, template_len, new_len):
    """Scale a position from template to new helix length."""
    return int(round(template_pos * new_len / template_len))


def render_pathview(dc):
    from PyQt6.QtCore import QMarginsF, QRectF
    from PyQt6.QtGui import QImage, QPainter, QColor
    scene = dc.win.pathscene
    rect = scene.itemsBoundingRect()
    if rect.isEmpty():
        rect = QRectF(0, 0, 1600, 400)
    margin = 30
    rect = rect.marginsAdded(QMarginsF(margin, margin, margin, margin))
    scale = 2.0
    w = int(rect.width() * scale)
    h = int(rect.height() * scale)
    if w > MAX_DIM or h > MAX_DIM:
        ratio = min(MAX_DIM / w, MAX_DIM / h)
        scale *= ratio
        w = int(rect.width() * scale)
        h = int(rect.height() * scale)
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(255, 255, 255))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(painter, source=rect)
    painter.end()
    return img


def build_variant(gap_nm, output_png, output_json=None):
    """Build a 2×12 cavity with correct routing at specified gap size."""
    sys.path.insert(0, PROJECT_ROOT)
    import cadnano2.cadnano as cadnano

    app = cadnano.initAppWithGui()
    from cadnano2.model.parts.honeycombpart import Crossovers

    dc = list(app.documentControllers)[0]
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    # ── Compute dimensions ──
    gap_bp = int(gap_nm / NM_PER_BP)
    n_cavity = 8
    n_helices = 24
    target_L = (SCAFFOLD_TARGET / 0.95 + n_cavity * gap_bp) / n_helices
    helix_len = int(ceil(target_L / STEP)) * STEP
    helix_len = max(helix_len, gap_bp + 140)
    S = helix_len / TEMPLATE_LEN  # scale factor

    print(f"  Gap: {gap_nm}nm = {gap_bp}bp", flush=True)
    print(f"  Helix length: {helix_len}bp ({helix_len // STEP} steps), scale={S:.3f}x", flush=True)

    # Extend part
    step = part.stepSize()
    if helix_len - 1 > part.maxBaseIdx():
        delta = int(ceil((helix_len - 1 - part.maxBaseIdx()) / step)) * step
        part.resizeVirtualHelices(0, delta, useUndoStack=True)

    # ── Create helices (same layout as template) ──
    ROW_A = [(12, c) for c in range(20, 8, -1)]  # H0-H11
    ROW_B = [(13, c) for c in range(9, 21)]        # H12-H23
    all_pos = ROW_A + ROW_B
    CAVITY_COLS = {13, 14, 15, 16}

    for r, c in all_pos:
        part.createVirtualHelix(r, c, useUndoStack=True)

    vh_by_num = {}
    for i, (r, c) in enumerate(all_pos):
        vh_by_num[i] = part.virtualHelixAtCoord((r, c))

    print(f"  Created {len(vh_by_num)} helices", flush=True)

    # ── Compute crossover positions ──
    # Scaled edges
    r12_edge_left = 5
    r12_edge_right = snap_to_lattice(scale_pos(246, TEMPLATE_LEN, helix_len),
                                      R12_INTRA_OFFSETS, helix_len)
    r13_edge_left = 2
    r13_edge_right = snap_to_lattice(scale_pos(242, TEMPLATE_LEN, helix_len),
                                      R13_INTRA_OFFSETS, helix_len)

    # Scaled seam (center of helix)
    r12_seam_left = snap_to_lattice(helix_len // 2 - 1, R12_INTRA_OFFSETS, helix_len)
    r12_seam_right = snap_to_lattice(helix_len // 2, R12_INTRA_OFFSETS, helix_len)
    # Ensure seam_right > seam_left
    if r12_seam_right <= r12_seam_left:
        r12_seam_right = snap_to_lattice(r12_seam_left + 1, R12_INTRA_OFFSETS, helix_len)

    r13_seam_left = snap_to_lattice(helix_len // 2 - 1, R13_INTRA_OFFSETS, helix_len)
    r13_seam_right = snap_to_lattice(helix_len // 2, R13_INTRA_OFFSETS, helix_len)
    if r13_seam_right <= r13_seam_left:
        r13_seam_right = snap_to_lattice(r13_seam_left + 1, R13_INTRA_OFFSETS, helix_len)

    # Cavity boundary positions (centered gap)
    gap_center = helix_len // 2
    r12_cav_left_target = gap_center - gap_bp // 2
    r12_cav_right_target = r12_cav_left_target + gap_bp
    r12_cav_left = snap_to_lattice(r12_cav_left_target, R12_INTRA_OFFSETS, helix_len)
    r12_cav_right = snap_to_lattice(r12_cav_right_target, R12_INTRA_OFFSETS, helix_len)
    # Ensure they're distinct and in the right order
    if r12_cav_right <= r12_cav_left:
        r12_cav_right = snap_to_lattice(r12_cav_left + gap_bp, R12_INTRA_OFFSETS, helix_len)

    r13_cav_left_target = gap_center - gap_bp // 2
    r13_cav_right_target = r13_cav_left_target + gap_bp
    r13_cav_left = snap_to_lattice(r13_cav_left_target, R13_INTRA_OFFSETS, helix_len)
    r13_cav_right = snap_to_lattice(r13_cav_right_target, R13_INTRA_OFFSETS, helix_len)
    if r13_cav_right <= r13_cav_left:
        r13_cav_right = snap_to_lattice(r13_cav_left + gap_bp, R13_INTRA_OFFSETS, helix_len)

    actual_gap_r12 = r12_cav_right - r12_cav_left
    actual_gap_r13 = r13_cav_right - r13_cav_left
    print(f"  Row 12: edges [{r12_edge_left}, {r12_edge_right}], "
          f"seam [{r12_seam_left}, {r12_seam_right}], "
          f"cavity [{r12_cav_left}, {r12_cav_right}] ({actual_gap_r12}bp)", flush=True)
    print(f"  Row 13: edges [{r13_edge_left}, {r13_edge_right}], "
          f"seam [{r13_seam_left}, {r13_seam_right}], "
          f"cavity [{r13_cav_left}, {r13_cav_right}] ({actual_gap_r13}bp)", flush=True)

    # ── Create scaffold strands ──
    for i, (r, c) in enumerate(all_pos):
        vh = vh_by_num[i]
        scaf_ss = vh.scaffoldStrandSet()
        is_cavity = c in CAVITY_COLS

        if r == 12:
            lo, hi = r12_edge_left, r12_edge_right
        else:
            lo, hi = r13_edge_left, r13_edge_right

        if is_cavity:
            if r == 12:
                g_start, g_end = r12_cav_left + 1, r12_cav_right - 1
            else:
                g_start, g_end = r13_cav_left + 1, r13_cav_right - 1
            # Left segment: [lo, g_start-1]
            scaf_ss.createStrand(lo, g_start - 1, useUndoStack=True)
            # Right segment: [g_end+1, hi]
            scaf_ss.createStrand(g_end + 1, hi, useUndoStack=True)
        else:
            scaf_ss.createStrand(lo, hi, useUndoStack=True)

    print(f"  Created scaffold strands", flush=True)

    # ── Place intra-pair crossovers ──
    xovers_placed = 0
    for pair_idx in range(12):
        h_a = pair_idx * 2
        h_b = pair_idx * 2 + 1
        vh_a = vh_by_num[h_a]
        vh_b = vh_by_num[h_b]
        r = all_pos[h_a][0]
        c_a = all_pos[h_a][1]
        is_cavity = c_a in CAVITY_COLS
        is_last = (pair_idx == 11)  # H22-H23

        if is_last:
            positions = [r13_edge_left, r13_edge_right]
        elif is_cavity:
            if r == 12:
                positions = [r12_edge_left, r12_cav_left, r12_cav_right, r12_edge_right]
            else:
                positions = [r13_edge_left, r13_cav_left, r13_cav_right, r13_edge_right]
        else:
            if r == 12:
                positions = [r12_edge_left, r12_seam_left, r12_seam_right, r12_edge_right]
            else:
                positions = [r13_edge_left, r13_seam_left, r13_seam_right, r13_edge_right]

        for pos in positions:
            try:
                sa = vh_a.scaffoldStrandSet().getStrand(pos)
                sb = vh_b.scaffoldStrandSet().getStrand(pos)
                if sa and sb:
                    part.createXover(sa, pos, sb, pos, useUndoStack=True)
                    xovers_placed += 1
            except Exception as e:
                print(f"    WARN intra: H{h_a}-H{h_b} at {pos}: {e}", flush=True)

    print(f"  Intra-pair crossovers: {xovers_placed}", flush=True)

    # ── Place inter-pair crossovers ──
    # Template positions for each inter-pair connection (scaled)
    TEMPLATE_INTER = {
        (1,2):   [64, 65, 200, 201],
        (3,4):   [32, 33, 200, 201],
        (5,6):   [32, 33, 200, 201],
        (7,8):   [32, 33, 211, 212],
        (9,10):  [53, 54, 211, 212],
        (11,12): [50, 51, 207, 208],
        (13,14): [36, 37, 204, 205],
        (15,16): [36, 37, 204, 205],
        (17,18): [36, 37, 204, 205],
        (19,20): [36, 37, 204, 205],
        (21,22): [36, 37, 183, 184],
    }

    inter_xovers = 0
    for (h_a, h_b), template_positions in TEMPLATE_INTER.items():
        vh_a = vh_by_num[h_a]
        vh_b = vh_by_num[h_b]

        # Get direction for this pair
        neighbors = part.getVirtualHelixNeighbors(vh_a)
        if vh_b in neighbors:
            dir_idx = neighbors.index(vh_b)
        else:
            neighbors = part.getVirtualHelixNeighbors(vh_b)
            if vh_a in neighbors:
                dir_idx = neighbors.index(vh_a)
                vh_a, vh_b = vh_b, vh_a
            else:
                print(f"    WARN: H{h_a} and H{h_b} not neighbors", flush=True)
                continue

        low_offsets = Crossovers.honeycombScafLow[dir_idx]
        high_offsets = Crossovers.honeycombScafHigh[dir_idx]

        # Scale each template position and snap to valid lattice position
        valid_offsets = sorted(set(list(low_offsets) + list(high_offsets)))

        for tp in template_positions:
            scaled = scale_pos(tp, TEMPLATE_LEN, helix_len)
            snapped = snap_to_lattice(scaled, valid_offsets, helix_len)

            if snapped is not None:
                try:
                    sa = vh_a.scaffoldStrandSet().getStrand(snapped)
                    sb = vh_b.scaffoldStrandSet().getStrand(snapped)
                    if sa and sb:
                        part.createXover(sa, snapped, sb, snapped, useUndoStack=True)
                        inter_xovers += 1
                except Exception:
                    pass

    print(f"  Inter-pair crossovers: {inter_xovers}", flush=True)

    # ── AutoStaple ──
    from cadnano2.model.parts.part import Part
    Part.autoStaple(part)
    staple_count = sum(1 for o in part.oligos() if o.isStaple())
    print(f"  AutoStaple: {staple_count} staples", flush=True)

    # ── Verify scaffold ──
    scaf_oligos = [o for o in part.oligos() if not o.isStaple()]
    total_bp = sum(o.length() for o in scaf_oligos)
    n_oligos = len(scaf_oligos)
    print(f"  Scaffold: {total_bp}bp in {n_oligos} oligo(s)", flush=True)

    # ── Save JSON ──
    if output_json:
        os.makedirs(os.path.dirname(output_json), exist_ok=True)
        dc.writeDocumentToFile(output_json)
        print(f"  Saved: {output_json}", flush=True)

    # ── Screenshot ──
    img = render_pathview(dc)
    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    img.save(output_png)
    print(f"  Screenshot: {output_png} ({img.width()}x{img.height()}px)", flush=True)

    return {'scaffold_bp': total_bp, 'n_oligos': n_oligos,
            'gap_actual_r12': actual_gap_r12, 'gap_actual_r13': actual_gap_r13}


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if len(sys.argv) >= 3:
        gap_nm = int(sys.argv[1])
        output_png = sys.argv[2]
        output_json = sys.argv[3] if len(sys.argv) >= 4 else None
        print(f"\n--- {gap_nm}nm gap ---", flush=True)
        build_variant(gap_nm, output_png, output_json)
        print("Done.", flush=True)
        return

    # Dispatch mode
    variants = [
        (20, 'screenshot_20nm.png', 'cavity_20nm_2x12_8064bp.json'),
        (30, 'screenshot_30nm.png', 'cavity_30nm_2x12_8064bp.json'),
        (40, 'screenshot_40nm.png', 'cavity_40nm_2x12_8064bp.json'),
    ]

    results = []
    for gap_nm, png_name, json_name in variants:
        png_path = os.path.join(OUTPUT_DIR, png_name)
        json_path = os.path.join(OUTPUT_DIR, json_name)
        print(f"\n=== {gap_nm}nm gap ===", flush=True)
        result = subprocess.run(
            [sys.executable, __file__, str(gap_nm), png_path, json_path],
            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
            timeout=90, capture_output=True, text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"  STDERR: {result.stderr[-500:]}")

    print("\nAll variants complete.", flush=True)


if __name__ == '__main__':
    main()
