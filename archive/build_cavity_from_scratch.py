#!/usr/bin/env python
"""
Build a 2x12 rectangle with cavity for p8064 scaffold from scratch.

Creates a cadnano design matching the PI's template pattern:
- 2x12 honeycomb grid: Row 12 cols 9-20, Row 13 cols 9-20 (24 helices)
- Dense scaffold crossovers at ALL valid honeycomb positions
- Cavity: cols 13-16 have scaffold gaps in the middle
- autoStaple for staple placement

Approach: Build the JSON directly by computing scaffold routing through all
crossover positions, then load in cadnano for autoStaple and screenshot.

Usage:
    cd /home/dan/Documents/code/cadnano2
    conda run -n cn24-agentic QT_QPA_PLATFORM=offscreen python tools/build_cavity_from_scratch.py
"""

import os
import sys
import json
from math import ceil
from collections import defaultdict

# CRITICAL: Must set before any Qt imports
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'results', 'from_scratch')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Parameters ──────────────────────────────────────────────────────────

SCAFFOLD_LENGTH = 8064  # p8064
HELIX_LENGTH = 420      # 20 steps of 21bp
STEP = 21

# Grid layout: 2 rows x 12 cols (same as template)
START_ROW = 12
START_COL = 9
N_ROWS = 2
N_COLS = 12

# Cavity: cols 13-16 (4 cols in each row = 8 helices)
CAVITY_COLS = [13, 14, 15, 16]

# Honeycomb crossover tables
SCAF_LOW = [[1, 11], [8, 18], [4, 15]]    # [p0, p1, p2]
SCAF_HIGH = [[2, 12], [9, 19], [5, 16]]

# Cavity gap ranges (scaled from template 252bp → 420bp)
# Template row12: gap at [68, 162], row13: gap at [75, 169]
SCALE = HELIX_LENGTH / 252.0


def is_even_parity(row, col):
    return (row % 2) == (col % 2)


def get_neighbors(row, col):
    """Get honeycomb neighbors (p0, p1, p2) for a given position."""
    if is_even_parity(row, col):
        return [(row, col + 1), (row - 1, col), (row, col - 1)]  # p0, p1, p2
    else:
        return [(row, col - 1), (row + 1, col), (row, col + 1)]  # p0, p1, p2


def get_direction(r1, c1, r2, c2):
    """Get the direction index (0,1,2) from (r1,c1) to (r2,c2)."""
    neighbors = get_neighbors(r1, c1)
    for i, (nr, nc) in enumerate(neighbors):
        if nr == r2 and nc == c2:
            return i
    return -1


def get_crossover_positions_for_pair(r1, c1, r2, c2, helix_length):
    """Get all valid scaffold crossover positions between two neighbor helices.

    Returns list of (low_idx, high_idx) double crossover position pairs.
    """
    direction = get_direction(r1, c1, r2, c2)
    if direction < 0:
        return []

    low_offsets = SCAF_LOW[direction]
    high_offsets = SCAF_HIGH[direction]

    positions = []
    for base in range(0, helix_length, STEP):
        for low_off, high_off in zip(low_offsets, high_offsets):
            low_idx = base + low_off
            high_idx = base + high_off
            if 0 <= low_idx < helix_length and 0 <= high_idx < helix_length:
                positions.append((low_idx, high_idx))

    return positions


def build_helix_list():
    """Build the list of helix positions in the same order as the template."""
    # Template order: row 12 cols 20→9 (descending), then row 13 cols 9→20 (ascending)
    helices = []
    for c in range(START_COL + N_COLS - 1, START_COL - 1, -1):  # 20 down to 9
        helices.append((START_ROW, c))
    for c in range(START_COL, START_COL + N_COLS):  # 9 up to 20
        helices.append((START_ROW + 1, c))
    return helices


