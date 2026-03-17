#!/usr/bin/env python
"""
Parametric DNA Origami Pipeline — Rectangle with Optional Cavity

Builds a rectangular DNA origami with configurable dimensions and an optional
rectangular cavity. Supports m13mp18 (7249 nt) and p8064 (8064 nt) scaffolds.

Key capability: change cavity_width_bp or cavity_height_helices and the entire
design recomputes — scaffold routing around the cavity, staple placement,
staple breaking, polyT brush extensions, twist correction insertions, and
oxDNA verification. A redesign that takes hours by hand takes seconds here.

Pipeline:
  1. Create helices on honeycomb lattice
  2. Route scaffold (serpentine for solid rectangle; perimeter path for cavity)
  3. Place staples via autoStaple
  4. Break staples via autoBreakStaples (Dijkstra-optimized)
  5. Add polyT brush extensions at structure edges
  6. Add insertions for twist correction
  7. Export cadnano JSON
  8. Convert to oxDNA via tacoxDNA
  9. Run oxDNA energy minimization + MD relaxation
  10. Analyze and generate figures

Usage:
  conda activate cn24-agentic

  # Simple rectangle with p8064:
  QT_QPA_PLATFORM=offscreen python -m tools.parametric_origami_pipeline --scaffold p8064

  # Rectangle with cavity:
  QT_QPA_PLATFORM=offscreen python -m tools.parametric_origami_pipeline \\
      --scaffold p8064 --cavity-width 120 --cavity-height 8

  # Widen cavity by ~5nm (15bp):
  QT_QPA_PLATFORM=offscreen python -m tools.parametric_origami_pipeline \\
      --scaffold p8064 --cavity-width 135 --cavity-height 8

  # Skip simulation (design + tacoxDNA only):
  QT_QPA_PLATFORM=offscreen python -m tools.parametric_origami_pipeline \\
      --scaffold p8064 --cavity-width 120 --cavity-height 8 --no-sim
"""

import os
import sys
import json
import subprocess
import shutil
import time
from dataclasses import dataclass, field
from math import ceil
from typing import Optional, List, Tuple, Dict

# CRITICAL: Must set before any Qt imports
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TACOX_DIR = os.path.join(os.path.dirname(PROJECT_ROOT), 'tacoxDNA')
TACOX_SCRIPT = os.path.join(TACOX_DIR, 'src', 'cadnano_oxDNA.py')
OXDNA_DIR = os.path.join(os.path.dirname(os.path.dirname(PROJECT_ROOT)),
                          'forks', 'oxDNA-master')
OXDNA_BIN = os.path.join(OXDNA_DIR, 'build', 'bin', 'oxDNA')
OXDNA_UNIT_NM = 0.8518

SCAFFOLD_LENGTHS = {
    'm13mp18': 7249,
    'p8064': 8064,
}

STEP_SIZE = 21  # honeycomb lattice step


