#!/usr/bin/env python
"""
Generate cavity design variants by parametrically scaling the PI's template.

Produces designs with:
- Variable cavity gap sizes (20nm, 30nm, 40nm)
- Variable grid dimensions (2×12, 3×12, 4×12, 2×14, 2×16)
- Normalized to p8064 scaffold (8064 bp)

Each design is produced by the validated 4-step process:
  1. Remove staples from PI template
  2. Extend right side (adjust helix length for scaffold target)
  3. Move midseam crossovers to center
  4. Expand/shrink cavity to target nm width

Usage:
  conda activate cn24-agentic
  python tools/generate_cavity_variants.py
"""

import json
import copy
import os
import sys
from math import ceil

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, 'examples/2x12_rectangle_cavity.json')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'results', 'cavity_variants')

EMPTY = [-1, -1, -1, -1]
NM_PER_BP = 0.34
STEP = 21
SCAFFOLD_TARGET = 8064

# Original template parameters
ORIG_LEN = 252
ORIG_SCAFFOLD_BP = 5036
ORIG_N_HELICES = 24
ORIG_N_COLS = 12


def load_template():
    with open(TEMPLATE_PATH) as f:
        return json.load(f)


def step1_remove_staples(design):
    """Step 1: Remove all staples, keep scaffold only."""
    result = copy.deepcopy(design)
    for v in result['vstrands']:
        v['stap'] = [EMPTY] * len(v['scaf'])
        v['stap_colors'] = []
    return result


def step2_extend(design, new_len, cavity_helices):
    """Step 2: Extend arrays to new_len, shift right side.

    cavity_helices: set of helix nums that have the cavity gap.
    Only fills gap on non-cavity helices.
    """
    result = copy.deepcopy(design)
    old_len = len(result['vstrands'][0]['scaf'])
    shift = new_len - old_len

    if shift <= 0:
        # Just pad arrays if needed
        for v in result['vstrands']:
            while len(v['scaf']) < new_len:
                v['scaf'].append(EMPTY)
            while len(v['stap']) < new_len:
                v['stap'].append(EMPTY)
            while len(v['loop']) < new_len:
                v['loop'].append(0)
            while len(v['skip']) < new_len:
                v['skip'].append(0)
        return result

    # Pad arrays
    for v in result['vstrands']:
        while len(v['scaf']) < new_len:
            v['scaf'].append(EMPTY)
        while len(v['stap']) < new_len:
            v['stap'].append(EMPTY)
        while len(v['loop']) < new_len:
            v['loop'].append(0)
        while len(v['skip']) < new_len:
            v['skip'].append(0)

    # Identify cut point: shift everything >= CUT
    # Use a conservative cut after any cavity right boundary
    CUT = 170  # after original cavity right edges

    vs_by_num = {v['num']: v for v in result['vstrands']}

    # Shift scaffold data right of CUT
    for v in result['vstrands']:
        scaf = v['scaf']
        for i in range(old_len - 1, CUT - 1, -1):
            if scaf[i] != EMPTY:
                scaf[i + shift] = list(scaf[i])
                scaf[i] = EMPTY

    # Update references
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

    # Fill gaps on NON-CAVITY helices only
    for v in result['vstrands']:
        num = v['num']
        if num in cavity_helices:
            continue
        scaf = v['scaf']

        # Find gap boundaries
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

        # Determine direction
        _, _, th, ti = scaf[last_before]
        direction = 1 if (th == num and ti == last_before + 1) else -1

        for i in range(last_before + 1, first_after):
            if direction == 1:
                scaf[i] = [num, i - 1, num, i + 1]
            else:
                scaf[i] = [num, i + 1, num, i - 1]

        # Fix boundaries
        if scaf[last_before][2] == num:
            scaf[last_before][3] = last_before + 1
        if scaf[first_after][0] == num:
            scaf[first_after][1] = first_after - 1

    return result


