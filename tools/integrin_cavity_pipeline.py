#!/usr/bin/env python
"""
Integrin αvβ3 Cavity Pipeline — Build, staple, convert, and submit to PACE.

Designs a 2-layer DNA origami with a cavity sized to fit integrin αvβ3
(~15nm × 20nm). Uses the 4-step template-scaling approach generalized
for variable grid widths and cavity sizes.

Strategy: Start from the PI's 2×12 template, extend to 2×N by adding
columns, then adjust cavity width and height.

Three candidate designs run concurrently on PACE RTX_6000 GPUs with
early stopping (500K steps gentle relax to check stability).

Usage:
  conda activate cn24-agentic
  python tools/integrin_cavity_pipeline.py
"""

import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

import sys
import io
import json
import copy
import subprocess
import shutil
import importlib
import importlib.util
from math import ceil
from dataclasses import dataclass
from typing import List, Tuple, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, '2x12_rectangle_cavity.json')
OUTPUT_BASE = os.path.join(PROJECT_ROOT, 'results', 'integrin_cavity')
TACOX_SCRIPT = os.path.join(os.path.dirname(PROJECT_ROOT), 'tacoxDNA', 'src', 'cadnano_oxDNA.py')

NM_PER_BP = 0.34
STEP = 21
SCAFFOLD_TARGET = 8064
HELIX_SPACING_NM = 2.6  # honeycomb inter-column

EMPTY = [-1, -1, -1, -1]

# ── Design Specification ─────────────────────────────────────────────────

@dataclass
class CavityDesign:
    name: str
    n_cols: int           # total columns (e.g., 14, 16)
    n_cavity_cols: int    # cavity columns (e.g., 6, 8)
    gap_bp: int           # cavity width in bp along helix axis
    helix_len: int = 0    # computed
    cavity_height_nm: float = 0.0  # computed
    cavity_width_nm: float = 0.0   # computed

    def compute(self):
        self.cavity_height_nm = self.n_cavity_cols * HELIX_SPACING_NM
        self.cavity_width_nm = self.gap_bp * NM_PER_BP
        n_helices = 2 * self.n_cols
        n_cavity = 2 * self.n_cavity_cols
        target_L = (SCAFFOLD_TARGET / 0.95 + n_cavity * self.gap_bp) / n_helices
        self.helix_len = int(ceil(target_L / STEP)) * STEP
        self.helix_len = max(self.helix_len, self.gap_bp + 140)
        return self


# ── Candidate Designs ────────────────────────────────────────────────────

DESIGNS = [
    CavityDesign(
        name='integrin_2x14_6cav_59bp',
        n_cols=14, n_cavity_cols=6, gap_bp=59,
    ).compute(),  # ~15.6nm × 20.1nm cavity
    CavityDesign(
        name='integrin_2x16_8cav_44bp',
        n_cols=16, n_cavity_cols=8, gap_bp=44,
    ).compute(),  # ~20.8nm × 15.0nm cavity
    CavityDesign(
        name='integrin_2x14_8cav_44bp',
        n_cols=14, n_cavity_cols=8, gap_bp=44,
    ).compute(),  # ~20.8nm × 15.0nm cavity (narrower structure)
]


# ── Build Design from Template Extension ─────────────────────────────────