def build_scaffold_routing(helices):
    """Build dense scaffold crossover routing matching the template pattern.

    The scaffold threads through ALL valid crossover positions between
    neighboring helices, creating the standard DNA origami weave pattern.

    Returns dict mapping (row, col) to list of scaffold entries [5p_vh, 5p_idx, 3p_vh, 3p_idx].
    """
    # First, determine the helix numbering (by position in list, matching template)
    pos_to_num = {}
    num_to_pos = {}
    for i, (r, c) in enumerate(helices):
        pos_to_num[(r, c)] = i
        num_to_pos[i] = (r, c)

    # Initialize scaffold arrays with empty entries
    scaf = {}
    for i, (r, c) in enumerate(helices):
        scaf[i] = [[-1, -1, -1, -1] for _ in range(HELIX_LENGTH)]

    # For each helix, determine scaffold range
    # Even parity: scaffold runs left→right (5'→3')
    # Odd parity: scaffold runs right→left (5'→3')
    # Scaffold entries: [5p_vh, 5p_idx, 3p_vh, 3p_idx]
    # For a base at index i on helix h:
    #   - 5p connection: where the 5' neighbor is (incoming)
    #   - 3p connection: where the 3' neighbor is (outgoing)

    # First, find all crossover positions between all neighbor pairs
    all_xovers = {}  # (num1, num2) -> [(low_idx, high_idx), ...]
    for i, (r1, c1) in enumerate(helices):
        for j, (r2, c2) in enumerate(helices):
            if i >= j:
                continue
            positions = get_crossover_positions_for_pair(r1, c1, r2, c2, HELIX_LENGTH)
            if positions:
                all_xovers[(i, j)] = positions

    # Determine cavity gap ranges for each helix
    cavity_gap = {}  # helix_num -> (gap_start, gap_end) or None
    for i, (r, c) in enumerate(helices):
        if c in CAVITY_COLS:
            if r == START_ROW:
                gap_start = int(68 * SCALE)
                gap_end = int(162 * SCALE)
            else:
                gap_start = int(75 * SCALE)
                gap_end = int(169 * SCALE)
            cavity_gap[i] = (gap_start, gap_end)

    # Determine scaffold strand ranges for each helix
    # Full helices: scaffold from edge to edge
    # Cavity helices: scaffold on left segment and right segment, gap in middle
    strand_ranges = {}
    for i, (r, c) in enumerate(helices):
        if i in cavity_gap:
            gap_start, gap_end = cavity_gap[i]
            # Determine the actual scaffold start/end from crossover positions
            # that are outside the gap
            # Left segment: from helix start to just before gap
            # Right segment: from just after gap to helix end
            strand_ranges[i] = [('left', gap_start), ('right', gap_end)]
        else:
            strand_ranges[i] = [('full', None)]

    # Now build the scaffold connectivity
    # For each position on each helix, determine the 5' and 3' connections

    # Compute scaffold range per helix: scaffold only exists between
    # the first and last crossover positions. Edges beyond crossovers are empty.
    # First, collect all crossover positions per helix
    xover_positions_per_helix = defaultdict(set)
    for (h1, h2), positions in all_xovers.items():
        for low_idx, high_idx in positions:
            xover_positions_per_helix[h1].add(low_idx)
            xover_positions_per_helix[h1].add(high_idx)
            xover_positions_per_helix[h2].add(low_idx)
            xover_positions_per_helix[h2].add(high_idx)

    # Determine scaffold start/end for each helix
    # For even parity: scaffold runs 5'→3' left to right
    #   Start at the lowest crossover position, end at the highest
    # For odd parity: scaffold runs 5'→3' right to left
    #   Start at the highest crossover position, end at the lowest
    helix_scaf_range = {}
    for i, (r, c) in enumerate(helices):
        if i not in xover_positions_per_helix:
            continue
        xpositions = sorted(xover_positions_per_helix[i])
        scaf_start = xpositions[0]
        scaf_end = xpositions[-1]
        helix_scaf_range[i] = (scaf_start, scaf_end)

    # For cavity helices, adjust scaffold ranges to have a gap
    for i in list(helix_scaf_range.keys()):
        if i in cavity_gap:
            gap_start, gap_end = cavity_gap[i]
            scaf_start, scaf_end = helix_scaf_range[i]
            # Filter crossover positions to those outside the gap
            valid_positions = [p for p in sorted(xover_positions_per_helix[i])
                             if p < gap_start or p >= gap_end]
            if valid_positions:
                # Left segment: scaf_start to last position before gap
                left_positions = [p for p in valid_positions if p < gap_start]
                right_positions = [p for p in valid_positions if p >= gap_end]
                helix_scaf_range[i] = (scaf_start, scaf_end)  # overall range
                # Store the gap info
                cavity_gap[i] = (
                    max(left_positions) + 1 if left_positions else gap_start,
                    min(right_positions) if right_positions else gap_end
                )

    # First pass: set up basic strand connectivity (along each helix)
    for i, (r, c) in enumerate(helices):
        if i not in helix_scaf_range:
            continue

        even = is_even_parity(r, c)
        scaf_start, scaf_end = helix_scaf_range[i]

        if i in cavity_gap:
            gap_s, gap_e = cavity_gap[i]
            # Left segment
            for idx in range(scaf_start, gap_s):
                if even:
                    prev_idx = idx - 1 if idx > scaf_start else -1
                    next_idx = idx + 1 if idx < gap_s - 1 else -1
                    scaf[i][idx] = [
                        i if prev_idx >= 0 else -1,
                        prev_idx if prev_idx >= 0 else -1,
                        i if next_idx >= 0 else -1,
                        next_idx if next_idx >= 0 else -1,
                    ]
                else:
                    prev_idx = idx + 1 if idx < gap_s - 1 else -1
                    next_idx = idx - 1 if idx > scaf_start else -1
                    scaf[i][idx] = [
                        i if prev_idx >= 0 else -1,
                        prev_idx if prev_idx >= 0 else -1,
                        i if next_idx >= 0 else -1,
                        next_idx if next_idx >= 0 else -1,
                    ]
            # Right segment
            for idx in range(gap_e, scaf_end + 1):
                if even:
                    prev_idx = idx - 1 if idx > gap_e else -1
                    next_idx = idx + 1 if idx <= scaf_end else -1
                    scaf[i][idx] = [
                        i if prev_idx >= 0 else -1,
                        prev_idx if prev_idx >= 0 else -1,
                        i if next_idx >= 0 else -1,
                        next_idx if next_idx >= 0 else -1,
                    ]
                else:
                    prev_idx = idx + 1 if idx < scaf_end else -1
                    next_idx = idx - 1 if idx > gap_e else -1
                    scaf[i][idx] = [
                        i if prev_idx >= 0 else -1,
                        prev_idx if prev_idx >= 0 else -1,
                        i if next_idx >= 0 else -1,
                        next_idx if next_idx >= 0 else -1,
                    ]
        else:
            # Full helix (between crossover bounds)
            for idx in range(scaf_start, scaf_end + 1):
                if even:
                    prev_idx = idx - 1 if idx > scaf_start else -1
                    next_idx = idx + 1 if idx < scaf_end else -1
                    scaf[i][idx] = [
                        i if prev_idx >= 0 else -1,
                        prev_idx if prev_idx >= 0 else -1,
                        i if next_idx >= 0 else -1,
                        next_idx if next_idx >= 0 else -1,
                    ]
                else:
                    prev_idx = idx + 1 if idx < scaf_end else -1
                    next_idx = idx - 1 if idx > scaf_start else -1
                    scaf[i][idx] = [
                        i if prev_idx >= 0 else -1,
                        prev_idx if prev_idx >= 0 else -1,
                        i if next_idx >= 0 else -1,
                        next_idx if next_idx >= 0 else -1,
                    ]

    # Now apply crossovers: at each crossover position, redirect the scaffold
    # A crossover at (low_idx, high_idx) between helix h1 and h2 means:
    # At low_idx: one helix's scaffold goes to the other helix
    # At high_idx: the other helix's scaffold comes back
    # This creates a double crossover (the scaffold crosses over and back)
    #
    # The convention depends on parity:
    # For scaffold at low_idx position between h1 (even) and h2:
    #   h1's scaffold at low_idx: 3' connection goes to h2 at low_idx
    #   h2's scaffold at low_idx: 5' connection comes from h1 at low_idx
    # For scaffold at high_idx:
    #   h2's scaffold at high_idx: 3' connection goes to h1 at high_idx
    #   h1's scaffold at high_idx: 5' connection comes from h2 at high_idx
    #
    # But this is more nuanced with honeycomb parity. Let me use the template
    # pattern to determine the correct crossover convention.

    xovers_placed = 0
    for (h1, h2), positions in sorted(all_xovers.items()):
        r1, c1 = helices[h1]
        r2, c2 = helices[h2]

        for low_idx, high_idx in positions:
            # Check if both positions are on valid scaffold regions
            h1_has_low = scaf[h1][low_idx] != [-1, -1, -1, -1]
            h2_has_low = scaf[h2][low_idx] != [-1, -1, -1, -1]
            h1_has_high = scaf[h1][high_idx] != [-1, -1, -1, -1]
            h2_has_high = scaf[h2][high_idx] != [-1, -1, -1, -1]

            if not (h1_has_low and h2_has_low and h1_has_high and h2_has_high):
                continue

            # Skip crossovers where one helix doesn't have scaffold at that position
            # (cavity gap region check)
            if scaf[h1][low_idx] == [-1, -1, -1, -1] or scaf[h2][low_idx] == [-1, -1, -1, -1]:
                continue
            if scaf[h1][high_idx] == [-1, -1, -1, -1] or scaf[h2][high_idx] == [-1, -1, -1, -1]:
                continue

            even1 = is_even_parity(r1, c1)

            # Double crossover convention from template analysis:
            # At LOW position:
            #   Even parity helix's 3' connection → other helix (crossover OUT)
            #   Odd parity helix's 5' connection ← other helix (crossover IN)
            # At HIGH position:
            #   Odd parity helix's 3' connection → other helix (crossover OUT)
            #   Even parity helix's 5' connection ← other helix (crossover IN)
            #
            # IMPORTANT: Only modify the crossover-side connection.
            # The other connection (5' at low for even, 3' at low for odd)
            # stays as the normal along-helix connection.

            if even1:
                # h1 is even, h2 is odd
                # Low: h1(even) 3' → h2, h2(odd) 5' ← h1
                scaf[h1][low_idx][2] = h2
                scaf[h1][low_idx][3] = low_idx
                scaf[h2][low_idx][0] = h1
                scaf[h2][low_idx][1] = low_idx
                # High: h2(odd) 3' → h1, h1(even) 5' ← h2
                scaf[h2][high_idx][2] = h1
                scaf[h2][high_idx][3] = high_idx
                scaf[h1][high_idx][0] = h2
                scaf[h1][high_idx][1] = high_idx
            else:
                # h1 is odd, h2 is even
                # Low: h2(even) 3' → h1, h1(odd) 5' ← h2
                scaf[h2][low_idx][2] = h1
                scaf[h2][low_idx][3] = low_idx
                scaf[h1][low_idx][0] = h2
                scaf[h1][low_idx][1] = low_idx
                # High: h1(odd) 3' → h2, h2(even) 5' ← h1
                scaf[h1][high_idx][2] = h2
                scaf[h1][high_idx][3] = high_idx
                scaf[h2][high_idx][0] = h1
                scaf[h2][high_idx][1] = high_idx

            xovers_placed += 1

    print(f"Crossovers placed: {xovers_placed}")

    # Count scaffold bases and check connectivity
    total_bases = 0
    for i in range(len(helices)):
        bases = sum(1 for entry in scaf[i] if entry != [-1, -1, -1, -1])
        total_bases += bases

    print(f"Total scaffold bases: {total_bases}")

    return scaf


