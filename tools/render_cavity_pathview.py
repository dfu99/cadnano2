#!/usr/bin/env python
"""Render a cadnano JSON file to a path view screenshot. Single-file mode only."""
import os, sys, io
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
MAX_DIM = 1800

def main():
    json_path = sys.argv[1]
    out_path = sys.argv[2]
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()
    from cadnano2.model.io.decoder import decode
    from PyQt6.QtCore import QMarginsF, QRectF
    from PyQt6.QtGui import QImage, QPainter, QColor
    dc = list(app.documentControllers)[0]
    doc = dc.document()
    with io.open(json_path, 'r', encoding='utf-8') as fd:
        decode(doc, fd.read())
    part = doc.selectedPart()
    scaf_oligos = [o for o in part.oligos() if not o.isStaple()]
    total_bp = sum(o.length() for o in scaf_oligos)
    n_oligos = len(scaf_oligos)
    print(f'  Scaffold: {total_bp}bp in {n_oligos} oligo(s)', flush=True)
    scene = dc.win.pathscene
    rect = scene.itemsBoundingRect()
    if rect.isEmpty(): rect = QRectF(0, 0, 1600, 400)
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
    img.save(out_path)
    print(f'  Screenshot: {out_path} ({w}x{h}px)', flush=True)

if __name__ == '__main__':
    main()
