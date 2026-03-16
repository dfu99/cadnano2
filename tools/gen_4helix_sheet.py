#!/usr/bin/env python
"""
Generate a flat 4-helix sheet with correct crossover handedness.

Strategy: Create double crossovers at edge positions, then remove
one half to leave the correct half crossover. This reproduces
exactly what a GUI user would do.

For each edge pair:
  - Left side of structure: create double, remove LEFT half → RIGHT half remains
  - Right side of structure: create double, remove RIGHT half → LEFT half remains

Usage:
  QT_QPA_PLATFORM=offscreen python tools/gen_4helix_sheet.py
"""

import os
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cadnano2.cadnano as cadnano

from PyQt6.QtCore import QRectF, QMarginsF
from PyQt6.QtGui import QImage, QPainter, QColor
from PyQt6.QtWidgets import QApplication


def render_pathview(dc):
    """Render the path view scene to a QImage."""
    win = dc.win
    scene = win.pathscene
    items_rect = scene.itemsBoundingRect()
    if items_rect.isEmpty():
        items_rect = QRectF(0, 0, 800, 200)
    margin = 20
    items_rect = items_rect.marginsAdded(QMarginsF(margin, margin, margin, margin))
    scale = 2.0
    width = int(items_rect.width() * scale)
    height = int(items_rect.height() * scale)
    max_dim = 4000
    if width > max_dim:
        scale *= max_dim / width
        width = max_dim
        height = int(items_rect.height() * scale)
    if height > max_dim:
        scale *= max_dim / height
        height = max_dim
        width = int(items_rect.width() * scale)
    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(255, 255, 255))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(painter, source=items_rect)
    painter.end()
    return image


def print_strand_info(part, label):
    """Print all scaffold strand info for debugging."""
    print(f"\n--- {label} ---")
    for h in range(4):
        vh = part.virtualHelix(h)
        if vh is None:
            continue
        ss = vh.scaffoldStrandSet()
        parity = "even" if vh.isEvenParity() else "odd"
        drawn = "L→R" if ss.isDrawn5to3() else "R→L"
        print(f"  H{h} ({parity}, {drawn}):")
        for strand in ss:
            lo, hi = strand.idxs()
            conn_lo = strand.connectionLow()
            conn_hi = strand.connectionHigh()
            idx5 = strand.idx5Prime()
            idx3 = strand.idx3Prime()
            lo_str = f"→H{conn_lo.virtualHelix().number()}[{conn_lo.idx5Prime() if conn_lo else '?'}]" if conn_lo else "free"
            hi_str = f"→H{conn_hi.virtualHelix().number()}[{conn_hi.idx3Prime() if conn_hi else '?'}]" if conn_hi else "free"
            print(f"    [{lo},{hi}] 5'@{idx5} 3'@{idx3} | lo:{lo_str} hi:{hi_str}")