def build_design(design: CavityDesign, output_dir: str):
    """Build a cavity design by extending the 2×12 template.

    Uses the 4-step template-scaling approach adapted for wider grids.
    For n_cols > 12, adds extra helix pairs to the template.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Load template
    with open(TEMPLATE_PATH) as f:
        template = json.load(f)

    n_cols = design.n_cols
    gap_bp = design.gap_bp
    helix_len = design.helix_len
    n_cav_cols = design.n_cavity_cols

    # Template has 24 helices (2×12), helix_len=252
    # For wider designs, we need to add more helices to the template

    if n_cols == 12:
        # Use template directly
        result = extend_template_12(template, design)
    else:
        # Create a wider template by adding helix pairs
        result = build_wider_template(template, design)

    # Save JSON
    json_path = os.path.join(output_dir, f'{design.name}.json')
    with open(json_path, 'w') as f:
        json.dump(result, f, separators=(',', ':'))

    return json_path, result


def build_wider_template(template, design: CavityDesign):
    """Build a wider design by creating helices from scratch.

    Uses cadnano API to create all helices, place crossovers, and route
    the scaffold. Then exports to JSON.
    """
    import cadnano2.cadnano as cadnano
    app = cadnano.app()
    if app is None:
        app = cadnano.initAppWithGui()

    from cadnano2.model.parts.honeycombpart import Crossovers
    from cadnano2.model.parts.part import Part

    dc = list(app.documentControllers)[0]
    # Don't call newDocument() — each subprocess starts fresh
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    n_cols = design.n_cols
    helix_len = design.helix_len
    gap_bp = design.gap_bp
    n_cav_cols = design.n_cavity_cols

    # Extend part size
    step = part.stepSize()
    if helix_len - 1 > part.maxBaseIdx():
        delta = int(ceil((helix_len - 1 - part.maxBaseIdx()) / step)) * step
        part.resizeVirtualHelices(0, delta, useUndoStack=True)

    # Create helices — same layout pattern as template
    # Row 12: columns from right to left (col start_col + n_cols - 1 down to start_col)
    # Row 13: columns from left to right (col start_col up to start_col + n_cols - 1)
    start_col = max(4, 20 - n_cols + 1)  # keep within grid bounds
    ROW_A = [(12, c) for c in range(start_col + n_cols - 1, start_col - 1, -1)]
    ROW_B = [(13, c) for c in range(start_col, start_col + n_cols)]
    all_pos = ROW_A + ROW_B

    # Cavity columns (centered)
    cav_col_start = start_col + (n_cols - n_cav_cols) // 2
    cav_col_end = cav_col_start + n_cav_cols
    CAVITY_COLS = set(range(cav_col_start, cav_col_end))

    for r, c in all_pos:
        part.createVirtualHelix(r, c, useUndoStack=True)

    vh_by_idx = {}
    for i, (r, c) in enumerate(all_pos):
        vh_by_idx[i] = part.virtualHelixAtCoord((r, c))

    n_helices = len(vh_by_idx)
    print(f'  Created {n_helices} helices ({n_cols} cols)', flush=True)

    # Compute cavity gap position (centered along helix)
    gap_center = helix_len // 2

    # Valid crossover offsets for intra-pair (row 12 uses p2, row 13 uses p0)
    R12_OFFSETS = [4, 5, 15, 16]
    R13_OFFSETS = [1, 2, 11, 12]

    def snap(target, offsets):
        best = None
        for k in range(helix_len // STEP + 1):
            for off in offsets:
                pos = k * STEP + off
                if 0 <= pos < helix_len:
                    if best is None or abs(pos - target) < abs(best - target):
                        best = pos
        return best

    # Crossover positions
    r12_edge_left = 5
    r12_edge_right = snap(helix_len - 6, R12_OFFSETS)
    r12_seam_left = snap(gap_center - 1, R12_OFFSETS)
    r12_seam_right = snap(gap_center, R12_OFFSETS)
    if r12_seam_right <= r12_seam_left:
        r12_seam_right = snap(r12_seam_left + 1, R12_OFFSETS)
    r12_cav_left = snap(gap_center - gap_bp // 2, R12_OFFSETS)
    r12_cav_right = snap(gap_center + gap_bp // 2, R12_OFFSETS)
    if r12_cav_right <= r12_cav_left:
        r12_cav_right = snap(r12_cav_left + gap_bp, R12_OFFSETS)

    r13_edge_left = 2
    r13_edge_right = snap(helix_len - 3, R13_OFFSETS)
    r13_seam_left = snap(gap_center - 1, R13_OFFSETS)
    r13_seam_right = snap(gap_center, R13_OFFSETS)
    if r13_seam_right <= r13_seam_left:
        r13_seam_right = snap(r13_seam_left + 1, R13_OFFSETS)
    r13_cav_left = snap(gap_center - gap_bp // 2, R13_OFFSETS)
    r13_cav_right = snap(gap_center + gap_bp // 2, R13_OFFSETS)
    if r13_cav_right <= r13_cav_left:
        r13_cav_right = snap(r13_cav_left + gap_bp, R13_OFFSETS)

    print(f'  Row 12: edges [{r12_edge_left},{r12_edge_right}], cavity [{r12_cav_left},{r12_cav_right}]', flush=True)
    print(f'  Row 13: edges [{r13_edge_left},{r13_edge_right}], cavity [{r13_cav_left},{r13_cav_right}]', flush=True)

    # Create scaffold strands
    for i, (r, c) in enumerate(all_pos):
        vh = vh_by_idx[i]
        scaf_ss = vh.scaffoldStrandSet()
        is_cavity = c in CAVITY_COLS

        if r == 12:
            lo, hi = r12_edge_left, r12_edge_right
            g_lo, g_hi = r12_cav_left + 1, r12_cav_right - 1
        else:
            lo, hi = r13_edge_left, r13_edge_right
            g_lo, g_hi = r13_cav_left + 1, r13_cav_right - 1

        if is_cavity:
            scaf_ss.createStrand(lo, g_lo - 1, useUndoStack=True)
            scaf_ss.createStrand(g_hi + 1, hi, useUndoStack=True)
        else:
            scaf_ss.createStrand(lo, hi, useUndoStack=True)

    # Place intra-pair crossovers
    n_pairs = n_cols
    xovers = 0
    for pair_idx in range(n_pairs):
        h_a = pair_idx * 2
        h_b = pair_idx * 2 + 1
        vh_a = vh_by_idx[h_a]
        vh_b = vh_by_idx[h_b]
        r = all_pos[h_a][0]
        c = all_pos[h_a][1]
        is_cavity = c in CAVITY_COLS
        is_last = (pair_idx == n_pairs - 1)

        if is_last:
            positions = [r13_edge_left, r13_edge_right]
        elif is_cavity:
            if r == 12:
                positions = [r12_edge_left, r12_cav_left, r12_cav_right, r12_edge_right]
            else:
                positions = [r13_edge_left, r13_cav_left, r13_cav_right, r13_edge_right]
        else:
            if r == 12:
                positions = [r12_edge_left, r12_seam_left, r12_seam_right, r12_edge_right]
            else:
                positions = [r13_edge_left, r13_seam_left, r13_seam_right, r13_edge_right]

        for pos in positions:
            try:
                sa = vh_a.scaffoldStrandSet().getStrand(pos)
                sb = vh_b.scaffoldStrandSet().getStrand(pos)
                if sa and sb:
                    part.createXover(sa, pos, sb, pos, useUndoStack=True)
                    xovers += 1
            except Exception:
                pass

    print(f'  Intra-pair crossovers: {xovers}', flush=True)

    # Place inter-pair crossovers
    inter_xovers = 0
    # Connect: (1,2), (3,4), ..., and cross-row (n_cols-1, n_cols)
    inter_pairs = []
    for i in range(1, n_cols * 2 - 1, 2):
        inter_pairs.append((i, i + 1))
    # Add cross-row connection
    inter_pairs.append((n_cols - 1, n_cols))

    for h_a, h_b in inter_pairs:
        if h_a >= n_helices or h_b >= n_helices:
            continue
        vh_a = vh_by_idx[h_a]
        vh_b = vh_by_idx[h_b]

        neighbors = part.getVirtualHelixNeighbors(vh_a)
        if vh_b not in neighbors:
            neighbors = part.getVirtualHelixNeighbors(vh_b)
            if vh_a not in neighbors:
                continue
            vh_a, vh_b = vh_b, vh_a

        dir_idx = neighbors.index(vh_b)
        low_offsets = Crossovers.honeycombScafLow[dir_idx]
        high_offsets = Crossovers.honeycombScafHigh[dir_idx]
        valid_offsets = sorted(set(list(low_offsets) + list(high_offsets)))

        # Place 2 double crossovers at ~1/4 and ~3/4 of helix
        for target_frac in [0.25, 0.75]:
            target = int(helix_len * target_frac)
            best = snap(target, valid_offsets)
            if best is not None:
                try:
                    sa = vh_a.scaffoldStrandSet().getStrand(best)
                    sb = vh_b.scaffoldStrandSet().getStrand(best)
                    if sa and sb:
                        part.createXover(sa, best, sb, best, useUndoStack=True)
                        inter_xovers += 1
                except Exception:
                    pass

    print(f'  Inter-pair crossovers: {inter_xovers}', flush=True)

    # AutoStaple
    Part.autoStaple(part)
    stap_count = sum(1 for o in part.oligos() if o.isStaple())

    # AutoBreak (all3, minLegLen=3)
    sg_path = os.path.join(PROJECT_ROOT, 'cadnano2', 'plugins', 'autobreak', 'staplegraph.py')
    sg_spec = importlib.util.spec_from_file_location(
        'cadnano2.plugins.autobreak.staplegraph', sg_path, submodule_search_locations=[])
    sg = importlib.util.module_from_spec(sg_spec)
    sys.modules['cadnano2.plugins.autobreak.staplegraph'] = sg
    sg_spec.loader.exec_module(sg)

    import types
    pkg = types.ModuleType('cadnano2.plugins.autobreak')
    pkg.__path__ = [os.path.join(PROJECT_ROOT, 'cadnano2', 'plugins', 'autobreak')]
    pkg.__package__ = 'cadnano2.plugins.autobreak'
    pkg.staplegraph = sg
    sys.modules['cadnano2.plugins.autobreak'] = pkg

    if 'cadnano2.plugins.autobreak.autobreak' in sys.modules:
        del sys.modules['cadnano2.plugins.autobreak.autobreak']
    ab_path = os.path.join(PROJECT_ROOT, 'cadnano2', 'plugins', 'autobreak', 'autobreak.py')
    ab_spec = importlib.util.spec_from_file_location(
        'cadnano2.plugins.autobreak.autobreak', ab_path, submodule_search_locations=[])
    ab = importlib.util.module_from_spec(ab_spec)
    sys.modules['cadnano2.plugins.autobreak.autobreak'] = ab
    ab_spec.loader.exec_module(ab)

    settings = {
        'minStapleLen': 18, 'maxStapleLen': 50,
        'tgtStapleLen': 32, 'minStapleLegLen': 3,
    }

    broken = 0
    for oligo in list(part.oligos()):
        if oligo.isStaple() and oligo.length() > settings['maxStapleLen']:
            try:
                ab.nxBreakStaple(oligo, settings)
                broken += 1
            except Exception:
                pass

    stap_count_after = sum(1 for o in part.oligos() if o.isStaple())
    scaf_oligos = [o for o in part.oligos() if not o.isStaple()]
    scaf_bp = sum(o.length() for o in scaf_oligos)
    n_scaf = len(scaf_oligos)

    print(f'  AutoStaple+Break: {stap_count_after} staples, scaffold {scaf_bp}bp in {n_scaf} oligo(s)', flush=True)

    # Save via encoder
    from cadnano2.model.io.encoder import encode
    output_dir = os.path.dirname(os.path.join(OUTPUT_BASE, design.name, 'x'))
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, f'{design.name}.json')
    helixOrderList = dc.win.pathroot.getSelectedPartOrderedVHList()
    with open(json_path, 'w') as f:
        encode(doc, helixOrderList, f)

    print(f'  Saved: {json_path}', flush=True)
    return json_path


def extend_template_12(template, design):
    """Use the 4-step process for 2×12 designs."""
    # Import from cavity_variant_sweep
    sys.path.insert(0, os.path.join(PROJECT_ROOT, 'tools'))
    from cavity_variant_sweep import (step1_remove_staples, step2_extend,
        step3_move_midseam, step4_set_cavity_width, fix_scaffold_directions)

    cavity_helices = {4, 5, 6, 7, 16, 17, 18, 19}
    row12_pairs = [(0,1),(2,3),(4,5),(6,7),(8,9),(10,11)]
    row13_pairs = [(12,13),(14,15),(16,17),(18,19),(20,21),(22,23)]
    cavity_pairs_r12 = [(4,5),(6,7)]
    cavity_pairs_r13 = [(16,17),(18,19)]
    cavity_pairs = set(cavity_pairs_r12 + cavity_pairs_r13)

    s1 = step1_remove_staples(template)
    s2 = step2_extend(s1, design.helix_len, cavity_helices)
    s3 = step3_move_midseam(s2, cavity_pairs, row12_pairs, row13_pairs)
    s4, _, _, _, _ = step4_set_cavity_width(s3, cavity_pairs_r12, cavity_pairs_r13, design.gap_bp)
    s5 = fix_scaffold_directions(s4)
    return s5


# ── tacoxDNA Conversion ──────────────────────────────────────────────────

def convert_to_oxdna(json_path, work_dir):
    """Convert cadnano JSON to oxDNA format."""
    cmd = [sys.executable, TACOX_SCRIPT, json_path, 'he']
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=work_dir)
    if result.returncode != 0:
        print(f'  tacoxDNA ERROR: {result.stderr[-200:]}', flush=True)
        return None, None

    base = os.path.basename(json_path)
    conf_path = os.path.join(work_dir, base + '.oxdna')
    top_path = os.path.join(work_dir, base + '.top')

    # Move to standard names
    start_conf = os.path.join(work_dir, 'start.conf')
    topology = os.path.join(work_dir, 'topology.top')
    shutil.move(conf_path, start_conf)
    shutil.move(top_path, topology)

    # Count nucleotides
    with open(topology) as f:
        header = f.readline().strip().split()
        n_nt = int(header[0])
        n_strands = int(header[1])

    print(f'  tacoxDNA: {n_nt} nucleotides, {n_strands} strands', flush=True)
    return start_conf, topology


# ── PACE SLURM Submission ────────────────────────────────────────────────

OXDNA_BIN = '/storage/home/hcoda1/6/dfu71/scratch/oxDNA/build/bin/oxDNA'

def write_oxdna_inputs(work_dir, early_stop_steps=500000):
    """Write oxDNA input files with early stopping for quick iteration."""

    # Stage 1: Minimization (CPU)
    with open(os.path.join(work_dir, 'input_min'), 'w') as f:
        f.write(f"""backend = CPU
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
""")

    # Stage 2: Gentle relax (GPU, early stopping)
    with open(os.path.join(work_dir, 'input_relax'), 'w') as f:
        f.write(f"""backend = CUDA
