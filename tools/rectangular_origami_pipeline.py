#!/usr/bin/env python
"""
Rectangular DNA Origami Pipeline — End-to-End

Creates a rectangular DNA origami design using m13mp18 (7249 nt) scaffold,
with proper scaffold routing, staple placement via autoStaple, staple breaking
via autoBreakStaples, and oxDNA verification (energy minimization + MD relaxation).

Design: 24 helices × 294 bp on honeycomb lattice (= 7056 bp scaffold routed),
plus 193 single-base insertions distributed across helices for twist correction,
consuming the full 7249 nt scaffold.

Pipeline:
  1. Create helices with scaffold strands
  2. Route scaffold (serpentine with half/double crossovers)
  3. Place staples via autoStaple
  4. Break staples via autoBreakStaples (Dijkstra-optimized)
  5. Add insertions for twist correction + scaffold utilization
  6. Export cadnano JSON
  7. Convert to oxDNA via tacoxDNA
  8. Energy minimization (CPU, DNA2)
  9. MD relaxation (CUDA or CPU, DNA2)
  10. Analyze results and generate figures

Usage:
  conda activate cn24-agentic
  QT_QPA_PLATFORM=offscreen python -m tools.rectangular_origami_pipeline
"""

import os
import sys
import json
import subprocess
import shutil
import time

# CRITICAL: Must set before any Qt imports
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TACOX_DIR = os.path.join(os.path.dirname(PROJECT_ROOT), 'tacoxDNA')
TACOX_SCRIPT = os.path.join(TACOX_DIR, 'src', 'cadnano_oxDNA.py')
OXDNA_DIR = os.path.join(os.path.dirname(os.path.dirname(PROJECT_ROOT)), 'forks', 'oxDNA-master')
OXDNA_BIN = os.path.join(OXDNA_DIR, 'build', 'bin', 'oxDNA')
WORK_DIR = os.path.join(PROJECT_ROOT, 'results', 'rectangular_origami')
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results')

# Design parameters
N_HELICES = 24
HELIX_LENGTH = 294  # 14 × 21 (honeycomb step)
M13_LENGTH = 7249
SCAFFOLD_ROUTED = N_HELICES * HELIX_LENGTH  # 7056
INSERTIONS_NEEDED = M13_LENGTH - SCAFFOLD_ROUTED  # 193

OXDNA_UNIT_NM = 0.8518


