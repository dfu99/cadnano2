#!/usr/bin/env python
"""Test serpentine: create correctly-sized strands and connect directly."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import cadnano2.cadnano as cadnano
app = cadnano.initAppWithGui()
from cadnano2.views.agent.agentmethods import AgentMethods
from cadnano2.model.parts.honeycombpart import Crossovers
from cadnano2.model.strand import Strand
from cadnano2.model.oligo import Oligo
import cadnano2.util as util
from math import ceil

dc = list(app.documentControllers)[0]
dc.actionAddHoneycombPartSlot()
doc = dc.document()
part = doc.selectedPart()

class MockDC:
    def __init__(self, a, d, p): self._app, self._doc, self._part = a, d, p
    def document(self): return self._doc
    def activePart(self): return self._part
    def undoStack(self): return self._doc.undoStack()

m = AgentMethods(MockDC(app, doc, part))

HELIX_LENGTH = 126
STEP = 21

# Extend part size
step = part.stepSize()
if HELIX_LENGTH - 1 > part.maxBaseIdx():
    delta = int(ceil((HELIX_LENGTH - 1 - part.maxBaseIdx()) / step)) * step
    part.resizeVirtualHelices(0, delta, useUndoStack=True)

# Create 4 helices (empty)
for i in range(4):
    part.createVirtualHelix(21, 4 + i, useUndoStack=True)

helices = sorted(part.getVirtualHelices(), key=lambda vh: vh.coord()[1])
for vh in helices:
    print(f"Helix {vh.number()} at {vh.coord()}, even={vh.isEvenParity()}")
n = len(helices)

# Get crossover positions
def get_valid_xover_positions(part, vh1, vh2, max_idx):
    neighbors = part.getVirtualHelixNeighbors(vh1)
    if vh2 not in neighbors:
        return []
    direction_idx = neighbors.index(vh2)
    low_offsets = Crossovers.honeycombScafLow[direction_idx]
    high_offsets = Crossovers.honeycombScafHigh[direction_idx]
    positions = []
    for base in range(0, max_idx + 1, STEP):
        for low_off, high_off in zip(low_offsets, high_offsets):
            low_idx = base + low_off
            high_idx = base + high_off
            if 0 <= low_idx <= max_idx and 0 <= high_idx <= max_idx:
                positions.append({'low_idx': low_idx, 'high_idx': high_idx})
    return positions

# Determine turn crossover positions
xover_positions = []
for i in range(n - 1):
    vh1, vh2 = helices[i], helices[i + 1]
    all_pos = get_valid_xover_positions(part, vh1, vh2, HELIX_LENGTH - 1)
    if vh1.isEvenParity():
        turn = all_pos[-1]
    else:
        turn = all_pos[0]
    xover_positions.append(turn)
    print(f"  Turn {vh1.number()}-{vh2.number()}: low={turn['low_idx']}, high={turn['high_idx']}")

# Determine strand ranges for each helix
strand_ranges = []
for i in range(n):
    vh = helices[i]
    if i == 0:
        xo = xover_positions[0]['low_idx']
        if vh.isEvenParity():
            strand_ranges.append((0, xo))
        else:
            strand_ranges.append((xo, HELIX_LENGTH - 1))
    elif i == n - 1:
        xo = xover_positions[-1]['low_idx']
        if vh.isEvenParity():
            strand_ranges.append((xo, HELIX_LENGTH - 1))
        else:
            strand_ranges.append((0, xo))
    else:
        xo_prev = xover_positions[i - 1]['low_idx']
        xo_next = xover_positions[i]['low_idx']
        lo = min(xo_prev, xo_next)
        hi = max(xo_prev, xo_next)
        strand_ranges.append((lo, hi))

for i, (vh, (lo, hi)) in enumerate(zip(helices, strand_ranges)):
    print(f"  Helix {vh.number()}: scaffold [{lo}:{hi}] len={hi-lo+1}")

# Create scaffold strands
for vh, (lo, hi) in zip(helices, strand_ranges):
    scaf_ss = vh.scaffoldStrandSet()
    scaf_ss.createStrand(lo, hi, useUndoStack=True)

# Now directly connect strands at their endpoints using setConnection
print("\nConnecting strands directly...")
for i in range(n - 1):
    vh1, vh2 = helices[i], helices[i + 1]
    xover_idx = xover_positions[i]['low_idx']

    scaf1 = vh1.scaffoldStrandSet().getStrand(xover_idx)
    scaf2 = vh2.scaffoldStrandSet().getStrand(xover_idx)

    if scaf1 is None or scaf2 is None:
        print(f"  ERROR: No strand at xover idx {xover_idx} on h{vh1.number()} or h{vh2.number()}")
        continue

    # Determine which strand is 5p and which is 3p at this crossover
    # The strand ending its 3' at this position is the 5p strand
    # The strand starting its 5' at this position is the 3p strand

    # For even parity: scaffold 5' at low, 3' at high (drawn 5to3)
    # For odd parity: scaffold 5' at high, 3' at low (drawn 3to5)
    lo1, hi1 = scaf1.idxs()
    lo2, hi2 = scaf2.idxs()

    # Strand that has its 3' end at xover_idx is the 5p strand
    is_3p_end_1 = (vh1.isEvenParity() and hi1 == xover_idx) or \
                  (not vh1.isEvenParity() and lo1 == xover_idx)
    is_5p_end_2 = (vh2.isEvenParity() and lo2 == xover_idx) or \
                  (not vh2.isEvenParity() and hi2 == xover_idx)

    if is_3p_end_1 and is_5p_end_2:
        strand5p, strand3p = scaf1, scaf2
    else:
        # Try the other way
        is_3p_end_2 = (vh2.isEvenParity() and hi2 == xover_idx) or \
                      (not vh2.isEvenParity() and lo2 == xover_idx)
        is_5p_end_1 = (vh1.isEvenParity() and lo1 == xover_idx) or \
                      (not vh1.isEvenParity() and hi1 == xover_idx)
        if is_3p_end_2 and is_5p_end_1:
            strand5p, strand3p = scaf2, scaf1
        else:
            print(f"  ERROR: Can't determine 5p/3p for h{vh1.number()}-h{vh2.number()}")
            print(f"    h{vh1.number()} even={vh1.isEvenParity()} [{lo1}:{hi1}]")
            print(f"    h{vh2.number()} even={vh2.isEvenParity()} [{lo2}:{hi2}]")
            continue

    # Connect using CreateXoverCommand approach
    olg5p = strand5p.oligo()
    olg3p = strand3p.oligo()

    # Merge oligos: the 5p oligo absorbs the 3p oligo
    if olg5p != olg3p:
        olg5p.incrementLength(olg3p.length())
        olg3p.removeFromPart()
        for s in strand3p.generator3pStrand():
            Strand.setOligo(s, olg5p)

    # Install crossover
    strand5p.setConnection3p(strand3p)
    strand3p.setConnection5p(strand5p)

    print(f"  Connected h{vh1.number()}[{lo1}:{hi1}] <-> h{vh2.number()}[{lo2}:{hi2}] at idx {xover_idx}")

# Final state
print("\nFinal scaffold oligos:")
scaf_count = 0
for o in part.oligos():
    if not o.isStaple():
        scaf_count += 1
        strands = []
        for s in o.strand5p().generator3pStrand():
            vh_num = s.virtualHelix().number()
            lo, hi = s.idxs()
            strands.append(f"h{vh_num}[{lo}:{hi}]")
        print(f"  Oligo len={o.length()}: {' -> '.join(strands)}")
print(f"\nTotal scaffold oligos: {scaf_count}")