backend_precision = mixed
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
steps = {early_stop_steps}
verlet_skin = 0.5
topology = topology.top
conf_file = minimized.conf
trajectory_file = trajectory.dat
energy_file = energy_relax.dat
lastconf_file = relaxed.conf
refresh_vel = 1
restart_step_counter = 1
time_scale = linear
print_conf_interval = {early_stop_steps // 5}
print_energy_every = 1000
no_stdout_energy = false
""")

    # SLURM scripts
    with open(os.path.join(work_dir, 'min.sh'), 'w') as f:
        f.write(f"""#!/bin/bash
#SBATCH -J {os.path.basename(work_dir)}_min
#SBATCH -A gts-yke8
#SBATCH --time=01:00:00
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=daniel.fu@emory.edu

cd $SLURM_SUBMIT_DIR
module load cuda/12.1.1 gcc/12.3.0

srun {OXDNA_BIN} input_min
""")

    with open(os.path.join(work_dir, 'relax.sh'), 'w') as f:
        f.write(f"""#!/bin/bash
#SBATCH -J {os.path.basename(work_dir)}_relax
#SBATCH -A gts-yke8
#SBATCH -N1 --gres=gpu:RTX_6000:1
#SBATCH --time=02:00:00
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=daniel.fu@emory.edu

cd $SLURM_SUBMIT_DIR
module load cuda/12.1.1 gcc/12.3.0

srun {OXDNA_BIN} input_relax
""")


def submit_to_pace(work_dir, design_name):
    """Upload to PACE and submit with dependency chain."""
    remote_dir = f'~/scratch/myoxDNAjobs/{design_name}'

    # rsync
    result = subprocess.run(
        ['rsync', '-av', work_dir + '/',
         f'dfu71@login-phoenix.pace.gatech.edu:{remote_dir}/'],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        print(f'  rsync ERROR: {result.stderr[-200:]}', flush=True)
        return None, None

    # Submit
    cmd = f"""cd {remote_dir} && \
CPU_ID=$(sbatch min.sh | awk '{{print $NF}}') && \
echo "MIN:$CPU_ID" && \
GPU_ID=$(sbatch --dependency=afterok:$CPU_ID relax.sh | awk '{{print $NF}}') && \
echo "RELAX:$GPU_ID"
"""
    result = subprocess.run(
        ['ssh', 'dfu71@login-phoenix.pace.gatech.edu', cmd],
        capture_output=True, text=True, timeout=30
    )
    print(f'  PACE: {result.stdout.strip()}', flush=True)
    if result.returncode != 0:
        print(f'  Submit ERROR: {result.stderr[-200:]}', flush=True)

    return result.stdout.strip()


# ── Main Pipeline ────────────────────────────────────────────────────────

def run_design(design: CavityDesign):
    """Run the full pipeline for one design."""
    print(f'\n{"="*60}', flush=True)
    print(f'DESIGN: {design.name}', flush=True)
    print(f'  Grid: 2×{design.n_cols}, Cavity: {design.n_cavity_cols} cols', flush=True)
    print(f'  Gap: {design.gap_bp}bp ({design.cavity_width_nm:.1f}nm)', flush=True)
    print(f'  Cavity: {design.cavity_width_nm:.1f}nm × {design.cavity_height_nm:.1f}nm', flush=True)
    print(f'  Helix length: {design.helix_len}bp', flush=True)
    print(f'{"="*60}', flush=True)

    work_dir = os.path.join(OUTPUT_BASE, design.name)
    os.makedirs(work_dir, exist_ok=True)

    # Step 1: Build design
    print('\n[1/4] Building design...', flush=True)
    json_path = build_wider_template(None, design)

    # Step 2: tacoxDNA
    print('\n[2/4] Converting to oxDNA...', flush=True)
    start_conf, topology = convert_to_oxdna(json_path, work_dir)
    if start_conf is None:
        print('  FAILED — skipping this design', flush=True)
        return None

    # Step 3: Write oxDNA inputs (early stopping: 500K steps)
    print('\n[3/4] Writing oxDNA inputs (early stop: 500K steps)...', flush=True)
    write_oxdna_inputs(work_dir, early_stop_steps=500000)

    # Step 4: Submit to PACE
    print('\n[4/4] Submitting to PACE...', flush=True)
    job_info = submit_to_pace(work_dir, design.name)

    return job_info


def main():
    os.makedirs(OUTPUT_BASE, exist_ok=True)

    # If called with a design index, run that single design
    if len(sys.argv) >= 2 and sys.argv[1].isdigit():
        idx = int(sys.argv[1])
        design = DESIGNS[idx]
        run_design(design)
        return

    # Otherwise, dispatch each design as a subprocess
    print('='*70, flush=True)
    print('INTEGRIN αvβ3 CAVITY PIPELINE', flush=True)
    print(f'Target cavity: ~15nm × 20nm', flush=True)
    print(f'3 candidate designs, early stopping (500K MD steps)', flush=True)
    print('='*70, flush=True)

    for i, design in enumerate(DESIGNS):
        print(f'\n=== Dispatching design {i}: {design.name} ===', flush=True)
        result = subprocess.run(
            [sys.executable, __file__, str(i)],
            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
            capture_output=True, text=True, timeout=300
        )
        print(result.stdout, flush=True)
        if result.returncode != 0:
            print(f'  STDERR (last 500): {result.stderr[-500:]}', flush=True)

    print('\n' + '='*70, flush=True)
    print('ALL DESIGNS DISPATCHED', flush=True)
    print('='*70, flush=True)


if __name__ == '__main__':
    main()
