#!/usr/bin/env python
"""Build a cross shape by trimming a rectangle — demonstrates the
'moving edge crossovers' technique.

Approach:
1. Build a full 4×8 rectangle with alternating scaffold routing
2. Shorten the outer rows (top/bottom) by moving their edge half-crossovers inward
3. Clear scaffold data beyond the new edges
4. Result: a cross/plus shape

Usage:
  python tools/build_cross_from_rect.py [output_name] [helix_len]
"""
import os, sys, json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.build_shape import build_shape

EMPTY = [-1, -1, -1, -1]


def trim_helix_left(vs_map, helix_num, new_left, partner_num):
    """Move the left edge crossover inward, trimming the helix.

    Clears scaffold data from old left to new_left-1.
    Updates the edge half-crossover to the new position.
    """
    scaf = vs_map[helix_num]['scaf']
    partner_scaf = vs_map[partner_num]['scaf']

    # Clear scaffold up to new edge
    for i in range(len(scaf)):
        if scaf[i] == list(EMPTY):
            continue
        if i < new_left:
            # Check if this position has a crossover to partner
            if scaf[i][0] == partner_num or scaf[i][2] == partner_num:
                # Remove crossover reference from partner too
                for j in range(len(partner_scaf)):
                    if partner_scaf[j][0] == helix_num and partner_scaf[j][1] == i:
                        partner_scaf[j][0] = partner_num
                        partner_scaf[j][1] = j - 1 if j > 0 else -1
                    if partner_scaf[j][2] == helix_num and partner_scaf[j][3] == i:
                        partner_scaf[j][2] = partner_num
                        partner_scaf[j][3] = j + 1 if j < len(partner_scaf) - 1 else -1
            scaf[i] = list(EMPTY)
        elif i == new_left:
            # This becomes the new edge — update 5' to be free or connect to partner
            r = vs_map[helix_num]['row']
            c = vs_map[helix_num]['col']
            parity = (r + c) % 2
            if parity == 0:
                # Even parity: 5' at left edge
                scaf[i][0] = -1
                scaf[i][1] = -1
            else:
                # Odd parity: 3' at left edge
                scaf[i][2] = -1
                scaf[i][3] = -1
            break


def trim_helix_right(vs_map, helix_num, new_right, partner_num):
    """Move the right edge crossover inward, trimming the helix."""
    scaf = vs_map[helix_num]['scaf']
    partner_scaf = vs_map[partner_num]['scaf']

    for i in range(len(scaf) - 1, -1, -1):
        if scaf[i] == list(EMPTY):
            continue
        if i > new_right:
            if scaf[i][0] == partner_num or scaf[i][2] == partner_num:
                for j in range(len(partner_scaf)):
                    if partner_scaf[j][0] == helix_num and partner_scaf[j][1] == i:
                        partner_scaf[j][0] = partner_num
                        partner_scaf[j][1] = j - 1
                    if partner_scaf[j][2] == helix_num and partner_scaf[j][3] == i:
                        partner_scaf[j][2] = partner_num
                        partner_scaf[j][3] = j + 1
            scaf[i] = list(EMPTY)
        elif i == new_right:
            r = vs_map[helix_num]['row']
            c = vs_map[helix_num]['col']
            parity = (r + c) % 2
            if parity == 0:
                # Even: 3' at right edge
                scaf[i][2] = -1
                scaf[i][3] = -1
            else:
                # Odd: 5' at right edge
                scaf[i][0] = -1
                scaf[i][1] = -1
            break