def main():
    app = cadnano.initAppWithGui()

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
    m = AgentMethods(mock)

    # Create 4-helix linear chain with scaffold strands
    result = m.createHelicesWithStrands(num_helices=4, strand_type="scaffold", length=126)
    print(f"Created helices: {result['created']} helices, {result['strand_type']}, length={result['length']}")

    # Get suggested positions for each pair
    for h1, h2 in [(0, 1), (1, 2), (2, 3)]:
        sugg = m.suggestCrossovers(h1, h2, "scaffold")
        positions = sugg.get('positions', [])
        print(f"\nH{h1}-H{h2}: {len(positions)} positions, first=({positions[0]['low_idx']},{positions[0]['high_idx']}), last=({positions[-1]['low_idx']},{positions[-1]['high_idx']})")

    print_strand_info(part, "After helix creation")

    # === H0-H1: Half crossovers at edges ===
    sugg01 = m.suggestCrossovers(0, 1, "scaffold")
    positions01 = sugg01['positions']
    left_pair_01 = positions01[0]    # left edge: low=1, high=2
    right_pair_01 = positions01[-1]  # right edge: low=116, high=117

    # LEFT side: Create double crossover, then remove left (Low) half → RIGHT half remains
    print(f"\n=== H0-H1 LEFT side: double at ({left_pair_01['low_idx']},{left_pair_01['high_idx']}), then remove Low ===")
    r = m.createCrossover(0, left_pair_01['low_idx'], 1, left_pair_01['low_idx'], "scaffold")
    print(f"  Double: {r}")
    print_strand_info(part, "After H0-H1 left double xover")

    # Remove the Low (left) half to leave only the High (right) half
    r = m.removeCrossover(0, left_pair_01['low_idx'], "scaffold")
    print(f"  Remove Low half: {r}")
    print_strand_info(part, "After removing Low half (right half remains)")

    # RIGHT side: Create double crossover, then remove right (High) half → LEFT half remains
    print(f"\n=== H0-H1 RIGHT side: double at ({right_pair_01['low_idx']},{right_pair_01['high_idx']}), then remove High ===")
    r = m.createCrossover(0, right_pair_01['low_idx'], 1, right_pair_01['low_idx'], "scaffold")
    print(f"  Double: {r}")

    # Remove the High (right) half to leave only the Low (left) half
    r = m.removeCrossover(0, right_pair_01['high_idx'], "scaffold")
    print(f"  Remove High half: {r}")
    print_strand_info(part, "After H0-H1 both edges done")

    # === H1-H2: Double crossover at midpoint ===
    sugg12 = m.suggestCrossovers(1, 2, "scaffold")
    positions12 = sugg12['positions']
    mid_pos = positions12[len(positions12) // 2]
    print(f"\n=== H1-H2: double crossover at ({mid_pos['low_idx']},{mid_pos['high_idx']}) ===")
    r = m.addCrossoversForPair(1, 2, "scaffold",
                                positions=[mid_pos['low_idx']],
                                crossover_type="double")
    print(f"  Result: {r}")
    print_strand_info(part, "After H1-H2 double xover")

    # === H2-H3: Half crossovers at edges ===
    sugg23 = m.suggestCrossovers(2, 3, "scaffold")
    positions23 = sugg23['positions']
    left_pair_23 = positions23[0]    # left edge
    right_pair_23 = positions23[-1]  # right edge

    # LEFT side: double then remove Low → RIGHT half remains
    print(f"\n=== H2-H3 LEFT side: double at ({left_pair_23['low_idx']},{left_pair_23['high_idx']}), then remove Low ===")
    r = m.createCrossover(2, left_pair_23['low_idx'], 3, left_pair_23['low_idx'], "scaffold")
    print(f"  Double: {r}")
    r = m.removeCrossover(2, left_pair_23['low_idx'], "scaffold")
    print(f"  Remove Low half: {r}")

    # RIGHT side: double then remove High → LEFT half remains
    print(f"\n=== H2-H3 RIGHT side: double at ({right_pair_23['low_idx']},{right_pair_23['high_idx']}), then remove High ===")
    r = m.createCrossover(2, right_pair_23['low_idx'], 3, right_pair_23['low_idx'], "scaffold")
    print(f"  Double: {r}")
    r = m.removeCrossover(2, right_pair_23['high_idx'], "scaffold")
    print(f"  Remove High half: {r}")

    print_strand_info(part, "After all crossovers")

    # Clean up orphan fragments
    print("\nCleaning orphan fragments...")
    for h in range(4):
        vh = part.virtualHelix(h)
        ss = vh.scaffoldStrandSet()
        for strand in list(ss):
            lo, hi = strand.idxs()
            length = hi - lo + 1
            conn_lo = strand.connectionLow()
            conn_hi = strand.connectionHigh()
            if conn_lo is None and conn_hi is None and length < 10:
                print(f"  Deleting orphan on H{h}: [{lo},{hi}] (len={length})")
                strand.strandSet().removeStrand(strand, useUndoStack=True)

    print_strand_info(part, "Final state (after cleanup)")

    # Save as cadnano JSON for PI to open in GUI
    outdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'results')
    os.makedirs(outdir, exist_ok=True)

    json_path = os.path.join(outdir, '4helix-flat-sheet.json')
    helixOrderList = dc.win.pathroot.getSelectedPartOrderedVHList()
    if helixOrderList:
        from cadnano2.model.io.encoder import encode
        with open(json_path, 'w') as f:
            encode(doc, helixOrderList, f)
        print(f"\nSaved JSON: {json_path}")

    # Render screenshot
    image = render_pathview(dc)
    outpath = os.path.join(outdir, 'obj-028-4helix-sheet-v3.png')
    image.save(outpath)
    print(f"Saved PNG: {outpath}")


if __name__ == '__main__':
    main()