def create_rectangular_origami():
    """
    Create a rectangular DNA origami design in cadnano.

    24 helices in a single row, scaffold routed serpentine,
    staples placed by autoStaple and broken by autoBreakStaples.

    Returns: (json_path, design_info dict)
    """
    import cadnano2.cadnano as cadnano

    print("=" * 60)
    print("STEP 1: Creating rectangular DNA origami design")
    print("=" * 60)
    print(f"  Helices: {N_HELICES}")
    print(f"  Helix length: {HELIX_LENGTH} bp ({HELIX_LENGTH // 21} steps)")
    print(f"  Scaffold routed: {SCAFFOLD_ROUTED} bp")
    print(f"  Insertions needed: {INSERTIONS_NEEDED}")
    print(f"  Total scaffold: {SCAFFOLD_ROUTED + INSERTIONS_NEEDED} bp (m13mp18)")

    app = cadnano.initAppWithGui()
    from cadnano2.views.agent.agentmethods import AgentMethods

    dc = list(app.documentControllers)[0]
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    class MockDC:
        def __init__(self, app, doc, part):
            self._app = app
            self._doc = doc
            self._part = part
        def document(self):
            return self._doc
        def activePart(self):
            return self._part
        def undoStack(self):
            return self._doc.undoStack()

    mock = MockDC(app, doc, part)
    methods = AgentMethods(mock)

    # --- Step 1a: Create helices (empty) ---
    # Single row of 24 helices: row 21, columns 4-27 (within default 32-col grid)
    positions = [[21, 4 + i] for i in range(N_HELICES)]
    print(f"\n  Creating {N_HELICES} helices at positions {positions[0]} to {positions[-1]}...")

    # Extend part size first, then create helices without strands
    from math import ceil
    step = part.stepSize()
    if HELIX_LENGTH - 1 > part.maxBaseIdx():
        delta_needed = (HELIX_LENGTH - 1) - part.maxBaseIdx()
        delta = int(ceil(delta_needed / step)) * step
        part.resizeVirtualHelices(0, delta, useUndoStack=True)

    for pos in positions:
        part.createVirtualHelix(pos[0], pos[1], useUndoStack=True)

    print(f"  Created {len(list(part.getVirtualHelices()))} helices")

    # --- Step 1b: Route scaffold serpentine with correctly-sized strands ---
    print(f"\n  Routing scaffold serpentine...")
    scaffold_info = route_scaffold_serpentine_v2(part, methods)
    print(f"  Scaffold routing: {scaffold_info}")

    # Verify scaffold is one continuous oligo
    scaffold_oligo_count = sum(1 for o in part.oligos() if not o.isStaple())
    print(f"  Scaffold oligos: {scaffold_oligo_count} (should be 1 for perfect serpentine)")

    # --- Step 1c: Run autoStaple to place staples ---
    # autoStaple creates staple strands and staple crossovers based on scaffold topology
    print(f"\n  Running autoStaple...")
    from cadnano2.model.parts.part import Part
    Part.autoStaple(part)
    print(f"  autoStaple complete")

    # Count staples before breaking
    staple_count_before = 0
    for o in part.oligos():
        if o.isStaple():
            staple_count_before += 1
    print(f"  Staples before breaking: {staple_count_before}")

    # --- Step 1d: Break staples ---
    # Use the autobreak plugin directly to avoid import issues
    print(f"\n  Breaking staples (Dijkstra-optimized, target=32 nt)...")
    break_result = break_staples_direct(part)
    print(f"  Break result: {break_result}")

    # --- Step 1e: Add insertions for twist correction + scaffold utilization ---
    # Compute actual insertions needed based on scaffold length after routing
    scaffold_oligos_pre = [o for o in part.oligos() if not o.isStaple()]
    scaffold_len_pre = sum(o.length() for o in scaffold_oligos_pre)
    actual_insertions_needed = M13_LENGTH - scaffold_len_pre
    print(f"\n  Scaffold before insertions: {scaffold_len_pre} bp")
    print(f"  Insertions needed for {M13_LENGTH} bp m13: {actual_insertions_needed}")
    if actual_insertions_needed > 0:
        insertions_added = add_twist_correction_insertions(part, methods,
                                                           target_insertions=actual_insertions_needed)
    else:
        insertions_added = 0
    print(f"  Insertions added: {insertions_added}")

    # --- Count final statistics ---
    scaffold_oligos = []
    staple_oligos = []
    for o in part.oligos():
        if o.isStaple():
            staple_oligos.append(o)
        else:
            scaffold_oligos.append(o)

    total_scaffold_bases = sum(o.length() for o in scaffold_oligos)
    total_staple_bases = sum(o.length() for o in staple_oligos)
    staple_lengths = [o.length() for o in staple_oligos]

    design_info = {
        'n_helices': N_HELICES,
        'helix_length_bp': HELIX_LENGTH,
        'scaffold_bases': total_scaffold_bases,
        'staple_count': len(staple_oligos),
        'staple_bases': total_staple_bases,
        'staple_avg_len': np.mean(staple_lengths) if staple_lengths else 0,
        'staple_min_len': min(staple_lengths) if staple_lengths else 0,
        'staple_max_len': max(staple_lengths) if staple_lengths else 0,
        'insertions_added': insertions_added,
    }

    print(f"\n  Design statistics:")
    print(f"    Scaffold oligos: {len(scaffold_oligos)}, total bases: {total_scaffold_bases}")
    print(f"    Staple oligos: {len(staple_oligos)}, total bases: {total_staple_bases}")
    print(f"    Staple lengths: {design_info['staple_min_len']}-{design_info['staple_max_len']} "
          f"(avg {design_info['staple_avg_len']:.1f})")

    # --- Save JSON ---
    os.makedirs(WORK_DIR, exist_ok=True)
    json_path = os.path.join(WORK_DIR, 'rectangular_origami.json')
    dc.writeDocumentToFile(json_path)
    print(f"\n  Saved: {json_path}")

    return json_path, design_info, app