def reconnect_edge_crossovers(vs_map, helix_a, helix_b):
    """Reconnect edge half-crossovers between paired helices at their
    current edge positions (leftmost and rightmost scaffold entries)."""
    scaf_a = vs_map[helix_a]['scaf']
    scaf_b = vs_map[helix_b]['scaf']

    # Find actual edges
    left_a = next(i for i, e in enumerate(scaf_a) if e != list(EMPTY))
    right_a = next(i for i in range(len(scaf_a) - 1, -1, -1) if scaf_a[i] != list(EMPTY))
    left_b = next(i for i, e in enumerate(scaf_b) if e != list(EMPTY))
    right_b = next(i for i in range(len(scaf_b) - 1, -1, -1) if scaf_b[i] != list(EMPTY))

    lo = max(left_a, left_b)
    hi = min(right_a, right_b)

    r_a, c_a = vs_map[helix_a]['row'], vs_map[helix_a]['col']
    r_b, c_b = vs_map[helix_b]['row'], vs_map[helix_b]['col']
    pa = (r_a + c_a) % 2
    pb = (r_b + c_b) % 2

    # Connect at lo
    if pa == 0:  # even: 5' at lo
        scaf_a[lo][0] = helix_b
        scaf_a[lo][1] = lo
    else:  # odd: 3' at lo
        scaf_a[lo][2] = helix_b
        scaf_a[lo][3] = lo

    if pb == 0:
        scaf_b[lo][0] = helix_a
        scaf_b[lo][1] = lo
    else:
        scaf_b[lo][2] = helix_a
        scaf_b[lo][3] = lo

    # Connect at hi
    if pa == 0:  # even: 3' at hi
        scaf_a[hi][2] = helix_b
        scaf_a[hi][3] = hi
    else:  # odd: 5' at hi
        scaf_a[hi][0] = helix_b
        scaf_a[hi][1] = hi

    if pb == 0:
        scaf_b[hi][2] = helix_a
        scaf_b[hi][3] = hi
    else:
        scaf_b[hi][0] = helix_a
        scaf_b[hi][1] = hi


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else 'cross_from_rect'
    helix_len = int(sys.argv[2]) if len(sys.argv) > 2 else 252

    # Step 1: Build a 4×8 rectangle
    # Rows 11-14, cols 7-14 (8 columns)
    rect_positions = []
    # Row 11: L→R
    for c in range(7, 15):
        rect_positions.append([11, c])
    # Row 12: R→L
    for c in range(14, 6, -1):
        rect_positions.append([12, c])
    # Row 13: L→R
    for c in range(7, 15):
        rect_positions.append([13, c])
    # Row 14: R→L
    for c in range(14, 6, -1):
        rect_positions.append([14, c])

    print(f"Step 1: Building 4×8 rectangle ({len(rect_positions)} helices)...")
    design, oligos = build_shape(name + '_rect', rect_positions, helix_len)

    # Save rectangle for reference
    os.makedirs('results/stress_test', exist_ok=True)
    with open(f'results/stress_test/{name}_rect.json', 'w') as f:
        json.dump(design, f, separators=(',', ':'))

    # Step 2: Trim top (row 11) and bottom (row 14) rows
    # Keep only center 4 cols (cols 10-13) for the arms
    # Bar (rows 12-13) stays full width (cols 7-14)
    vs_map = {v['num']: v for v in design['vstrands']}

    # Build helix lookup by position
    pos_to_num = {}
    for v in design['vstrands']:
        pos_to_num[(v['row'], v['col'])] = v['num']

    # Trim left side of row 11 and 14 (cols 7-9 → clear)
    # Trim right side of row 11 and 14 (cols 14 → keep, but 14-15 if wider)
    trim_left = 80   # Move left edge from ~5 to ~80 (shortening by ~75bp)
    trim_right = 170  # Move right edge from ~246 to ~170

    print(f"Step 2: Trimming rows 11,14 edges to [{trim_left}..{trim_right}]...")

    # For rows 11 and 14, clear cols 7-9 and col 14 (keep 10-13)
    for row in [11, 14]:
        for col in [7, 8, 9, 14]:
            if (row, col) in pos_to_num:
                num = pos_to_num[(row, col)]
                # Clear all scaffold data on this helix
                scaf = vs_map[num]['scaf']
                for i in range(len(scaf)):
                    if scaf[i] != list(EMPTY):
                        # Also clear partner refs
                        for other_v in design['vstrands']:
                            other_scaf = other_v['scaf']
                            for j in range(len(other_scaf)):
                                if other_scaf[j][0] == num:
                                    other_scaf[j][0] = other_v['num']
                                    other_scaf[j][1] = j - 1
                                if other_scaf[j][2] == num:
                                    other_scaf[j][2] = other_v['num']
                                    other_scaf[j][3] = j + 1
                    scaf[i] = list(EMPTY)
                print(f"  Cleared H{num} at ({row},{col})")

    # Reconnect the edges where we broke connections
    # Row 11: remaining helices are cols 10-13, need to reconnect edge crossovers
    for row in [11, 14]:
        remaining = sorted([c for c in range(7, 15) if (row, c) in pos_to_num
                           and any(e != list(EMPTY) for e in vs_map[pos_to_num[(row, c)]]['scaf'])])
        if not remaining:
            continue
        print(f"  Row {row} remaining cols: {remaining}")

    # Fix the edge crossovers for remaining pairs
    # After clearing, the edge helices need their crossovers fixed
    for row in [11, 14]:
        remaining_cols = sorted([c for c in range(7, 15)
                                if (row, c) in pos_to_num
                                and any(e != list(EMPTY) for e in vs_map[pos_to_num[(row, c)]]['scaf'])])
        if len(remaining_cols) >= 2:
            # The routing pairs within this row
            nums_in_row = [pos_to_num[(row, c)] for c in remaining_cols]
            # Fix edge pair connections
            for i in range(0, len(nums_in_row), 2):
                if i + 1 < len(nums_in_row):
                    reconnect_edge_crossovers(vs_map, nums_in_row[i], nums_in_row[i + 1])

    # Verify result
    visited = set()
    open_oligos = 0
    loops = 0
    for v in design['vstrands']:
        for i, e in enumerate(v['scaf']):
            if e == list(EMPTY):
                continue
            key = (v['num'], i)
            if key in visited:
                continue
            if e[0] < 0:
                open_oligos += 1
                cur_h, cur_i = v['num'], i
                ct = 0
                while ct < 20000:
                    if (cur_h, cur_i) in visited:
                        break
                    visited.add((cur_h, cur_i))
                    ct += 1
                    entry = vs_map[cur_h]['scaf'][cur_i]
                    if entry[2] < 0:
                        break
                    cur_h, cur_i = entry[2], entry[3]

    total = sum(1 for v in design['vstrands'] for e in v['scaf'] if e != list(EMPTY))
    unvisited = total - len(visited)
    if unvisited > 0:
        for v in design['vstrands']:
            for i, e in enumerate(v['scaf']):
                if e == list(EMPTY) or (v['num'], i) in visited:
                    continue
                loops += 1
                cur_h, cur_i = v['num'], i
                ct = 0
                while ct < 20000:
                    if (cur_h, cur_i) in visited:
                        break
                    visited.add((cur_h, cur_i))
                    ct += 1
                    entry = vs_map[cur_h]['scaf'][cur_i]
                    if entry[2] < 0:
                        break
                    cur_h, cur_i = entry[2], entry[3]

    total_oligos = open_oligos + loops
    active_helices = sum(1 for v in design['vstrands']
                        if any(e != list(EMPTY) for e in v['scaf']))
    print(f"\nResult: {active_helices} active helices, {total}bp, "
          f"{open_oligos} open + {loops} loops = {total_oligos} oligo(s)")

    # Remove empty helices from design
    design['vstrands'] = [v for v in design['vstrands']
                         if any(e != list(EMPTY) for e in v['scaf'])]
    print(f"Kept {len(design['vstrands'])} helices after removing empties")

    out = f'results/stress_test/{name}.json'
    with open(out, 'w') as f:
        json.dump(design, f, separators=(',', ':'))
    print(f"Saved: {out}")


if __name__ == '__main__':
    main()
