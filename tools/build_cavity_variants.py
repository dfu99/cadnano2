#!/usr/bin/env python
"""
Build 2×12 cavity designs with variable gap sizes from scratch in cadnano.

Creates each design from scratch on the honeycomb lattice:
1. Create 24 helices (2 rows × 12 cols)
2. Create scaffold strands with variable-width cavity gaps
3. Place intra-pair and inter-pair crossovers
4. Run autoStaple
5. Take screenshot

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
    """Build a 2×12 cavity design with specified gap from scratch."""
    sys.path.insert(0, PROJECT_ROOT)
    import cadnano2.cadnano as cadnano

    app = cadnano.initAppWithGui()
    from cadnano2.model.parts.honeycombpart import Crossovers

    dc = list(app.documentControllers)[0]
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    # ── Parameters ──
    gap_bp = int(gap_nm / NM_PER_BP)
    n_helices = 24
    n_cavity = 8
    n_full = n_helices - n_cavity

    # Compute helix length to fit scaffold
    # scaffold = n_full * (helix_len - margins) + n_cavity * (helix_len - gap - margins)
    # Approximate: need n_full * L + n_cavity * (L - gap_bp) ≈ target / 0.95
    target_L = (SCAFFOLD_TARGET / 0.95 + n_cavity * gap_bp) / n_helices
    helix_len = int(ceil(target_L / STEP)) * STEP
    helix_len = max(helix_len, gap_bp + 140)

    print(f"  Gap: {gap_nm}nm = {gap_bp}bp", flush=True)
    print(f"  Helix length: {helix_len}bp ({helix_len // STEP} steps)", flush=True)

    # Extend part size
    step = part.stepSize()
    if helix_len - 1 > part.maxBaseIdx():
        delta = int(ceil((helix_len - 1 - part.maxBaseIdx()) / step)) * step
        part.resizeVirtualHelices(0, delta, useUndoStack=True)

    # ── Create helices (same layout as PI's template) ──
    # Row 12: H0-H11 at (12, 20→9)
    # Row 13: H12-H23 at (13, 9→20)
    ROW_A = [(12, c) for c in range(20, 8, -1)]  # H0-H11
    ROW_B = [(13, c) for c in range(9, 21)]        # H12-H23
    all_positions = ROW_A + ROW_B

    # Cavity columns: cols 13-16 (same as template)
    CAVITY_COLS = {13, 14, 15, 16}

    for r, c in all_positions:
        part.createVirtualHelix(r, c, useUndoStack=True)

    vh_by_num = {}
    for i, (r, c) in enumerate(all_positions):
        vh = part.virtualHelixAtCoord((r, c))
        vh_by_num[i] = vh

    print(f"  Created {len(vh_by_num)} helices", flush=True)

    # ── Compute cavity gap position (centered) ──
    gap_center = helix_len // 2
    # Row 12 gap (even parity helices have specific valid crossover offsets)
    r12_gap_start = ((gap_center - gap_bp // 2) // STEP) * STEP + 5  # near valid xover
    r12_gap_end = r12_gap_start + gap_bp
    # Row 13 gap
    r13_gap_start = ((gap_center - gap_bp // 2) // STEP) * STEP + 2
    r13_gap_end = r13_gap_start + gap_bp

    print(f"  Row 12 cavity: bp {r12_gap_start}-{r12_gap_end}", flush=True)
    print(f"  Row 13 cavity: bp {r13_gap_start}-{r13_gap_end}", flush=True)

    # ── Create scaffold strands ──
    for i, (r, c) in enumerate(all_positions):
        vh = vh_by_num[i]
        scaf_ss = vh.scaffoldStrandSet()
        is_cavity = c in CAVITY_COLS

        # Strand boundaries (avoid first/last few bases for crossover room)
        if vh.isEvenParity():
            lo, hi = 5, helix_len - 6
        else:
            lo, hi = 2, helix_len - 3

        if is_cavity:
            if r == 12:
                g_start, g_end = r12_gap_start, r12_gap_end
            else:
                g_start, g_end = r13_gap_start, r13_gap_end

            # Left segment
            if g_start > lo + 2:
                scaf_ss.createStrand(lo, g_start - 1, useUndoStack=True)
            # Right segment
            if g_end < hi - 2:
                scaf_ss.createStrand(g_end + 1, hi, useUndoStack=True)
        else:
            scaf_ss.createStrand(lo, hi, useUndoStack=True)

    print(f"  Created scaffold strands", flush=True)

    # ── Place intra-pair crossovers ──
    # Pairs: (0,1), (2,3), ..., (22,23)
    # Use the PI's template pattern:
    #   Non-cavity: edge-left, seam-left, seam-right, edge-right
    #   Cavity: edge-left, gap-left, gap-right, edge-right
    #   Last pair: edge-left, edge-right only

    xovers_placed = 0

    for pair_idx in range(12):
        h_a = pair_idx * 2
        h_b = pair_idx * 2 + 1
        vh_a = vh_by_num[h_a]
        vh_b = vh_by_num[h_b]
        r = all_positions[h_a][0]
        c_a = all_positions[h_a][1]
        is_cavity = c_a in CAVITY_COLS
        is_last = (pair_idx == 11)

        # Get valid crossover positions from honeycomb tables
        neighbors = part.getVirtualHelixNeighbors(vh_a)
        if vh_b not in neighbors:
            continue
        dir_idx = neighbors.index(vh_b)

        if is_last:
            # Last pair: only edge crossovers
            if r == 12:
                positions = [5, helix_len - 6]
            else:
                positions = [2, helix_len - 3]
        elif is_cavity:
            if r == 12:
                positions = [5, r12_gap_start - 2, r12_gap_end + 2, helix_len - 6]
            else:
                positions = [2, r13_gap_start - 2, r13_gap_end + 2, helix_len - 3]
        else:
            # Non-cavity: edge and seam crossovers
            seam = helix_len // 2
            if r == 12:
                positions = [5, seam - 1, seam, helix_len - 6]
            else:
                positions = [2, seam - 1, seam, helix_len - 3]

        for pos in positions:
            try:
                strand_a = vh_a.scaffoldStrandSet().getStrand(pos)
                strand_b = vh_b.scaffoldStrandSet().getStrand(pos)
                if strand_a and strand_b:
                    part.createXover(strand_a, pos, strand_b, pos, useUndoStack=True)
                    xovers_placed += 1
            except Exception as e:
                pass  # some positions may not work

    print(f"  Intra-pair crossovers: {xovers_placed}", flush=True)

    # ── Place inter-pair crossovers ──
    # H1→H2, H3→H4, ..., H21→H22, H11→H12 (cross-row)
    inter_pairs = [(1,2), (3,4), (5,6), (7,8), (9,10), (11,12),
                   (13,14), (15,16), (17,18), (19,20), (21,22)]

    inter_xovers = 0
    for h_a, h_b in inter_pairs:
        vh_a = vh_by_num[h_a]
        vh_b = vh_by_num[h_b]

        neighbors = part.getVirtualHelixNeighbors(vh_a)
        if vh_b not in neighbors:
            neighbors = part.getVirtualHelixNeighbors(vh_b)
            if vh_a not in neighbors:
                continue
            vh_a, vh_b = vh_b, vh_a

        dir_idx = neighbors.index(vh_b)
        low_offsets = Crossovers.honeycombScafLow[dir_idx]
        high_offsets = Crossovers.honeycombScafHigh[dir_idx]

        # Place crossovers at ~1/3 and ~2/3 of helix length
        targets = [int(helix_len * 0.25), int(helix_len * 0.75)]

        for target in targets:
            best_pos = None
            best_dist = 9999
            for base in range(0, helix_len, step):
                for lo_off in low_offsets:
                    pos = base + lo_off
                    if 0 <= pos < helix_len:
                        dist = abs(pos - target)
                        if dist < best_dist:
                            best_pos = pos
                            best_dist = dist

            if best_pos is not None:
                try:
                    sa = vh_a.scaffoldStrandSet().getStrand(best_pos)
                    sb = vh_b.scaffoldStrandSet().getStrand(best_pos)
                    if sa and sb:
                        part.createXover(sa, best_pos, sb, best_pos, useUndoStack=True)
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
    print(f"  Scaffold: {total_bp}bp in {n_oligos} oligos", flush=True)

    # ── Save JSON ──
    if output_json:
        os.makedirs(os.path.dirname(output_json), exist_ok=True)
        dc.writeDocumentToFile(output_json)
        print(f"  Saved JSON: {output_json}", flush=True)

    # ── Screenshot ──
    img = render_pathview(dc)
    os.makedirs(os.path.dirname(output_png), exist_ok=True)
    img.save(output_png)
    print(f"  Screenshot: {output_png} ({img.width()}x{img.height()}px)", flush=True)

    return True


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