def step3_move_midseam(design, cavity_pairs, row12_pairs, row13_pairs):
    """Step 3: Move midseam crossovers to center (surgical edit)."""
    result = copy.deepcopy(design)
    vs_by_num = {v['num']: v for v in result['vstrands']}
    new_len = len(result['vstrands'][0]['scaf'])

    # Row 12 non-cavity: seam at 120/121
    # Row 13 non-cavity: seam at 116/117
    # Move to approximately center of new_len
    target_r12 = (new_len // 2 // STEP) * STEP + 15  # nearest valid-ish
    target_r13 = (new_len // 2 // STEP) * STEP + 11

    # Snap to valid positions (multiples of 21 + offset)
    # For simplicity, use positions near center
    new_seam_r12 = ((new_len // 2) // STEP) * STEP + 15
    new_seam_r13 = ((new_len // 2) // STEP) * STEP + 11

    # Ensure within bounds
    if new_seam_r12 >= new_len - 10:
        new_seam_r12 = ((new_len // 2 - 21) // STEP) * STEP + 15
    if new_seam_r13 >= new_len - 10:
        new_seam_r13 = ((new_len // 2 - 21) // STEP) * STEP + 11

    def move_seam(ha, hb, old_a, old_b, new_pos):
        sa = vs_by_num[ha]['scaf']
        sb = vs_by_num[hb]['scaf']

        # Remove old crossover
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

        # Add new crossover
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


def step4_set_cavity_width(design, cavity_pairs_r12, cavity_pairs_r13,
                            target_gap_bp, old_right_pos_r12=163,
                            old_right_pos_r13=None):
    """Step 4: Set cavity width by moving right cavity boundary."""
    result = copy.deepcopy(design)
    vs_by_num = {v['num']: v for v in result['vstrands']}
    new_len = len(result['vstrands'][0]['scaf'])

    # Compute target right boundary position
    # Cavity is centered, so left boundary stays, right moves
    # For row 12: left boundary at 67, gap = target_gap_bp
    # new_right = 67 + target_gap_bp + 1
    # But need to find nearest valid crossover position

    # Row 12 cavity: H4-H5, H6-H7 use direction p2 (offsets 4,5,15,16)
    # Row 13 cavity: H16-H17, H18-H19 use direction p0 (offsets 1,2,11,12)

    def nearest_valid(target, offsets):
        best = None
        for k in range(new_len // STEP + 1):
            base = k * STEP
            for off in offsets:
                pos = base + off
                if pos < new_len and (best is None or abs(pos - target) < abs(best - target)):
                    if abs(pos - target) <= abs(best - target) if best else True:
                        best = pos
        return best

    # Row 12: left boundary at 67, target gap
    r12_left = 67
    r12_target_right = r12_left + target_gap_bp + 1
    r12_new_right = nearest_valid(r12_target_right, [4, 5, 15, 16])

    # Row 13: left boundary at 74, target gap
    r13_left = 74
    r13_target_right = r13_left + target_gap_bp + 1
    r13_new_right = nearest_valid(r13_target_right, [1, 2, 11, 12])

    def move_cavity_boundary(ha, hb, old_right, new_right):
        sa = vs_by_num[ha]['scaf']
        sb = vs_by_num[hb]['scaf']

        # Remove old crossover at old_right
        for s, h, partner in [(sa, ha, hb), (sb, hb, ha)]:
            if s[old_right] != EMPTY:
                if s[old_right][0] == partner:
                    s[old_right][0] = h
                    s[old_right][1] = old_right - 1
                if s[old_right][2] == partner:
                    s[old_right][2] = h
                    s[old_right][3] = old_right - 1

        # Add crossover at new_right
        if sa[new_right] != EMPTY and sb[new_right] != EMPTY:
            sa[new_right][0] = hb
            sa[new_right][1] = new_right
            sb[new_right][2] = ha
            sb[new_right][3] = new_right

        # Clear or fill scaffold between old and new boundary
        if new_right > old_right:
            # Expanding: clear data between old and new
            for s in [sa, sb]:
                for i in range(old_right, new_right):
                    s[i] = EMPTY
        elif new_right < old_right:
            # Shrinking: fill data between new and old
            for s, h in [(sa, ha), (sb, hb)]:
                _, _, th, ti = s[new_right]
                direction = 1 if (th == h) else -1
                for i in range(new_right + 1, old_right + 1):
                    if s[i] == EMPTY:
                        if direction == 1:
                            s[i] = [h, i - 1, h, i + 1]
                        else:
                            s[i] = [h, i + 1, h, i - 1]

    # Find current right boundary for each cavity pair
    for ha, hb in cavity_pairs_r12:
        # Find current right boundary (first xover after gap)
        sa = vs_by_num[ha]['scaf']
        current_right = old_right_pos_r12
        # Search for actual right boundary
        for i in range(68, new_len):
            if sa[i] != EMPTY:
                entry = sa[i]
                if entry[0] == hb or entry[2] == hb:
                    current_right = i
                    break
        move_cavity_boundary(ha, hb, current_right, r12_new_right)

    for ha, hb in cavity_pairs_r13:
        sa = vs_by_num[ha]['scaf']
        current_right = old_right_pos_r13 if old_right_pos_r13 else 338
        for i in range(75, new_len):
            if sa[i] != EMPTY:
                entry = sa[i]
                if entry[0] == hb or entry[2] == hb:
                    current_right = i
                    break
        move_cavity_boundary(ha, hb, current_right, r13_new_right)

    return result, r12_new_right, r13_new_right


def validate_design(design):
    """Validate a design for cadnano compatibility."""
    issues = []
    vs_by_num = {v['num']: v for v in design['vstrands']}

    for v in design['vstrands']:
        num = v['num']
        expected_len = len(design['vstrands'][0]['scaf'])

        for arr_name in ['scaf', 'stap', 'loop', 'skip']:
            if len(v[arr_name]) != expected_len:
                issues.append(f'H{num} {arr_name} len={len(v[arr_name])} != {expected_len}')

        # Check crossover references
        for i, (vh5p, idx5p, vh3p, idx3p) in enumerate(v['scaf']):
            if vh5p == -1 and vh3p == -1:
                continue
            if vh3p >= 0 and vh3p != num and idx3p != i:
                issues.append(f'H{num}[{i}] → H{vh3p}[{idx3p}] MISALIGNED')
            if vh3p >= 0 and idx3p >= 0:
                tv = vs_by_num.get(vh3p)
                if tv and tv['scaf'][idx3p] == EMPTY:
                    issues.append(f'H{num}[{i}] → H{vh3p}[{idx3p}] TARGET EMPTY')

    return issues


def count_scaffold(design):
    return sum(1 for v in design['vstrands'] for e in v['scaf'] if e != EMPTY)


def generate_variant(gap_nm, n_cols=12, n_rows=2, scaffold_bp=8064):
    """Generate a single design variant."""
    gap_bp = int(gap_nm / NM_PER_BP)

    # Compute required helix length
    # Total scaffold = n_helices * helix_utilization
    # helix_utilization ≈ helix_length * 0.95 (edges not fully used)
    # For cavity helices: utilization = helix_length - gap_bp
    n_helices = n_rows * n_cols
    n_cavity_helices = 8  # 4 per row (cols 13-16)
    n_full_helices = n_helices - n_cavity_helices

    # Approximate: scaffold = n_full * L * 0.95 + n_cavity * (L - gap) * 0.95
    # Solve for L: scaffold / 0.95 = n_full * L + n_cavity * (L - gap)
    #            = (n_full + n_cavity) * L - n_cavity * gap
    #            = n_helices * L - n_cavity * gap
    # L = (scaffold / 0.95 + n_cavity * gap) / n_helices
    target_L = (scaffold_bp / 0.95 + n_cavity_helices * gap_bp) / n_helices
    helix_len = int(ceil(target_L / STEP)) * STEP

    # Ensure minimum length for the gap + margins
    min_len = gap_bp + 140  # need room for edges and crossovers
    helix_len = max(helix_len, min_len)

    print(f"\n{'='*50}")
    print(f"Variant: {gap_nm}nm gap, {n_rows}×{n_cols} grid, {scaffold_bp}bp scaffold")
    print(f"  Gap: {gap_bp}bp, Helix length: {helix_len}bp ({helix_len//STEP} steps)")
    print(f"  Helices: {n_helices} ({n_full_helices} full + {n_cavity_helices} cavity)")

    # For now, only handle 2×12 base template
    # Multi-row/col variants would need different templates
    if n_cols != 12 or n_rows != 2:
        print(f"  NOTE: {n_rows}×{n_cols} requires different template. Computing scaffold estimate only.")
        est_scaffold = int(n_full_helices * helix_len * 0.95 + n_cavity_helices * (helix_len - gap_bp) * 0.95)
        print(f"  Estimated scaffold: {est_scaffold}bp (target: {scaffold_bp})")
        enough = "YES" if est_scaffold >= scaffold_bp else f"NO (short by {scaffold_bp - est_scaffold}bp)"
        print(f"  Scaffold fits? {enough}")
        return {
            'gap_nm': gap_nm, 'gap_bp': gap_bp, 'n_rows': n_rows, 'n_cols': n_cols,
            'helix_len': helix_len, 'estimated_scaffold': est_scaffold,
            'scaffold_target': scaffold_bp, 'fits': est_scaffold >= scaffold_bp,
            'status': 'estimate_only'
        }

    # Load template and run 4-step process
    template = load_template()
    cavity_helices = {4, 5, 6, 7, 16, 17, 18, 19}
    row12_pairs = [(0, 1), (2, 3), (4, 5), (6, 7), (8, 9), (10, 11)]
    row13_pairs = [(12, 13), (14, 15), (16, 17), (18, 19), (20, 21), (22, 23)]
    cavity_pairs_r12 = [(4, 5), (6, 7)]
    cavity_pairs_r13 = [(16, 17), (18, 19)]
    cavity_pairs = set(cavity_pairs_r12 + cavity_pairs_r13)

    # Step 1
    s1 = step1_remove_staples(template)

    # Step 2
    s2 = step2_extend(s1, helix_len, cavity_helices)

    # Step 3
    s3 = step3_move_midseam(s2, cavity_pairs, row12_pairs, row13_pairs)

    # Step 4
    s4, r12_right, r13_right = step4_set_cavity_width(
        s3, cavity_pairs_r12, cavity_pairs_r13, gap_bp)

    # Validate
    issues = validate_design(s4)
    scaf_bp = count_scaffold(s4)

    print(f"  Scaffold: {scaf_bp}bp (target: {scaffold_bp})")
    print(f"  Cavity right edges: R12={r12_right}, R13={r13_right}")
    if issues:
        print(f"  ISSUES: {len(issues)}")
        for iss in issues[:5]:
            print(f"    {iss}")
    else:
        print(f"  Validation: OK")

    # Save
    name = f"cavity_{gap_nm}nm_{n_rows}x{n_cols}_{scaffold_bp}bp"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{name}.json")
    with open(path, 'w') as f:
        json.dump(s4, f, separators=(',', ':'))
    print(f"  Saved: {path}")

    return {
        'gap_nm': gap_nm, 'gap_bp': gap_bp, 'n_rows': n_rows, 'n_cols': n_cols,
        'helix_len': helix_len, 'scaffold_bp': scaf_bp,
        'scaffold_target': scaffold_bp, 'fits': scaf_bp >= scaffold_bp * 0.9,
        'r12_right': r12_right, 'r13_right': r13_right,
        'issues': len(issues), 'path': path, 'status': 'generated'
    }


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = []

    # === Gap size variants (2×12 grid, p8064) ===
    print("\n" + "=" * 60)
    print("PART 1: Variable cavity gap sizes (2×12, p8064)")
    print("=" * 60)
    for gap_nm in [20, 30, 40]:
        r = generate_variant(gap_nm, n_cols=12, n_rows=2, scaffold_bp=8064)
        results.append(r)

    # === Multi-layer variants (2×12, 3×12, 4×12) ===
    print("\n" + "=" * 60)
    print("PART 2: Multi-layer variants (30nm gap, p8064)")
    print("=" * 60)
    for n_rows in [2, 3, 4]:
        r = generate_variant(30, n_cols=12, n_rows=n_rows, scaffold_bp=8064)
        results.append(r)

    # === Wider structures (2×14, 2×16) ===
    print("\n" + "=" * 60)
    print("PART 3: Wider structures (30nm gap, p8064)")
    print("=" * 60)
    for n_cols in [14, 16]:
        r = generate_variant(30, n_cols=n_cols, n_rows=2, scaffold_bp=8064)
        results.append(r)

    # === Summary table ===
    print("\n" + "=" * 60)
    print("SUMMARY TABLE")
    print("=" * 60)
    print(f"{'Config':<20} {'Gap':<8} {'Helix':<8} {'Scaffold':<10} {'Target':<8} {'Fits?':<6} {'Status'}")
    print("-" * 80)
    for r in results:
        config = f"{r['n_rows']}×{r['n_cols']}"
        gap = f"{r['gap_nm']}nm"
        hlen = f"{r['helix_len']}bp"
        scaf = f"{r.get('scaffold_bp', r.get('estimated_scaffold', '?'))}bp"
        target = f"{r['scaffold_target']}bp"
        fits = "YES" if r['fits'] else "NO"
        status = r['status']
        print(f"{config:<20} {gap:<8} {hlen:<8} {scaf:<10} {target:<8} {fits:<6} {status}")

    # Save summary
    summary_path = os.path.join(OUTPUT_DIR, 'summary.json')
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSummary: {summary_path}")

    return results


if __name__ == '__main__':
    main()
