#!/usr/bin/env python
"""Screenshot a design showing only scaffold (hide staples)."""
import os, sys, io
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import cadnano2.cadnano as cadnano
app = cadnano.initAppWithGui()
from cadnano2.model.io.decoder import decode
from cadnano2.views.sliceview.partitem import PartItem
from cadnano2.views.sliceview.emptyhelixitem import EmptyHelixItem
from PyQt6.QtCore import QMarginsF, QRectF
from PyQt6.QtGui import QImage, QPainter, QColor

input_json = sys.argv[1]
output_prefix = sys.argv[2]

dc = list(app.documentControllers)[0]
doc = dc.document()
with io.open(input_json, 'r') as fd:
    decode(doc, fd.read())

part = doc.selectedPart()
scaf = [o for o in part.oligos() if not o.isStaple()]
stap = [o for o in part.oligos() if o.isStaple()]
vhs = list(part.getVirtualHelices())
print(f'{len(vhs)} helices, {len(scaf)} scaf, {len(stap)} stap')

# Hide staple strands in the path view
ps = dc.win.pathscene
from cadnano2.views.pathview.strand.stranditem import StrandItem
hidden = []
for item in ps.items():
    if isinstance(item, StrandItem):
        strand = item.strand()
        oligo = strand.oligo()
        if oligo.isStaple():
            item.setVisible(False)
            hidden.append(item)
print(f'Hidden {len(hidden)} staple strand items')

# Slice view - active only
ss = dc.win.slicescene
part_items = [item for item in ss.items() if isinstance(item, PartItem)]
hidden_empty = []
if part_items:
    for item in ss.items():
        if isinstance(item, EmptyHelixItem) and not item.childItems():
            item.setVisible(False)
            hidden_empty.append(item)
    active = list(part_items[0]._virtualHelixHash.values())
    if active:
        ur = None
        for vhi in active:
            r = vhi.mapToScene(vhi.boundingRect()).boundingRect()
            ur = r if ur is None else ur.united(r)
        sr = ur.marginsAdded(QMarginsF(5, 5, 5, 5))
    else:
        sr = ss.itemsBoundingRect()
else:
    sr = ss.itemsBoundingRect()

sc = 4.0
sw, sh = int(sr.width() * sc), int(sr.height() * sc)
if sw > 2000:
    sc *= 2000 / sw
    sw, sh = int(sr.width() * sc), int(sr.height() * sc)
si = QImage(sw, sh, QImage.Format.Format_ARGB32_Premultiplied)
si.fill(QColor(255, 255, 255))
p = QPainter(si)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
ss.render(p, source=sr)
p.end()
si.save(f'{output_prefix}_slice.png')
print(f'Slice: {output_prefix}_slice.png ({sw}x{sh})')

# Path view
pr = ps.itemsBoundingRect()
pr = pr.marginsAdded(QMarginsF(30, 30, 30, 30))
pc = 3.0
pw, ph = int(pr.width() * pc), int(pr.height() * pc)
if pw > 4000:
    pc *= 4000 / pw
    pw, ph = int(pr.width() * pc), int(pr.height() * pc)
pi2 = QImage(pw, ph, QImage.Format.Format_ARGB32_Premultiplied)
pi2.fill(QColor(255, 255, 255))
p2 = QPainter(pi2)
p2.setRenderHint(QPainter.RenderHint.Antialiasing)
ps.render(p2, source=pr)
p2.end()
pi2.save(f'{output_prefix}_path.png')
print(f'Path: {output_prefix}_path.png ({pw}x{ph})')