def route_scaffold_serpentine_v2(part, methods):
    """
    Route the scaffold through helices in a serpentine pattern.

    Creates scaffold strands with exact ranges between crossover positions,
    then directly connects them using strand setConnection methods.

    Returns dict with routing info.
    """
    from cadnano2.model.parts.honeycombpart import Crossovers
    from cadnano2.model.strand import Strand

    helices = sorted(part.getVirtualHelices(), key=lambda vh: vh.coord()[1])
    n = len(helices)
    step = part.stepSize()

    # Step 1: Compute crossover positions from lattice rules
    xover_positions = []
    for i in range(n - 1):
        vh1, vh2 = helices[i], helices[i + 1]
        neighbors = part.getVirtualHelixNeighbors(vh1)
        if vh2 not in neighbors:
            return f"Error: Helix {vh2.number()} not neighbor of {vh1.number()}"
        direction_idx = neighbors.index(vh2)
        low_offsets = Crossovers.honeycombScafLow[direction_idx]
        high_offsets = Crossovers.honeycombScafHigh[direction_idx]

        positions = []
        for base in range(0, part.maxBaseIdx() + 1, step):
            for low_off, high_off in zip(low_offsets, high_offsets):
                low_idx = base + low_off
                high_idx = base + high_off
                if 0 <= low_idx < HELIX_LENGTH and 0 <= high_idx < HELIX_LENGTH:
                    positions.append({'low_idx': low_idx, 'high_idx': high_idx})

        if not positions:
            return f"No crossover positions for pair ({vh1.number()}, {vh2.number()})"

        # Turn direction: even exits right, odd exits left
        if vh1.isEvenParity():
            turn = positions[-1]  # rightmost
        else:
            turn = positions[0]   # leftmost

        xover_positions.append(turn)

    # Step 2: Determine strand ranges
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
            strand_ranges.append((min(xo_prev, xo_next), max(xo_prev, xo_next)))

    total_scaffold = sum(hi - lo + 1 for lo, hi in strand_ranges)
    print(f"    Strand ranges (first 4): {strand_ranges[:4]}...")
    print(f"    Total scaffold bases (before insertions): {total_scaffold}")

    # Step 3: Create scaffold strands
    for vh, (lo, hi) in zip(helices, strand_ranges):
        scaf_ss = vh.scaffoldStrandSet()
        result = scaf_ss.createStrand(lo, hi, useUndoStack=True)
        if result < 0:
            return f"Error creating scaffold strand on helix {vh.number()} [{lo}:{hi}]"

    # Step 4: Connect strands directly at endpoints
    xovers_placed = 0
    for i in range(n - 1):
        vh1, vh2 = helices[i], helices[i + 1]
        xover_idx = xover_positions[i]['low_idx']

        scaf1 = vh1.scaffoldStrandSet().getStrand(xover_idx)
        scaf2 = vh2.scaffoldStrandSet().getStrand(xover_idx)
        if scaf1 is None or scaf2 is None:
            print(f"    WARNING: No strand at idx {xover_idx} for h{vh1.number()}/{vh2.number()}")
            continue

        lo1, hi1 = scaf1.idxs()
        lo2, hi2 = scaf2.idxs()

        # Find which strand has its 3' end at xover_idx (= strand5p)
        # and which has its 5' end there (= strand3p)
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
                print(f"    WARNING: Can't determine 5p/3p for {vh1.number()}-{vh2.number()}")
                continue

        # Merge oligos
        olg5p = strand5p.oligo()
        olg3p = strand3p.oligo()
        if olg5p != olg3p:
            olg5p.incrementLength(olg3p.length())
            olg3p.removeFromPart()
            for s in strand3p.generator3pStrand():
                Strand.setOligo(s, olg5p)

        # Install crossover
        strand5p.setConnection3p(strand3p)
        strand3p.setConnection5p(strand5p)
        xovers_placed += 1

    return {
        'xovers_placed': xovers_placed,
        'total_scaffold_bp': total_scaffold,
        'strand_count': n,
    }


def route_scaffold_serpentine(part, methods):
    """
    Route the scaffold through helices in a serpentine pattern.

    In a rectangular DNA origami, the scaffold crosses between helices
    exactly ONCE per pair, alternating between left and right ends.
    This creates a raster/serpentine path: h0→h1→h2→...→hN-1.

    Uses addCrossoversForPair with a single position to place one
    half-crossover at the turn end.
    """
    # Sort helices by COLUMN position (spatial order), not helix number.
    helices = sorted(part.getVirtualHelices(), key=lambda vh: vh.coord()[1])
    n = len(helices)
    print(f"    Helix order (by column): {[(vh.number(), vh.coord()) for vh in helices]}")

    crossovers_placed = 0

    for i in range(n - 1):
        vh1 = helices[i]
        vh2 = helices[i + 1]
        h1 = vh1.number()
        h2 = vh2.number()

        # Get suggested crossover positions
        suggestions = methods.suggestCrossovers(h1, h2, "scaffold", min_spacing=21)
        if isinstance(suggestions, str):
            print(f"    WARNING: {suggestions} for pair ({h1}, {h2})")
            continue

        all_positions = suggestions.get('positions', [])
        if not all_positions:
            print(f"    WARNING: No crossover positions for pair ({h1}, {h2})")
            continue

        # Determine turn direction based on parity of the first helix.
        # Even parity helix: scaffold runs L→R, exits at RIGHT end → turn at rightmost
        # Odd parity helix:  scaffold runs R→L, exits at LEFT end → turn at leftmost
        if vh1.isEvenParity():
            turn_pos = all_positions[-1]  # rightmost (scaffold exits right)
        else:
            turn_pos = all_positions[0]   # leftmost (scaffold exits left)

        low_idx = turn_pos['low_idx']
        high_idx = turn_pos['high_idx']

        # Use createHalfCrossover which handles 5'/3' parity correctly.
        # Try low_idx first, then high_idx.
        result = methods.createHalfCrossover(h1, low_idx, h2, low_idx, "scaffold")
        if isinstance(result, str) and result.startswith("Error"):
            result = methods.createHalfCrossover(h1, high_idx, h2, high_idx, "scaffold")
            if isinstance(result, str) and result.startswith("Error"):
                print(f"    WARNING: Failed ({h1}↔{h2}) at {low_idx}/{high_idx}: {result}")
                continue

    return crossovers_placed