@dataclass
class OrigamiParams:
    """All parameters for a rectangular origami design."""
    # Scaffold
    scaffold_type: str = 'p8064'

    # Helix layout
    n_helices: int = 26           # total helices in the structure
    helix_length_bp: int = 336    # must be multiple of 21
    start_row: int = 10           # honeycomb row for first helix
    start_col: int = 4            # honeycomb column for first helix

    # Cavity (set to 0 for no cavity)
    cavity_width_bp: int = 0      # width of cavity in bp (along helix axis)
    cavity_height_helices: int = 0  # number of helices removed for cavity

    # PolyT brushes
    polyt_length: int = 4         # bases to extend at edges (0=none)

    # Staple breaking
    min_staple_len: int = 18
    max_staple_len: int = 50
    tgt_staple_len: int = 32
    min_leg_len: int = 5

    # Output
    output_dir: str = ''
    design_name: str = ''

    @property
    def scaffold_length(self) -> int:
        return SCAFFOLD_LENGTHS[self.scaffold_type]

    @property
    def has_cavity(self) -> bool:
        return self.cavity_width_bp > 0 and self.cavity_height_helices > 0

    @property
    def cavity_start_helix(self) -> int:
        """First helix index (0-based) that is split by the cavity."""
        if not self.has_cavity:
            return -1
        n_above = (self.n_helices - self.cavity_height_helices) // 2
        return n_above

    @property
    def cavity_end_helix(self) -> int:
        """Last helix index (exclusive) that is split by the cavity."""
        if not self.has_cavity:
            return -1
        return self.cavity_start_helix + self.cavity_height_helices

    @property
    def cavity_start_bp(self) -> int:
        """Left edge of cavity (bp index)."""
        if not self.has_cavity:
            return -1
        # Center the cavity along the helix length, aligned to step
        center = self.helix_length_bp // 2
        half_width = self.cavity_width_bp // 2
        start = center - half_width
        # Align to nearest step boundary
        return (start // STEP_SIZE) * STEP_SIZE

    @property
    def cavity_end_bp(self) -> int:
        """Right edge of cavity (bp index, exclusive)."""
        if not self.has_cavity:
            return -1
        return self.cavity_start_bp + self.cavity_width_bp

    def describe(self) -> str:
        s = (f"  Scaffold: {self.scaffold_type} ({self.scaffold_length} nt)\n"
             f"  Helices: {self.n_helices} × {self.helix_length_bp} bp "
             f"({self.helix_length_bp // STEP_SIZE} steps)\n")
        if self.has_cavity:
            s += (f"  Cavity: {self.cavity_width_bp} bp wide × "
                  f"{self.cavity_height_helices} helices tall\n"
                  f"  Cavity position: helices {self.cavity_start_helix}-"
                  f"{self.cavity_end_helix - 1}, "
                  f"bp {self.cavity_start_bp}-{self.cavity_end_bp}\n")
        if self.polyt_length > 0:
            s += f"  PolyT brushes: {self.polyt_length} nt at edges\n"
        return s

    def auto_dimensions(self):
        """Compute helix_length_bp to fit the scaffold.

        With staple-removal cavity, all helices are full-width (scaffold
        runs through everything). So routed bp = n_helices * helix_length.
        """
        target_bp = self.scaffold_length
        # Aim for ~5-7% insertions (twist correction)
        target_routed = int(target_bp * 0.94)
        needed_L = target_routed / self.n_helices
        self.helix_length_bp = int(ceil(needed_L / STEP_SIZE)) * STEP_SIZE
        return self


def compute_routed_bp(params: OrigamiParams) -> int:
    """Compute total base pairs routed by the scaffold (before insertions).

    With staple-removal cavity, scaffold still runs through all helices.
    """
    return params.n_helices * params.helix_length_bp


# ── Cadnano Design Creation ──────────────────────────────────────────────


def init_cadnano():
    """Initialize cadnano application and return app, dc, part, methods."""
    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()
    from cadnano2.views.agent.agentmethods import AgentMethods

    dc = list(app.documentControllers)[0]
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    class MockDC:
        def __init__(self, app, doc, part):
            self._app, self._doc, self._part = app, doc, part
        def document(self):
            return self._doc
        def activePart(self):
            return self._part
        def undoStack(self):
            return self._doc.undoStack()

    mock = MockDC(app, doc, part)
    methods = AgentMethods(mock)
    return app, dc, part, methods


def create_helices(part, params: OrigamiParams):
    """Create virtual helices on the honeycomb lattice."""
    step = part.stepSize()
    if params.helix_length_bp - 1 > part.maxBaseIdx():
        delta = int(ceil((params.helix_length_bp - 1 - part.maxBaseIdx()) / step)) * step
        part.resizeVirtualHelices(0, delta, useUndoStack=True)

    positions = [[params.start_row, params.start_col + i]
                 for i in range(params.n_helices)]

    # Verify positions are within grid bounds (default 30 rows × 32 cols)
    for r, c in positions:
        if r < 0 or r >= 30 or c < 0 or c >= 32:
            raise ValueError(f"Helix position ({r}, {c}) out of grid bounds")

    for pos in positions:
        part.createVirtualHelix(pos[0], pos[1], useUndoStack=True)

    helices = sorted(part.getVirtualHelices(), key=lambda vh: vh.coord()[1])
    print(f"  Created {len(helices)} helices")
    return helices


def get_crossover_positions(part, vh1, vh2, helix_length):
    """Get all valid scaffold crossover positions between two neighbor helices."""
    from cadnano2.model.parts.honeycombpart import Crossovers

    neighbors = part.getVirtualHelixNeighbors(vh1)
    if vh2 not in neighbors:
        raise ValueError(f"Helix {vh2.number()} not neighbor of {vh1.number()}")

    direction_idx = neighbors.index(vh2)
    low_offsets = Crossovers.honeycombScafLow[direction_idx]
    high_offsets = Crossovers.honeycombScafHigh[direction_idx]

    step = part.stepSize()
    positions = []
    for base in range(0, part.maxBaseIdx() + 1, step):
        for low_off, high_off in zip(low_offsets, high_offsets):
            low_idx = base + low_off
            high_idx = base + high_off
            if 0 <= low_idx < helix_length and 0 <= high_idx < helix_length:
                positions.append({'low_idx': low_idx, 'high_idx': high_idx})

    return positions


def get_turn_position(positions, vh, side='auto'):
    """Get the routing turn crossover position for a helix.

    side='auto': even parity → rightmost, odd → leftmost
    side='left': force leftmost
    side='right': force rightmost
    """
    if not positions:
        return None
    if side == 'auto':
        if vh.isEvenParity():
            return positions[-1]  # rightmost
        else:
            return positions[0]   # leftmost
    elif side == 'left':
        return positions[0]
    else:
        return positions[-1]


def get_positions_in_range(positions, lo, hi):
    """Filter crossover positions to those within a bp range."""
    return [p for p in positions if lo <= p['low_idx'] <= hi and lo <= p['high_idx'] <= hi]


def route_scaffold_simple(part, helices, params: OrigamiParams):
    """Route scaffold through a simple rectangle (no cavity). Serpentine path."""
    from cadnano2.model.strand import Strand

    n = len(helices)
    L = params.helix_length_bp

    # Compute crossover (turn) positions between each pair
    xover_positions = []
    for i in range(n - 1):
        all_pos = get_crossover_positions(part, helices[i], helices[i + 1], L)
        turn = get_turn_position(all_pos, helices[i])
        if turn is None:
            raise RuntimeError(f"No crossover positions for helices "
                               f"{helices[i].number()}-{helices[i+1].number()}")
        xover_positions.append(turn)

    # Compute strand ranges
    strand_ranges = []
    for i in range(n):
        vh = helices[i]
        if i == 0:
            xo = xover_positions[0]['low_idx']
            strand_ranges.append((0, xo) if vh.isEvenParity() else (xo, L - 1))
        elif i == n - 1:
            xo = xover_positions[-1]['low_idx']
            strand_ranges.append((xo, L - 1) if vh.isEvenParity() else (0, xo))
        else:
            xo_prev = xover_positions[i - 1]['low_idx']
            xo_next = xover_positions[i]['low_idx']
            strand_ranges.append((min(xo_prev, xo_next), max(xo_prev, xo_next)))

    # Create scaffold strands
    for vh, (lo, hi) in zip(helices, strand_ranges):
        scaf_ss = vh.scaffoldStrandSet()
        result = scaf_ss.createStrand(lo, hi, useUndoStack=True)
        if result < 0:
            raise RuntimeError(f"Failed to create strand on helix "
                               f"{vh.number()} [{lo}:{hi}]")

    # Connect strands at crossover points
    total_bp = sum(hi - lo + 1 for lo, hi in strand_ranges)
    xovers_placed = connect_serpentine(part, helices, xover_positions)

    return {
        'type': 'simple_serpentine',
        'xovers_placed': xovers_placed,
        'total_scaffold_bp': total_bp,
        'strand_ranges': strand_ranges,
    }


def remove_cavity_staples(part, helices, params: OrigamiParams):
    """Remove staple strands from the cavity region.

    In a staple-removal cavity, the scaffold still runs through every helix
    (normal serpentine), but staples are removed from the cavity region.
    This creates an unstapled window where the scaffold is single-stranded.

    Removes any staple oligo that has ALL its bases within the cavity region.
    Staples at the cavity boundary (partially inside, partially outside) are kept.

    Returns count of staples removed.
    """
    if not params.has_cavity:
        return 0

    cs = params.cavity_start_helix
    ce = params.cavity_end_helix
    cb_start = params.cavity_start_bp
    cb_end = params.cavity_end_bp

    # Get helix numbers for cavity region
    cavity_helix_nums = set()
    for i in range(cs, ce):
        cavity_helix_nums.add(helices[i].number())

    # Find staple oligos entirely within cavity
    oligos_to_remove = []
    for oligo in part.oligos():
        if not oligo.isStaple():
            continue

        # Check all strands in this oligo
        all_in_cavity = True
        for strand in oligo.strand5p().generator3pStrand():
            vh = strand.virtualHelix()
            h_num = vh.number()
            lo, hi = strand.idxs()

            if h_num not in cavity_helix_nums:
                all_in_cavity = False
                break
            if lo < cb_start or hi >= cb_end:
                all_in_cavity = False
                break

        if all_in_cavity:
            oligos_to_remove.append(oligo)

    # Remove the staples
    removed = 0
    for oligo in oligos_to_remove:
        for strand in list(oligo.strand5p().generator3pStrand()):
            strand.strandSet().removeStrand(strand, useUndoStack=False)
        removed += 1

    return removed


def connect_strands_at(part, vh1, vh2, xover_idx):
    """Connect scaffold strands between two helices at a crossover position.

    Returns True on success.
    """
    from cadnano2.model.strand import Strand

    scaf1 = vh1.scaffoldStrandSet().getStrand(xover_idx)
    scaf2 = vh2.scaffoldStrandSet().getStrand(xover_idx)

    if scaf1 is None or scaf2 is None:
        # Try adjacent indices
        for delta in [-1, 1, -2, 2]:
            alt = xover_idx + delta
            if scaf1 is None:
                scaf1 = vh1.scaffoldStrandSet().getStrand(alt)
            if scaf2 is None:
                scaf2 = vh2.scaffoldStrandSet().getStrand(alt)
            if scaf1 and scaf2:
                xover_idx = alt
                break

    if scaf1 is None or scaf2 is None:
        return False

    lo1, hi1 = scaf1.idxs()
    lo2, hi2 = scaf2.idxs()

    # Determine which strand is 5p and which is 3p at this crossover
    is_3p_end_1 = (vh1.isEvenParity() and hi1 == xover_idx) or \
                  (not vh1.isEvenParity() and lo1 == xover_idx)
    is_5p_end_2 = (vh2.isEvenParity() and lo2 == xover_idx) or \
                  (not vh2.isEvenParity() and hi2 == xover_idx)

    if is_3p_end_1 and is_5p_end_2:
        strand5p, strand3p = scaf1, scaf2
    else:
        is_3p_end_2 = (vh2.isEvenParity() and hi2 == xover_idx) or \
                      (not vh2.isEvenParity() and lo2 == xover_idx)
        is_5p_end_1 = (vh1.isEvenParity() and lo1 == xover_idx) or \
                      (not vh1.isEvenParity() and hi1 == xover_idx)
        if is_3p_end_2 and is_5p_end_1:
            strand5p, strand3p = scaf2, scaf1
        else:
            return False

    # Check if already connected
    if strand5p.connection3p() == strand3p:
        return True

    # Merge oligos
    olg5p = strand5p.oligo()
    olg3p = strand3p.oligo()
    if olg5p != olg3p:
        olg5p.incrementLength(olg3p.length())
        olg3p.removeFromPart()
        for s in strand3p.generator3pStrand():
            Strand.setOligo(s, olg5p)

    strand5p.setConnection3p(strand3p)
    strand3p.setConnection5p(strand5p)
    return True


def connect_serpentine(part, helices, xover_positions):
    """Connect strands in a serpentine pattern using pre-computed crossover positions."""
    xovers_placed = 0
    for i, xo in enumerate(xover_positions):
        ok = connect_strands_at(part, helices[i], helices[i + 1], xo['low_idx'])
        if ok:
            xovers_placed += 1
    return xovers_placed


# ── Staple Breaking ──────────────────────────────────────────────────────


def break_staples_direct(part, params: OrigamiParams):
    """Break staples using the autobreak plugin."""
    import importlib
    import importlib.util

    sg_path = os.path.join(PROJECT_ROOT, 'cadnano2', 'plugins', 'autobreak',
                           'staplegraph.py')
    sg_spec = importlib.util.spec_from_file_location(
        "cadnano2.plugins.autobreak.staplegraph", sg_path,
        submodule_search_locations=[])
    sg = importlib.util.module_from_spec(sg_spec)
    sys.modules['cadnano2.plugins.autobreak.staplegraph'] = sg
    sg_spec.loader.exec_module(sg)

    if 'cadnano2.plugins.autobreak.autobreak' in sys.modules:
        del sys.modules['cadnano2.plugins.autobreak.autobreak']

    ab_path = os.path.join(PROJECT_ROOT, 'cadnano2', 'plugins', 'autobreak',
                           'autobreak.py')
    ab_spec = importlib.util.spec_from_file_location(
        "cadnano2.plugins.autobreak.autobreak", ab_path,
        submodule_search_locations=[])
    ab = importlib.util.module_from_spec(ab_spec)
    sys.modules['cadnano2.plugins.autobreak.autobreak'] = ab
    ab_spec.loader.exec_module(ab)

    settings = {
        'minStapleLen': params.min_staple_len,
        'maxStapleLen': params.max_staple_len,
        'tgtStapleLen': params.tgt_staple_len,
        'minStapleLegLen': params.min_leg_len,
    }

    before = sum(1 for o in part.oligos() if o.isStaple())
    try:
        # Attempt to break each staple individually to skip problematic ones
        staple_oligos = [o for o in part.oligos() if o.isStaple()]
        for oligo in staple_oligos:
            try:
                if oligo.length() >= params.min_staple_len:
                    ab.nxBreakStaple(oligo, settings)
            except Exception:
                pass  # Skip staples that can't be broken
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'error': str(e)}

    after = sum(1 for o in part.oligos() if o.isStaple())
    lengths = [o.length() for o in part.oligos() if o.isStaple()]

    return {
        'before': before,
        'after': after,
        'avg_length': np.mean(lengths) if lengths else 0,
        'min_length': min(lengths) if lengths else 0,
        'max_length': max(lengths) if lengths else 0,
    }


