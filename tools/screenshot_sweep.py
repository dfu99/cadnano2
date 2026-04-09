#!/usr/bin/env python
"""Screenshot cavity sweep designs and verify in cadnano."""
import os, sys, io, json
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cadnano2.cadnano as cadnano
app = cadnano.initAppWithGui()

# Import Qt AFTER app init
from cadnano2.model.io.decoder import decode
from PyQt6.QtCore import QRectF, QMarginsF
from PyQt6.QtGui import QImage, QPainter, QColor

dc = list(app.documentControllers)[0]

outdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'results', 'cavity_sweep')

designs = [
    'cavity_40x26nm_2x22_pad6',
    'cavity_45x26nm_2x22_pad6',
    'cavity_50x26nm_2x22_pad6',
]

for name in designs:
    json_path = os.path.join(outdir, name + '.json')
    if not os.path.exists(json_path):
        print(f'{name}: NOT FOUND')
        continue

    dc.newDocument()
    doc = dc.document()
    with io.open(json_path, 'r', encoding='utf-8') as fd:
        decode(doc, fd.read())

    part = doc.selectedPart()
    scaffold_oligos = [o for o in part.oligos() if not o.isStaple()]
    scaf_count = len(scaffold_oligos)
    scaf_bp = sum(o.length() for o in scaffold_oligos)
    starts = sum(1 for o in scaffold_oligos if o.strand5p().connection5p() is None)
    status = 'VERIFIED' if starts == 0 else f'BROKEN({starts})'
    print(f'{name}: {scaf_count} oligo(s), {scaf_bp}bp, {status}')

    scene = dc.win.pathscene
    rect = scene.itemsBoundingRect()
    if rect.isEmpty():
        rect = QRectF(0, 0, 1600, 400)
    rect = rect.marginsAdded(QMarginsF(30, 30, 30, 30))

    scale = 2.0
    w, h = int(rect.width() * scale), int(rect.height() * scale)
    if w > 6000:
        scale *= 6000 / w
        w, h = int(rect.width() * scale), int(rect.height() * scale)

    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(p, source=rect)
    p.end()

    png_path = os.path.join(outdir, name + '.png')
    img.save(png_path)
    print(f'  Screenshot: {png_path} ({w}x{h})')
