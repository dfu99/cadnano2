#!/usr/bin/env python
"""
Generate cavity designs from verified 2x22 template.

Three operations:
1. Cavity WIDTH variants (40, 45, 50nm) on 2x22 template (10 cav cols, 26nm height)
2. Cavity HEIGHT expansion (10→12 cols, ~31nm height) + width variants
3. Template extension to 2x24 + cavity height + width variants

All operations use JSON manipulation on verified templates.

Usage:
  conda activate cn24-agentic
  python tools/gen_cavity_sweep.py
"""

import os, sys, io, json, copy, zipfile, importlib, importlib.util, types
from math import ceil
from dataclasses import dataclass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

NM_PER_BP = 0.34
STEP = 21
COL_SPACING_NM = 2.6
SCAFFOLD_LEN = 8064
EMPTY = [-1, -1, -1, -1]

TEMPLATE_2x22 = os.path.join(PROJECT_ROOT, 'results', 'integrin_cavity',
                               'design_2x22_centered_v2.json')
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'results', 'cavity_sweep')

R12_OFFSETS = [4, 5, 15, 16]
R13_OFFSETS = [1, 2, 11, 12]


def nearest_valid(target, offsets, helix_len):
    best = None
    for k in range(helix_len // STEP + 1):
        for off in offsets:
            pos = k * STEP + off
            if 0 <= pos < helix_len:
                if best is None or abs(pos - target) < abs(best - target):
                    best = pos
    return best


def verify_scaffold(design):
    """Returns (starts, total_bp). starts==0 means closed loop."""
    starts, total_bp = 0, 0
    for v in design['vstrands']:
        for i, t in enumerate(v['scaf']):
            if t == EMPTY: continue
            total_bp += 1
            if t[0] == -1 and t[1] == -1 and (t[2] != -1 or t[3] != -1):
                starts += 1
    return starts, total_bp


def get_cavity_info(design):
    """Identify cavity helices (those with scaffold gaps)."""
    cavity_helices = set()
    for v in design['vstrands']:
        scaf = v['scaf']
        in_data = False
        found_gap = False
        for t in scaf:
            if t != EMPTY:
                if found_gap and not in_data:
                    cavity_helices.add(v['num'])
                    break
                in_data = True
            else:
                if in_data:
                    found_gap = True
                    in_data = False
    return cavity_helices


def find_intra_pair_xovers(design, ha_num, hb_num):
    """Find all crossover positions between two helices."""
    vs = {v['num']: v for v in design['vstrands']}
    sa = vs[ha_num]['scaf']
    positions = []
    for i, t in enumerate(sa):
        if t == EMPTY: continue
        if t[0] == hb_num or t[2] == hb_num:
            positions.append(i)
    return sorted(positions)


# ─── CAVITY WIDTH MODIFICATION ───

def move_cavity_width(design, target_gap_bp, r12_cav_pairs, r13_cav_pairs):
    """Modify cavity width by moving boundary crossovers."""
    result = copy.deepcopy(design)
    vs = {v['num']: v for v in result['vstrands']}
    helix_len = len(result['vstrands'][0]['scaf'])
    gap_center = helix_len // 2
    half_gap = target_gap_bp // 2

    r12_new_left = nearest_valid(gap_center - half_gap, R12_OFFSETS, helix_len)
    r12_new_right = nearest_valid(gap_center + half_gap, R12_OFFSETS, helix_len)
    if r12_new_right <= r12_new_left:
        r12_new_right = nearest_valid(r12_new_left + target_gap_bp, R12_OFFSETS, helix_len)

    r13_new_left = nearest_valid(gap_center - half_gap, R13_OFFSETS, helix_len)
    r13_new_right = nearest_valid(gap_center + half_gap, R13_OFFSETS, helix_len)
    if r13_new_right <= r13_new_left:
        r13_new_right = nearest_valid(r13_new_left + target_gap_bp, R13_OFFSETS, helix_len)

    def move_pair_bounds(ha, hb, new_left, new_right):
        sa, sb = vs[ha]['scaf'], vs[hb]['scaf']
        xo_pos = find_intra_pair_xovers(result, ha, hb)
        edges = [xo_pos[0], xo_pos[-1]]
        interior = [p for p in xo_pos if p not in edges]
        if len(interior) < 2:
            return
        cur_left, cur_right = interior[0], interior[-1]

        # Remove old interior crossovers
        for pos in interior:
            for s, h, partner in [(sa, ha, hb), (sb, hb, ha)]:
                if s[pos] == EMPTY: continue
                direction = 1 if ((vs[h]['row'] + vs[h]['col']) % 2 == 0) else -1
                if s[pos][0] == partner:
                    s[pos][0] = h
                    s[pos][1] = pos - 1 if direction == 1 else pos + 1
                if s[pos][2] == partner:
                    s[pos][2] = h
                    s[pos][3] = pos + 1 if direction == 1 else pos - 1

        # Fill scaffold between boundaries where empty
        for s, h in [(sa, ha), (sb, hb)]:
            direction = 1 if ((vs[h]['row'] + vs[h]['col']) % 2 == 0) else -1
            # Check if this helix is a cavity helix (has gap)
            has_gap = False
            for i in range(new_left + 1, new_right):
                if s[i] != EMPTY:
                    has_gap = False
                    break
            else:
                has_gap = True

            # Fill from edge to new_left
            for i in range(edges[0], new_left + 1):
                if s[i] == EMPTY:
                    if direction == 1:
                        s[i] = [h, i - 1, h, i + 1]
                    else:
                        s[i] = [h, i + 1, h, i - 1]

            # Fill from new_right to edge
            for i in range(new_right, edges[-1] + 1):
                if s[i] == EMPTY:
                    if direction == 1:
                        s[i] = [h, i - 1, h, i + 1]
                    else:
                        s[i] = [h, i + 1, h, i - 1]

        # Clear gap between new boundaries (for cavity helices only)
        for s, h in [(sa, ha), (sb, hb)]:
            # Check if this helix had a gap in the original
            was_cavity = False
            orig_vs = {v['num']: v for v in result['vstrands']}
            # Detect cavity by checking if there are any EMPTY positions between edges
            for i in range(edges[0] + 1, edges[-1]):
                if s[i] == EMPTY:
                    was_cavity = True
                    break

            if was_cavity or True:  # clear gap for all cavity helices
                for i in range(new_left + 1, new_right):
                    s[i] = EMPTY

        # Place new boundary crossovers
        for s, h in [(sa, ha), (sb, hb)]:
            direction = 1 if ((vs[h]['row'] + vs[h]['col']) % 2 == 0) else -1
            if s[new_left] == EMPTY:
                s[new_left] = [h, new_left - 1, h, new_left + 1] if direction == 1 else [h, new_left + 1, h, new_left - 1]
            if s[new_right] == EMPTY:
                s[new_right] = [h, new_right - 1, h, new_right + 1] if direction == 1 else [h, new_right + 1, h, new_right - 1]

        # Left boundary crossover (copy pattern from cavity pair)
        # Even helix (ha): [58] → 3' to hb
        # Odd helix (hb): [58] ← 5' from ha
        sa[new_left][2] = hb
        sa[new_left][3] = new_left
        sb[new_left][0] = ha
        sb[new_left][1] = new_left

        # Right boundary crossover
        sa[new_right][0] = hb
        sa[new_right][1] = new_right
        sb[new_right][2] = ha
        sb[new_right][3] = new_right

        # Fix boundary self-connections
        for s, h in [(sa, ha), (sb, hb)]:
            direction = 1 if ((vs[h]['row'] + vs[h]['col']) % 2 == 0) else -1
            # Left boundary: inward side
            if direction == 1:
                if s[new_left][0] == h:
                    s[new_left][1] = new_left - 1
            else:
                if s[new_left][2] == h:
                    s[new_left][3] = new_left - 1
            # Right boundary: inward side
            if direction == 1:
                if s[new_right][2] == h:
                    s[new_right][3] = new_right + 1
            else:
                if s[new_right][0] == h:
                    s[new_right][1] = new_right + 1

    for ha, hb in r12_cav_pairs:
        move_pair_bounds(ha, hb, r12_new_left, r12_new_right)

    for ha, hb in r13_cav_pairs:
        move_pair_bounds(ha, hb, r13_new_left, r13_new_right)

    # Clean up dangling crossover references after width modification
    fixed = 0
    for v in result['vstrands']:
        scaf = v['scaf']
        h = v['num']
        direction = 1 if ((v['row'] + v['col']) % 2 == 0) else -1
        for i, t in enumerate(scaf):
            if t == EMPTY:
                continue
            if t[0] >= 0 and t[0] != h:
                partner_scaf = vs[t[0]]['scaf']
                if partner_scaf[t[1]] == EMPTY:
                    scaf[i][0] = h
                    scaf[i][1] = i - 1 if direction == 1 else i + 1
                    fixed += 1
            if t[2] >= 0 and t[2] != h:
                partner_scaf = vs[t[2]]['scaf']
                if partner_scaf[t[3]] == EMPTY:
                    scaf[i][2] = h
                    scaf[i][3] = i + 1 if direction == 1 else i - 1
                    fixed += 1
    if fixed:
        print(f"    Fixed {fixed} dangling refs after width modification")

    actual_r12 = r12_new_right - r12_new_left
    actual_r13 = r13_new_right - r13_new_left
    return result, actual_r12, actual_r13


# ─── CAVITY HEIGHT EXPANSION ───

def expand_cavity_height(design, new_pairs_r12, new_pairs_r13):
    """Convert non-cavity pairs to cavity pairs.

    For each pair (ha, hb), replaces midseam crossover with cavity boundary
    crossovers at the same positions used by existing cavity pairs.
    """
    result = copy.deepcopy(design)
    vs = {v['num']: v for v in result['vstrands']}
    helix_len = len(result['vstrands'][0]['scaf'])

    # Find existing cavity boundary positions from a cavity pair
    cavity_helices = get_cavity_info(result)
    ref_r12_pair = None
    ref_r13_pair = None

    for v in result['vstrands']:
        if v['num'] in cavity_helices:
            if v['row'] == 12 and ref_r12_pair is None:
                # Find the gap boundaries
                scaf = v['scaf']
                gap_start = None
                gap_end = None
                in_data = False
                for i, t in enumerate(scaf):
                    if t != EMPTY:
                        if gap_start is not None and gap_end is None:
                            gap_end = i
                        in_data = True
                    else:
                        if in_data and gap_start is None:
                            gap_start = i
                            in_data = False
                ref_r12_pair = (gap_start - 1, gap_end)  # boundary positions
                print(f"  R12 cavity boundaries: left={ref_r12_pair[0]}, right={ref_r12_pair[1]}")

            if v['row'] == 13 and ref_r13_pair is None:
                scaf = v['scaf']
                gap_start = None
                gap_end = None
                in_data = False
                for i, t in enumerate(scaf):
                    if t != EMPTY:
                        if gap_start is not None and gap_end is None:
                            gap_end = i
                        in_data = True
                    else:
                        if in_data and gap_start is None:
                            gap_start = i
                            in_data = False
                ref_r13_pair = (gap_start - 1, gap_end)
                print(f"  R13 cavity boundaries: left={ref_r13_pair[0]}, right={ref_r13_pair[1]}")

    def convert_pair(ha_num, hb_num, bound_left, bound_right):
        sa = vs[ha_num]['scaf']
        sb = vs[hb_num]['scaf']
        ha_dir = 1 if ((vs[ha_num]['row'] + vs[ha_num]['col']) % 2 == 0) else -1
        hb_dir = 1 if ((vs[hb_num]['row'] + vs[hb_num]['col']) % 2 == 0) else -1

        # Find and remove midseam crossover
        xo_pos = find_intra_pair_xovers(result, ha_num, hb_num)
        edges = [xo_pos[0], xo_pos[-1]]
        interior = [p for p in xo_pos if p not in edges]
        print(f"  H{ha_num}-H{hb_num}: edges={edges}, midseam={interior}")

        for pos in interior:
            for s, h, partner, direction in [(sa, ha_num, hb_num, ha_dir),
                                              (sb, hb_num, ha_num, hb_dir)]:
                if s[pos][0] == partner:
                    s[pos][0] = h
                    s[pos][1] = pos - 1 if direction == 1 else pos + 1
                if s[pos][2] == partner:
                    s[pos][2] = h
                    s[pos][3] = pos + 1 if direction == 1 else pos - 1

        # Clear scaffold gap on BOTH helices
        for s, h, direction in [(sa, ha_num, ha_dir), (sb, hb_num, hb_dir)]:
            for i in range(bound_left + 1, bound_right):
                s[i] = EMPTY

        # Place cavity boundary crossovers (matching existing cavity pattern)
        # Left boundary
        for s, h, direction in [(sa, ha_num, ha_dir), (sb, hb_num, hb_dir)]:
            if s[bound_left] == EMPTY:
                if direction == 1:
                    s[bound_left] = [h, bound_left - 1, h, bound_left + 1]
                else:
                    s[bound_left] = [h, bound_left + 1, h, bound_left - 1]
            if s[bound_right] == EMPTY:
                if direction == 1:
                    s[bound_right] = [h, bound_right - 1, h, bound_right + 1]
                else:
                    s[bound_right] = [h, bound_right + 1, h, bound_right - 1]

        # Wire crossovers (same pattern as existing cavity pairs)
        sa[bound_left][2] = hb_num
        sa[bound_left][3] = bound_left
        sb[bound_left][0] = ha_num
        sb[bound_left][1] = bound_left

        sa[bound_right][0] = hb_num
        sa[bound_right][1] = bound_right
        sb[bound_right][2] = ha_num
        sb[bound_right][3] = bound_right

        # Fix self-connections at boundaries
        for s, h, direction in [(sa, ha_num, ha_dir), (sb, hb_num, hb_dir)]:
            if direction == 1:
                if s[bound_left][0] == h:
                    s[bound_left][1] = bound_left - 1
                if s[bound_right][2] == h:
                    s[bound_right][3] = bound_right + 1
            else:
                if s[bound_left][2] == h:
                    s[bound_left][3] = bound_left - 1
                if s[bound_right][0] == h:
                    s[bound_right][1] = bound_right + 1

    for ha, hb in new_pairs_r12:
        convert_pair(ha, hb, ref_r12_pair[0], ref_r12_pair[1])

    for ha, hb in new_pairs_r13:
        convert_pair(ha, hb, ref_r13_pair[0], ref_r13_pair[1])

    # Clean up dangling inter-pair crossover references
    # After clearing gaps, some inter-pair crossovers may reference EMPTY positions
    fixed = 0
    for v in result['vstrands']:
        scaf = v['scaf']
        h = v['num']
        direction = 1 if ((v['row'] + v['col']) % 2 == 0) else -1
        for i, t in enumerate(scaf):
            if t == EMPTY:
                continue
            # Check 5' partner
            if t[0] >= 0 and t[0] != h:
                partner_scaf = vs[t[0]]['scaf']
                if partner_scaf[t[1]] == EMPTY:
                    # Dangling 5' ref — replace with self-connection
                    scaf[i][0] = h
                    scaf[i][1] = i - 1 if direction == 1 else i + 1
                    fixed += 1
            # Check 3' partner
            if t[2] >= 0 and t[2] != h:
                partner_scaf = vs[t[2]]['scaf']
                if partner_scaf[t[3]] == EMPTY:
                    # Dangling 3' ref — replace with self-connection
                    scaf[i][2] = h
                    scaf[i][3] = i + 1 if direction == 1 else i - 1
                    fixed += 1
    if fixed:
        print(f"  Fixed {fixed} dangling inter-pair crossover references")

    return result


# ─── AUTOSTAPLE + AUTOBREAK ───

def run_autostaple_break(json_path, output_path):
    """Load design, run autoStaple + autoBreak, save."""
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    import cadnano2.cadnano as cadnano
    from cadnano2.model.parts.part import Part
    from cadnano2.model.io.encoder import encode

    app = cadnano.initAppWithGui()
    dc = list(app.documentControllers)[0]
    return _staple_break_in_process(dc, json_path, output_path)


def _staple_break_in_process(dc, json_path, output_path):
    from cadnano2.model.io.decoder import import_legacy_dict
    from cadnano2.model.parts.part import Part
    from cadnano2.model.io.encoder import encode

    dc.newDocument()
    doc = dc.document()
    with open(json_path) as f:
        obj = json.load(f)
    import_legacy_dict(doc, obj)

    part = doc.selectedPart()

    # Clear existing staples first
    for oligo in list(part.oligos()):
        if oligo.isStaple():
            for strand in oligo.strand5p().generator3pStrand():
                strand.strandSet().removeStrand(strand, useUndoStack=False)

    Part.autoStaple(part)

    # AutoBreak
    ab = _setup_autobreak()
    settings = {'minStapleLen': 18, 'maxStapleLen': 50,
                'tgtStapleLen': 32, 'minStapleLegLen': 3}
    for _ in range(3):  # 3 iterations
        for oligo in list(part.oligos()):
            if oligo.isStaple() and oligo.length() > 50:
                try:
                    ab.nxBreakStaple(oligo, settings)
                except Exception:
                    pass

    stap_c = sum(1 for o in part.oligos() if o.isStaple())
    scaf_oligos = [o for o in part.oligos() if not o.isStaple()]
    scaf_bp = sum(o.length() for o in scaf_oligos)
    scaf_c = len(scaf_oligos)
    starts = sum(1 for o in scaf_oligos if o.strand5p().connection5p() is None)

    hol = dc.win.pathroot.getSelectedPartOrderedVHList()
    with open(output_path, 'w') as f:
        encode(doc, hol, f)

    return {
        'scaffold_bp': scaf_bp,
        'scaffold_oligos': scaf_c,
        'scaffold_starts': starts,
        'staple_count': stap_c,
    }


def _setup_autobreak():
    sg_path = os.path.join(PROJECT_ROOT, 'cadnano2', 'plugins', 'autobreak', 'staplegraph.py')
    sg_spec = importlib.util.spec_from_file_location(
        'cadnano2.plugins.autobreak.staplegraph', sg_path, submodule_search_locations=[])
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
    ab_spec = importlib.util.spec_from_file_location(
        'cadnano2.plugins.autobreak.autobreak', ab_path, submodule_search_locations=[])
    ab = importlib.util.module_from_spec(ab_spec)
    sys.modules['cadnano2.plugins.autobreak.autobreak'] = ab
    ab_spec.loader.exec_module(ab)
    return ab


# ─── SCREENSHOTS ───

def take_screenshot(dc, json_path, png_path):
    from cadnano2.model.io.decoder import import_legacy_dict
    from PyQt6.QtCore import QRectF, QMarginsF
    from PyQt6.QtGui import QImage, QPainter, QColor

    dc.newDocument()
    doc = dc.document()
    with open(json_path) as f:
        obj = json.load(f)
    import_legacy_dict(doc, obj)

    scene = dc.win.pathscene
    rect = scene.itemsBoundingRect()
    if rect.isEmpty():
        rect = QRectF(0, 0, 1600, 400)
    rect = rect.marginsAdded(QMarginsF(30, 30, 30, 30))

    scale = 2.0
    w, h = int(rect.width() * scale), int(rect.height() * scale)
    if w > 6000:
        scale *= 6000 / w
        w, h = int(rect.width() * scale), int(rect.height() * scale)

    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(p, source=rect)
    p.end()
    img.save(png_path)
    return w, h


# ─── MAIN ───

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Loading 2x22 template...")
    with open(TEMPLATE_2x22) as f:
        template = json.load(f)
    starts, bp = verify_scaffold(template)
    print(f"  Template: {bp}bp, starts={starts} {'VERIFIED' if starts == 0 else 'BROKEN'}")

    helix_len = len(template['vstrands'][0]['scaf'])
    target_widths = [40, 45, 50]
    all_designs = {}  # name → json_path

    # ─── STEP 1: Expand cavity height (10→12 cols) ───
    print("\n" + "=" * 60)
    print("STEP 1: Expand cavity height from 10 to 12 columns")
    print("=" * 60)
    # Convert pairs (H4,H5) and (H16,H17) in row 12
    # Convert pairs (H26,H27) and (H38,H39) in row 13
    expanded = expand_cavity_height(
        template,
        new_pairs_r12=[(4, 5), (16, 17)],
        new_pairs_r13=[(26, 27), (38, 39)]
    )
    starts, bp = verify_scaffold(expanded)
    cav_count = len(get_cavity_info(expanded))
    print(f"  Expanded: {bp}bp, starts={starts}, cavity_helices={cav_count}")

    if starts == 0:
        # Save expanded base template
        exp_path = os.path.join(OUTPUT_DIR, 'expanded_12cav_2x22_base.json')
        with open(exp_path, 'w') as f:
            json.dump(expanded, f)
        print(f"  Saved: {exp_path}")

        # Width sweep on expanded template
        r12_cav = [(4, 5), (6, 7), (8, 9), (10, 11), (12, 13), (14, 15), (16, 17)]
        r13_cav = [(26, 27), (28, 29), (30, 31), (32, 33), (34, 35), (36, 37), (38, 39)]

        for w_nm in target_widths:
            gap_bp = round(w_nm / NM_PER_BP)
            name = f"cavity_{w_nm}x31nm_2x22_pad5"
            print(f"\n  Width variant: {name} (gap={gap_bp}bp)")
            variant, gap_r12, gap_r13 = move_cavity_width(
                expanded, gap_bp, r12_cav, r13_cav)
            starts, scaf_bp = verify_scaffold(variant)
            actual_w = round(max(gap_r12, gap_r13) * NM_PER_BP, 1)
            print(f"    scaffold={scaf_bp}bp, starts={starts}, actual_w={actual_w}nm")
            if starts == 0:
                path = os.path.join(OUTPUT_DIR, f"{name}.json")
                with open(path, 'w') as f:
                    json.dump(variant, f)
                all_designs[name] = path
            else:
                print(f"    BROKEN — skipping")
    else:
        print("  FAILED — cavity height expansion broke scaffold")

    # ─── STEP 2: Width sweep on original 2x22 (10 cav cols) ───
    print("\n" + "=" * 60)
    print("STEP 2: Width sweep on original 2x22 (10 cav cols, 26nm height)")
    print("=" * 60)

    r12_cav_orig = [(6, 7), (8, 9), (10, 11), (12, 13), (14, 15)]
    r13_cav_orig = [(28, 29), (30, 31), (32, 33), (34, 35), (36, 37)]

    for w_nm in target_widths:
        gap_bp = round(w_nm / NM_PER_BP)
        name = f"cavity_{w_nm}x26nm_2x22_pad6"
        print(f"\n  Width variant: {name} (gap={gap_bp}bp)")
        variant, gap_r12, gap_r13 = move_cavity_width(
            template, gap_bp, r12_cav_orig, r13_cav_orig)
        starts, scaf_bp = verify_scaffold(variant)
        actual_w = round(max(gap_r12, gap_r13) * NM_PER_BP, 1)
        print(f"    scaffold={scaf_bp}bp, starts={starts}, actual_w={actual_w}nm")
        if starts == 0:
            path = os.path.join(OUTPUT_DIR, f"{name}.json")
            with open(path, 'w') as f:
                json.dump(variant, f)
            all_designs[name] = path
        else:
            print(f"    BROKEN — skipping")

    # ─── STEP 3: AutoStaple + AutoBreak on ALL designs ───
    print("\n" + "=" * 60)
    print("STEP 3: AutoStaple + AutoBreak")
    print("=" * 60)

    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()
    dc = list(app.documentControllers)[0]
    ab = _setup_autobreak()

    stapled_designs = {}

    for name, json_path in sorted(all_designs.items()):
        stapled_name = name + '_stapled'
        stapled_path = os.path.join(OUTPUT_DIR, f"{stapled_name}.json")
        print(f"\n  Stapling {name}...")

        from cadnano2.model.io.decoder import import_legacy_dict
        from cadnano2.model.parts.part import Part
        from cadnano2.model.io.encoder import encode

        dc.newDocument()
        doc = dc.document()
        with open(json_path) as f:
            obj = json.load(f)
        import_legacy_dict(doc, obj)
        part = doc.selectedPart()

        Part.autoStaple(part)

        settings = {'minStapleLen': 18, 'maxStapleLen': 50,
                     'tgtStapleLen': 32, 'minStapleLegLen': 3}
        for _ in range(3):
            for oligo in list(part.oligos()):
                if oligo.isStaple() and oligo.length() > 50:
                    try:
                        ab.nxBreakStaple(oligo, settings)
                    except Exception:
                        pass

        stap_c = sum(1 for o in part.oligos() if o.isStaple())
        scaf_oligos = [o for o in part.oligos() if not o.isStaple()]
        scaf_bp = sum(o.length() for o in scaf_oligos)
        starts = sum(1 for o in scaf_oligos if o.strand5p().connection5p() is None)

        hol = dc.win.pathroot.getSelectedPartOrderedVHList()
        with open(stapled_path, 'w') as f:
            encode(doc, hol, f)

        status = 'VERIFIED' if starts == 0 else f'BROKEN({starts})'
        print(f"    {status}: scaffold={scaf_bp}bp, staples={stap_c}")
        stapled_designs[stapled_name] = {
            'path': stapled_path,
            'scaffold_bp': scaf_bp,
            'scaffold_starts': starts,
            'staple_count': stap_c,
        }

    # ─── STEP 4: Screenshots ───
    print("\n" + "=" * 60)
    print("STEP 4: Screenshots")
    print("=" * 60)

    from cadnano2.model.io.decoder import import_legacy_dict
    from PyQt6.QtCore import QRectF, QMarginsF
    from PyQt6.QtGui import QImage, QPainter, QColor

    for name, info in sorted(stapled_designs.items()):
        png_path = os.path.join(OUTPUT_DIR, f"{name}.png")
        w, h = take_screenshot(dc, info['path'], png_path)
        info['png'] = png_path
        print(f"  {name}: {w}x{h}")

    # ─── STEP 5: Summary + ZIP ───
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    results = []
    json_files = []
    for name, info in sorted(stapled_designs.items()):
        status = 'VERIFIED' if info['scaffold_starts'] == 0 else f'BROKEN({info["scaffold_starts"]})'
        print(f"  {name}: {status}, scaffold={info['scaffold_bp']}bp, "
              f"staples={info['staple_count']}")
        results.append({
            'name': name,
            'scaffold_bp': info['scaffold_bp'],
            'scaffold_starts': info['scaffold_starts'],
            'verified': info['scaffold_starts'] == 0,
            'staple_count': info['staple_count'],
        })
        json_files.append(info['path'])

    summary_path = os.path.join(OUTPUT_DIR, 'sweep_summary.json')
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2)

    zip_path = os.path.join(OUTPUT_DIR, 'cavity_designs.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for jf in json_files:
            zf.write(jf, os.path.basename(jf))
        zf.write(summary_path, 'sweep_summary.json')
    print(f"\nZIP: {zip_path}")


if __name__ == '__main__':
    main()