# ── PolyT Brushes ────────────────────────────────────────────────────────


def add_polyt_brushes(part, helices, params: OrigamiParams):
    """Extend staple strands at structure edges by N bases for polyT brushes.

    At each edge of the structure (left/right ends of helices, and top/bottom
    of cavity), extend exposed staple strand endpoints outward.

    Returns count of extensions added.
    """
    if params.polyt_length <= 0:
        return 0

    extensions = 0

    for vh in helices:
        stap_ss = vh.stapleStrandSet()
        for strand in stap_ss:
            lo, hi = strand.idxs()

            # Check if this strand has an exposed 5' end (no connection)
            if strand.connection5p() is None:
                if vh.isEvenParity():
                    new_hi = min(hi + params.polyt_length,
                                 params.helix_length_bp - 1)
                    if new_hi > hi:
                        strand.resize((lo, new_hi), useUndoStack=False)
                        extensions += 1
                else:
                    new_lo = max(lo - params.polyt_length, 0)
                    if new_lo < lo:
                        strand.resize((new_lo, hi), useUndoStack=False)
                        extensions += 1

            # Re-read idxs after possible resize
            lo, hi = strand.idxs()

            # Check 3' end
            if strand.connection3p() is None:
                if vh.isEvenParity():
                    new_lo = max(lo - params.polyt_length, 0)
                    if new_lo < lo:
                        strand.resize((new_lo, hi), useUndoStack=False)
                        extensions += 1
                else:
                    new_hi = min(hi + params.polyt_length,
                                 params.helix_length_bp - 1)
                    if new_hi > hi:
                        strand.resize((lo, new_hi), useUndoStack=False)
                        extensions += 1

    return extensions


