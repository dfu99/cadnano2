#!/usr/bin/env python
import os, sys, io
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import cadnano2.cadnano as cadnano
from cadnano2.model.io.decoder import decode
app = cadnano.initAppWithGui()

files = [
    'examples/2x4.json', 'examples/2x5.json', 'examples/2x5-2.json',
    'examples/2x6.json', 'examples/2x8.json',
    'examples/validScaffoldRouting-1.json', 'examples/validScaffoldRouting-2.json',
    'examples/14hb.json', 'examples/20hb.json', 'examples/3x4.json',
    'results/integrin_cavity/design_2x14.json',
    'results/integrin_cavity/design_2x16.json',
    'results/integrin_cavity/design_2x18.json',
    'results/integrin_cavity/design_2x20.json',
    'results/stress_test/6hb_scaffonly.json',
    'results/stress_test/rect_2x8_both.json',
]
# Also check stress_test for scaffold-only designs
import glob
for g in glob.glob('results/stress_test/*.json'):
    if g not in files:
        files.append(g)

for f in files:
    if not os.path.exists(f):
        continue
    try:
        dc = list(app.documentControllers)[0]
        dc.newDocument()
        doc = dc.document()
        with io.open(f, 'r') as fd:
            decode(doc, fd.read())
        part = doc.selectedPart()
        scaf = [o for o in part.oligos() if not o.isStaple()]
        stap = [o for o in part.oligos() if o.isStaple()]
        vhs = list(part.getVirtualHelices())
        bp = sum(o.length() for o in scaf)
        print(f'{os.path.basename(f):45s} {len(vhs):3d}h {len(scaf):3d}scaf {len(stap):4d}stap {bp:6d}bp')
    except Exception as e:
        print(f'{os.path.basename(f):45s} ERROR: {e}')