def build_json(helices, scaf):
    """Build the cadnano JSON structure."""
    vstrands = []
    for i, (r, c) in enumerate(helices):
        vstrand = {
            'row': r,
            'col': c,
            'num': i,
            'scaf': scaf[i],
            'stap': [[-1, -1, -1, -1] for _ in range(HELIX_LENGTH)],
            'loop': [0] * HELIX_LENGTH,
            'skip': [0] * HELIX_LENGTH,
            'scafLoop': [],
            'stapLoop': [],
            'stap_colors': [],
            'scaf_colors': [],
        }
        vstrands.append(vstrand)

    design = {
        'name': 'p8064_2x12_cavity',
        'vstrands': vstrands,
    }
    return design


def load_and_autostable(json_path):
    """Load design in cadnano and run autoStaple."""
    import io
    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()

    dc = list(app.documentControllers)[0]

    # Load the JSON file using cadnano's decode
    from cadnano2.model.io.decoder import decode
    dc.newDocument(fname=json_path)
    with io.open(json_path, 'r', encoding='utf-8') as fd:
        decode(dc._document, fd.read())

    doc = dc.document()
    part = doc.selectedPart()

    if part is None:
        print("ERROR: No part found after loading JSON")
        return None, None, None

    # Count scaffold before autoStaple
    scaffold_oligos = [o for o in part.oligos() if not o.isStaple()]
    print(f"Scaffold oligos after load: {len(scaffold_oligos)}")
    for o in scaffold_oligos:
        print(f"  Length: {o.length()} bp")

    # Run autoStaple
    from cadnano2.model.parts.part import Part
    Part.autoStaple(part)

    staple_count = sum(1 for o in part.oligos() if o.isStaple())
    scaffold_count = sum(1 for o in part.oligos() if not o.isStaple())
    print(f"After autoStaple: {staple_count} staples, {scaffold_count} scaffold oligos")

    # Save the updated design
    updated_path = json_path.replace('.json', '_stapled.json')
    dc.writeDocumentToFile(updated_path)
    print(f"Saved stapled design: {updated_path}")

    return app, dc, part