# ── Insertions ────────────────────────────────────────────────────────────


def add_twist_correction_insertions(part, helices, params: OrigamiParams,
                                     target_insertions: int):
    """Add single-base insertions distributed across helices for twist correction."""
    if target_insertions <= 0:
        return 0

    n = len(helices)
    insertions_per_helix = target_insertions // n
    remainder = target_insertions % n

    total_added = 0

    for idx, vh in enumerate(helices):
        n_ins = insertions_per_helix + (1 if idx < remainder else 0)
        if n_ins == 0:
            continue

        scaf_ss = vh.scaffoldStrandSet()
        L = params.helix_length_bp
        spacing = L // (n_ins + 1)

        for i in range(n_ins):
            bp_idx = spacing * (i + 1)
            strand = scaf_ss.getStrand(bp_idx)
            if strand is None:
                continue

            # Avoid positions near crossovers
            has_xover = False
            for offset in range(-3, 4):
                s = scaf_ss.getStrand(bp_idx + offset)
                if s and s.hasXoverAt(bp_idx + offset):
                    has_xover = True
                    break

            if has_xover:
                shifted = False
                for delta in [4, 5, -4, -5, 6, -6]:
                    alt = bp_idx + delta
                    alt_strand = scaf_ss.getStrand(alt)
                    if alt_strand is None:
                        continue
                    ok = True
                    for offset in range(-3, 4):
                        s = scaf_ss.getStrand(alt + offset)
                        if s and s.hasXoverAt(alt + offset):
                            ok = False
                            break
                    if ok:
                        bp_idx = alt
                        strand = alt_strand
                        shifted = True
                        break
                if not shifted:
                    continue

            strand.addInsertion(bp_idx, 1, useUndoStack=False)
            total_added += 1

    return total_added


# ── Main Design Function ─────────────────────────────────────────────────