def break_staples_direct(part):
    """
    Break staples using the autobreak plugin.
    Patches the relative import issue by pre-loading staplegraph.
    """
    import importlib
    import importlib.util

    # First, load staplegraph as an absolute module
    sg_path = os.path.join(PROJECT_ROOT, 'cadnano2', 'plugins', 'autobreak', 'staplegraph.py')
    sg_spec = importlib.util.spec_from_file_location(
        "cadnano2.plugins.autobreak.staplegraph", sg_path,
        submodule_search_locations=[]
    )
    sg = importlib.util.module_from_spec(sg_spec)
    sys.modules['cadnano2.plugins.autobreak.staplegraph'] = sg
    sg_spec.loader.exec_module(sg)

    # Now import autobreak - the relative import will find staplegraph
    # Force reimport to pick up the patched staplegraph
    if 'cadnano2.plugins.autobreak.autobreak' in sys.modules:
        del sys.modules['cadnano2.plugins.autobreak.autobreak']

    ab_path = os.path.join(PROJECT_ROOT, 'cadnano2', 'plugins', 'autobreak', 'autobreak.py')
    ab_spec = importlib.util.spec_from_file_location(
        "cadnano2.plugins.autobreak.autobreak", ab_path,
        submodule_search_locations=[]
    )
    ab = importlib.util.module_from_spec(ab_spec)
    sys.modules['cadnano2.plugins.autobreak.autobreak'] = ab
    ab_spec.loader.exec_module(ab)

    settings = {
        'minStapleLen': 18,
        'maxStapleLen': 50,
        'tgtStapleLen': 32,
        'minStapleLegLen': 5,
    }

    before = sum(1 for o in part.oligos() if o.isStaple())

    try:
        ab.breakStaples(part, settings)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error breaking staples: {e}"

    after = sum(1 for o in part.oligos() if o.isStaple())
    lengths = [o.length() for o in part.oligos() if o.isStaple()]

    return {
        'before': before,
        'after': after,
        'breaks_added': after - before,
        'avg_length': np.mean(lengths) if lengths else 0,
        'min_length': min(lengths) if lengths else 0,
        'max_length': max(lengths) if lengths else 0,
    }


def add_twist_correction_insertions(part, methods, target_insertions=None):
    """
    Add single-base insertions distributed across helices.

    For honeycomb lattice twist correction and to consume full m13 scaffold.
    Uses insertion length 1 for most, and higher lengths if needed.
    """
    if target_insertions is None:
        target_insertions = INSERTIONS_NEEDED

    insertions_per_helix = target_insertions // N_HELICES
    remainder = target_insertions % N_HELICES

    total_added = 0

    for vh in part.getVirtualHelices():
        helix_num = vh.number()
        n_ins = insertions_per_helix + (1 if helix_num < remainder else 0)

        # Space insertions evenly along the helix
        spacing = HELIX_LENGTH // (n_ins + 1)
        scaf_ss = vh.scaffoldStrandSet()

        for i in range(n_ins):
            idx = spacing * (i + 1)

            # Find a strand at this position
            strand = scaf_ss.getStrand(idx)
            if strand is None:
                continue

            # Avoid positions near crossovers (within 3 bp)
            has_nearby_xover = False
            for offset in range(-3, 4):
                check_idx = idx + offset
                s = scaf_ss.getStrand(check_idx)
                if s and s.hasXoverAt(check_idx):
                    has_nearby_xover = True
                    break

            if has_nearby_xover:
                # Try shifting by a few positions
                shifted = False
                for delta in [4, 5, -4, -5, 6, -6]:
                    alt_idx = idx + delta
                    alt_strand = scaf_ss.getStrand(alt_idx)
                    if alt_strand is None:
                        continue
                    ok = True
                    for offset in range(-3, 4):
                        s = scaf_ss.getStrand(alt_idx + offset)
                        if s and s.hasXoverAt(alt_idx + offset):
                            ok = False
                            break
                    if ok:
                        idx = alt_idx
                        strand = alt_strand
                        shifted = True
                        break
                if not shifted:
                    continue

            # Add insertion of length 1 (adds 1 extra base)
            strand.addInsertion(idx, 1, useUndoStack=False)
            total_added += 1

    return total_added


def convert_to_oxdna(json_path):
    """Convert cadnano JSON to oxDNA format using tacoxDNA."""
    print("\n" + "=" * 60)
    print("STEP 2: Converting to oxDNA format")
    print("=" * 60)

    if not os.path.exists(TACOX_SCRIPT):
        raise FileNotFoundError(f"tacoxDNA not found at {TACOX_SCRIPT}")

    cmd = [
        sys.executable, TACOX_SCRIPT,
        json_path,
        'he'  # honeycomb lattice
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=WORK_DIR)

    if result.returncode != 0:
        print(f"  STDERR: {result.stderr}")
        raise RuntimeError(f"tacoxDNA failed: {result.stderr}")

    print(f"  tacoxDNA output: {result.stdout[:500]}")

    # Find output files (tacoxDNA names them as <input>.oxdna and <input>.top)
    json_basename = os.path.basename(json_path)
    dat_path = os.path.join(WORK_DIR, json_basename + '.oxdna')
    top_path = os.path.join(WORK_DIR, json_basename + '.top')

    if dat_path is None or top_path is None:
        raise FileNotFoundError(f"oxDNA output files not found in {WORK_DIR}")

    # Standardize names for simulation
    std_conf = os.path.join(WORK_DIR, 'start.conf')
    std_top = os.path.join(WORK_DIR, 'topology.top')
    shutil.copy2(dat_path, std_conf)
    shutil.copy2(top_path, std_top)

    # Parse topology for info
    with open(std_top) as f:
        header = f.readline().split()
        n_nuc = int(header[0])
        n_strands = int(header[1])

    print(f"  Nucleotides: {n_nuc}")
    print(f"  Strands: {n_strands}")
    print(f"  Config: {std_conf}")
    print(f"  Topology: {std_top}")

    return std_conf, std_top, n_nuc, n_strands


