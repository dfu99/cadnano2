import os, sys, io
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import cadnano2.cadnano as cadnano
app = cadnano.initAppWithGui()
from cadnano2.model.io.decoder import decode
files = [
    'examples/2x4.json','examples/2x5.json','examples/2x6.json',
    'examples/2x8.json','examples/3x4.json',
    'examples/validScaffoldRouting-1.json','examples/validScaffoldRouting-2.json',
    'results/integrin_cavity/design_2x14.json',
    'results/integrin_cavity/design_2x16.json',
    'results/integrin_cavity/design_2x18.json',
    'results/integrin_cavity/design_2x20.json',
]
root = os.path.join(os.path.dirname(__file__), '..')
for f in files:
    fp = os.path.join(root, f)
    if not os.path.exists(fp): continue
    dc = list(app.documentControllers)[0]
    dc.newDocument()
    doc = dc.document()
    with io.open(fp, 'r') as fd: decode(doc, fd.read())
    part = doc.selectedPart()
    scaf = [o for o in part.oligos() if not o.isStaple()]
    stap = [o for o in part.oligos() if o.isStaple()]
    vhs = list(part.getVirtualHelices())
    bp = sum(o.length() for o in scaf)
    print(f'{os.path.basename(f):40s} {len(vhs):3d}h {len(scaf):2d}scaf {len(stap):4d}stap {bp:6d}bp')