def verify_design(part):
    """Print design statistics."""
    oligos = list(part.oligos())
    scaffolds = [o for o in oligos if not o.isStaple()]
    staples = [o for o in oligos if o.isStaple()]

    print(f"\n{'='*60}")
    print(f"DESIGN VERIFICATION")
    print(f"{'='*60}")
    print(f"Scaffold oligos: {len(scaffolds)}")
    total_scaf = 0
    for o in scaffolds:
        print(f"  Length: {o.length()} bp")
        total_scaf += o.length()
    print(f"Total scaffold bp: {total_scaf}")
    print(f"Target: {SCAFFOLD_LENGTH} bp, difference: {SCAFFOLD_LENGTH - total_scaf}")

    print(f"Staple oligos: {len(staples)}")
    if staples:
        lengths = [o.length() for o in staples]
        print(f"  Avg: {sum(lengths)/len(lengths):.1f}, Min: {min(lengths)}, Max: {max(lengths)}")


def render_screenshot(dc, output_path):
    """Render the path view to a PNG screenshot."""
    from PyQt6.QtCore import QRectF, QMarginsF
    from PyQt6.QtGui import QImage, QPainter, QColor

    win = dc.win
    scene = win.pathscene
    items_rect = scene.itemsBoundingRect()

    if items_rect.isEmpty():
        print("WARNING: Scene is empty, cannot render screenshot")
        return

    margin = 50
    items_rect = items_rect.marginsAdded(QMarginsF(margin, margin, margin, margin))

    scale = 2.0
    max_dim = 16000
    width = int(items_rect.width() * scale)
    height = int(items_rect.height() * scale)

    if width > max_dim:
        scale *= max_dim / width
        width = max_dim
        height = int(items_rect.height() * scale)
    if height > max_dim:
        scale *= max_dim / height
        height = max_dim
        width = int(items_rect.width() * scale)

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(255, 255, 255))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(painter, source=items_rect)
    painter.end()

    image.save(output_path)
    print(f"Screenshot saved: {output_path}")