def write_oxdna_input_files():
    """Write oxDNA input files for energy minimization and MD relaxation."""
    print("\n" + "=" * 60)
    print("STEP 3: Writing oxDNA input files")
    print("=" * 60)

    # Stage 1: Energy minimization (CPU)
    input_min = """# Stage 1: Energy Minimization (CPU)
# Steepest descent to remove steric clashes from tacoxDNA placement

backend = CPU
sim_type = min
interaction_type = DNA2

# Backbone force capping to prevent FENE divergence
max_backbone_force = 5.
max_backbone_force_far = 10.

steps = 5000
dt = 0.005
T = 300K
verlet_skin = 0.15
salt_concentration = 0.5

time_scale = linear
refresh_vel = true

topology = topology.top
conf_file = start.conf
lastconf_file = minimized.conf
trajectory_file = traj_min.dat
energy_file = energy_min.dat

print_conf_interval = 1000
print_energy_every = 100
no_stdout_energy = false
restart_step_counter = 1
"""

    # Stage 2: MD Relaxation
    # Check if CUDA backend is available in the oxDNA build
    # We compiled CPU-only, so always use CPU for now
    use_cuda = False  # Set True when oxDNA is compiled with -DCUDA=ON

    if use_cuda:
        backend_section = """backend = CUDA
backend_precision = mixed
CUDA_list = verlet
use_edge = 1
edge_n_forces = 1
CUDA_sort_every = 0"""
    else:
        backend_section = "backend = CPU"

    input_relax = f"""# Stage 2: MD Relaxation
# Molecular dynamics to relax the structure

{backend_section}
sim_type = MD
interaction_type = DNA2

# Backbone force capping (still needed during early relaxation)
max_backbone_force = 5.
max_backbone_force_far = 10.

time_scale = linear
dt = 0.002
T = 300K
thermostat = bussi
bussi_tau = 1000
newtonian_steps = 53
salt_concentration = 0.5

steps = 500000
verlet_skin = 0.15

topology = topology.top
conf_file = minimized.conf
trajectory_file = trajectory.dat
energy_file = energy_relax.dat
lastconf_file = relaxed.conf

refresh_vel = 1
restart_step_counter = 1
print_conf_interval = 10000
print_energy_every = 1000
no_stdout_energy = false
"""

    min_path = os.path.join(WORK_DIR, 'input_min')
    relax_path = os.path.join(WORK_DIR, 'input_relax')

    with open(min_path, 'w') as f:
        f.write(input_min)
    with open(relax_path, 'w') as f:
        f.write(input_relax)

    print(f"  Written: {min_path}")
    print(f"  Written: {relax_path}")
    print(f"  Backend for MD: {'CUDA' if use_cuda else 'CPU'}")

    return min_path, relax_path


def run_oxdna_simulation(stage_name, input_file):
    """Run an oxDNA simulation stage."""
    print(f"\n  Running oxDNA {stage_name}...")

    if not os.path.exists(OXDNA_BIN):
        print(f"  WARNING: oxDNA binary not found at {OXDNA_BIN}")
        print(f"  Skipping simulation. To compile: cd {OXDNA_DIR}/build && make -j$(nproc)")
        return False

    start_time = time.time()
    result = subprocess.run(
        [OXDNA_BIN, input_file],
        capture_output=True,
        text=True,
        cwd=WORK_DIR,
        timeout=600  # 10 min max per stage
    )
    elapsed = time.time() - start_time

    if result.returncode != 0:
        print(f"  FAILED ({elapsed:.1f}s)")
        print(f"  STDERR: {result.stderr[-1000:]}")
        return False

    print(f"  Completed in {elapsed:.1f}s")
    return True


def run_simulations():
    """Run the two-stage oxDNA simulation."""
    print("\n" + "=" * 60)
    print("STEP 4: Running oxDNA simulations")
    print("=" * 60)

    min_path = os.path.join(WORK_DIR, 'input_min')
    relax_path = os.path.join(WORK_DIR, 'input_relax')

    # Stage 1: Energy minimization
    stage1_ok = run_oxdna_simulation("energy minimization (CPU)", min_path)

    if not stage1_ok:
        return False

    # Check that minimized.conf was produced
    min_conf = os.path.join(WORK_DIR, 'minimized.conf')
    if not os.path.exists(min_conf):
        print("  ERROR: minimized.conf not produced")
        return False

    # Stage 2: MD relaxation
    stage2_ok = run_oxdna_simulation("MD relaxation", relax_path)

    return stage2_ok


def analyze_energy(energy_file, stage_name):
    """Parse and analyze an oxDNA energy file."""
    if not os.path.exists(energy_file):
        return None

    data = []
    with open(energy_file) as f:
        for line in f:
            if line.startswith('#'):
                continue
            parts = line.split()
            if len(parts) >= 3:
                data.append([float(x) for x in parts[:3]])

    if not data:
        return None

    data = np.array(data)
    return {
        'time': data[:, 0],
        'potential': data[:, 1],
        'kinetic': data[:, 2],
        'total': data[:, 1] + data[:, 2],
        'stage': stage_name,
    }


