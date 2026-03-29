#!/usr/bin/env python
"""Build arbitrary DNA origami shapes from a list of helix positions.

Uses the simple alternating routing pattern:
- Intra-pair: half crossovers at edges
- Inter-pair: full crossover at midseam
- Last pair: edges only

Usage:
  python tools/build_shape.py <shape_name> <positions_json> [helix_len]

  positions_json: JSON array of [row, col] pairs, ordered as routing path
  e.g., '[[12,14],[12,13],[12,12],[12,11],[12,10],[12,9]]' for a 6HB
"""
import os, sys, json

EMPTY = [-1, -1, -1, -1]


def build_shape(name, positions, helix_len=252):
    """Build a DNA origami design from helix positions.

    Positions must be ordered as the scaffold routing path:
    H0, H1, H2, ... where (H0,H1), (H2,H3), etc. are intra-pairs.
    """
    assert len(positions) % 2 == 0, "Need even number of helices for pairing"

    design = {'name': name, 'vstrands': []}

    for i, (r, c) in enumerate(positions):
        vs = {
            'num': i, 'row': r, 'col': c,
            'scaf': [list(EMPTY)] * helix_len,
            'stap': [list(EMPTY)] * helix_len,
            'loop': [0] * helix_len,
            'skip': [0] * helix_len,
            'scafLoop': [], 'stapLoop': [],
            'stap_colors': [], 'scaf_colors': [],
        }
        design['vstrands'].append(vs)

    vs_map = {v['num']: v for v in design['vstrands']}
    n = len(positions)

    # Edge positions based on row parity
    # Row 12 (and even rows): edges at 5, 246
    # Row 13 (and odd rows): edges at 2, 242
    def edges(r):
        if r % 2 == 0:
            return 5, min(246, helix_len - 6)
        else:
            return 2, min(242, helix_len - 10)

    # Fill scaffold data
    for v in design['vstrands']:
        num = v['num']
        scaf = v['scaf']
        r, c = v['row'], v['col']
        parity = (r + c) % 2
        lo, hi = edges(r)
        for i in range(lo, hi + 1):
            if parity == 0:
                scaf[i] = [num, i - 1, num, i + 1]
            else:
                scaf[i] = [num, i + 1, num, i - 1]

    # Intra-pairs: (0,1), (2,3), ..., (n-2,n-1)
    intra_pairs = [(i * 2, i * 2 + 1) for i in range(n // 2)]
    # Inter-pairs: (1,2), (3,4), ..., (n-3,n-2) — skip last pair
    inter_pairs = [(i * 2 + 1, i * 2 + 2) for i in range(n // 2 - 1)]

    # Place intra-pair edge half crossovers
    for ha, hb in intra_pairs:
        sa = vs_map[ha]['scaf']
        sb = vs_map[hb]['scaf']
        r_a = positions[ha][0]
        r_b = positions[hb][0]
        lo_a, hi_a = edges(r_a)
        lo_b, hi_b = edges(r_b)

        # Use the min of lo values and min of hi values for the crossover position
        lo = max(lo_a, lo_b)
        hi = min(hi_a, hi_b)

        # Left edge
        sa[lo][0] = hb; sa[lo][1] = lo
        sb[lo][2] = ha; sb[lo][3] = lo
        # Right edge
        sa[hi][2] = hb; sa[hi][3] = hi
        sb[hi][0] = ha; sb[hi][1] = hi

    # Place inter-pair midseam full crossovers
    # Find valid midseam position for each pair
    STEP = 21
    for ha, hb in inter_pairs:
        sa = vs_map[ha]['scaf']
        sb = vs_map[hb]['scaf']
        r_a, r_b = positions[ha][0], positions[hb][0]
        lo_a, hi_a = edges(r_a)
        lo_b, hi_b = edges(r_b)

        # Midseam at center of helix
        center = helix_len // 2

        # Find valid position: try offsets that work for honeycomb
        # Common valid offsets mod 21: {1,2}, {4,5}, {8,9}, {11,12}, {15,16}
        best_lo = None
        best_dist = 9999
        for off_pair in [(1, 2), (4, 5), (8, 9), (11, 12), (15, 16)]:
            for k in range(helix_len // STEP + 1):
                lo = k * STEP + off_pair[0]
                hi = k * STEP + off_pair[1]
                if lo > lo_a and lo > lo_b and hi < hi_a and hi < hi_b:
                    dist = abs(lo - center)
                    if dist < best_dist:
                        best_lo = lo
                        best_hi = hi
                        best_dist = dist

        if best_lo is None:
            print(f"  WARNING: No valid midseam for H{ha}-H{hb}")
            continue

        # At lo: ha 5' from hb, hb 3' to ha
        sa[best_lo][0] = hb; sa[best_lo][1] = best_lo
        sb[best_lo][2] = ha; sb[best_lo][3] = best_lo
        # At hi: ha 3' to hb, hb 5' from ha
        sa[best_hi][2] = hb; sa[best_hi][3] = best_hi
        sb[best_hi][0] = ha; sb[best_hi][1] = best_hi

    # Verify
    visited = set()
    open_oligos = 0
    for v in design['vstrands']:
        for i, e in enumerate(v['scaf']):
            if e == EMPTY:
                continue
            key = (v['num'], i)
            if key in visited:
                continue
            if e[0] < 0:
                open_oligos += 1
                cur_h, cur_i = v['num'], i
                while True:
                    if (cur_h, cur_i) in visited:
                        break
                    visited.add((cur_h, cur_i))
                    entry = vs_map[cur_h]['scaf'][cur_i]
                    if entry[2] < 0:
                        break
                    cur_h, cur_i = entry[2], entry[3]

    total = sum(1 for v in design['vstrands'] for e in v['scaf'] if e != EMPTY)
    unvisited = total - len(visited)

    # Count closed loops
    loops = 0
    if unvisited > 0:
        for v in design['vstrands']:
            for i, e in enumerate(v['scaf']):
                if e == EMPTY:
                    continue
                if (v['num'], i) not in visited:
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
    print(f"{name}: {len(positions)} helices, {total}bp, "
          f"{open_oligos} open + {loops} loops = {total_oligos} oligo(s)")

    return design, total_oligos


def main():
    name = sys.argv[1]
    positions = json.loads(sys.argv[2])
    helix_len = int(sys.argv[3]) if len(sys.argv) > 3 else 252

    design, oligos = build_shape(name, positions, helix_len)

    os.makedirs('results/stress_test', exist_ok=True)
    out = f'results/stress_test/{name}.json'
    with open(out, 'w') as f:
        json.dump(design, f, separators=(',', ':'))
    print(f"Saved: {out}")


if __name__ == '__main__':
    main()
