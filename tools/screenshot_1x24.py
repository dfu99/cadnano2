#!/usr/bin/env python
"""Generate a 1x24 helix design and screenshot slice+path separately."""
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cadnano2.cadnano as cadnano
from PyQt6.QtCore import QMarginsF, QRectF
from PyQt6.QtGui import QImage, QPainter, QColor

app = cadnano.initAppWithGui()
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
methods = AgentMethods(MockDC(app, doc, part))

positions = [[15, 4+i] for i in range(24)]
methods.createHelicesWithStrands(positions=positions, strand_type="scaffold", length=126)

vhs = list(part.getVirtualHelices())
scaf = [o for o in part.oligos() if not o.isStaple()]
print(f'{len(vhs)} helices, {len(scaf)} scaffold oligos')

prefix = sys.argv[1] if len(sys.argv) > 1 else 'drafts/paper_package/figures/fig_1x24'

# Slice view - active helices only
from cadnano2.views.sliceview.partitem import PartItem
ss = dc.win.slicescene
part_items = [item for item in ss.items() if isinstance(item, PartItem)]
if part_items:
    active_items = list(part_items[0]._virtualHelixHash.values())
    union_rect = None
    for vhi in active_items:
        item_rect = vhi.mapToScene(vhi.boundingRect()).boundingRect()
        union_rect = item_rect if union_rect is None else union_rect.united(item_rect)
    sr = union_rect.marginsAdded(QMarginsF(15, 15, 15, 15))
else:
    sr = ss.itemsBoundingRect()

sc = 4.0
sw, sh = int(sr.width() * sc), int(sr.height() * sc)
if sw > 3000:
    sc *= 3000 / sw
    sw, sh = int(sr.width() * sc), int(sr.height() * sc)
si = QImage(sw, sh, QImage.Format.Format_ARGB32_Premultiplied)
si.fill(QColor(255, 255, 255))
p = QPainter(si)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
ss.render(p, source=sr)
p.end()
si.save(f'{prefix}_slice.png')
print(f'Slice: {prefix}_slice.png ({sw}x{sh})')

# Path view
ps = dc.win.pathscene
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
pi2.save(f'{prefix}_path.png')
print(f'Path: {prefix}_path.png ({pw}x{ph})')
