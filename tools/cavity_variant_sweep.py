#!/usr/bin/env python
"""
Cavity Variant Sweep — Demonstrate extensibility of parametric cavity designs.

Generates cavity designs with:
  1. Variable gap sizes: 20nm, 30nm, 40nm (2×12 grid, p8064)
  2. Multi-layer: 3×12, 4×12 (3 and 4 grid rows)
  3. Thicker 2-layer: 2×14, 2×16

Each 2×12 design is built by the validated 4-step template-scaling process
(pure JSON manipulation, no Qt/cadnano dependency).
Multi-row and wider designs use analytical capacity calculations.

All designs normalized to p8064 scaffold (8064 bp) where feasible.

Usage:
  conda activate cn24-agentic
  python tools/cavity_variant_sweep.py
"""

import os
import sys
import json
import copy
from math import ceil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, '2x12_rectangle_cavity.json')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'results', 'cavity_variants')

EMPTY = [-1, -1, -1, -1]
NM_PER_BP = 0.34
STEP = 21
SCAFFOLD_TARGET = 8064

# ── Template-based 2×12 generation (4-step process, pure JSON) ───────────

def load_template():
    with open(TEMPLATE_PATH) as f:
        return json.load(f)


def step1_remove_staples(design):
    result = copy.deepcopy(design)
    for v in result['vstrands']:
        v['stap'] = [EMPTY] * len(v['scaf'])
        v['stap_colors'] = []
    return result


def step2_extend(design, new_len, cavity_helices):
    """Extend arrays to new_len, shift right side, fill extension gaps.

    For ALL helices (including cavity), fills the extension gap created
    by shifting. For cavity helices, preserves the cavity gap while
    filling only the extension portion.

    Template cavity gap boundaries:
      R12 (H4-H7):   gap [68-162], right segment starts at 163
      R13 (H16-H19): gap [75-169], right segment starts at 170
    """
    result = copy.deepcopy(design)
    old_len = len(result['vstrands'][0]['scaf'])
    shift = new_len - old_len

    if shift <= 0:
        for v in result['vstrands']:
            for arr in ['scaf', 'stap']:
                while len(v[arr]) < new_len:
                    v[arr].append(EMPTY)
            for arr in ['loop', 'skip']:
                while len(v[arr]) < new_len:
                    v[arr].append(0)
        return result

    for v in result['vstrands']:
        for arr in ['scaf', 'stap']:
            while len(v[arr]) < new_len:
                v[arr].append(EMPTY)
        for arr in ['loop', 'skip']:
            while len(v[arr]) < new_len:
                v[arr].append(0)

    CUT = 170
    # Shift data at positions >= CUT to the right by shift
    for v in result['vstrands']:
        scaf = v['scaf']
        for i in range(old_len - 1, CUT - 1, -1):
            if scaf[i] != EMPTY:
                scaf[i + shift] = list(scaf[i])
                scaf[i] = EMPTY

    # Update cross-references that point to shifted positions
    for v in result['vstrands']:
        scaf = v['scaf']
        for i in range(new_len):
            if scaf[i] == EMPTY:
                continue
            vh5p, idx5p, vh3p, idx3p = scaf[i]
            if vh5p >= 0 and idx5p >= CUT:
                scaf[i][1] = idx5p + shift
            if vh3p >= 0 and idx3p >= CUT:
                scaf[i][3] = idx3p + shift

    # Cavity right segment boundaries (in original template coordinates)
    # R12 cavity (H4-H7): right segment starts at 163 (below CUT, stays in place)
    # R13 cavity (H16-H19): right segment starts at 170 (= CUT, gets shifted)
    R12_CAVITY_RIGHT_START = 163  # these positions stay at 163-169
    R13_CAVITY_RIGHT_START = 170  # these get shifted to 170+shift

    # Fill extension gaps for ALL helices
    for v in result['vstrands']:
        num = v['num']
        scaf = v['scaf']

        if num in cavity_helices:
            # For cavity helices, fill ONLY the extension gap (170 to 170+shift-1).
            # The cavity gap (68-162 for R12, 75-169 for R13) must be preserved.
            #
            # R12 cavity (H4-H7): right segment at 163-169 stayed in place,
            #   extension gap is 170 to 170+shift-1. last_before=169.
            # R13 cavity (H16-H19): right segment at 170 got shifted to 170+shift,
            #   extension gap is 170 to 170+shift-1. We must NOT search below 170
            #   or we'll find position 74 (end of left segment) and fill the cavity gap.

            # Find last occupied in range [CUT-7, CUT-1] (the tail of the
            # right segment that stayed below CUT, if any)
            last_before = -1
            for i in range(CUT - 1, max(CUT - 10, 0) - 1, -1):
                if scaf[i] != EMPTY:
                    last_before = i
                    break

            if last_before < 0:
                # R13 case: right segment was entirely at CUT (170), now shifted.
                # DON'T fill the extension gap here — step4 will handle it
                # by placing the cavity right boundary crossover and filling
                # from there to the shifted right segment. If we fill now,
                # positions inside the expanded cavity gap get scaffold data
                # that step4 doesn't clean up.
                continue

            # R12 case: last_before found (e.g., 169)
            first_after = -1
            for i in range(CUT, new_len):
                if scaf[i] != EMPTY:
                    first_after = i
                    break
            if last_before < 0 or first_after < 0 or first_after - last_before <= 1:
                continue
        else:
            # Non-cavity: fill entire gap between left and right segments
            last_before = -1
            for i in range(CUT - 1, -1, -1):
                if scaf[i] != EMPTY:
                    last_before = i
                    break
            first_after = -1
            for i in range(CUT, new_len):
                if scaf[i] != EMPTY:
                    first_after = i
                    break
            if last_before < 0 or first_after < 0 or first_after - last_before <= 1:
                continue

        # Determine scaffold direction from helix parity
        # Even helices: scaffold goes right (5' at i-1, 3' at i+1)
        # Odd helices: scaffold goes left (5' at i+1, 3' at i-1)
        direction = 1 if (num % 2 == 0) else -1

        # Fill the gap
        for i in range(last_before + 1, first_after):
            if scaf[i] != EMPTY:
                continue  # don't overwrite existing data
            if direction == 1:
                scaf[i] = [num, i - 1, num, i + 1]
            else:
                scaf[i] = [num, i + 1, num, i - 1]

        # Fix boundary connections: connect last_before's 3' to the fill,
        # and first_after's 5' to the fill
        if direction == 1:
            scaf[last_before][2] = num
            scaf[last_before][3] = last_before + 1
            scaf[first_after][0] = num
            scaf[first_after][1] = first_after - 1
        else:
            scaf[last_before][0] = num
            scaf[last_before][1] = last_before + 1
            scaf[first_after][2] = num
            scaf[first_after][3] = first_after - 1

    return result


