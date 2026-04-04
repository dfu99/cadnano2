#!/usr/bin/env python
"""
Generate path view screenshots of valid vs invalid scaffold routing examples.
Uses existing example designs and also creates programmatic examples.

Outputs clean PNGs (white background, no annotations) for Illustrator import.

Usage:
    QT_QPA_PLATFORM=offscreen python -m tools.gen_scaffold_routing_fig
"""
import os
import sys
import io

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLES_DIR = os.path.join(PROJECT_ROOT, 'examples')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results', 'scaffold_routing')


def screenshot_path_view(dc, output_path, scale=3.0, max_width=3000):
    """Capture the cadnano path view as a white-background PNG."""
    from PyQt6.QtCore import QMarginsF, QRectF
    from PyQt6.QtGui import QImage, QPainter, QColor

    ps = dc.win.pathscene
    pr = ps.itemsBoundingRect()
    if pr.isEmpty():
        pr = QRectF(0, 0, 1600, 400)
    pr = pr.marginsAdded(QMarginsF(30, 30, 30, 30))

    pw, ph = int(pr.width() * scale), int(pr.height() * scale)
    if pw > max_width:
        scale *= max_width / pw
        pw = int(pr.width() * scale)
        ph = int(pr.height() * scale)

    img = QImage(pw, ph, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(255, 255, 255))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    ps.render(painter, source=pr)
    painter.end()
    img.save(output_path)


def load_design(app, json_path):
    """Load a cadnano JSON and return (dc, scaffold_count, staple_count)."""
    from cadnano2.model.io.decoder import decode

    dc = list(app.documentControllers)[0]
    dc.newDocument()
    doc = dc.document()

    with io.open(json_path, 'r', encoding='utf-8') as fd:
        decode(doc, fd.read())

    part = doc.selectedPart()
    scaf = [o for o in part.oligos() if not o.isStaple()]
    stap = [o for o in part.oligos() if o.isStaple()]
    n_helices = len(list(part.getVirtualHelices()))
    scaf_len = sum(o.length() for o in scaf)

    return dc, len(scaf), len(stap), n_helices, scaf_len


def create_fragmented_routing(app):
    """Create a design with helices and crossovers but fragmented scaffold."""
    dc = list(app.documentControllers)[0]
    dc.newDocument()
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    class MockDC:
        def __init__(self, a, d, p):
            self._app, self._doc, self._part = a, d, p
        def document(self): return self._doc
        def activePart(self): return self._part
        def undoStack(self): return self._doc.undoStack()

    from cadnano2.views.agent.agentmethods import AgentMethods
    mock = MockDC(app, doc, part)
    methods = AgentMethods(mock)

    # 1×6 flat sheet with dense crossovers (produces many scaffold fragments)
    positions = [[15, 10+i] for i in range(6)]
    methods.createHelicesWithStrands(positions=positions, strand_type="both", length=126)
    methods.addAllNeighborCrossovers("scaffold")
    methods.addAllNeighborCrossovers("staple")

    scaf = [o for o in part.oligos() if not o.isStaple()]
    return dc, len(scaf)


def create_missing_crossovers(app):
    """Create a design with helices and strands but NO crossovers."""
    dc = list(app.documentControllers)[0]
    dc.newDocument()
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    class MockDC:
        def __init__(self, a, d, p):
            self._app, self._doc, self._part = a, d, p
        def document(self): return self._doc
        def activePart(self): return self._part
        def undoStack(self): return self._doc.undoStack()

    from cadnano2.views.agent.agentmethods import AgentMethods
    mock = MockDC(app, doc, part)
    methods = AgentMethods(mock)

    positions = [[15, 10+i] for i in range(6)]
    methods.createHelicesWithStrands(positions=positions, strand_type="scaffold", length=126)

    scaf = [o for o in part.oligos() if not o.isStaple()]
    return dc, len(scaf)


def main():
    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()

    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Collect all designs: (name, source, is_valid)
    designs = []

    # --- Valid routing examples from files ---
    for fn in sorted(os.listdir(EXAMPLES_DIR)):
        if fn.startswith('validScaffoldRouting') and fn.endswith('.json'):
            designs.append((fn.replace('.json', ''), os.path.join(EXAMPLES_DIR, fn), True))

    # --- Known good designs ---
    for fn in ['2x4.json', '2x6.json', '2x8.json']:
        path = os.path.join(EXAMPLES_DIR, fn)
        if os.path.exists(path):
            designs.append((fn.replace('.json', ''), path, None))  # verify at load

    # --- Invalid routing examples from files ---
    for fn in sorted(os.listdir(EXAMPLES_DIR)):
        if fn.startswith('invalidScaffoldRouting') and fn.endswith('.json'):
            designs.append((fn.replace('.json', ''), os.path.join(EXAMPLES_DIR, fn), False))

    # --- Programmatic invalid examples ---
    designs.append(('fragmented_dense_xovers', 'PROGRAMMATIC_FRAGMENTED', False))
    designs.append(('no_crossovers', 'PROGRAMMATIC_NO_XOVERS', False))

    print(f"Processing {len(designs)} designs...\n")

    for name, source, expected_valid in designs:
        print(f"{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}")

        try:
            if source == 'PROGRAMMATIC_FRAGMENTED':
                dc, n_scaf = create_fragmented_routing(app)
                n_stap = 0
                n_helices = 6
                scaf_len = 0
            elif source == 'PROGRAMMATIC_NO_XOVERS':
                dc, n_scaf = create_missing_crossovers(app)
                n_stap = 0
                n_helices = 6
                scaf_len = 0
            else:
                dc, n_scaf, n_stap, n_helices, scaf_len = load_design(app, source)

            is_valid = (n_scaf == 1)
            status = "VALID" if is_valid else "INVALID"
            print(f"  Scaffold oligos: {n_scaf} → {status}")
            print(f"  Helices: {n_helices}, Staples: {n_stap}")

            # Screenshot
            prefix = "valid" if is_valid else "invalid"
            out_path = os.path.join(RESULTS_DIR, f'{prefix}_{name}.png')
            screenshot_path_view(dc, out_path)
            print(f"  Screenshot: {out_path}")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"  Done. Output in {RESULTS_DIR}/")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
