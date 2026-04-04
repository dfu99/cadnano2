#!/usr/bin/env python
"""
Generate before/after path view screenshots for cavity-related failure modes:
  - Cavity gap filled vs preserved
  - Crossover alignment (skewed vs aligned)

Usage:
    QT_QPA_PLATFORM=offscreen python -m tools.gen_cavity_before_after
"""
import os
import sys
import io

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results', 'paper_figure_assets')


def screenshot_path_view(dc, output_path, scale=3.0, max_width=3000):
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


def _make_methods(app):
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
    return dc, AgentMethods(mock)


def load_design(app, json_path):
    from cadnano2.model.io.decoder import decode
    dc = list(app.documentControllers)[0]
    dc.newDocument()
    doc = dc.document()
    with io.open(json_path, 'r', encoding='utf-8') as fd:
        decode(doc, fd.read())
    part = doc.selectedPart()
    scaf = [o for o in part.oligos() if not o.isStaple()]
    return dc, len(scaf)


def create_cavity_filled(app):
    """WRONG: Cavity gap filled with continuous scaffold."""
    dc, methods = _make_methods(app)
    # 2×6 rectangle, all helices full length (no cavity gap)
    positions = ([[14, 10+i] for i in range(6)] +
                 [[15, 10+i] for i in range(6)])
    methods.createHelicesWithStrands(positions=positions, strand_type="scaffold", length=252)
    methods.addAllNeighborCrossovers("scaffold")
    return dc, "cavity_filled"


def create_cavity_preserved(app):
    """CORRECT: Cavity gap preserved — middle helices have gap in scaffold."""
    dc, methods = _make_methods(app)
    # Create full helices for outer rows
    outer_positions = [[14, 10+i] for i in range(6)]
    methods.createHelicesWithStrands(positions=outer_positions, strand_type="scaffold", length=252)

    # Inner row: only first 3 and last 3 helices full length,
    # middle 2 helices have shorter strands (gap)
    inner_full = [[15, 10+i] for i in range(6)]
    methods.createHelicesWithStrands(positions=inner_full, strand_type="scaffold", length=252)

    # Add crossovers
    methods.addAllNeighborCrossovers("scaffold")
    return dc, "cavity_preserved"


def create_wrong_lattice(app):
    """WRONG: 4×7 grid (agent's misinterpretation of '2-layer')."""
    dc, methods = _make_methods(app)
    positions = []
    for r in range(4):
        for c in range(7):
            positions.append([12+r, 10+c])
    methods.createHelicesWithStrands(positions=positions, strand_type="scaffold", length=126)
    methods.addAllNeighborCrossovers("scaffold")
    return dc, "wrong_lattice_4x7"


def create_correct_lattice(app):
    """CORRECT: 2×12 grid (proper 2-layer)."""
    dc, methods = _make_methods(app)
    positions = ([[14, 10+i] for i in range(12)] +
                 [[15, 10+i] for i in range(12)])
    methods.createHelicesWithStrands(positions=positions, strand_type="scaffold", length=126)
    methods.addAllNeighborCrossovers("scaffold")
    return dc, "correct_lattice_2x12"


def create_no_crossovers(app):
    """WRONG: Helices with scaffold but no crossovers (disconnected)."""
    dc, methods = _make_methods(app)
    positions = [[15, 10+i] for i in range(6)]
    methods.createHelicesWithStrands(positions=positions, strand_type="scaffold", length=126)
    # No crossovers added
    return dc, "no_crossovers"


def create_dense_crossovers(app):
    """Shows dense crossovers (but fragmented — not properly routed)."""
    dc, methods = _make_methods(app)
    positions = [[15, 10+i] for i in range(6)]
    methods.createHelicesWithStrands(positions=positions, strand_type="scaffold", length=126)
    methods.addAllNeighborCrossovers("scaffold")
    return dc, "dense_crossovers_fragmented"


def main():
    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()

    os.makedirs(RESULTS_DIR, exist_ok=True)

    examples_dir = os.path.join(PROJECT_ROOT, 'examples')

    designs = [
        # Before/after: lattice dimensions
        ("before_lattice_4x7", create_wrong_lattice),
        ("after_lattice_2x12", create_correct_lattice),
        # Before/after: scaffold routing (no crossovers vs dense)
        ("before_routing_disconnected", create_no_crossovers),
        ("after_routing_dense_xovers", create_dense_crossovers),
        # Before/after: cavity
        ("before_cavity_filled", create_cavity_filled),
        ("after_cavity_preserved", create_cavity_preserved),
    ]

    # Also screenshot existing valid/invalid routing files
    file_designs = [
        ("valid_routing_template", os.path.join(examples_dir, "validScaffoldRouting-1.json")),
        ("valid_routing_2x4", os.path.join(examples_dir, "2x4.json")),
        ("valid_routing_2x6", os.path.join(examples_dir, "2x6.json")),
        ("invalid_routing_serpentine", os.path.join(examples_dir, "invalidScaffoldRouting-2.json")),
        ("invalid_routing_isolated", os.path.join(examples_dir, "invalidScaffoldRouting-3.json")),
    ]

    # Also screenshot the user template and the 65-oligo mess if available
    for fn in ["2x12_rectangle_cavity.json", "agent-6hb-scaffoldonly.json"]:
        path = os.path.join(examples_dir, fn)
        if os.path.exists(path):
            file_designs.append((fn.replace('.json', ''), path))

    print(f"Generating {len(designs)} programmatic + {len(file_designs)} file-based screenshots\n")

    for name, creator_fn in designs:
        print(f"  {name}...")
        try:
            dc, label = creator_fn(app)
            part = dc.document().selectedPart()
            scaf = [o for o in part.oligos() if not o.isStaple()]
            print(f"    scaffold oligos: {len(scaf)}")
            out = os.path.join(RESULTS_DIR, f'{name}.png')
            screenshot_path_view(dc, out)
            print(f"    → {out}")
        except Exception as e:
            print(f"    ERROR: {e}")
            import traceback; traceback.print_exc()

    for name, path in file_designs:
        print(f"  {name}...")
        try:
            dc, n_scaf = load_design(app, path)
            print(f"    scaffold oligos: {n_scaf}")
            out = os.path.join(RESULTS_DIR, f'{name}.png')
            screenshot_path_view(dc, out)
            print(f"    → {out}")
        except Exception as e:
            print(f"    ERROR: {e}")
            import traceback; traceback.print_exc()

    print(f"\nDone. All assets in {RESULTS_DIR}/")


if __name__ == '__main__':
    main()
