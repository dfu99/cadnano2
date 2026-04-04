#!/usr/bin/env python
"""Build a single integrin cavity design. Called as subprocess."""
import os, sys, io, json, subprocess, shutil
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from math import ceil
import importlib, importlib.util, types

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_BASE = os.path.join(PROJECT_ROOT, 'results', 'integrin_cavity')
TACOX_SCRIPT = os.path.join(os.path.dirname(PROJECT_ROOT), 'tacoxDNA', 'src', 'cadnano_oxDNA.py')
OXDNA_BIN = '/storage/home/hcoda1/6/dfu71/scratch/oxDNA/build/bin/oxDNA'

NM_PER_BP = 0.34
STEP = 21
SCAFFOLD_TARGET = 8064

EMPTY = [-1, -1, -1, -1]
R12_OFFSETS = [4, 5, 15, 16]
R13_OFFSETS = [1, 2, 11, 12]


def snap(target, offsets, helix_len):
    best = None
    for k in range(helix_len // STEP + 1):
        for off in offsets:
            pos = k * STEP + off
            if 0 <= pos < helix_len:
                if best is None or abs(pos - target) < abs(best - target):
                    best = pos
    return best


def main():
    name = sys.argv[1]
    n_cols = int(sys.argv[2])
    n_cav_cols = int(sys.argv[3])
    gap_bp = int(sys.argv[4])

    n_helices = 2 * n_cols
    n_cavity = 2 * n_cav_cols
    target_L = (SCAFFOLD_TARGET / 0.95 + n_cavity * gap_bp) / n_helices
    helix_len = int(ceil(target_L / STEP)) * STEP
    helix_len = max(helix_len, gap_bp + 140)

    cav_w_nm = round(gap_bp * NM_PER_BP, 1)
    cav_h_nm = round(n_cav_cols * 2.6, 1)

    work_dir = os.path.join(OUTPUT_BASE, name)
    os.makedirs(work_dir, exist_ok=True)

    print(f'Design: {name}', flush=True)
    print(f'  Grid: 2x{n_cols}, Cavity: {n_cav_cols} cols, Gap: {gap_bp}bp', flush=True)
    print(f'  Cavity: {cav_w_nm}nm x {cav_h_nm}nm, Helix: {helix_len}bp', flush=True)

    # ── Build in cadnano ──
    print('[1/4] Building...', flush=True)
    sys.path.insert(0, PROJECT_ROOT)
    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()

    from cadnano2.model.parts.honeycombpart import Crossovers
    from cadnano2.model.parts.part import Part
    from cadnano2.model.io.encoder import encode

    dc = list(app.documentControllers)[0]
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    step = part.stepSize()
    if helix_len - 1 > part.maxBaseIdx():
        delta = int(ceil((helix_len - 1 - part.maxBaseIdx()) / step)) * step
        part.resizeVirtualHelices(0, delta, useUndoStack=True)

    start_col = max(4, 20 - n_cols + 1)
    ROW_A = [(12, c) for c in range(start_col + n_cols - 1, start_col - 1, -1)]
    ROW_B = [(13, c) for c in range(start_col, start_col + n_cols)]
    all_pos = ROW_A + ROW_B

    cav_col_start = start_col + (n_cols - n_cav_cols) // 2
    cav_col_end = cav_col_start + n_cav_cols
    CAVITY_COLS = set(range(cav_col_start, cav_col_end))

    for r, c in all_pos:
        part.createVirtualHelix(r, c, useUndoStack=True)

    vh_by_idx = {}
    for i, (r, c) in enumerate(all_pos):
        vh_by_idx[i] = part.virtualHelixAtCoord((r, c))

    print(f'  {len(vh_by_idx)} helices, cavity cols {cav_col_start}-{cav_col_end-1}', flush=True)

    gap_center = helix_len // 2
    r12_el = 5
    r12_er = snap(helix_len - 6, R12_OFFSETS, helix_len)
    r12_sl = snap(gap_center - 1, R12_OFFSETS, helix_len)
    r12_sr = snap(gap_center, R12_OFFSETS, helix_len)
    if r12_sr <= r12_sl: r12_sr = snap(r12_sl + 1, R12_OFFSETS, helix_len)
    r12_cl = snap(gap_center - gap_bp // 2, R12_OFFSETS, helix_len)
    r12_cr = snap(gap_center + gap_bp // 2, R12_OFFSETS, helix_len)
    if r12_cr <= r12_cl: r12_cr = snap(r12_cl + gap_bp, R12_OFFSETS, helix_len)

    r13_el = 2
    r13_er = snap(helix_len - 3, R13_OFFSETS, helix_len)
    r13_sl = snap(gap_center - 1, R13_OFFSETS, helix_len)
    r13_sr = snap(gap_center, R13_OFFSETS, helix_len)
    if r13_sr <= r13_sl: r13_sr = snap(r13_sl + 1, R13_OFFSETS, helix_len)
    r13_cl = snap(gap_center - gap_bp // 2, R13_OFFSETS, helix_len)
    r13_cr = snap(gap_center + gap_bp // 2, R13_OFFSETS, helix_len)
    if r13_cr <= r13_cl: r13_cr = snap(r13_cl + gap_bp, R13_OFFSETS, helix_len)

    # Create scaffold strands
    for i, (r, c) in enumerate(all_pos):
        vh = vh_by_idx[i]
        scaf_ss = vh.scaffoldStrandSet()
        is_cav = c in CAVITY_COLS
        if r == 12:
            lo, hi = r12_el, r12_er
            gl, gr = r12_cl + 1, r12_cr - 1
        else:
            lo, hi = r13_el, r13_er
            gl, gr = r13_cl + 1, r13_cr - 1
        if is_cav:
            scaf_ss.createStrand(lo, gl - 1, useUndoStack=True)
            scaf_ss.createStrand(gr + 1, hi, useUndoStack=True)
        else:
            scaf_ss.createStrand(lo, hi, useUndoStack=True)

    # Intra-pair crossovers
    n_pairs = n_cols
    xo = 0
    for pi in range(n_pairs):
        ha, hb = pi * 2, pi * 2 + 1
        va, vb = vh_by_idx[ha], vh_by_idx[hb]
        r, c = all_pos[ha]
        is_cav = c in CAVITY_COLS
        is_last = (pi == n_pairs - 1)
        if is_last:
            positions = [r13_el, r13_er]
        elif is_cav:
            positions = ([r12_el, r12_cl, r12_cr, r12_er] if r == 12
                        else [r13_el, r13_cl, r13_cr, r13_er])
        else:
            positions = ([r12_el, r12_sl, r12_sr, r12_er] if r == 12
                        else [r13_el, r13_sl, r13_sr, r13_er])
        for pos in positions:
            try:
                sa = va.scaffoldStrandSet().getStrand(pos)
                sb = vb.scaffoldStrandSet().getStrand(pos)
                if sa and sb:
                    part.createXover(sa, pos, sb, pos, useUndoStack=True)
                    xo += 1
            except: pass
    print(f'  Intra-pair xovers: {xo}', flush=True)

    # Inter-pair crossovers
    ixo = 0
    inter_pairs = [(2*i+1, 2*i+2) for i in range(n_cols - 1)]
    for ha, hb in inter_pairs:
        if ha >= n_helices or hb >= n_helices: continue
        va, vb = vh_by_idx[ha], vh_by_idx[hb]
        neighbors = part.getVirtualHelixNeighbors(va)
        if vb not in neighbors:
            neighbors = part.getVirtualHelixNeighbors(vb)
            if va not in neighbors: continue
            va, vb = vb, va
        di = neighbors.index(vb)
        lo_off = Crossovers.honeycombScafLow[di]
        hi_off = Crossovers.honeycombScafHigh[di]
        valid = sorted(set(list(lo_off) + list(hi_off)))
        for frac in [0.25, 0.75]:
            target = int(helix_len * frac)
            best = snap(target, valid, helix_len)
            if best is not None:
                try:
                    sa = va.scaffoldStrandSet().getStrand(best)
                    sb = vb.scaffoldStrandSet().getStrand(best)
                    if sa and sb:
                        part.createXover(sa, best, sb, best, useUndoStack=True)
                        ixo += 1
                except: pass
    print(f'  Inter-pair xovers: {ixo}', flush=True)

    # AutoStaple
    Part.autoStaple(part)

    # AutoBreak
    sg_path = os.path.join(PROJECT_ROOT, 'cadnano2', 'plugins', 'autobreak', 'staplegraph.py')
    sg_spec = importlib.util.spec_from_file_location('cadnano2.plugins.autobreak.staplegraph', sg_path, submodule_search_locations=[])
    sg = importlib.util.module_from_spec(sg_spec)
    sys.modules['cadnano2.plugins.autobreak.staplegraph'] = sg
    sg_spec.loader.exec_module(sg)
    pkg = types.ModuleType('cadnano2.plugins.autobreak')
    pkg.__path__ = [os.path.join(PROJECT_ROOT, 'cadnano2', 'plugins', 'autobreak')]
    pkg.staplegraph = sg
    sys.modules['cadnano2.plugins.autobreak'] = pkg
    if 'cadnano2.plugins.autobreak.autobreak' in sys.modules:
        del sys.modules['cadnano2.plugins.autobreak.autobreak']
    ab_path = os.path.join(PROJECT_ROOT, 'cadnano2', 'plugins', 'autobreak', 'autobreak.py')
    ab_spec = importlib.util.spec_from_file_location('cadnano2.plugins.autobreak.autobreak', ab_path, submodule_search_locations=[])
    ab = importlib.util.module_from_spec(ab_spec)
    sys.modules['cadnano2.plugins.autobreak.autobreak'] = ab
    ab_spec.loader.exec_module(ab)

    settings = {'minStapleLen': 18, 'maxStapleLen': 50, 'tgtStapleLen': 32, 'minStapleLegLen': 3}
    for oligo in list(part.oligos()):
        if oligo.isStaple() and oligo.length() > 50:
            try: ab.nxBreakStaple(oligo, settings)
            except: pass

    stap_c = sum(1 for o in part.oligos() if o.isStaple())
    scaf_c = sum(1 for o in part.oligos() if not o.isStaple())
    scaf_bp = sum(o.length() for o in part.oligos() if not o.isStaple())
    print(f'  Staples: {stap_c}, Scaffold: {scaf_bp}bp in {scaf_c} oligo(s)', flush=True)

    # Save
    json_path = os.path.join(work_dir, name + '.json')
    hol = dc.win.pathroot.getSelectedPartOrderedVHList()
    with open(json_path, 'w') as f:
        encode(doc, hol, f)
    print(f'  Saved: {json_path}', flush=True)

    # ── tacoxDNA ──
    print('[2/4] tacoxDNA...', flush=True)
    result = subprocess.run([sys.executable, TACOX_SCRIPT, json_path, 'he'],
                           capture_output=True, text=True, cwd=work_dir)
    base = os.path.basename(json_path)
    conf_src = os.path.join(work_dir, base + '.oxdna')
    top_src = os.path.join(work_dir, base + '.top')
    if os.path.exists(conf_src):
        shutil.move(conf_src, os.path.join(work_dir, 'start.conf'))
        shutil.move(top_src, os.path.join(work_dir, 'topology.top'))
        with open(os.path.join(work_dir, 'topology.top')) as f:
            h = f.readline().strip().split()
            print(f'  {h[0]} nucleotides, {h[1]} strands', flush=True)
    else:
        print(f'  tacoxDNA FAILED: {result.stderr[-200:]}', flush=True)
        return

    # ── oxDNA inputs (early stopping: 500K steps) ──
    print('[3/4] Writing oxDNA inputs (500K early stop)...', flush=True)
    with open(os.path.join(work_dir, 'input_min'), 'w') as f:
        f.write("backend = CPU\nsim_type = min\ninteraction_type = DNA2\n"
                "max_backbone_force = 5.\nmax_backbone_force_far = 10.\n"
                "steps = 10000\ndt = 0.005\nT = 300K\nverlet_skin = 0.15\n"
                "salt_concentration = 1.0\ntime_scale = linear\nrefresh_vel = 1\n"
                "topology = topology.top\nconf_file = start.conf\n"
                "lastconf_file = minimized.conf\ntrajectory_file = traj_min.dat\n"
                "energy_file = energy_min.dat\nprint_conf_interval = 10000\n"
                "print_energy_every = 20\nno_stdout_energy = false\nrestart_step_counter = 1\n")
    with open(os.path.join(work_dir, 'input_relax'), 'w') as f:
        f.write("backend = CUDA\nbackend_precision = mixed\nsim_type = MD\n"
                "interaction_type = DNA2\nmax_backbone_force = 5.\n"
                "max_backbone_force_far = 0.1\ndt = 0.003\nT = 300K\n"
                "thermostat = john\ndiff_coeff = 2.5\nnewtonian_steps = 103\n"
                "salt_concentration = 0.5\nmax_density_multiplier = 15\n"
                "steps = 500000\nverlet_skin = 0.5\n"
                "topology = topology.top\nconf_file = minimized.conf\n"
                "trajectory_file = trajectory.dat\nenergy_file = energy_relax.dat\n"
                "lastconf_file = relaxed.conf\nrefresh_vel = 1\n"
                "restart_step_counter = 1\ntime_scale = linear\n"
                "print_conf_interval = 100000\nprint_energy_every = 1000\n"
                "no_stdout_energy = false\n")
    with open(os.path.join(work_dir, 'min.sh'), 'w') as f:
        f.write(f"#!/bin/bash\n#SBATCH -J {name}_min\n#SBATCH -A gts-yke8\n"
                f"#SBATCH --time=01:00:00\n#SBATCH --mail-type=END,FAIL\n"
                f"#SBATCH --mail-user=daniel.fu@emory.edu\n\ncd $SLURM_SUBMIT_DIR\n"
                f"module load cuda/12.1.1 gcc/12.3.0\n\nsrun {OXDNA_BIN} input_min\n")
    with open(os.path.join(work_dir, 'relax.sh'), 'w') as f:
        f.write(f"#!/bin/bash\n#SBATCH -J {name}_relax\n#SBATCH -A gts-yke8\n"
                f"#SBATCH -N1 --gres=gpu:RTX_6000:1\n#SBATCH --time=02:00:00\n"
                f"#SBATCH --mail-type=END,FAIL\n#SBATCH --mail-user=daniel.fu@emory.edu\n\n"
                f"cd $SLURM_SUBMIT_DIR\nmodule load cuda/12.1.1 gcc/12.3.0\n\n"
                f"srun {OXDNA_BIN} input_relax\n")

    # ── Submit to PACE ──
    print('[4/4] Submitting to PACE...', flush=True)
    remote = f'~/scratch/myoxDNAjobs/{name}'
    r = subprocess.run(['rsync', '-av', work_dir + '/', f'dfu71@login-phoenix.pace.gatech.edu:{remote}/'],
                      capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        print(f'  rsync failed: {r.stderr[-200:]}', flush=True)
        return

    cmd = (f"cd {remote} && "
           f"CPU_ID=$(sbatch min.sh | awk '{{print $NF}}') && echo MIN:$CPU_ID && "
           f"GPU_ID=$(sbatch --dependency=afterok:$CPU_ID relax.sh | awk '{{print $NF}}') && echo RELAX:$GPU_ID")
    r = subprocess.run(['ssh', 'dfu71@login-phoenix.pace.gatech.edu', cmd],
                      capture_output=True, text=True, timeout=30)
    print(f'  PACE: {r.stdout.strip()}', flush=True)
    print('DONE', flush=True)


if __name__ == '__main__':
    main()
