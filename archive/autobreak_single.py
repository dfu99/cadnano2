#!/usr/bin/env python
"""Run autobreak with specific parameters on a cadnano design."""
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

def main():
    import io, json, importlib, importlib.util

    input_json = sys.argv[1]
    name = sys.argv[2]
    min_leg = int(sys.argv[3])
    target = int(sys.argv[4])
    out_dir = sys.argv[5] if len(sys.argv) > 5 else 'results/autobreak_sweep'

    os.makedirs(out_dir, exist_ok=True)
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, base)
    # autobreak imports 'cadnano' but the package is 'cadnano2'
    import cadnano2
    sys.modules['cadnano'] = cadnano2

    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()

    # Load autobreak AFTER QApplication — use the package import path
    ab_pkg = os.path.join(base, 'cadnano2', 'plugins', 'autobreak')
    if ab_pkg not in sys.path:
        sys.path.insert(0, ab_pkg)
    # Import staplegraph first so autobreak's 'from . import staplegraph' can find it
    sg_spec = importlib.util.spec_from_file_location(
        'cadnano2.plugins.autobreak.staplegraph',
        os.path.join(ab_pkg, 'staplegraph.py'),
        submodule_search_locations=[])
    sg = importlib.util.module_from_spec(sg_spec)
    sys.modules['cadnano2.plugins.autobreak.staplegraph'] = sg
    sys.modules['staplegraph'] = sg  # for relative import fallback
    sg_spec.loader.exec_module(sg)

    ab_spec = importlib.util.spec_from_file_location(
        'cadnano2.plugins.autobreak.autobreak',
        os.path.join(ab_pkg, 'autobreak.py'),
        submodule_search_locations=[])
    ab_mod = importlib.util.module_from_spec(ab_spec)
    sys.modules['cadnano2.plugins.autobreak.autobreak'] = ab_mod
    ab_spec.loader.exec_module(ab_mod)

    from cadnano2.model.io.decoder import decode
    from cadnano2.model.io.encoder import encode
    from cadnano2.model.parts.part import Part
    from PyQt6.QtCore import QMarginsF, QRectF
    from PyQt6.QtGui import QImage, QPainter, QColor

    dc = list(app.documentControllers)[0]
    doc = dc.document()

    with io.open(input_json, 'r', encoding='utf-8') as fd:
        decode(doc, fd.read())

    part = doc.selectedPart()
    Part.autoStaple(part)
    stap_before = sum(1 for o in part.oligos() if o.isStaple())

    settings = {
        'minStapleLen': 18,
        'maxStapleLen': 50,
        'tgtStapleLen': target,
        'minStapleLegLen': min_leg,
    }

    unsolvable = 0
    for oligo in list(part.oligos()):
        if oligo.isStaple() and oligo.length() >= settings['minStapleLen']:
            try:
                ab_mod.nxBreakStaple(oligo, settings)
            except Exception:
                unsolvable += 1

    stap_after = sum(1 for o in part.oligos() if o.isStaple())
    lengths = sorted([o.length() for o in part.oligos() if o.isStaple()])

    result = {
        'name': name,
        'minStapleLegLen': min_leg,
        'tgtStapleLen': target,
        'staples_before': stap_before,
        'staples_after': stap_after,
        'min_len': min(lengths) if lengths else 0,
        'max_len': max(lengths) if lengths else 0,
        'avg_len': round(sum(lengths) / len(lengths), 1) if lengths else 0,
        'short_under_18': sum(1 for l in lengths if l < 18),
        'long_over_50': sum(1 for l in lengths if l > 50),
        'unsolvable': unsolvable,
    }

    print(json.dumps(result), flush=True)

    # Screenshot
    scene = dc.win.pathscene
    rect = scene.itemsBoundingRect()
    if rect.isEmpty():
        rect = QRectF(0, 0, 1600, 400)
    margin = 30
    rect = rect.marginsAdded(QMarginsF(margin, margin, margin, margin))
    scale = 2.0
    w = int(rect.width() * scale)
    h = int(rect.height() * scale)
    if w > 1800 or h > 1800:
        ratio = min(1800 / w, 1800 / h)
        scale *= ratio
        w = int(rect.width() * scale)
        h = int(rect.height() * scale)
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(255, 255, 255))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(painter, source=rect)
    painter.end()
    img.save(os.path.join(out_dir, f'screenshot_{name}.png'))

    helixOrderList = dc.win.pathroot.getSelectedPartOrderedVHList()
    if helixOrderList:
        with open(os.path.join(out_dir, f'design_{name}.json'), 'w') as f:
            encode(doc, helixOrderList, f)

if __name__ == '__main__':
    main()