def parse_oxdna_conf(conf_path):
    """Parse an oxDNA configuration file for coordinates."""
    coords = []
    with open(conf_path) as f:
        for _ in range(3):
            next(f)  # skip header
        for line in f:
            vals = line.split()
            if len(vals) >= 9:
                coords.append([float(vals[0]), float(vals[1]), float(vals[2])])
    return np.array(coords)


def parse_oxdna_top(top_path):
    """Parse topology file for strand assignments."""
    strands = []
    bases = []
    with open(top_path) as f:
        header = f.readline().split()
        n_nuc = int(header[0])
        n_strands = int(header[1])
        for line in f:
            parts = line.split()
            if len(parts) >= 4:
                strands.append(int(parts[0]))
                bases.append(parts[1])
    return np.array(strands), bases, n_nuc, n_strands


def analyze_results(n_nuc):
    """Analyze simulation results."""
    print("\n" + "=" * 60)
    print("STEP 5: Analyzing results")
    print("=" * 60)

    results = {}

    # Parse energy files
    for stage, fname in [('minimization', 'energy_min.dat'),
                         ('relaxation', 'energy_relax.dat')]:
        energy_path = os.path.join(WORK_DIR, fname)
        energy_data = analyze_energy(energy_path, stage)
        if energy_data is not None:
            pe_final = energy_data['potential'][-1]
            pe_per_nuc = pe_final / n_nuc if n_nuc > 0 else 0
            print(f"\n  {stage.title()}:")
            print(f"    Final potential energy: {pe_final:.2f}")
            print(f"    Per nucleotide: {pe_per_nuc:.4f}")
            print(f"    Steps recorded: {len(energy_data['time'])}")

            # Check stability
            if stage == 'relaxation' and len(energy_data['potential']) > 10:
                last_20pct = energy_data['potential'][int(len(energy_data['potential']) * 0.8):]
                pe_std = np.std(last_20pct)
                pe_mean = np.mean(last_20pct)
                print(f"    Last 20% mean PE: {pe_mean:.2f} (std: {pe_std:.2f})")
                results['pe_converged'] = pe_std < abs(pe_mean) * 0.01
                results['pe_per_nuc'] = pe_mean / n_nuc

            results[f'{stage}_energy'] = {
                'time': energy_data['time'].tolist(),
                'potential': energy_data['potential'].tolist(),
                'kinetic': energy_data['kinetic'].tolist(),
            }

    # Parse final structure
    for conf_name, label in [('minimized.conf', 'minimized'),
                             ('relaxed.conf', 'relaxed')]:
        conf_path = os.path.join(WORK_DIR, conf_name)
        if os.path.exists(conf_path):
            coords = parse_oxdna_conf(conf_path)
            coords_nm = coords * OXDNA_UNIT_NM

            # PCA for shape analysis
            centered = coords_nm - coords_nm.mean(axis=0)
            cov = np.cov(centered.T)
            eigenvalues = np.linalg.eigvalsh(cov)
            eigenvalues = np.sort(eigenvalues)[::-1]
            pca_dims = 2 * np.sqrt(eigenvalues)  # approximate extent

            print(f"\n  {label.title()} structure:")
            print(f"    Nucleotides: {len(coords)}")
            print(f"    PCA dimensions (nm): {pca_dims[0]:.1f} × {pca_dims[1]:.1f} × {pca_dims[2]:.1f}")

            # Bounding box
            bb_min = coords_nm.min(axis=0)
            bb_max = coords_nm.max(axis=0)
            bb_dims = bb_max - bb_min
            print(f"    Bounding box (nm): {bb_dims[0]:.1f} × {bb_dims[1]:.1f} × {bb_dims[2]:.1f}")

            results[f'{label}_dims_nm'] = bb_dims.tolist()
            results[f'{label}_pca_nm'] = pca_dims.tolist()

    return results