def main():
    print("=" * 60)
    print("BUILD 2x12 RECTANGLE WITH CAVITY — p8064 SCAFFOLD")
    print("=" * 60)
    print(f"Grid: {N_ROWS}x{N_COLS} (rows {START_ROW}-{START_ROW+N_ROWS-1}, "
          f"cols {START_COL}-{START_COL+N_COLS-1})")
    print(f"Helix length: {HELIX_LENGTH} bp ({HELIX_LENGTH//STEP} steps)")
    print(f"Cavity columns: {CAVITY_COLS}")
    print(f"Scaffold: p8064 ({SCAFFOLD_LENGTH} bp)")
    print()

    # Step 1: Build helix list
    print("── Step 1: Build helix list ──")
    helices = build_helix_list()
    for i, (r, c) in enumerate(helices):
        parity = "even" if is_even_parity(r, c) else "odd"
        print(f"  Helix {i:2d}: ({r},{c}) {parity}")

    # Step 2: Build scaffold routing with dense crossovers
    print("\n── Step 2: Build scaffold routing ──")
    scaf = build_scaffold_routing(helices)

    # Step 3: Build JSON
    print("\n── Step 3: Build JSON ──")
    design = build_json(helices, scaf)
    json_path = os.path.join(OUTPUT_DIR, 'p8064_2x12_cavity.json')
    with open(json_path, 'w') as f:
        json.dump(design, f)
    print(f"JSON saved: {json_path}")

    # Step 4: Load in cadnano and run autoStaple
    print("\n── Step 4: Load and autoStaple ──")
    app, dc, part = load_and_autostable(json_path)

    if part is not None:
        # Step 5: Verify
        verify_design(part)

        # Step 6: Screenshot
        print("\n── Step 6: Screenshot ──")
        screenshot_path = os.path.join(OUTPUT_DIR, 'screenshot.png')
        render_screenshot(dc, screenshot_path)

    print(f"\n{'='*60}")
    print("DONE")
    print(f"{'='*60}")

    return app


if __name__ == '__main__':
    app = main()