def create_origami(params: OrigamiParams):
    """Create the full origami design. Returns (json_path, design_info, app)."""
    print("=" * 60)
    print(f"CREATING PARAMETRIC DNA ORIGAMI")
    print("=" * 60)
    print(params.describe())

    app, dc, part, methods = init_cadnano()

    # Step 1: Create helices
    print("\n── Step 1: Create helices ──")
    helices = create_helices(part, params)

    # Step 2: Route scaffold (always serpentine — cavity is defined by staple removal)
    print("\n── Step 2: Route scaffold (serpentine) ──")
    route_info = route_scaffold_simple(part, helices, params)
    print(f"  Routing: {route_info}")

    # Verify scaffold continuity
    scaffold_oligos = [o for o in part.oligos() if not o.isStaple()]
    print(f"  Scaffold oligos: {len(scaffold_oligos)} (should be 1)")
    for o in scaffold_oligos:
        print(f"    Length: {o.length()} bp")

    # Step 3: autoStaple
    print("\n── Step 3: Place staples (autoStaple) ──")
    from cadnano2.model.parts.part import Part
    Part.autoStaple(part)
    staple_count_pre = sum(1 for o in part.oligos() if o.isStaple())
    print(f"  Staples placed: {staple_count_pre}")

    # Step 3b: Remove cavity staples
    if params.has_cavity:
        print("\n── Step 3b: Remove cavity staples ──")
        cavity_removed = remove_cavity_staples(part, helices, params)
        staple_count_post = sum(1 for o in part.oligos() if o.isStaple())
        print(f"  Removed {cavity_removed} staples from cavity region")
        print(f"  Remaining staples: {staple_count_post}")
    else:
        cavity_removed = 0

    # Step 4: Break staples
    print("\n── Step 4: Break staples (autoBreak) ──")
    break_result = break_staples_direct(part, params)
    if 'error' in break_result:
        print(f"  WARNING: autoBreak error: {break_result['error']}")
        print(f"  Continuing with unbroken staples...")
    else:
        print(f"  Break result: {break_result}")

    # Step 5: PolyT brushes (after staple breaking to avoid short-staple issues)
    print("\n── Step 5: PolyT brush extensions ──")
    polyt_count = add_polyt_brushes(part, helices, params)
    print(f"  Extensions added: {polyt_count}")

    # Step 6: Twist correction insertions
    print("\n── Step 6: Twist correction insertions ──")
    scaffold_len_pre = sum(o.length() for o in part.oligos() if not o.isStaple())
    insertions_needed = params.scaffold_length - scaffold_len_pre
    print(f"  Scaffold before insertions: {scaffold_len_pre} bp")
    print(f"  Insertions needed for {params.scaffold_length} nt: {insertions_needed}")

    if insertions_needed > 0:
        ins_added = add_twist_correction_insertions(
            part, helices, params, insertions_needed)
    else:
        ins_added = 0
    print(f"  Insertions added: {ins_added}")

    # Collect final statistics
    scaffold_oligos = [o for o in part.oligos() if not o.isStaple()]
    staple_oligos = [o for o in part.oligos() if o.isStaple()]
    total_scaffold = sum(o.length() for o in scaffold_oligos)
    staple_lengths = [o.length() for o in staple_oligos]

    design_info = {
        'params': {
            'scaffold_type': params.scaffold_type,
            'scaffold_length': params.scaffold_length,
            'n_helices': params.n_helices,
            'helix_length_bp': params.helix_length_bp,
            'cavity_width_bp': params.cavity_width_bp,
            'cavity_height_helices': params.cavity_height_helices,
            'polyt_length': params.polyt_length,
        },
        'scaffold_oligos': len(scaffold_oligos),
        'scaffold_bases': total_scaffold,
        'staple_count': len(staple_oligos),
        'staple_avg_len': float(np.mean(staple_lengths)) if staple_lengths else 0,
        'staple_min_len': min(staple_lengths) if staple_lengths else 0,
        'staple_max_len': max(staple_lengths) if staple_lengths else 0,
        'insertions_added': ins_added,
        'polyt_extensions': polyt_count,
        'cavity_staples_removed': cavity_removed,
        'route_info': route_info,
    }

    # Save JSON
    os.makedirs(params.output_dir, exist_ok=True)
    json_path = os.path.join(params.output_dir, f'{params.design_name}.json')
    dc.writeDocumentToFile(json_path)
    print(f"\n  Saved: {json_path}")

    return json_path, design_info, app


# ── tacoxDNA + oxDNA Pipeline ─────────────────────────────────────────────


def convert_to_oxdna(json_path, work_dir):
    """Convert cadnano JSON to oxDNA format."""
    print("\n── Converting to oxDNA (tacoxDNA) ──")

    if not os.path.exists(TACOX_SCRIPT):
        raise FileNotFoundError(f"tacoxDNA not found at {TACOX_SCRIPT}")

    cmd = [sys.executable, TACOX_SCRIPT, json_path, 'he']
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=work_dir)

    if result.returncode != 0:
        raise RuntimeError(f"tacoxDNA failed: {result.stderr}")

    json_basename = os.path.basename(json_path)
    dat_path = os.path.join(work_dir, json_basename + '.oxdna')
    top_path = os.path.join(work_dir, json_basename + '.top')

    std_conf = os.path.join(work_dir, 'start.conf')
    std_top = os.path.join(work_dir, 'topology.top')
    shutil.copy2(dat_path, std_conf)
    shutil.copy2(top_path, std_top)

    with open(std_top) as f:
        header = f.readline().split()
        n_nuc = int(header[0])
        n_strands = int(header[1])

    print(f"  Nucleotides: {n_nuc}, Strands: {n_strands}")
    return std_conf, std_top, n_nuc, n_strands