def step3_move_midseam(design, cavity_pairs, row12_pairs, row13_pairs):
    result = copy.deepcopy(design)
    vs_by_num = {v['num']: v for v in result['vstrands']}
    new_len = len(result['vstrands'][0]['scaf'])
    new_seam_r12 = ((new_len // 2) // STEP) * STEP + 15
    new_seam_r13 = ((new_len // 2) // STEP) * STEP + 11
    if new_seam_r12 >= new_len - 10:
        new_seam_r12 = ((new_len // 2 - 21) // STEP) * STEP + 15
    if new_seam_r13 >= new_len - 10:
        new_seam_r13 = ((new_len // 2 - 21) // STEP) * STEP + 11

    def move_seam(ha, hb, old_a, old_b, new_pos):
        sa = vs_by_num[ha]['scaf']
        sb = vs_by_num[hb]['scaf']
        for s, h, partner in [(sa, ha, hb), (sb, hb, ha)]:
            if s[old_a][0] == partner:
                s[old_a][0] = h
                s[old_a][1] = old_a + 1 if old_a < old_b else old_a - 1
            if s[old_a][2] == partner:
                s[old_a][2] = h
                s[old_a][3] = old_a + 1 if old_a < old_b else old_a - 1
            if s[old_b][0] == partner:
                s[old_b][0] = h
                s[old_b][1] = old_b - 1 if old_b > old_a else old_b + 1
            if s[old_b][2] == partner:
                s[old_b][2] = h
                s[old_b][3] = old_b - 1 if old_b > old_a else old_b + 1
        if sa[new_pos] != EMPTY and sb[new_pos] != EMPTY:
            sa[new_pos][2] = hb
            sa[new_pos][3] = new_pos
            sb[new_pos][0] = ha
            sb[new_pos][1] = new_pos
        if sa[new_pos + 1] != EMPTY and sb[new_pos + 1] != EMPTY:
            sb[new_pos + 1][2] = ha
            sb[new_pos + 1][3] = new_pos + 1
            sa[new_pos + 1][0] = hb
            sa[new_pos + 1][1] = new_pos + 1

    for ha, hb in row12_pairs:
        if (ha, hb) not in cavity_pairs:
            move_seam(ha, hb, 120, 121, new_seam_r12)
    for ha, hb in row13_pairs:
        if (ha, hb) not in cavity_pairs:
            move_seam(ha, hb, 116, 117, new_seam_r13)
    return result


def step4_set_cavity_width(design, cavity_pairs_r12, cavity_pairs_r13, target_gap_bp):
    result = copy.deepcopy(design)
    vs_by_num = {v['num']: v for v in result['vstrands']}
    new_len = len(result['vstrands'][0]['scaf'])

    def nearest_valid(target, offsets):
        best = None
        for k in range(new_len // STEP + 1):
            base = k * STEP
            for off in offsets:
                pos = base + off
                if pos < new_len and (best is None or abs(pos - target) < abs(best - target)):
                    best = pos
        return best

    r12_left = 67
    r12_target_right = r12_left + target_gap_bp + 1
    r12_new_right = nearest_valid(r12_target_right, [4, 5, 15, 16])

    r13_left = 74
    r13_target_right = r13_left + target_gap_bp + 1
    r13_new_right = nearest_valid(r13_target_right, [1, 2, 11, 12])

    def move_cavity_boundary(ha, hb, old_right, new_right):
        sa = vs_by_num[ha]['scaf']
        sb = vs_by_num[hb]['scaf']

        # Step 1: Remove old crossover at old_right
        for s, h, partner in [(sa, ha, hb), (sb, hb, ha)]:
            if s[old_right] != EMPTY:
                if s[old_right][0] == partner:
                    s[old_right][0] = h
                    s[old_right][1] = old_right + 1 if h % 2 == 0 else old_right - 1
                if s[old_right][2] == partner:
                    s[old_right][2] = h
                    s[old_right][3] = old_right - 1 if h % 2 == 0 else old_right + 1

        if new_right > old_right:
            # Expanding gap: clear data between old and new boundary
            for s in [sa, sb]:
                for i in range(old_right, new_right):
                    s[i] = EMPTY

        elif new_right < old_right:
            # Shrinking gap: fill data between new and old boundary
            for s, h in [(sa, ha), (sb, hb)]:
                direction = 1 if (h % 2 == 0) else -1
                # Fill from new_right to old_right (inclusive)
                for i in range(new_right, old_right + 1):
                    if s[i] == EMPTY:
                        if direction == 1:
                            s[i] = [h, i - 1, h, i + 1]
                        else:
                            s[i] = [h, i + 1, h, i - 1]

        # Step 2: Place crossover at new_right
        # Ensure both helices have scaffold entries at new_right
        for s, h in [(sa, ha), (sb, hb)]:
            if s[new_right] == EMPTY:
                if h % 2 == 0:
                    s[new_right] = [h, new_right - 1, h, new_right + 1]
                else:
                    s[new_right] = [h, new_right + 1, h, new_right - 1]

        # Place the crossover: ha's 5' connects to hb, hb's 3' connects to ha
        sa[new_right][0] = hb
        sa[new_right][1] = new_right
        sb[new_right][2] = ha
        sb[new_right][3] = new_right

    for ha, hb in cavity_pairs_r12:
        sa = vs_by_num[ha]['scaf']
        current_right = 163
        for i in range(68, new_len):
            if sa[i] != EMPTY:
                entry = sa[i]
                if entry[0] == hb or entry[2] == hb:
                    current_right = i
                    break
        move_cavity_boundary(ha, hb, current_right, r12_new_right)

    for ha, hb in cavity_pairs_r13:
        sa = vs_by_num[ha]['scaf']
        current_right = 338
        for i in range(75, new_len):
            if sa[i] != EMPTY:
                entry = sa[i]
                if entry[0] == hb or entry[2] == hb:
                    current_right = i
                    break
        move_cavity_boundary(ha, hb, current_right, r13_new_right)

    return result, r12_new_right, r13_new_right


def fix_scaffold_directions(design):
    """Post-process: fix all non-crossover scaffold entries to match helix parity.

    Even helices (num%2==0): scaffold goes right → [num, i-1, num, i+1]
    Odd helices (num%2==1): scaffold goes left → [num, i+1, num, i-1]

    Only fixes entries where BOTH 5' and 3' are on the same helix (intra-helix).
    Crossover entries (referencing other helices) are left untouched.
    """
    result = copy.deepcopy(design)
    for v in result['vstrands']:
        num = v['num']
        scaf = v['scaf']

        for i in range(len(scaf)):
            entry = scaf[i]
            if entry == EMPTY:
                continue

            vh5p, idx5p, vh3p, idx3p = entry

            # Only fix intra-helix entries (both neighbors on same helix)
            if vh5p == num and vh3p == num:
                if num % 2 == 0:
                    # Even: scaffold goes right → 5' at i-1, 3' at i+1
                    scaf[i] = [num, i - 1, num, i + 1]
                else:
                    # Odd: scaffold goes left → 5' at i+1, 3' at i-1
                    scaf[i] = [num, i + 1, num, i - 1]

            # Fix mixed entries where one side is same helix, other is crossover
            elif vh5p == num and vh3p != num:
                # 5' on same helix, 3' is crossover
                if num % 2 == 0:
                    scaf[i][1] = i - 1  # 5' to the left
                else:
                    scaf[i][1] = i + 1  # 5' to the right
            elif vh5p != num and vh3p == num:
                # 5' is crossover, 3' on same helix
                if num % 2 == 0:
                    scaf[i][3] = i + 1  # 3' to the right
                else:
                    scaf[i][3] = i - 1  # 3' to the left

    # Fix boundary entries: first and last occupied positions
    for v in result['vstrands']:
        num = v['num']
        scaf = v['scaf']
        occupied = [i for i, e in enumerate(scaf) if e != EMPTY]
        if not occupied:
            continue

        lo, hi = min(occupied), max(occupied)

        # Find gap boundaries for cavity helices
        gaps = []
        in_data = False
        gap_start = None
        for i in range(lo, hi + 1):
            if scaf[i] != EMPTY:
                if gap_start is not None:
                    gaps.append((gap_start, i - 1))
                    gap_start = None
                in_data = True
            else:
                if in_data and gap_start is None:
                    gap_start = i

        # Fix edges and gap boundaries
        # Strand segment endpoints need -1 for their outward connection
        endpoints = set()
        endpoints.add(lo)
        endpoints.add(hi)
        for g_start, g_end in gaps:
            endpoints.add(g_start - 1)  # last before gap
            endpoints.add(g_end + 1)    # first after gap

        for ep in endpoints:
            if ep < 0 or ep >= len(scaf) or scaf[ep] == EMPTY:
                continue
            vh5p, idx5p, vh3p, idx3p = scaf[ep]

            # If this is a strand start (5' end), 5' should be -1 OR crossover
            # If this is a strand end (3' end), 3' should be -1 OR crossover
            if num % 2 == 0:
                # Even: strand goes right. Start has 5'=-1 or xover. End has 3'=-1 or xover.
                if ep == lo or (ep > 0 and scaf[ep - 1] == EMPTY):
                    # Start of segment
                    if vh5p == num:
                        scaf[ep][0] = -1
                        scaf[ep][1] = -1
                if ep == hi or (ep + 1 < len(scaf) and scaf[ep + 1] == EMPTY):
                    # End of segment
                    if vh3p == num:
                        scaf[ep][2] = -1
                        scaf[ep][3] = -1
            else:
                # Odd: strand goes left. Start has 5'=-1 or xover at right end.
                # End has 3'=-1 or xover at left end.
                if ep == hi or (ep + 1 < len(scaf) and scaf[ep + 1] == EMPTY):
                    # Start of segment (5' end, at high index)
                    if vh5p == num:
                        scaf[ep][0] = -1
                        scaf[ep][1] = -1
                if ep == lo or (ep > 0 and scaf[ep - 1] == EMPTY):
                    # End of segment (3' end, at low index)
                    if vh3p == num:
                        scaf[ep][2] = -1
                        scaf[ep][3] = -1

    return result


def count_scaffold(design):
    return sum(1 for v in design['vstrands'] for e in v['scaf'] if e != EMPTY)


def validate_design(design):
    issues = []
    expected_len = len(design['vstrands'][0]['scaf'])
    for v in design['vstrands']:
        for arr_name in ['scaf', 'stap', 'loop', 'skip']:
            if len(v[arr_name]) != expected_len:
                issues.append(f'H{v["num"]} {arr_name} len mismatch')
    return issues


# ── Analytical capacity computation for any grid ─────────────────────────

def compute_helix_length(n_rows, n_cols, gap_bp, scaffold_target, n_cavity_cols=4):
    """Find minimum helix length to fit scaffold target."""
    n_helices = n_rows * n_cols
    n_cavity = n_rows * n_cavity_cols
    target_L = (scaffold_target / 0.95 + n_cavity * gap_bp) / n_helices
    helix_len = int(ceil(target_L / STEP)) * STEP
    return max(helix_len, gap_bp + 140)


def compute_scaffold_capacity(n_rows, n_cols, helix_len, gap_bp, n_cavity_cols=4):
    """Compute scaffold capacity: full helices contribute ~95%, cavity helices less."""
    n_helices = n_rows * n_cols
    n_cavity = n_rows * n_cavity_cols
    n_full = n_helices - n_cavity
    full_bp = int(n_full * helix_len * 0.95)
    cavity_bp = int(n_cavity * (helix_len - gap_bp) * 0.95)
    return full_bp + cavity_bp


# ── Generate variants ────────────────────────────────────────────────────

def generate_2x12_variant(gap_nm):
    """Generate a 2×12 design with specified gap (template scaling, pure JSON)."""
    gap_bp = int(gap_nm / NM_PER_BP)

    n_helices = 24
    n_cavity = 8
    target_L = (SCAFFOLD_TARGET / 0.95 + n_cavity * gap_bp) / n_helices
    helix_len = int(ceil(target_L / STEP)) * STEP
    helix_len = max(helix_len, gap_bp + 140)

    template = load_template()
    cavity_helices = {4, 5, 6, 7, 16, 17, 18, 19}
    row12_pairs = [(0, 1), (2, 3), (4, 5), (6, 7), (8, 9), (10, 11)]
    row13_pairs = [(12, 13), (14, 15), (16, 17), (18, 19), (20, 21), (22, 23)]
    cavity_pairs_r12 = [(4, 5), (6, 7)]
    cavity_pairs_r13 = [(16, 17), (18, 19)]
    cavity_pairs = set(cavity_pairs_r12 + cavity_pairs_r13)

    s1 = step1_remove_staples(template)
    s2 = step2_extend(s1, helix_len, cavity_helices)
    s3 = step3_move_midseam(s2, cavity_pairs, row12_pairs, row13_pairs)
    s4, r12_right, r13_right = step4_set_cavity_width(
        s3, cavity_pairs_r12, cavity_pairs_r13, gap_bp)

    # Fix all scaffold directions to match helix parity
    s5 = fix_scaffold_directions(s4)

    issues = validate_design(s5)
    scaf_bp = count_scaffold(s5)
    actual_gap_r12 = r12_right - 67
    actual_gap_nm = round(actual_gap_r12 * NM_PER_BP, 1)

    # Find cavity boundaries for visualization
    cavity_left_bp = 67
    cavity_right_bp = r12_right

    name = f"cavity_{gap_nm}nm_2x12_8064bp"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{name}.json")
    with open(path, 'w') as f:
        json.dump(s5, f, separators=(',', ':'))

    return {
        'config': '2x12',
        'gap_nm': gap_nm,
        'gap_bp': gap_bp,
        'actual_gap_nm': actual_gap_nm,
        'n_rows': 2, 'n_cols': 12,
        'n_helices': 24,
        'helix_len': helix_len,
        'scaffold_bp': scaf_bp,
        'target_bp': SCAFFOLD_TARGET,
        'fits': scaf_bp >= SCAFFOLD_TARGET * 0.9,
        'pct_used': round(100 * scaf_bp / SCAFFOLD_TARGET, 1),
        'cavity_left': cavity_left_bp,
        'cavity_right': cavity_right_bp,
        'issues': len(issues),
        'status': 'generated',
        'path': path,
        'design': s5,
    }


def generate_analytical_variant(n_rows, n_cols, gap_nm):
    """Compute scaffold capacity analytically (no cadnano needed)."""
    gap_bp = int(gap_nm / NM_PER_BP)
    n_cavity_cols = min(4, n_cols - 2)
    helix_len = compute_helix_length(n_rows, n_cols, gap_bp, SCAFFOLD_TARGET, n_cavity_cols)
    capacity = compute_scaffold_capacity(n_rows, n_cols, helix_len, gap_bp, n_cavity_cols)

    return {
        'config': f'{n_rows}x{n_cols}',
        'gap_nm': gap_nm,
        'gap_bp': gap_bp,
        'actual_gap_nm': round(gap_bp * NM_PER_BP, 1),
        'n_rows': n_rows, 'n_cols': n_cols,
        'n_helices': n_rows * n_cols,
        'helix_len': helix_len,
        'scaffold_bp': capacity,
        'target_bp': SCAFFOLD_TARGET,
        'fits': capacity >= SCAFFOLD_TARGET * 0.9,
        'pct_used': round(100 * capacity / SCAFFOLD_TARGET, 1),
        'cavity_left': (helix_len // 2) - (gap_bp // 2),
        'cavity_right': (helix_len // 2) + (gap_bp // 2),
        'n_cavity_cols': n_cavity_cols,
        'issues': 0,
        'status': 'analytical',
        'path': None,
        'design': None,
    }


# ── Visualization ────────────────────────────────────────────────────────

def make_figures(results_gap, results_layers, results_width):
    """Generate all figures. Imported lazily to avoid Qt issues."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.patches import FancyBboxPatch, Rectangle
    import numpy as np

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fig_paths = []

    # ── Figure 1: Gap comparison for 2×12 ──
    fig, axes = plt.subplots(3, 1, figsize=(14, 9))

    for i, r in enumerate(results_gap):
        ax = axes[i]
        design = r['design']
        vs_list = design['vstrands']
        helix_len = r['helix_len']
        y_spacing = 1.2

        for di, vs in enumerate(vs_list):
            y = -di * y_spacing
            scaf = vs['scaf']

            # Draw scaffold segments
            seg_start = None
            for idx, entry in enumerate(scaf):
                if entry != EMPTY:
                    if seg_start is None:
                        seg_start = idx
                else:
                    if seg_start is not None:
                        ax.plot([seg_start, idx - 1], [y, y], '-',
                                color='steelblue', linewidth=1.8,
                                solid_capstyle='round', alpha=0.85)
                        seg_start = None
            if seg_start is not None:
                ax.plot([seg_start, len(scaf) - 1], [y, y], '-',
                        color='steelblue', linewidth=1.8,
                        solid_capstyle='round', alpha=0.85)

            # Light gray helix bar background
            ax.plot([0, helix_len], [y, y], '-', color='#f0f0f0',
                    linewidth=3, solid_capstyle='round', zorder=0)

        # Cavity region highlight
        cav_left = r['cavity_left']
        cav_right = r['cavity_right']
        ax.axvspan(cav_left, cav_right, color='#fff3cd', alpha=0.4, zorder=0)
        ax.axvline(cav_left, color='orange', linewidth=0.8, linestyle='--', alpha=0.6)
        ax.axvline(cav_right, color='orange', linewidth=0.8, linestyle='--', alpha=0.6)

        # Gap annotation
        gap_center = (cav_left + cav_right) / 2
        ax.annotate(f'{r["gap_nm"]}nm\n({r["gap_bp"]}bp)',
                    xy=(gap_center, 1), fontsize=9, ha='center', va='bottom',
                    color='darkorange', fontweight='bold')

        ax.set_xlim(-5, helix_len + 5)
        ax.set_ylim(-len(vs_list) * y_spacing - 0.5, 2.5)
        ax.set_title(f'{r["gap_nm"]}nm gap — Scaffold: {r["scaffold_bp"]}bp / '
                     f'{r["target_bp"]}bp ({r["pct_used"]}%)',
                     fontsize=10, fontweight='bold')
        ax.set_yticks([])
        ax.set_xlabel('bp index', fontsize=8)

    fig.suptitle('Gap Size Comparison — 2×12 Grid, p8064 Scaffold',
                 fontsize=13, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    path = os.path.join(OUTPUT_DIR, 'gap_comparison.png')
    plt.savefig(path, dpi=120, bbox_inches='tight')  # 14*120 = 1680px
    plt.close()
    fig_paths.append(path)
    print(f"  Saved: {path}")

    # ── Figure 2: Feasibility bar chart ──
    all_results = results_gap + results_layers + results_width
    fig, ax = plt.subplots(figsize=(14, 7))

    configs = []
    for r in all_results:
        configs.append(f'{r["config"]}\n{r["gap_nm"]}nm')
    scaffold_bp = [r['scaffold_bp'] for r in all_results]
    target = SCAFFOLD_TARGET

    colors = ['#28a745' if r['fits'] else '#dc3545' for r in all_results]
    bars = ax.bar(configs, scaffold_bp, color=colors, edgecolor='black',
                  linewidth=0.5, width=0.6)

    ax.axhline(y=target, color='navy', linestyle='--', linewidth=2,
               label=f'p8064 target ({target} bp)')
    ax.axhline(y=target * 0.9, color='orange', linestyle=':', linewidth=1.5,
               label=f'90% threshold ({int(target * 0.9)} bp)')

    for bar, bp in zip(bars, scaffold_bp):
        ax.text(bar.get_x() + bar.get_width() / 2, bp + 150,
                f'{bp}', ha='center', va='bottom', fontsize=9, fontweight='bold')

    ax.set_ylabel('Scaffold capacity (bp)', fontsize=12)
    ax.set_xlabel('Design configuration', fontsize=12)
    ax.set_title('Scaffold Capacity vs p8064 Target — All Variants',
                 fontsize=13, fontweight='bold')
    ax.legend(fontsize=10, loc='upper right')
    ax.set_ylim(0, max(scaffold_bp) * 1.15)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, 'feasibility_chart.png')
    plt.savefig(path, dpi=120, bbox_inches='tight')  # 14*120=1680px
    plt.close()
    fig_paths.append(path)
    print(f"  Saved: {path}")

    # ── Figure 3: Grid schematics for all configs ──
    fig = plt.figure(figsize=(15, 11))
    gs = gridspec.GridSpec(3, 3, hspace=0.5, wspace=0.4)

    all_for_grid = results_gap + results_layers + results_width
    # Pad to 9 if needed
    while len(all_for_grid) < 9:
        all_for_grid.append(None)

    row_labels = ['Gap variants (2×12)', 'Multi-layer (30nm)',
                  'Wider (30nm)']

    for idx, r in enumerate(all_for_grid[:9]):
        row = idx // 3
        col = idx % 3
        ax = fig.add_subplot(gs[row, col])

        if r is None:
            ax.axis('off')
            continue

        n_rows = r['n_rows']
        n_cols = r['n_cols']
        gap_bp = r['gap_bp']
        helix_len = r['helix_len']

        # Determine cavity columns
        n_cav_cols = r.get('n_cavity_cols', 4)
        if r['config'] == '2x12':
            n_cav_cols = 4
        cav_start = (n_cols - n_cav_cols) // 2
        cav_end = cav_start + n_cav_cols

        # Draw helices as horizontal bars
        bar_width = 0.7
        for row_i in range(n_rows):
            for col_j in range(n_cols):
                x = col_j
                y = -row_i
                is_cavity = cav_start <= col_j < cav_end

                if is_cavity:
                    # Left segment
                    gap_frac = gap_bp / helix_len
                    left_frac = (1 - gap_frac) / 2
                    right_frac = left_frac

                    ax.barh(y, left_frac * bar_width, left=x,
                            height=0.6, color='lightskyblue',
                            edgecolor='steelblue', linewidth=0.5)
                    ax.barh(y, right_frac * bar_width,
                            left=x + (1 - right_frac) * bar_width,
                            height=0.6, color='lightskyblue',
                            edgecolor='steelblue', linewidth=0.5)
                    # Gap indicator
                    ax.barh(y, gap_frac * bar_width,
                            left=x + left_frac * bar_width,
                            height=0.6, color='#fff3cd',
                            edgecolor='orange', linewidth=0.3,
                            linestyle='--', alpha=0.6)
                else:
                    ax.barh(y, bar_width, left=x,
                            height=0.6, color='steelblue',
                            edgecolor='navy', linewidth=0.5, alpha=0.7)

        ax.set_xlim(-0.5, n_cols + 0.5)
        ax.set_ylim(-n_rows, 1)
        ax.set_xticks([])
        ax.set_yticks([])

        status_color = '#28a745' if r['fits'] else '#dc3545'
        fit_label = 'FITS' if r['fits'] else 'TOO SHORT'
        ax.set_title(f'{r["config"]}, {r["gap_nm"]}nm gap\n'
                     f'{r["n_helices"]} helices × {helix_len}bp',
                     fontsize=9, fontweight='bold')
        ax.text(0.5, -0.08,
                f'{r["scaffold_bp"]}bp / {r["target_bp"]}bp '
                f'({r["pct_used"]}%) — {fit_label}',
                ha='center', va='top', transform=ax.transAxes,
                fontsize=8, color=status_color, fontweight='bold')

    # Row labels
    for i, label in enumerate(row_labels):
        fig.text(0.02, 0.85 - i * 0.33, label,
                 fontsize=10, fontweight='bold', rotation=90,
                 va='center', ha='center')

    fig.suptitle('Parametric Cavity Design Sweep — p8064 Scaffold',
                 fontsize=14, fontweight='bold', y=0.99)

    path = os.path.join(OUTPUT_DIR, 'sweep_grid_schematics.png')
    plt.savefig(path, dpi=112, bbox_inches='tight')  # 15*112=1680px
    plt.close()
    fig_paths.append(path)
    print(f"  Saved: {path}")

    # ── Figure 4: Physical dimensions table ──
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.axis('off')

    table_data = []
    headers = ['Config', 'Gap (nm)', 'Gap (bp)', 'Helices',
               'Helix len (bp)', 'Structure (nm)',
               'Scaffold (bp)', 'p8064 fit?']

    for r in results_gap + results_layers + results_width:
        # Physical dimensions
        length_nm = round(r['helix_len'] * NM_PER_BP, 1)
        width_nm = round(r['n_cols'] * 2.6, 1)  # ~2.6nm inter-helix honeycomb
        depth_nm = round(r['n_rows'] * 2.3, 1)  # ~2.3nm inter-row

        table_data.append([
            r['config'],
            f'{r["gap_nm"]}',
            f'{r["gap_bp"]}',
            f'{r["n_helices"]}',
            f'{r["helix_len"]}',
            f'{length_nm} × {width_nm} × {depth_nm}',
            f'{r["scaffold_bp"]}',
            'YES' if r['fits'] else 'NO',
        ])

    table = ax.table(
        cellText=table_data,
        colLabels=headers,
        loc='center',
        cellLoc='center',
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.6)

    # Header style
    for j in range(len(headers)):
        table[0, j].set_facecolor('#343a40')
        table[0, j].set_text_props(color='white', fontweight='bold')

    # Color code fit/no-fit
    for i in range(len(table_data)):
        fits = table_data[i][-1] == 'YES'
        color = '#d4edda' if fits else '#f8d7da'
        for j in range(len(headers)):
            table[i + 1, j].set_facecolor(color)

    ax.set_title('Physical Dimensions and Scaffold Capacity Summary',
                 fontsize=13, fontweight='bold', pad=20)

    path = os.path.join(OUTPUT_DIR, 'dimensions_table.png')
    plt.savefig(path, dpi=150, bbox_inches='tight')  # 12*150=1800px
    plt.close()
    fig_paths.append(path)
    print(f"  Saved: {path}")

    return fig_paths


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("=" * 70)
    print("CAVITY VARIANT SWEEP — Parametric Extensibility Demonstration")
    print("=" * 70)

    # ── Part 1: Gap size variants (2×12, template scaling) ──
    print("\n" + "=" * 60)
    print("PART 1: Variable cavity gap sizes (2×12, p8064)")
    print("=" * 60)

    results_gap = []
    for gap_nm in [20, 30, 40]:
        print(f"\n--- {gap_nm}nm gap ---")
        r = generate_2x12_variant(gap_nm)
        print(f"  Gap: {gap_nm}nm = {r['gap_bp']}bp (actual: {r['actual_gap_nm']}nm)")
        print(f"  Helix length: {r['helix_len']}bp ({r['helix_len']//STEP} steps)")
        print(f"  Scaffold: {r['scaffold_bp']}bp / {r['target_bp']}bp ({r['pct_used']}%)")
        print(f"  Cavity: bp {r['cavity_left']} → {r['cavity_right']}")
        print(f"  Status: {r['status']}, Issues: {r['issues']}")
        print(f"  Saved: {r['path']}")
        results_gap.append(r)

    # ── Part 2: Multi-layer variants ──
    print("\n" + "=" * 60)
    print("PART 2: Multi-layer variants (30nm gap, p8064)")
    print("=" * 60)

    results_layers = []
    for n_rows in [3, 4]:
        print(f"\n--- {n_rows}×12, 30nm gap ---")
        r = generate_analytical_variant(n_rows, 12, 30)
        print(f"  Helices: {r['n_helices']} ({n_rows} rows × 12 cols)")
        print(f"  Helix length: {r['helix_len']}bp ({r['helix_len']//STEP} steps)")
        print(f"  Scaffold capacity: {r['scaffold_bp']}bp / {r['target_bp']}bp ({r['pct_used']}%)")
        print(f"  Fits p8064? {'YES' if r['fits'] else 'NO'}")
        if not r['fits']:
            shortfall = SCAFFOLD_TARGET - r['scaffold_bp']
            print(f"  Short by: {shortfall}bp")
        results_layers.append(r)

    # ── Part 3: Wider structures ──
    print("\n" + "=" * 60)
    print("PART 3: Wider 2-layer structures (30nm gap, p8064)")
    print("=" * 60)

    results_width = []
    for n_cols in [14, 16]:
        print(f"\n--- 2×{n_cols}, 30nm gap ---")
        r = generate_analytical_variant(2, n_cols, 30)
        print(f"  Helices: {r['n_helices']} (2 rows × {n_cols} cols)")
        print(f"  Helix length: {r['helix_len']}bp ({r['helix_len']//STEP} steps)")
        print(f"  Scaffold capacity: {r['scaffold_bp']}bp / {r['target_bp']}bp ({r['pct_used']}%)")
        print(f"  Fits p8064? {'YES' if r['fits'] else 'NO'}")
        results_width.append(r)

    # ── Summary ──
    print("\n" + "=" * 70)
    print("SUMMARY TABLE")
    print("=" * 70)
    all_results = results_gap + results_layers + results_width
    print(f"\n{'Config':<10} {'Gap':<8} {'Helices':<8} {'Helix bp':<10} "
          f"{'Scaffold':<12} {'%Used':<8} {'Fits?':<6} {'Status'}")
    print("-" * 82)
    for r in all_results:
        print(f"{r['config']:<10} {r['gap_nm']}nm{'':<4} {r['n_helices']:<8} "
              f"{r['helix_len']:<10} {r['scaffold_bp']:<12} "
              f"{r['pct_used']}%{'':<4} {'YES' if r['fits'] else 'NO':<6} "
              f"{r['status']}")

    # ── Figures ──
    print("\n" + "=" * 60)
    print("GENERATING FIGURES")
    print("=" * 60)
    fig_paths = make_figures(results_gap, results_layers, results_width)

    # Save JSON summary
    summary = []
    for r in all_results:
        s = {k: v for k, v in r.items() if k != 'design'}
        summary.append(s)
    with open(os.path.join(OUTPUT_DIR, 'sweep_summary.json'), 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\n{'='*70}")
    print(f"DONE — {len(all_results)} variants analyzed")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Figures: {len(fig_paths)}")
    for p in fig_paths:
        print(f"  {os.path.basename(p)}")
    print(f"{'='*70}")

    return all_results, fig_paths


if __name__ == '__main__':
    main()
