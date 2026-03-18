#!/usr/bin/env python
"""
Scale up 2x12_rectangle_cavity.json to fit the p8064 scaffold (8064 bp).

Strategy:
  - Original helix length: 252bp (12 steps of 21)
  - New helix length: 420bp (20 steps of 21)
  - Full helices: row12 8-410 (403bp), row13 3-403 (401bp)
  - Cavity helices: gap enlarged to 198bp to hit exactly 8064bp total
  - Crossover topology preserved via segment-wise linear index mapping
  - autoStaple regenerates staple strands after loading in cadnano

Output:
  results/scaled_template/2x12_rectangle_cavity_p8064.json
  results/scaled_template/screenshot.png
"""

import os
import sys
import json
import math

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(BASE_DIR, "2x12_rectangle_cavity.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "results", "scaled_template")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "2x12_rectangle_cavity_p8064.json")
SCREENSHOT_FILE = os.path.join(OUTPUT_DIR, "screenshot.png")

OLD_LEN = 252
NEW_LEN = 420
TARGET_SCAFFOLD_BP = 8064
SCALE = NEW_LEN / OLD_LEN

# Helix classifications
ROW12_FULL = {0, 1, 2, 3, 8, 9, 10, 11}
ROW12_CAVITY = {4, 5, 6, 7}
ROW13_FULL = {12, 13, 14, 15, 20, 21, 22, 23}
ROW13_CAVITY = {16, 17, 18, 19}

# Exact gap boundaries computed to give 8064bp total:
# Row12 cavity gap: 93-290 (198bp), yielding 85+120=205bp per helix
# Row13 cavity gap: 104-301 (198bp), yielding 101+102=203bp per helix
# Total: 8*403 + 8*401 + 4*205 + 4*203 = 8064

# Original gap positions in template:
# Row12 cavity: gap 68-162
# Row13 cavity: gap 75-169


def log(msg):
    print(msg, flush=True)


def build_index_map(old_occupied, old_gap, new_start, new_end, new_gap_start, new_gap_end):
    """Build a mapping from old indices to new indices.

    For full helices: simple linear mapping.
    For cavity helices: map before-gap and after-gap segments separately.
    """
    idx_map = {}

    if old_gap is None:
        # Full helix: linear map
        old_start = min(old_occupied)
        old_end = max(old_occupied)
        old_range = old_end - old_start
        new_range = new_end - new_start
        for old_i in old_occupied:
            t = (old_i - old_start) / old_range if old_range > 0 else 0
            new_i = round(new_start + t * new_range)
            new_i = max(new_start, min(new_end, new_i))
            idx_map[old_i] = new_i
    else:
        # Cavity helix: map two segments
        gap_s, gap_e = old_gap
        before = sorted(i for i in old_occupied if i < gap_s)
        after = sorted(i for i in old_occupied if i > gap_e)

        # Map before-gap segment
        if before:
            b_old_start = min(before)
            b_old_end = max(before)
            b_new_start = new_start
            b_new_end = new_gap_start - 1
            b_old_range = b_old_end - b_old_start
            b_new_range = b_new_end - b_new_start
            for old_i in before:
                t = (old_i - b_old_start) / b_old_range if b_old_range > 0 else 0
                new_i = round(b_new_start + t * b_new_range)
                new_i = max(b_new_start, min(b_new_end, new_i))
                idx_map[old_i] = new_i

        # Map after-gap segment
        if after:
            a_old_start = min(after)
            a_old_end = max(after)
            a_new_start = new_gap_end + 1
            a_new_end = new_end
            a_old_range = a_old_end - a_old_start
            a_new_range = a_new_end - a_new_start
            for old_i in after:
                t = (old_i - a_old_start) / a_old_range if a_old_range > 0 else 0
                new_i = round(a_new_start + t * a_new_range)
                new_i = max(a_new_start, min(a_new_end, new_i))
                idx_map[old_i] = new_i

    return idx_map


def find_gap(strand_array):
    """Find gap in strand array."""
    occupied = [i for i, s in enumerate(strand_array) if s != [-1, -1, -1, -1]]
    if not occupied:
        return None
    full = set(range(min(occupied), max(occupied) + 1))
    gap = sorted(full - set(occupied))
    if gap:
        return (min(gap), max(gap))
    return None


def determine_direction(strand, seg_start, seg_end, helix_num):
    """Determine strand direction within a segment."""
    for idx in range(seg_start, seg_end + 1):
        entry = strand[idx]
        if entry == [-1, -1, -1, -1]:
            continue
        _, _, three_h, three_i = entry
        if three_h == helix_num and three_i >= 0:
            return 1 if three_i > idx else -1
        five_h, five_i, _, _ = entry
        if five_h == helix_num and five_i >= 0:
            return 1 if five_i < idx else -1
    return 1


def fill_strand_gaps(strand, helix_num):
    """Fill interpolated gaps in the strand to create continuous segments."""
    occupied = sorted(i for i in range(len(strand)) if strand[i] != [-1, -1, -1, -1])
    if len(occupied) < 2:
        return

    # Find segments (separated by large gaps = cavity)
    segments = [[occupied[0]]]
    for k in range(1, len(occupied)):
        if occupied[k] - occupied[k - 1] > 10:
            segments.append([occupied[k]])
        else:
            segments[-1].append(occupied[k])

    for seg in segments:
        seg_start = min(seg)
        seg_end = max(seg)
        direction = determine_direction(strand, seg_start, seg_end, helix_num)

        for i in range(seg_start, seg_end + 1):
            if strand[i] != [-1, -1, -1, -1]:
                continue
            if direction == 1:
                strand[i] = [helix_num, i - 1, helix_num, i + 1]
            else:
                strand[i] = [helix_num, i + 1, helix_num, i - 1]


def scale_design(design):
    """Scale the design, returning new JSON structure."""
    new_design = {"name": design["name"], "vstrands": []}

    # Build index maps for all helices
    all_maps = {}
    for vs in design["vstrands"]:
        hnum = vs["num"]
        scaf = vs["scaf"]
        occupied = sorted(i for i, s in enumerate(scaf) if s != [-1, -1, -1, -1])
        if not occupied:
            all_maps[hnum] = {}
            continue

        gap = find_gap(scaf) if hnum in (ROW12_CAVITY | ROW13_CAVITY) else None

        if hnum in ROW12_FULL:
            idx_map = build_index_map(occupied, None, 8, 410, None, None)
        elif hnum in ROW12_CAVITY:
            idx_map = build_index_map(occupied, gap, 8, 410, 93, 290)
        elif hnum in ROW13_FULL:
            idx_map = build_index_map(occupied, None, 3, 403, None, None)
        elif hnum in ROW13_CAVITY:
            idx_map = build_index_map(occupied, gap, 3, 403, 104, 301)
        else:
            idx_map = {}

        all_maps[hnum] = idx_map

    # Build new vstrands
    for vs in design["vstrands"]:
        hnum = vs["num"]
        idx_map = all_maps[hnum]

        new_vs = {
            "row": vs["row"],
            "col": vs["col"],
            "num": hnum,
            "scaf": [[-1, -1, -1, -1]] * NEW_LEN,
            "stap": [[-1, -1, -1, -1]] * NEW_LEN,
            "loop": [0] * NEW_LEN,
            "skip": [0] * NEW_LEN,
            "scafLoop": vs.get("scafLoop", []),
            "stapLoop": vs.get("stapLoop", []),
            "stap_colors": [],
            "scaf_colors": vs.get("scaf_colors", []),
        }

        # Map scaffold strand entries
        old_scaf = vs["scaf"]
        new_scaf = new_vs["scaf"]

        for old_i, entry in enumerate(old_scaf):
            if entry == [-1, -1, -1, -1]:
                continue
            if old_i not in idx_map:
                continue

            new_i = idx_map[old_i]
            five_h, five_i, three_h, three_i = entry

            # Remap references
            new_five_i = five_i
            new_three_i = three_i

            if five_h >= 0 and five_i >= 0:
                ref_map = all_maps.get(five_h, {})
                new_five_i = ref_map.get(five_i, round(five_i * SCALE))

            if three_h >= 0 and three_i >= 0:
                ref_map = all_maps.get(three_h, {})
                new_three_i = ref_map.get(three_i, round(three_i * SCALE))

            new_scaf[new_i] = [five_h, new_five_i, three_h, new_three_i]

        # Fill continuity gaps
        fill_strand_gaps(new_scaf, hnum)

        # Scale loop/skip
        for old_i, new_i in idx_map.items():
            if old_i < len(vs["loop"]):
                new_vs["loop"][new_i] = vs["loop"][old_i]
            if old_i < len(vs["skip"]):
                new_vs["skip"][new_i] = vs["skip"][old_i]

        # Scale scaf_colors
        for entry in vs.get("scaf_colors", []):
            if len(entry) == 2:
                old_ci, color = entry
                if old_ci in idx_map:
                    new_ci = idx_map[old_ci]
                else:
                    try:
                        new_ci = round(old_ci * SCALE)
                    except (OverflowError, ValueError):
                        new_ci = old_ci
                new_vs["scaf_colors"].append([new_ci, color])

        new_design["vstrands"].append(new_vs)

    return new_design


def verify(design):
    """Verify scaffold count and crossover consistency."""
    total = 0
    occupied_set = set()
    for vs in design["vstrands"]:
        hnum = vs["num"]
        for i, s in enumerate(vs["scaf"]):
            if s != [-1, -1, -1, -1]:
                total += 1
                occupied_set.add((hnum, i))

    issues = []
    for vs in design["vstrands"]:
        hnum = vs["num"]
        for i, entry in enumerate(vs["scaf"]):
            if entry == [-1, -1, -1, -1]:
                continue
            five_h, five_i, three_h, three_i = entry
            if five_h >= 0 and five_i >= 0 and (five_h, five_i) not in occupied_set:
                issues.append(f"H{hnum}[{i}] 5'->H{five_h}[{five_i}] missing")
            if three_h >= 0 and three_i >= 0 and (three_h, three_i) not in occupied_set:
                issues.append(f"H{hnum}[{i}] 3'->H{three_h}[{three_i}] missing")

    return total, issues


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    log(f"Loading template: {INPUT_FILE}")
    with open(INPUT_FILE) as f:
        design = json.load(f)

    orig_total = sum(sum(1 for s in vs["scaf"] if s != [-1, -1, -1, -1])
                     for vs in design["vstrands"])
    log(f"Original: {len(design['vstrands'])} helices, {OLD_LEN}bp arrays, "
        f"{orig_total}bp scaffold")

    log(f"\nScaling to {NEW_LEN}bp arrays...")
    scaled = scale_design(design)

    total, issues = verify(scaled)
    log(f"Scaled scaffold: {total}bp (target: {TARGET_SCAFFOLD_BP})")

    if issues:
        log(f"Crossover issues ({len(issues)}):")
        for iss in issues[:20]:
            log(f"  {iss}")
    else:
        log("Crossover consistency: OK")

    # Print summary
    log("\nScaled helix summary:")
    for vs in scaled["vstrands"]:
        occ = [i for i, s in enumerate(vs["scaf"]) if s != [-1, -1, -1, -1]]
        gap = find_gap(vs["scaf"])
        gap_str = f" gap={gap[0]}-{gap[1]} ({gap[1]-gap[0]+1}bp)" if gap else ""
        r = f"{min(occ)}-{max(occ)}" if occ else "empty"
        log(f"  H{vs['num']:2d}: {len(occ):3d}bp range={r}{gap_str}")

    # Save
    log(f"\nSaving: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(scaled, f, separators=(",", ":"))

    # Phase 2: cadnano
    log("\n=== Phase 2: cadnano headless ===")
    try:
        run_cadnano_phase()
    except Exception as e:
        log(f"cadnano phase error: {e}")
        import traceback
        traceback.print_exc()


def run_cadnano_phase():
    """Load in cadnano, autoStaple, save, screenshot."""
    sys.path.insert(0, BASE_DIR)
    import cadnano2.cadnano as cadnano
    from PyQt6.QtCore import QRectF, QMarginsF
    from PyQt6.QtGui import QImage, QPainter, QColor

    log("Initializing cadnano...")
    app_instance = cadnano.initAppWithGui()
    log("App ready.")

    dc = list(app_instance.documentControllers)[0]

    log(f"Loading: {OUTPUT_FILE}")
    dc.openAfterMaybeSaveCallback(OUTPUT_FILE)

    doc = dc.document()
    part = doc.selectedPart()
    if part is None:
        log("ERROR: No part loaded")
        return

    vhs = list(part.getVirtualHelices())
    log(f"Loaded {len(vhs)} helices in cadnano")

    log("Running autoStaple...")
    from cadnano2.model.parts.part import Part
    Part.autoStaple(part)
    log("autoStaple done.")

    # Save with staples
    helixOrderList = dc.win.pathroot.getSelectedPartOrderedVHList()
    if helixOrderList:
        from cadnano2.model.io.encoder import encode
        with open(OUTPUT_FILE, "w") as f:
            encode(doc, helixOrderList, f)
        log(f"Saved with staples: {OUTPUT_FILE}")

    # Screenshot
    log("Rendering screenshot...")
    scene = dc.win.pathscene
    rect = scene.itemsBoundingRect()
    if rect.isEmpty():
        rect = QRectF(0, 0, 1600, 400)
    margin = 20
    rect = rect.marginsAdded(QMarginsF(margin, margin, margin, margin))

    s = 2.0
    w = int(rect.width() * s)
    h = int(rect.height() * s)
    for max_d in [8000]:
        if w > max_d:
            s *= max_d / w
            w = max_d
            h = int(rect.height() * s)
        if h > max_d:
            s *= max_d / h
            h = max_d
            w = int(rect.width() * s)

    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(p, source=rect)
    p.end()
    img.save(SCREENSHOT_FILE)
    log(f"Screenshot: {SCREENSHOT_FILE}")
    log("Done!")


if __name__ == "__main__":
    main()