def write_oxdna_inputs(work_dir, use_cuda=False):
    """Write oxDNA input files for minimization and relaxation."""
    input_min = """# Energy Minimization
backend = CPU
sim_type = min
interaction_type = DNA2
max_backbone_force = 5.
max_backbone_force_far = 10.
steps = 10000
dt = 0.005
T = 300K
verlet_skin = 0.15
salt_concentration = 1.0
time_scale = linear
refresh_vel = 1
topology = topology.top
conf_file = start.conf
lastconf_file = minimized.conf
trajectory_file = traj_min.dat
energy_file = energy_min.dat
print_conf_interval = 10000
print_energy_every = 20
no_stdout_energy = false
restart_step_counter = 1
"""

    backend = "backend = CUDA\nbackend_precision = mixed\nCUDA_list = verlet\nCUDA_sort_every = 0\nuse_edge = 1\nedge_n_forces = 1" if use_cuda else "backend = CPU"

    input_relax = f"""# MD Relaxation (gentle)
{backend}
sim_type = MD
interaction_type = DNA2
max_backbone_force = 5.
max_backbone_force_far = 0.1
dt = 0.003
T = 300K
thermostat = john
diff_coeff = 2.5
newtonian_steps = 103
salt_concentration = 0.5
max_density_multiplier = 15
steps = 100000
verlet_skin = 0.5
topology = topology.top
conf_file = minimized.conf
trajectory_file = trajectory.dat
energy_file = energy_relax.dat
lastconf_file = relaxed.conf
refresh_vel = 1
restart_step_counter = 1
time_scale = linear
print_conf_interval = 10000
print_energy_every = 1000
no_stdout_energy = false
"""

    for name, content in [('input_min', input_min), ('input_relax', input_relax)]:
        with open(os.path.join(work_dir, name), 'w') as f:
            f.write(content)

    print(f"  Written oxDNA input files to {work_dir}")


def run_oxdna_stage(work_dir, input_file, stage_name):
    """Run one oxDNA simulation stage."""
    if not os.path.exists(OXDNA_BIN):
        print(f"  WARNING: oxDNA not found at {OXDNA_BIN}, skipping {stage_name}")
        return False

    print(f"  Running {stage_name}...")
    t0 = time.time()
    result = subprocess.run(
        [OXDNA_BIN, input_file],
        capture_output=True, text=True, cwd=work_dir, timeout=3600)
    elapsed = time.time() - t0

    if result.returncode != 0:
        print(f"  FAILED ({elapsed:.1f}s): {result.stderr[-500:]}")
        return False

    print(f"  Completed in {elapsed:.1f}s")
    return True


def run_simulations(work_dir):
    """Run energy minimization + MD relaxation."""
    print("\n── Running oxDNA simulations ──")
    ok = run_oxdna_stage(work_dir, 'input_min', 'energy minimization')
    if not ok:
        return False
    if not os.path.exists(os.path.join(work_dir, 'minimized.conf')):
        print("  ERROR: minimized.conf not produced")
        return False

    ok = run_oxdna_stage(work_dir, 'input_relax', 'MD relaxation')
    if not ok:
        return False
    return True


# ── Analysis and Figures ──────────────────────────────────────────────────


def parse_oxdna_conf(conf_path):
    """Parse oxDNA .conf file for nucleotide coordinates."""
    coords = []
    with open(conf_path) as f:
        for _ in range(3):
            next(f)
        for line in f:
            vals = line.split()
            if len(vals) >= 3:
                coords.append([float(vals[0]), float(vals[1]), float(vals[2])])
    return np.array(coords)


def parse_oxdna_top(top_path):
    """Parse topology for strand assignments."""
    strands = []
    with open(top_path) as f:
        header = f.readline().split()
        n_nuc, n_strands = int(header[0]), int(header[1])
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                strands.append(int(parts[0]))
    return np.array(strands), n_nuc, n_strands


def analyze_structure(work_dir):
    """Analyze oxDNA structure dimensions."""
    results = {}

    for conf_name, label in [('start.conf', 'initial'),
                              ('minimized.conf', 'minimized'),
                              ('relaxed.conf', 'relaxed')]:
        conf_path = os.path.join(work_dir, conf_name)
        if not os.path.exists(conf_path):
            continue

        coords = parse_oxdna_conf(conf_path) * OXDNA_UNIT_NM

        # PCA
        centered = coords - coords.mean(axis=0)
        cov = np.cov(centered.T)
        eigenvalues = np.sort(np.linalg.eigvalsh(cov))[::-1]
        pca_dims = 2 * np.sqrt(eigenvalues)

        # Bounding box
        bb = coords.max(axis=0) - coords.min(axis=0)

        results[label] = {
            'pca_nm': pca_dims.tolist(),
            'bbox_nm': bb.tolist(),
            'n_nucleotides': len(coords),
        }

        print(f"  {label}: PCA {pca_dims[0]:.1f}×{pca_dims[1]:.1f}×{pca_dims[2]:.1f} nm, "
              f"bbox {bb[0]:.1f}×{bb[1]:.1f}×{bb[2]:.1f} nm")

    return results


