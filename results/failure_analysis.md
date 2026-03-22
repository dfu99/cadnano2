# Failure Analysis: AI-Assisted Parametric DNA Origami Design

## Overview

This document records the failure modes, root causes, and fixes discovered
during AI-assisted parametric DNA origami design. Each failure represents
a domain knowledge gap that the AI agent encountered and that required
human expert (PI) intervention to resolve.

The verifier at `tools/cadnano_verifier.py` catches all of these failures
automatically, enabling faster iteration for future users.

---

## Failure 1: Scaffold Direction from Shifted References

**Symptom:** cadnano hangs when loading the JSON file.
**Root cause:** When extending helix arrays (step2), the gap-fill code
determined scaffold direction by reading the 3' reference of the last
occupied position. But this reference had already been shifted rightward,
pointing to position 296 instead of 170. The fill used the wrong direction
for even helices.
**Fix:** Always use helix parity to determine direction:
- Even (num%2==0) → scaffold goes right: `[num, i-1, num, i+1]`
- Odd (num%2==1) → scaffold goes left: `[num, i+1, num, i-1]`
**Verifier check:** `verify_scaffold_directions()`

## Failure 2: Extra Cavity Section (Double Gap)

**Symptom:** PI visually identified an extra cavity section in the design.
**Root cause:** `step2_extend` shifted the right side of the scaffold data
but skipped gap-filling for cavity helices entirely. This left TWO gaps:
the original cavity gap AND the extension gap.
**Fix:** Fill the extension gap for cavity helices too (only skip the
actual cavity gap region, not the extension).
**Verifier check:** `verify_cavity_gaps()`

## Failure 3: Crossover on EMPTY Position

**Symptom:** Cavity boundary crossovers missing; scaffold fragmented.
**Root cause:** `step4_set_cavity_width` tried to place crossovers at
positions that were EMPTY (inside the original cavity gap). The code
`if sa[pos] != EMPTY` silently skipped the crossover placement.
**Fix:** Create a scaffold entry at the position first, then place the
crossover.
**Verifier check:** `verify_crossover_symmetry()`

## Failure 4: Spurious Midseam on Last Pair

**Symptom:** Scaffold split into 2 oligos (was 1 in template).
**Root cause:** `step3_move_midseam` iterated all non-cavity row 13 pairs,
including H22-H23 (the last pair). This pair should have ONLY edge
crossovers — it connects the two scaffold halves. The function removed a
non-existent old seam (no-op) but ADDED a new one.
**Fix:** Exclude `LAST_PAIR = (22, 23)` from the midseam move loop.
**Verifier check:** `verify_last_pair()`

## Failure 5: Right Boundary Expansion Destroys Left Boundary

**Symptom:** Left cavity boundary crossover missing after step4.
**Root cause:** When the original right boundary (position 163) was to the
LEFT of the new left boundary (173), the right-side "expand gap" code
cleared positions 163-224, destroying the left boundary crossover at 173.
**Fix:** Don't clear during right boundary expansion; use the post-step
gap-clearing instead.
**Verifier check:** `verify_crossover_symmetry()`

## Failure 6: Edge Crossover Destroyed by Boundary Search

**Symptom:** Scaffold fragmented into 4+ oligos for wider cavity designs.
**Root cause:** For newly-converted cavity pairs (e.g., H2-H3 expanding
from 4-column to 8-column cavity), the left boundary search found the
EDGE crossover at position 5 (instead of the midseam crossover). The
`move_boundary` function then filled positions 5-173, overwriting the
edge crossover.
**Fix:** Skip edge positions when searching for cavity boundaries — only
look for crossovers after position 5 (R12) or 2 (R13).
**Verifier check:** `verify_segment_counts()` (destroyed edges create
odd segment counts)

## Failure 7: Stray Midseam Fragments in Gap

**Symptom:** Scaffold fragmented (tiny 2bp oligos in the cavity gap).
**Root cause:** The gap-clearing step preserved entries that referenced the
partner helix, thinking they were boundary crossovers. But they were
stray fragments of the original midseam crossovers.
**Fix:** Clear ALL entries inside the gap unconditionally — boundary
crossovers are AT the boundary positions (not inside the gap).
**Verifier check:** `verify_cavity_gaps()`

## Failure 8: From-Scratch Build (65 Scaffold Oligos)

**Symptom:** Designs built from scratch using `createXover` had 55-65
scaffold oligos instead of 1.
**Root cause:** `part.createXover()` splits strands at the crossover
position. Multiple crossovers placed in arbitrary order create many
small fragments that don't reconnect into a single loop.
**Fix:** NEVER build from scratch. Always modify the PI's template, which
has correct routing. The template gives 1 scaffold oligo for free — our
job is to scale and reshape without breaking it.
**Verifier check:** `verify_scaffold_connectivity()`

---

## Key Principles (Learned from Failures)

1. **Scaffold direction = helix parity.** Never derive direction from
   crossover references — they may have been shifted.
2. **Template-first.** The PI's template encodes domain knowledge that
   took years to develop. Modify it; don't rebuild from scratch.
3. **Verify before proceeding.** Run `cadnano_verifier.py` after every
   modification step. Don't proceed to autoStaple/oxDNA with a broken
   scaffold.
4. **Edge crossovers are sacred.** The edge crossovers at positions 5/2
   are the intra-pair connections that hold the scaffold loop together.
   Never overwrite them during cavity operations.
5. **The last pair is special.** It connects the two scaffold halves with
   edges only. Adding a midseam splits the scaffold.