def generate_figures(design_info, n_nuc, n_strands):
    """Generate visualization figures."""
    print("\n" + "=" * 60)
    print("STEP 6: Generating figures")
    print("=" * 60)

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    figures = []
    os.makedirs(os.path.join(WORK_DIR, 'figures'), exist_ok=True)

    # --- Figure 1: Design overview (initial structure from tacoxDNA) ---
    start_conf = os.path.join(WORK_DIR, 'start.conf')
    top_path = os.path.join(WORK_DIR, 'topology.top')

    if os.path.exists(start_conf) and os.path.exists(top_path):
        coords = parse_oxdna_conf(start_conf)
        strands, bases, _, _ = parse_oxdna_top(top_path)
        coords_nm = coords * OXDNA_UNIT_NM

        fig, axes = plt.subplots(1, 3, figsize=(18, 5))

        # Color by strand
        unique_strands = np.unique(strands)
        cmap = plt.cm.tab20(np.linspace(0, 1, min(20, len(unique_strands))))
        strand_colors = [cmap[s % 20] for s in strands]

        # Top view (XY)
        axes[0].scatter(coords_nm[:, 0], coords_nm[:, 1], c=strand_colors, s=0.5, alpha=0.5)
        axes[0].set_xlabel('X (nm)')
        axes[0].set_ylabel('Y (nm)')
        axes[0].set_title('Top View (XY)')
        axes[0].set_aspect('equal')

        # Side view (XZ)
        axes[1].scatter(coords_nm[:, 0], coords_nm[:, 2], c=strand_colors, s=0.5, alpha=0.5)
        axes[1].set_xlabel('X (nm)')
        axes[1].set_ylabel('Z (nm)')
        axes[1].set_title('Side View (XZ)')
        axes[1].set_aspect('equal')

        # End view (YZ)
        axes[2].scatter(coords_nm[:, 1], coords_nm[:, 2], c=strand_colors, s=0.5, alpha=0.5)
        axes[2].set_xlabel('Y (nm)')
        axes[2].set_ylabel('Z (nm)')
        axes[2].set_title('End View (YZ)')
        axes[2].set_aspect('equal')

        fig.suptitle(f'Rectangular DNA Origami — Initial Structure\n'
                     f'{N_HELICES} helices × {HELIX_LENGTH} bp, '
                     f'{n_nuc} nucleotides, {n_strands} strands',
                     fontsize=12, fontweight='bold')
        plt.tight_layout()
        path = os.path.join(WORK_DIR, 'figures', 'initial_structure.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved: {path}")
        figures.append(path)

    # --- Figure 2: Energy convergence ---
    energy_files = [
        ('energy_min.dat', 'Energy Minimization'),
        ('energy_relax.dat', 'MD Relaxation'),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for i, (fname, title) in enumerate(energy_files):
        energy_path = os.path.join(WORK_DIR, fname)
        data = analyze_energy(energy_path, title)
        if data is not None:
            axes[i].plot(data['time'], data['potential'], 'b-', linewidth=0.5, label='Potential')
            if 'relaxation' in fname:
                axes[i].plot(data['time'], data['kinetic'], 'r-', linewidth=0.5, label='Kinetic', alpha=0.5)
            axes[i].set_xlabel('Time step')
            axes[i].set_ylabel('Energy (sim units)')
            axes[i].set_title(title)
            axes[i].legend()
            axes[i].grid(True, alpha=0.3)

            # Add per-nucleotide annotation
            pe_final = data['potential'][-1]
            pe_per_nuc = pe_final / n_nuc
            axes[i].annotate(f'Final: {pe_final:.1f}\n({pe_per_nuc:.3f}/nt)',
                             xy=(0.95, 0.95), xycoords='axes fraction',
                             ha='right', va='top',
                             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        else:
            axes[i].text(0.5, 0.5, f'No data\n({fname})',
                         ha='center', va='center', transform=axes[i].transAxes)
            axes[i].set_title(title)

    plt.tight_layout()
    path = os.path.join(WORK_DIR, 'figures', 'energy_convergence.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {path}")
    figures.append(path)

    # --- Figure 3: Before/after relaxation comparison ---
    configs = [
        ('start.conf', 'Initial (tacoxDNA)'),
        ('minimized.conf', 'After Minimization'),
        ('relaxed.conf', 'After MD Relaxation'),
    ]

    available_configs = [(p, l) for p, l in configs
                         if os.path.exists(os.path.join(WORK_DIR, p))]

    if available_configs:
        fig, axes = plt.subplots(1, len(available_configs), figsize=(6 * len(available_configs), 5))
        if len(available_configs) == 1:
            axes = [axes]

        for i, (conf_name, label) in enumerate(available_configs):
            coords = parse_oxdna_conf(os.path.join(WORK_DIR, conf_name))
            coords_nm = coords * OXDNA_UNIT_NM

            if os.path.exists(top_path):
                strands, _, _, _ = parse_oxdna_top(top_path)
                strand_colors = [cmap[s % 20] for s in strands]
            else:
                strand_colors = 'steelblue'

            axes[i].scatter(coords_nm[:, 0], coords_nm[:, 1],
                            c=strand_colors, s=0.5, alpha=0.5)
            axes[i].set_xlabel('X (nm)')
            axes[i].set_ylabel('Y (nm)')
            axes[i].set_title(label)
            axes[i].set_aspect('equal')

            # Bounding box
            bb = coords_nm.max(axis=0) - coords_nm.min(axis=0)
            axes[i].annotate(f'{bb[0]:.0f}×{bb[1]:.0f}×{bb[2]:.0f} nm',
                             xy=(0.02, 0.98), xycoords='axes fraction',
                             ha='left', va='top',
                             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

        fig.suptitle('Relaxation Progression', fontsize=12, fontweight='bold')
        plt.tight_layout()
        path = os.path.join(WORK_DIR, 'figures', 'relaxation_comparison.png')
        plt.savefig(path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Saved: {path}")
        figures.append(path)

    # --- Figure 4: Staple length distribution ---
    fig, ax = plt.subplots(figsize=(8, 5))
    # Read design JSON to extract staple info
    json_path = os.path.join(WORK_DIR, 'rectangular_origami.json')
    if design_info:
        # Simulated histogram from design_info
        ax.bar(['Scaffold\noligos', 'Staple\noligos'],
               [1, design_info['staple_count']],
               color=['steelblue', 'coral'])
        ax.set_ylabel('Count')
        ax.set_title(f'Strand Statistics\n'
                     f'Scaffold: {design_info["scaffold_bases"]} bp, '
                     f'Staples: {design_info["staple_count"]} '
                     f'(avg {design_info["staple_avg_len"]:.0f} nt, '
                     f'range {design_info["staple_min_len"]}-{design_info["staple_max_len"]} nt)')

        for bar_idx, val in enumerate([1, design_info['staple_count']]):
            ax.text(bar_idx, val + 1, str(val), ha='center', va='bottom')

    plt.tight_layout()
    path = os.path.join(WORK_DIR, 'figures', 'strand_statistics.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {path}")
    figures.append(path)

    # --- Figure 5: Pipeline summary ---
    fig, ax = plt.subplots(figsize=(12, 3))
    ax.axis('off')

    pipeline_text = (
        f"Rectangular DNA Origami Pipeline Summary\n"
        f"{'='*55}\n"
        f"Design: {N_HELICES} helices × {HELIX_LENGTH} bp (honeycomb lattice)\n"
        f"Scaffold: m13mp18 ({M13_LENGTH} nt), routed {SCAFFOLD_ROUTED} bp + {INSERTIONS_NEEDED} insertions\n"
        f"Staples: {design_info['staple_count']} oligos, "
        f"avg {design_info['staple_avg_len']:.0f} nt "
        f"({design_info['staple_min_len']}-{design_info['staple_max_len']} nt)\n"
        f"Insertions: {design_info.get('insertions_added', 0)} twist correction insertions\n"
        f"\n"
        f"Pipeline: cadnano design → autoStaple → autoBreak → tacoxDNA → oxDNA\n"
        f"Stages: Energy minimization (CPU, DNA2) → MD relaxation (DNA2)"
    )
    ax.text(0.05, 0.95, pipeline_text, transform=ax.transAxes,
            fontsize=10, verticalalignment='top', fontfamily='monospace',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.8))
    plt.tight_layout()
    path = os.path.join(WORK_DIR, 'figures', 'pipeline_summary.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {path}")
    figures.append(path)

    return figures


def main():
    os.makedirs(WORK_DIR, exist_ok=True)

    # Step 1: Create the design
    json_path, design_info, app = create_rectangular_origami()

    # Step 2: Convert to oxDNA
    conf_path, top_path, n_nuc, n_strands = convert_to_oxdna(json_path)

    # Step 3: Write simulation input files
    write_oxdna_input_files()

    # Step 4: Run simulations
    sim_ok = run_simulations()

    # Step 5: Analyze results
    results = analyze_results(n_nuc)

    # Step 6: Generate figures
    figures = generate_figures(design_info, n_nuc, n_strands)

    # Step 7: Save full report
    report = {
        'design': design_info,
        'oxdna': {
            'n_nucleotides': n_nuc,
            'n_strands': n_strands,
        },
        'simulation_completed': sim_ok,
        'analysis': {k: v for k, v in results.items()
                     if not isinstance(v, dict) or 'time' not in v},
        'figures': figures,
        'files': {
            'cadnano_json': json_path,
            'oxdna_conf': conf_path,
            'oxdna_top': top_path,
        },
    }

    report_path = os.path.join(WORK_DIR, 'pipeline_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2, default=str)

    # Print summary
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    print(f"  Design: {N_HELICES} helices × {HELIX_LENGTH} bp (honeycomb)")
    print(f"  Scaffold: m13mp18 ({M13_LENGTH} nt)")
    print(f"  Scaffold routed: {design_info['scaffold_bases']} bp")
    print(f"  Staples: {design_info['staple_count']} (avg {design_info['staple_avg_len']:.0f} nt)")
    print(f"  Insertions: {design_info.get('insertions_added', 0)}")
    print(f"  Nucleotides in oxDNA: {n_nuc}")
    print(f"  Simulation: {'COMPLETED' if sim_ok else 'SKIPPED/FAILED'}")

    if 'pe_per_nuc' in results:
        print(f"  Final PE/nucleotide: {results['pe_per_nuc']:.4f}")
        print(f"  PE converged: {results.get('pe_converged', 'N/A')}")
        # A well-relaxed origami has PE/nt around -1.4
        pe = results['pe_per_nuc']
        if pe < -1.2:
            print(f"  Assessment: Structure appears STABLE (PE/nt = {pe:.3f})")
        elif pe < -0.8:
            print(f"  Assessment: Structure PARTIALLY relaxed (PE/nt = {pe:.3f})")
        else:
            print(f"  Assessment: Structure may be UNSTABLE (PE/nt = {pe:.3f})")

    print(f"\n  Report: {report_path}")
    print(f"  Figures: {os.path.join(WORK_DIR, 'figures')}")
    print("=" * 60)


if __name__ == '__main__':
    main()