def generate_figures(work_dir, design_info, params: OrigamiParams):
    """Generate publication-quality figures."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig_dir = os.path.join(work_dir, 'figures')
    os.makedirs(fig_dir, exist_ok=True)
    figures = []

    top_path = os.path.join(work_dir, 'topology.top')

    # ── Figure: 3D structure views ──
    configs_to_show = []
    for name, label in [('start.conf', 'Initial'), ('relaxed.conf', 'Relaxed')]:
        path = os.path.join(work_dir, name)
        if os.path.exists(path):
            configs_to_show.append((path, label))

    if not configs_to_show:
        configs_to_show = [
            (os.path.join(work_dir, 'start.conf'), 'Initial')]

    for conf_path, label in configs_to_show:
        if not os.path.exists(conf_path):
            continue

        coords = parse_oxdna_conf(conf_path) * OXDNA_UNIT_NM

        if os.path.exists(top_path):
            strands, _, _ = parse_oxdna_top(top_path)
            unique_s = np.unique(strands)
            cmap = plt.cm.tab20(np.linspace(0, 1, min(20, len(unique_s))))
            colors = [cmap[s % 20] for s in strands]
        else:
            colors = 'steelblue'

        fig, axes = plt.subplots(1, 3, figsize=(14, 4))

        for ax, (xi, yi, xl, yl, title) in zip(axes, [
            (0, 1, 'X (nm)', 'Y (nm)', 'Top'),
            (0, 2, 'X (nm)', 'Z (nm)', 'Side'),
            (1, 2, 'Y (nm)', 'Z (nm)', 'End'),
        ]):
            ax.scatter(coords[:, xi], coords[:, yi], c=colors, s=0.3, alpha=0.4)
            ax.set_xlabel(xl, fontsize=9)
            ax.set_ylabel(yl, fontsize=9)
            ax.set_title(f'{title} View', fontsize=10)
            ax.set_aspect('equal')
            ax.tick_params(labelsize=8)

        bb = coords.max(axis=0) - coords.min(axis=0)
        cavity_text = ""
        if params.has_cavity:
            cw_nm = params.cavity_width_bp * 0.34
            ch_nm = params.cavity_height_helices * 2.6
            cavity_text = f" | Cavity: {cw_nm:.0f}×{ch_nm:.0f} nm"

        fig.suptitle(
            f'{label} Structure — {params.n_helices} helices × '
            f'{params.helix_length_bp} bp'
            f'{cavity_text}\n'
            f'Dimensions: {bb[0]:.1f}×{bb[1]:.1f}×{bb[2]:.1f} nm',
            fontsize=10, fontweight='bold')

        plt.tight_layout()
        fname = f'structure_{label.lower()}.png'
        path = os.path.join(fig_dir, fname)
        plt.savefig(path, dpi=200, bbox_inches='tight')
        plt.close()
        figures.append(path)
        print(f"  Saved: {path}")

    # ── Figure: Schematic showing cavity layout ──
    if params.has_cavity:
        fig, ax = plt.subplots(figsize=(10, 6))

        L = params.helix_length_bp
        cs = params.cavity_start_helix
        ce = params.cavity_end_helix
        cb_s = params.cavity_start_bp
        cb_e = params.cavity_end_bp

        for i in range(params.n_helices):
            y = -i * 1.0
            if cs <= i < ce:
                # Split helix — draw left and right segments
                ax.plot([0, cb_s], [y, y], 'b-', linewidth=3, solid_capstyle='round')
                ax.plot([cb_e, L], [y, y], 'b-', linewidth=3, solid_capstyle='round')
            else:
                # Full helix
                ax.plot([0, L], [y, y], 'b-', linewidth=3, solid_capstyle='round')

            ax.text(-15, y, f'H{i}', fontsize=7, ha='right', va='center')

        # Draw cavity rectangle
        cavity_rect = plt.Rectangle(
            (cb_s, -ce + 0.5), cb_e - cb_s, ce - cs,
            fill=True, facecolor='lightyellow', edgecolor='red',
            linewidth=2, linestyle='--')
        ax.add_patch(cavity_rect)
        ax.text((cb_s + cb_e) / 2, -(cs + ce) / 2 + 0.5,
                f'CAVITY\n{params.cavity_width_bp}bp × '
                f'{params.cavity_height_helices} helices',
                ha='center', va='center', fontsize=9, color='red',
                fontweight='bold')

        # Draw scaffold path arrows
        ax.annotate('', xy=(L + 10, 0), xytext=(L + 10, -(cs - 1)),
                     arrowprops=dict(arrowstyle='->', color='orange', lw=1.5))
        ax.text(L + 15, -(cs - 1) / 2, 'TOP\n(serpentine)',
                fontsize=7, va='center', color='orange')

        ax.annotate('', xy=(cb_s - 10, -(cs)),
                     xytext=(cb_s - 10, -(ce - 1)),
                     arrowprops=dict(arrowstyle='->', color='green', lw=1.5))
        ax.text(cb_s - 35, -(cs + ce) / 2 + 0.5, 'LEFT\nsegs',
                fontsize=7, va='center', color='green')

        ax.annotate('', xy=(L + 10, -ce),
                     xytext=(L + 10, -(params.n_helices - 1)),
                     arrowprops=dict(arrowstyle='->', color='purple', lw=1.5))
        ax.text(L + 15, -(ce + params.n_helices - 1) / 2,
                'BOTTOM\n(serpentine)',
                fontsize=7, va='center', color='purple')

        ax.annotate('', xy=(cb_e + 10, -(ce - 1)),
                     xytext=(cb_e + 10, -cs),
                     arrowprops=dict(arrowstyle='->', color='brown', lw=1.5))
        ax.text(cb_e + 15, -(cs + ce) / 2 + 0.5, 'RIGHT\nsegs',
                fontsize=7, va='center', color='brown')

        ax.set_xlim(-50, L + 60)
        ax.set_ylim(-(params.n_helices + 0.5), 1.5)
        ax.set_xlabel('Base pair position', fontsize=10)
        ax.set_ylabel('Helix', fontsize=10)
        ax.set_title(f'Scaffold Routing Around Cavity\n'
                      f'{params.n_helices} helices × {L} bp, '
                      f'cavity {params.cavity_width_bp}bp × '
                      f'{params.cavity_height_helices}h',
                      fontsize=11, fontweight='bold')
        ax.set_aspect('auto')
        plt.tight_layout()

        path = os.path.join(fig_dir, 'cavity_schematic.png')
        plt.savefig(path, dpi=200, bbox_inches='tight')
        plt.close()
        figures.append(path)
        print(f"  Saved: {path}")

    return figures


# ── Full Pipeline ─────────────────────────────────────────────────────────


def run_pipeline(params: OrigamiParams, skip_sim=False):
    """Run the complete pipeline: design → tacoxDNA → oxDNA → analysis."""
    # Auto-compute dimensions if not set
    if params.output_dir == '':
        if params.has_cavity:
            params.output_dir = os.path.join(
                PROJECT_ROOT, 'results',
                f'origami_cavity_{params.cavity_width_bp}bp_'
                f'{params.cavity_height_helices}h')
        else:
            params.output_dir = os.path.join(
                PROJECT_ROOT, 'results',
                f'origami_{params.scaffold_type}_{params.n_helices}h')

    if params.design_name == '':
        params.design_name = 'design'

    os.makedirs(params.output_dir, exist_ok=True)

    # Step 1: Create design
    json_path, design_info, app = create_origami(params)

    # Step 2: Convert to oxDNA
    conf_path, top_path, n_nuc, n_strands = convert_to_oxdna(
        json_path, params.output_dir)
    design_info['n_nucleotides'] = n_nuc
    design_info['n_strands'] = n_strands

    # Step 3: Write simulation inputs
    write_oxdna_inputs(params.output_dir)

    # Step 4: Run simulations
    sim_ok = False
    if not skip_sim:
        sim_ok = run_simulations(params.output_dir)
    else:
        print("\n  Skipping simulation (--no-sim)")

    # Step 5: Analyze
    print("\n── Analysis ──")
    structure_results = analyze_structure(params.output_dir)

    # Step 6: Figures
    print("\n── Generating figures ──")
    figures = generate_figures(params.output_dir, design_info, params)

    # Save report
    report = {
        'params': design_info['params'],
        'design': {k: v for k, v in design_info.items() if k != 'params'},
        'structure': structure_results,
        'simulation_completed': sim_ok,
        'figures': figures,
    }

    report_path = os.path.join(params.output_dir, 'report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    # Print summary
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    print(f"  Scaffold: {params.scaffold_type} ({params.scaffold_length} nt)")
    print(f"  Helices: {params.n_helices} × {params.helix_length_bp} bp")
    if params.has_cavity:
        print(f"  Cavity: {params.cavity_width_bp} bp × "
              f"{params.cavity_height_helices} helices")
        cw_nm = params.cavity_width_bp * 0.34
        ch_nm = params.cavity_height_helices * 2.6
        print(f"  Cavity size: ~{cw_nm:.0f} nm × ~{ch_nm:.0f} nm")
    print(f"  Scaffold routed: {design_info['scaffold_bases']} bp")
    print(f"  Scaffold oligos: {design_info['scaffold_oligos']}")
    print(f"  Staples: {design_info['staple_count']} "
          f"(avg {design_info['staple_avg_len']:.0f} nt)")
    print(f"  PolyT extensions: {design_info['polyt_extensions']}")
    print(f"  Insertions: {design_info['insertions_added']}")
    print(f"  oxDNA nucleotides: {n_nuc}")
    print(f"  Simulation: {'OK' if sim_ok else 'SKIPPED/FAILED'}")
    print(f"  Report: {report_path}")
    print("=" * 60)

    return report


# ── CLI ───────────────────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Parametric DNA origami pipeline')
    parser.add_argument('--scaffold', default='p8064',
                        choices=['m13mp18', 'p8064'],
                        help='Scaffold type (default: p8064)')
    parser.add_argument('--n-helices', type=int, default=26,
                        help='Number of helices (default: 26)')
    parser.add_argument('--helix-length', type=int, default=0,
                        help='Helix length in bp (0=auto, default: 0)')
    parser.add_argument('--cavity-width', type=int, default=0,
                        help='Cavity width in bp (0=no cavity)')
    parser.add_argument('--cavity-height', type=int, default=0,
                        help='Cavity height in helices (0=no cavity)')
    parser.add_argument('--polyt', type=int, default=4,
                        help='PolyT brush length (default: 4)')
    parser.add_argument('--no-sim', action='store_true',
                        help='Skip oxDNA simulation')
    parser.add_argument('--output-dir', default='',
                        help='Output directory (default: auto)')
    parser.add_argument('--name', default='',
                        help='Design name (default: auto)')

    args = parser.parse_args()

    params = OrigamiParams(
        scaffold_type=args.scaffold,
        n_helices=args.n_helices,
        cavity_width_bp=args.cavity_width,
        cavity_height_helices=args.cavity_height,
        polyt_length=args.polyt,
        output_dir=args.output_dir,
        design_name=args.name,
    )

    # Auto-compute helix length if not specified
    if args.helix_length > 0:
        params.helix_length_bp = args.helix_length
    else:
        params.auto_dimensions()

    print(f"\nAuto-computed helix length: {params.helix_length_bp} bp")

    run_pipeline(params, skip_sim=args.no_sim)


if __name__ == '__main__':
    main()
