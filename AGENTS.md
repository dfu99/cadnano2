# AGENTS.md — Bug Report for Codex

This document describes concrete, reproducible bugs in the cadnano2 agent methods layer.
The primary symptom is `fail-01.json`: a 6-helix (2×3) bundle where the scaffold has
**~40 crossovers** (should have ~6) and **all 6 helices have exposed 5' and 3' ends**
(should be zero — the scaffold should form a single closed loop).

---

## Problem 1 — Wrong method being called (agent behavior)

When prompted "create a 4-helix bundle with an 84bp scaffold routing", the Claude API
backend calls `addAllNeighborCrossovers` (or `addCrossoversForPair` for every neighbor pair)
instead of `planScaffoldRouting`.

`addAllNeighborCrossovers` creates **double crossovers (DX motifs)** between every
neighboring helix pair at every valid geometrical position (~every 11 bp). For a 2×3
grid this produces ~40 crossovers. The scaffold ends up broken into dozens of fragments,
none of which form a closed loop. All helices have exposed 5' and 3' ends.

**What the system prompt says:**
```
SCAFFOLD ROUTING for 2×N grids:
1. createHelicesWithStrands(num_helices=2N, strand_type="scaffold", length=L)
2. planScaffoldRouting()
3. verifyDesign()
```

The agent ignores this instruction. The instruction needs to be made more forceful or
the wrong methods need to be gated/removed from the tool list when scaffold routing is
the goal.

---

## Problem 2 — `deleteExposedFragments` crashes with AttributeError

**File:** `cadnano2/views/agent/agentmethods.py`
**Method:** `deleteExposedFragments` (around line 2601)

### The bug

```python
if strand.connectionLow():
    strand.connectionLow().remove(useUndoStack=True)   # ← WRONG
if strand.connectionHigh():
    strand.connectionHigh().remove(useUndoStack=True)  # ← WRONG
```

`strand.connectionLow()` and `strand.connectionHigh()` return a **Strand object**
(the neighboring strand), not a crossover/connection object. `Strand` has no `.remove()`
method. This raises:

```
AttributeError: 'Strand' object has no attribute 'remove'
```

### The correct API

To remove a crossover, use `part.removeXover(strand5p, strand3p, useUndoStack)`.

**How to find strand5p and strand3p:**
- `strand.connection3p()` — the Strand whose 5' end is connected to this strand's 3' end
- `strand.connection5p()` — the Strand whose 3' end is connected to this strand's 5' end
- `removeXover(strand5p, strand3p)` expects `strand5p.connection3p() == strand3p`

```python
# To remove the crossover at the 3' end of `strand`:
conn3p = strand.connection3p()
if conn3p is not None:
    part.removeXover(strand, conn3p, useUndoStack=True)

# To remove the crossover at the 5' end of `strand`:
conn5p = strand.connection5p()
if conn5p is not None:
    part.removeXover(conn5p, strand, useUndoStack=True)
```

After removing the crossover, the strand is isolated and can be deleted:
```python
ss.removeStrand(strand, useUndoStack=True)
```

### The correct implementation of deleteExposedFragments

```python
def deleteExposedFragments(self, strand_type="scaffold"):
    part = self.activePart
    if part is None:
        return "Error: No active part"

    stype = strand_type.lower()
    get_ss = (lambda vh: vh.scaffoldStrandSet()) if stype == "scaffold" \
        else (lambda vh: vh.stapleStrandSet())

    # Snapshot all strands with at least one free end BEFORE making changes.
    # A free 5' end means connection5p() is None.
    # A free 3' end means connection3p() is None.
    dangling = []
    for vh in part.getVirtualHelices():
        for strand in list(get_ss(vh)):
            if strand.connection5p() is None or strand.connection3p() is None:
                dangling.append((vh.number(), strand))

    if not dangling:
        return f"No exposed {strand_type} fragments found — design is clean."

    part.undoStack().beginMacro(
        f"Delete {len(dangling)} exposed {strand_type} fragment(s)"
    )
    deleted = 0
    for vh_num, strand in dangling:
        vh = part.virtualHelix(vh_num)
        if vh is None:
            continue
        ss = get_ss(vh)
        try:
            # Remove crossover at 3' end first
            conn3p = strand.connection3p()
            if conn3p is not None:
                part.removeXover(strand, conn3p, useUndoStack=True)
            # Remove crossover at 5' end
            conn5p = strand.connection5p()
            if conn5p is not None:
                part.removeXover(conn5p, strand, useUndoStack=True)
            # Now isolated — safe to delete
            ss.removeStrand(strand, useUndoStack=True)
            deleted += 1
        except Exception:
            pass  # already removed as side-effect of another deletion
    part.undoStack().endMacro()

    return (f"Deleted {deleted} exposed {strand_type} fragment(s). "
            f"Design should now have no free ends.")
```

---

## Problem 3 — `removeCrossover` has the same AttributeError

**File:** `cadnano2/views/agent/agentmethods.py`
**Method:** `removeCrossover` (around line 1181)

