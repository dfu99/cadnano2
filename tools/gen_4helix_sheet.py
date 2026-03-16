#!/usr/bin/env python
"""
Generate a corrected flat 4-helix sheet screenshot.

PI correction: left half crossovers should use the High index (one position
to the right of the Low index). Right half crossovers are correct as-is.

Usage:
  QT_QPA_PLATFORM=offscreen python -m tools.gen_4helix_sheet
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
    print(f"Created helices: {result}")

    # Get suggested positions for each pair
    for h1, h2 in [(0, 1), (1, 2), (2, 3)]:
        sugg = m.suggestCrossovers(h1, h2, "scaffold")
        print(f"\nH{h1}-H{h2} suggestions:")
        if isinstance(sugg, dict):
            for p in sugg.get('positions', []):
                print(f"  low={p['low_idx']}, high={p['high_idx']}, "
                      f"edge={p.get('is_edge')}, turn={p.get('is_routing_turn')}")
            print(f"  routing_turn_idx: {sugg.get('routing_turn_idx')}")

    # H0-H1: Two half crossovers at edges
    # Left edge: use HIGH index (PI correction: one to the right)
    # Right edge: use LOW index (already correct per PI)
    sugg01 = m.suggestCrossovers(0, 1, "scaffold")
    positions01 = sugg01['positions']
    left01 = positions01[0]   # first position
    right01 = positions01[-1]  # last position

    # Left half crossover: use high_idx instead of low_idx
    left_idx_01 = left01['high_idx']
    # Right half crossover: use low_idx (correct per PI)
    right_idx_01 = right01['low_idx']

    print(f"\nH0-H1 half crossovers: left={left_idx_01}, right={right_idx_01}")
    r = m.createHalfCrossover(0, left_idx_01, 1, left_idx_01, "scaffold")
    print(f"  Left: {r}")
    r = m.createHalfCrossover(0, right_idx_01, 1, right_idx_01, "scaffold")
    print(f"  Right: {r}")

    # H1-H2: One double crossover at midpoint
    sugg12 = m.suggestCrossovers(1, 2, "scaffold")
    positions12 = sugg12['positions']
    mid_pos = positions12[len(positions12) // 2]
    print(f"\nH1-H2 double crossover at low={mid_pos['low_idx']}, high={mid_pos['high_idx']}")
    r = m.addCrossoversForPair(1, 2, "scaffold",
                                positions=[mid_pos['low_idx']],
                                crossover_type="double")
    print(f"  Result: {r}")

    # H2-H3: Two half crossovers at edges
    sugg23 = m.suggestCrossovers(2, 3, "scaffold")
    positions23 = sugg23['positions']
    left23 = positions23[0]
    right23 = positions23[-1]

    # Left half crossover: use high_idx (PI correction)
    left_idx_23 = left23['high_idx']
    # Right half crossover: use low_idx (correct per PI)
    right_idx_23 = right23['low_idx']

    print(f"\nH2-H3 half crossovers: left={left_idx_23}, right={right_idx_23}")
    r = m.createHalfCrossover(2, left_idx_23, 3, left_idx_23, "scaffold")
    print(f"  Left: {r}")
    r = m.createHalfCrossover(2, right_idx_23, 3, right_idx_23, "scaffold")
    print(f"  Right: {r}")

    # Clean up orphan fragments (strands disconnected by half crossovers)
    # Any short strand with no crossover connections is an orphan
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

    # Render screenshot
    image = render_pathview(dc)
    outdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'results')
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, 'obj-024-4helix-flat-sheet-corrected.png')
    image.save(outpath)
    print(f"\nSaved: {outpath}")


if __name__ == '__main__':
    main()
