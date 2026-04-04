#!/usr/bin/env python
"""
Generate a 2x14 design as the agent would have produced BEFORE learning
scaffold routing rules. Uses only addAllNeighborCrossovers (dense but
fragmented) — no midseam pattern, no half-crossover placement rules.

This reproduces the early failure mode where the agent could place helices
and add crossovers but couldn't produce a single continuous scaffold.
"""
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import cadnano2.cadnano as cadnano
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

# Create 2x14 grid with both scaffold and staple strands
positions = ([[14, 4+i] for i in range(14)] +
             [[15, 4+i] for i in range(14)])
methods.createHelicesWithStrands(positions=positions, strand_type="both", length=252)

# Add crossovers the naive way — dense, no routing knowledge
methods.addAllNeighborCrossovers("scaffold")
methods.addAllNeighborCrossovers("staple")

# Count oligos
scaf = [o for o in part.oligos() if not o.isStaple()]
stap = [o for o in part.oligos() if o.isStaple()]
print(f'{len(list(part.getVirtualHelices()))} helices, {len(scaf)} scaffold oligos, {len(stap)} staple oligos')

# Save JSON
out_json = os.path.join(os.path.dirname(__file__), '..', 'drafts', 'paper_package',
                         'figures', 'abstract_components', 'early_2x14_naive.json')
dc.writeDocumentToFile(out_json)
print(f'Saved: {out_json}')

# Screenshot
from tools.screenshot_separate_views import *