```python
strand.connectionLow().remove(useUndoStack=True)   # ← WRONG
strand.connectionHigh().remove(useUndoStack=True)  # ← WRONG
```

Same bug as Problem 2. Fix using `part.removeXover()`:

```python
conn = strand.connectionLow()
if conn is not None:
    # Determine 5p/3p direction
    if strand.connection3p() == conn:
        part.removeXover(strand, conn, useUndoStack=True)
    else:
        part.removeXover(conn, strand, useUndoStack=True)
```

---

## Problem 4 — `planScaffoldRouting` fragment deletion is also broken

**File:** `cadnano2/views/agent/agentmethods.py`
**Method:** `planScaffoldRouting` (around line 2561)

The inline fragment deletion after crossover creation does:

```python
ss.removeStrand(strand, useUndoStack=True)
```

on strands that may still have crossover connections. `removeStrand` does not
automatically disconnect crossovers. This will either crash or leave dangling
crossover references.

**Fix:** Use the same pattern as the corrected `deleteExposedFragments` above —
call `part.removeXover()` to disconnect before calling `ss.removeStrand()`.

Also: use `strand.connection5p() is None or strand.connection3p() is None` as the
condition (not `connectionLow`/`connectionHigh`, which are parity-dependent aliases).

---

## Problem 5 — `planScaffoldRouting` createXover direction (unverified fix)

**File:** `cadnano2/views/agent/agentmethods.py`
**Method:** `planScaffoldRouting` (around line 2554)

The original code had:
```python
part.createXover(s_a, idx, s_b, idx, useUndoStack=True)
```

This was changed to:
```python
part.createXover(s_b, idx, s_a, idx, useUndoStack=True)
```

The reasoning: `addCrossoversForPair` uses:
- LOW crossover: `createXover(even_strand, idx, odd_strand, idx)` — even is strand5p
- HIGH crossover: `createXover(odd_strand, idx, even_strand, idx)` — odd is strand5p

In `planScaffoldRouting`, `vh_a` is the source helix and `vh_b` is the destination:
- When `vh_a` is even (exits HIGH): `vh_b` is odd → `createXover(odd=s_b, idx, even=s_a, idx)`
- When `vh_a` is odd (exits LOW): `vh_b` is even → `createXover(even=s_b, idx, odd=s_a, idx)`

Both cases reduce to `createXover(s_b, idx, s_a, idx)`.

**This fix is logically derived but has NOT been confirmed to produce a closed scaffold
loop in cadnano.** After fixing Problems 2–4, test by loading the result in cadnano and
verifying `verifyDesign()` returns a score of 1.0 with no exposed ends.

---

## Key cadnano API Reference

```python
# Strand connections (from cadnano2/model/strand.py)
strand.connection3p()    # → Strand or None — strand connected at 3' end
strand.connection5p()    # → Strand or None — strand connected at 5' end
strand.connectionLow()   # parity-dependent alias for connection5p or connection3p
strand.connectionHigh()  # parity-dependent alias — DON'T use for crossover removal

# Remove a crossover (from cadnano2/model/parts/part.py line 677)
part.removeXover(strand5p, strand3p, useUndoStack=True)
# Requires: strand5p.connection3p() == strand3p

# Remove an isolated strand (no crossovers attached)
strandSet.removeStrand(strand, useUndoStack=True)

# isEvenParity — from strand.py lines 61-74:
# Even parity (row%2 == col%2): connectionLow = connection5p, connectionHigh = connection3p
# Odd parity: connectionLow = connection3p, connectionHigh = connection5p
```

---

## What a correct scaffold routing looks like

For a 2×N bundle (2 rows, N columns), a correct single-pass scaffold routing has:
- **Exactly 2N half-crossovers** (one at each turn of the serpentine path)
- **Zero exposed ends** — the scaffold forms a single closed loop
- **Each helix body** between its two crossovers is part of the loop; tails outside
  the crossovers are isolated fragments and should be deleted

The serpentine path visits: top row left→right, then bottom row right→left, closing
back to the start. Each turn uses a single `createXover` (half-crossover), NOT a
double crossover (DX motif).

`addAllNeighborCrossovers` and `addCrossoversForPair` create DX motifs (pairs of
half-crossovers used for structural stability in staple routing). They are **wrong**
for scaffold routing and produce dozens of fragments with exposed ends.

---

## Files to fix

1. `cadnano2/views/agent/agentmethods.py`
   - `deleteExposedFragments` (~line 2601): replace `.remove()` with `part.removeXover()`
   - `removeCrossover` (~line 1218): same fix
   - `planScaffoldRouting` (~line 2561): fix inline fragment deletion

2. `cadnano2/views/agent/agentbackend.py`
   - `CLAUDE_SYSTEM_PROMPT`: strengthen the instruction to use `planScaffoldRouting`
     for 2×N scaffold routing and explicitly forbid `addAllNeighborCrossovers` for
     scaffold routing tasks
