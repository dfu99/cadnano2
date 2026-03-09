#!/usr/bin/env python3
"""
generate_training_designs.py

Programmatically generate valid cadnano honeycomb designs for LLM fine-tuning.
No cadnano GUI required. Outputs JSONL in the same format as export_training_data.py.

Designs generated (by default):
  - 2-helix bundles: 5 lengths × 6 starting positions = 30 examples
  - Additional expert JSON files (via --expert flag)

Usage:
    # Generate 2HB designs:
    python tools/generate_training_designs.py \\
        --output ~/.cadnano2/training_data.jsonl

    # Include expert designs too:
    python tools/generate_training_designs.py \\
        --output ~/.cadnano2/training_data.jsonl \\
        --expert agent-6hb-scaffoldonly.json

    # Check what will be generated:
    python tools/generate_training_designs.py --stats

    # Then fine-tune:
    python tools/finetune_unsloth.py --data ~/.cadnano2/training_data.jsonl

Design validity:
  - Scaffold forms a single closed loop through all helices
  - Even-parity helices: scaffold 5'->3' goes left-to-right (increasing index)
  - Odd-parity helices:  scaffold 5'->3' goes right-to-left (decreasing index)
  - Half-crossovers at helix endpoints connect the loop
"""

import argparse
import json
import os
import sys


SYSTEM_PROMPT = (
    "You are a cadnano DNA nanostructure design assistant. "
    "Use the provided tools to build the requested design step by step. "
    "Always start with createHelicesWithStrands, then add crossovers."
)

# Default lengths to generate (multiples of 21 = valid honeycomb scaffold lengths)
DEFAULT_LENGTHS = [42, 63, 84, 105, 126, 147, 168]

# Starting positions (row, col) for the first helix of each 2HB.
# Second helix is placed at (row, col+1).
# Uses varied positions to teach position-invariance.
TWO_HB_STARTS = [
    (0, 0),
    (0, 2),
    (0, 4),
    (2, 0),
    (2, 2),
    (4, 0),
]


# ─── Honeycomb crossover tables (from cadnano2/model/parts/honeycombpart.py) ──

# Scaffold crossover positions (mod 21 offsets) for each of 3 neighbor directions.
# Low and High form adjacent pairs for double crossovers.
SCAF_LOW  = [[1, 11], [8, 18], [4, 15]]   # direction p0, p1, p2
SCAF_HIGH = [[2, 12], [9, 19], [5, 16]]

# Neighbor directions: given a helix at (row, col),
# Even parity: p0=(r,c+1), p1=(r-1,c), p2=(r,c-1)
# Odd  parity: p0=(r,c-1), p1=(r+1,c), p2=(r,c+1)

STEP = 21   # honeycomb step size


# ─── Honeycomb helpers ────────────────────────────────────────────────────────

def is_even_parity(row: int, col: int) -> bool:
    """Cadnano honeycomb parity: even iff (row%2 == col%2).

    Even-parity helices carry scaffold 5'->3' left-to-right (increasing index).
    Odd-parity helices carry scaffold 5'->3' right-to-left (decreasing index).
    """
    return (row % 2) == (col % 2)


def make_vstrand(row: int, col: int, num: int, scaf: list, stap: list, length: int) -> dict:
    return {
        "row": row, "col": col, "num": num,
        "scaf": scaf,
        "stap": stap,
        "loop":     [0] * length,
        "skip":     [0] * length,
        "scafLoop": 0,
        "stapLoop": 0,
        "stap_colors": [],
        "scaf_colors": [],
    }


def _neighbor_direction(r_a: int, c_a: int, r_b: int, c_b: int) -> int:
    """Return the neighbor direction index (0, 1, or 2) from helix A to B.

    Returns -1 if B is not a honeycomb neighbor of A.
    """
    if is_even_parity(r_a, c_a):
        # Even: p0=(r,c+1), p1=(r-1,c), p2=(r,c-1)
        if (r_b, c_b) == (r_a, c_a + 1):
            return 0
        if (r_b, c_b) == (r_a - 1, c_a):
            return 1
        if (r_b, c_b) == (r_a, c_a - 1):
            return 2
    else:
        # Odd: p0=(r,c-1), p1=(r+1,c), p2=(r,c+1)
        if (r_b, c_b) == (r_a, c_a - 1):
            return 0
        if (r_b, c_b) == (r_a + 1, c_a):
            return 1
        if (r_b, c_b) == (r_a, c_a + 1):
            return 2
    return -1


def _valid_positions(direction: int, L: int, use_low: bool) -> list[int]:
    """Return all valid scaffold crossover positions for a direction and type.

    Args:
        direction: neighbor direction index (0, 1, or 2)
        L: total helix length (number of bases)
        use_low: True for Low positions, False for High positions
    """
    offsets = SCAF_LOW[direction] if use_low else SCAF_HIGH[direction]
    positions = []
    for base in range(0, L, STEP):
        for off in offsets:
            idx = base + off
            if 0 <= idx < L:
                positions.append(idx)
    return sorted(positions)


def _pick_crossover_position(positions: list[int], near_high: bool) -> int:
    """Pick the crossover position nearest to one end of the helix.

    Args:
        positions: sorted list of valid positions
        near_high: True to pick the highest position, False for lowest
    """
    return positions[-1] if near_high else positions[0]


def _pick_crossover_position_near(positions: list[int], target: int) -> int:
    """Pick the valid position closest to a target index."""
    return min(positions, key=lambda p: abs(p - target))


# ─── 2-Helix Bundle generator ─────────────────────────────────────────────────

def generate_2hb(row: int = 0, col: int = 0, length: int = 84) -> dict:
    """Generate a 2-helix bundle cadnano JSON dict.

    Helices:
        H0 at (row, col)
        H1 at (row, col+1)

    Scaffold routing (closed loop):
        Even helix goes L->R.  Odd helix goes R->L.
        Half-crossovers connect them at positions 0 (left) and length-1 (right).

    Returns a cadnano JSON dict (not serialised) with an extra '_task' key
    containing a natural-language task description.
    """
    L = length
    h0_even = is_even_parity(row, col)

    # Assign even / odd roles (helix numbers stay 0 and 1)
    if h0_even:
        en, od = 0, 1
        en_pos = (row, col)
        od_pos = (row, col + 1)
    else:
        en, od = 1, 0
        en_pos = (row, col + 1)
        od_pos = (row, col)

    # ── Even helix scaffold (5'->3' = L->R, increasing index) ─────────────
    # Left end  (pos 0):   5' enters from odd helix via half-crossover
    # Right end (pos L-1): 3' exits  to  odd helix via half-crossover
    scaf_en = [[-1, -1, -1, -1] for _ in range(L)]
    scaf_en[0]     = [od, 0,   en, 1]
    for i in range(1, L - 1):
        scaf_en[i] = [en, i-1, en, i+1]
    scaf_en[L - 1] = [en, L-2, od, L-1]

    # ── Odd helix scaffold (5'->3' = R->L, decreasing index) ──────────────
    # Right end (pos L-1): 5' enters from even helix via half-crossover
    # Left end  (pos 0):   3' exits  to  even helix via half-crossover
    scaf_od = [[-1, -1, -1, -1] for _ in range(L)]
    scaf_od[L - 1] = [en, L-1, od, L-2]
    for i in range(L - 2, 0, -1):
        scaf_od[i] = [od, i+1, od, i-1]
    scaf_od[0]     = [od, 1,   en, 0]

    stap_en = [[-1, -1, -1, -1] for _ in range(L)]
    stap_od = [[-1, -1, -1, -1] for _ in range(L)]

    vstrands = [None, None]
    vstrands[en] = make_vstrand(en_pos[0], en_pos[1], en, scaf_en, stap_en, L)
    vstrands[od] = make_vstrand(od_pos[0], od_pos[1], od, scaf_od, stap_od, L)

    task = (
        f"Create a 2-helix bundle with a {L}bp scaffold strand. "
        f"Place the helices at row {row}, columns {col} and {col + 1}."
    )

    return {
        "name":     f"2hb_r{row}c{col}_L{L}",
        "vstrands": vstrands,
        "_task":    task,
    }


# ─── General bundle generator ─────────────────────────────────────────────────

def _build_neighbor_graph(positions: list[tuple[int, int]]) -> dict:
    """Build adjacency list from honeycomb neighbor relationships."""
    pos_set = {(r, c) for r, c in positions}
    adj = {(r, c): [] for r, c in positions}
    for r, c in positions:
        if is_even_parity(r, c):
            neighbors = [(r, c + 1), (r - 1, c), (r, c - 1)]
        else:
            neighbors = [(r, c - 1), (r + 1, c), (r, c + 1)]
        for nb in neighbors:
            if nb in pos_set and nb not in adj[(r, c)]:
                adj[(r, c)].append(nb)
    return adj


def _find_hamiltonian_path(adj: dict, positions: list[tuple[int, int]]) -> list:
    """Find a Hamiltonian path through the neighbor graph using DFS backtracking.

    Returns a list of (row, col) tuples visiting every position exactly once.
    Starts from degree-1 nodes (endpoints) for efficiency.
    """
    pos_set = set(positions)
    # Prefer starting from degree-1 nodes (chain endpoints)
    starts = [p for p in positions if len(adj[p]) == 1]
    if not starts:
        starts = list(positions)

    for start in starts:
        path = [start]
        visited = {start}

        def dfs():
            if len(path) == len(positions):
                return True
            for nb in adj[path[-1]]:
                if nb not in visited:
                    path.append(nb)
                    visited.add(nb)
                    if dfs():
                        return True
                    path.pop()
                    visited.remove(nb)
            return False

        if dfs():
            return path

    return []


def _route_and_build(helix_positions: list[tuple[int, int]], length: int,
                     name: str, task: str) -> dict:
    """Route scaffold through arbitrary honeycomb helix positions.

    Core routing engine: finds a Hamiltonian path through the neighbor graph,
    computes crossover positions using honeycomb tables, builds scaffold arrays
    with out-and-back serpentine routing forming a single closed loop.

    Args:
        helix_positions: list of (row, col) tuples for each helix
        length: scaffold length per helix (should be multiple of 21)
        name: design name for output
        task: natural language task description

    Returns:
        cadnano JSON dict with '_task' key
    """
    L = length
    num_helices = len(helix_positions)

    # Build neighbor graph and find Hamiltonian path
    adj = _build_neighbor_graph(helix_positions)
    chain = _find_hamiltonian_path(adj, helix_positions)
    if len(chain) != num_helices:
        raise ValueError(
            f"Cannot find Hamiltonian path for {num_helices} helices. "
            f"Check that positions form a connected chain."
        )

    # Assign helix numbers: chain[0] = H0, chain[1] = H1, etc.
    pos_to_num = {pos: i for i, pos in enumerate(chain)}

    # ── Compute crossover positions for each consecutive pair ────────────
    M = num_helices
    pair_out = [0] * (M - 1)
    pair_ret = [0] * (M - 1)

    # Precompute valid positions for each pair
    pair_out_valid = []
    pair_ret_valid = []
    for i in range(M - 1):
        r_a, c_a = chain[i]
        r_b, c_b = chain[i + 1]
        d = _neighbor_direction(r_a, c_a, r_b, c_b)
        assert d >= 0, f"Helices {chain[i]} and {chain[i+1]} are not neighbors"
        even_a = is_even_parity(r_a, c_a)
        pair_out_valid.append(_valid_positions(d, L, use_low=even_a))
        pair_ret_valid.append(_valid_positions(d, L, use_low=not even_a))

    # Pair 0: end pair for h_0
    even_0 = is_even_parity(*chain[0])
    if even_0:
        pair_out[0] = pair_out_valid[0][-1]
        pair_ret[0] = pair_ret_valid[0][0]
    else:
        pair_out[0] = pair_out_valid[0][0]
        pair_ret[0] = pair_ret_valid[0][-1]

    # Greedy: for each subsequent pair, determine constraints from h_k
    for k in range(1, M - 1):
        even_k = is_even_parity(*chain[k])
        out_prev = pair_out[k - 1]
        ret_prev = pair_ret[k - 1]
        is_last = (k == M - 2)

        if even_k:
            if out_prev < ret_prev:
                cands_out = [p for p in pair_out_valid[k]
                             if out_prev < p < ret_prev]
                cands_ret = [p for p in pair_ret_valid[k]
                             if out_prev < p < ret_prev]
                if not cands_out or not cands_ret:
                    raise ValueError(
                        f"No room for pair {k} on even h_k={chain[k]} "
                        f"between out_prev={out_prev} and ret_prev={ret_prev}"
                    )
                mid = (out_prev + ret_prev) // 2
                pair_out[k] = _pick_crossover_position_near(cands_out, mid)
                cands_ret = [p for p in cands_ret if p > pair_out[k]]
                if not cands_ret:
                    raise ValueError(
                        f"No valid ret position above out={pair_out[k]} "
                        f"for pair {k}"
                    )
                pair_ret[k] = _pick_crossover_position_near(cands_ret, mid)
            else:
                cands_ret = [p for p in pair_ret_valid[k] if p < ret_prev]
                cands_out = [p for p in pair_out_valid[k] if p > out_prev]
                if not cands_ret or not cands_out:
                    raise ValueError(
                        f"No room for pair {k} on even h_k={chain[k]} "
                        f"outside ret_prev={ret_prev}, out_prev={out_prev}"
                    )
                pair_ret[k] = cands_ret[0] if is_last else \
                    _pick_crossover_position_near(cands_ret, ret_prev // 2)
                pair_out[k] = cands_out[-1] if is_last else \
                    _pick_crossover_position_near(cands_out, (out_prev + L) // 2)
        else:
            if out_prev > ret_prev:
                cands_out = [p for p in pair_out_valid[k]
                             if ret_prev < p < out_prev]
                cands_ret = [p for p in pair_ret_valid[k]
                             if ret_prev < p < out_prev]
                if not cands_out or not cands_ret:
                    raise ValueError(
                        f"No room for pair {k} on odd h_k={chain[k]} "
                        f"between ret_prev={ret_prev} and out_prev={out_prev}"
                    )
                mid = (ret_prev + out_prev) // 2
                pair_out[k] = _pick_crossover_position_near(cands_out, mid)
                cands_ret = [p for p in cands_ret if p < pair_out[k]]
                if not cands_ret:
                    raise ValueError(
                        f"No valid ret position below out={pair_out[k]} "
                        f"for pair {k}"
                    )
                pair_ret[k] = _pick_crossover_position_near(cands_ret, mid)
            else:
                cands_out = [p for p in pair_out_valid[k] if p < out_prev]
                cands_ret = [p for p in pair_ret_valid[k] if p > ret_prev]
                if not cands_out or not cands_ret:
                    raise ValueError(
                        f"No room for pair {k} on odd h_k={chain[k]} "
                        f"outside out_prev={out_prev}, ret_prev={ret_prev}"
                    )
                pair_out[k] = cands_out[0] if is_last else \
                    _pick_crossover_position_near(cands_out, out_prev // 2)
                pair_ret[k] = cands_ret[-1] if is_last else \
                    _pick_crossover_position_near(cands_ret, (ret_prev + L) // 2)

    # ── Build scaffold arrays for each helix ────────────────────────────
    scaf_arrays = {}
    for idx in range(M):
        r_i, c_i = chain[idx]
        num_i = pos_to_num[(r_i, c_i)]
        even_i = is_even_parity(r_i, c_i)
        scaf = [[-1, -1, -1, -1] for _ in range(L)]

        if idx == 0:
            num_next = pos_to_num[chain[1]]
            lo = min(pair_ret[0], pair_out[0])
            hi = max(pair_ret[0], pair_out[0])
            if even_i:
                scaf[lo] = [num_next, lo, num_i, lo + 1]
                for j in range(lo + 1, hi):
                    scaf[j] = [num_i, j - 1, num_i, j + 1]
                scaf[hi] = [num_i, hi - 1, num_next, hi]
            else:
                scaf[hi] = [num_next, hi, num_i, hi - 1]
                for j in range(hi - 1, lo, -1):
                    scaf[j] = [num_i, j + 1, num_i, j - 1]
                scaf[lo] = [num_i, lo + 1, num_next, lo]

        elif idx == M - 1:
            num_prev = pos_to_num[chain[M - 2]]
            lo = min(pair_out[M - 2], pair_ret[M - 2])
            hi = max(pair_out[M - 2], pair_ret[M - 2])
            if even_i:
                scaf[lo] = [num_prev, lo, num_i, lo + 1]
                for j in range(lo + 1, hi):
                    scaf[j] = [num_i, j - 1, num_i, j + 1]
                scaf[hi] = [num_i, hi - 1, num_prev, hi]
            else:
                scaf[hi] = [num_prev, hi, num_i, hi - 1]
                for j in range(hi - 1, lo, -1):
                    scaf[j] = [num_i, j + 1, num_i, j - 1]
                scaf[lo] = [num_i, lo + 1, num_prev, lo]

        else:
            num_prev = pos_to_num[chain[idx - 1]]
            num_next = pos_to_num[chain[idx + 1]]

            xo_prev_out = pair_out[idx - 1]
            xo_prev_ret = pair_ret[idx - 1]
            xo_next_out = pair_out[idx]
            xo_next_ret = pair_ret[idx]

            positions_on_helix = sorted([
                (xo_prev_out, 'out_prev', num_prev),
                (xo_prev_ret, 'ret_prev', num_prev),
                (xo_next_out, 'out_next', num_next),
                (xo_next_ret, 'ret_next', num_next),
            ])
            p0_idx, p0_type, p0_nbr = positions_on_helix[0]
            p1_idx, p1_type, p1_nbr = positions_on_helix[1]
            p2_idx, p2_type, p2_nbr = positions_on_helix[2]
            p3_idx, p3_type, p3_nbr = positions_on_helix[3]

            def _build_segment_lr(lo_idx, lo_nbr, hi_idx, hi_nbr):
                scaf[lo_idx] = [lo_nbr, lo_idx, num_i, lo_idx + 1]
                for j in range(lo_idx + 1, hi_idx):
                    scaf[j] = [num_i, j - 1, num_i, j + 1]
                scaf[hi_idx] = [num_i, hi_idx - 1, hi_nbr, hi_idx]

            def _build_segment_rl(hi_idx, hi_nbr, lo_idx, lo_nbr):
                scaf[hi_idx] = [hi_nbr, hi_idx, num_i, hi_idx - 1]
                for j in range(hi_idx - 1, lo_idx, -1):
                    scaf[j] = [num_i, j + 1, num_i, j - 1]
                scaf[lo_idx] = [num_i, lo_idx + 1, lo_nbr, lo_idx]

            if even_i:
                _build_segment_lr(p0_idx, p0_nbr, p1_idx, p1_nbr)
                _build_segment_lr(p2_idx, p2_nbr, p3_idx, p3_nbr)
            else:
                _build_segment_rl(p1_idx, p1_nbr, p0_idx, p0_nbr)
                _build_segment_rl(p3_idx, p3_nbr, p2_idx, p2_nbr)

        scaf_arrays[(r_i, c_i)] = scaf

    # ── Assemble vstrands ────────────────────────────────────────────────
    vstrands = [None] * num_helices
    for pos, num in pos_to_num.items():
        r, c = pos
        stap = [[-1, -1, -1, -1] for _ in range(L)]
        vstrands[num] = make_vstrand(r, c, num, scaf_arrays[pos], stap, L)

    return {
        "name":     name,
        "vstrands": vstrands,
        "_task":    task,
    }


# ─── Layout-specific generators ──────────────────────────────────────────────

def generate_1xN(N: int, row: int = 0, col: int = 0, length: int = 84) -> dict:
    """Generate a 1×N linear chain bundle with full scaffold routing.

    Places N helices in a single row. Requires even N >= 4 (for N=2 use
    generate_2hb). Odd N is geometrically impossible: the honeycomb crossover
    table ordering (High = Low + 1) makes the interior helix constraint
    incompatible with the end helix parity constraint.

    Args:
        N: number of helices (even, >= 4)
        row: starting row
        col: starting column
        length: scaffold length per helix
    """
    if N < 4 or N % 2 != 0:
        raise ValueError("1×N requires even N >= 4 (use generate_2hb for N=2)")

    positions = [(row, col + c) for c in range(N)]
    name = f"1x{N}_r{row}c{col}_L{length}"
    task = (
        f"Create a {N}-helix linear chain with a {length}bp scaffold strand. "
        f"Place the helices at row {row}, columns {col} to {col + N - 1}."
    )
    return _route_and_build(positions, length, name, task)


def generate_2xN(N: int, row: int = 0, col: int = 0, length: int = 84) -> dict:
    """Generate a 2×N grid bundle with full scaffold routing.

    Places helices in a 2-row grid at the given starting position.

    Args:
        N: number of columns (total helices = 2*N)
        row: starting row
        col: starting column
        length: scaffold length per helix (should be multiple of 21)
    """
    num_helices = 2 * N
    positions = []
    for c in range(N):
        positions.append((row, col + c))
    for c in range(N):
        positions.append((row + 1, col + c))

    name = f"2x{N}_r{row}c{col}_L{length}"
    task = (
        f"Create a {num_helices}-helix bundle (2×{N}) with a {length}bp scaffold strand. "
        f"Place the helices starting at row {row}, column {col}."
    )
    return _route_and_build(positions, length, name, task)


# Starting positions for 1×N linear chains — any row works.
ONE_XN_STARTS = [
    (0, 0),   # even parity start
    (0, 1),   # odd parity start
    (1, 0),   # odd parity start
    (2, 0),   # even parity start
]

# Starting positions for 2×N grids — each must have cross-row connections.
# Cross-row connections require odd-parity columns at the grid endpoints.
# Starting at odd-parity positions (r%2 != c%2) ensures both end columns connect.
TWO_XN_STARTS = [
    (0, 1),   # odd parity start
    (1, 0),   # odd parity start
    (2, 1),   # odd parity start
]


# ─── Trajectory extraction (mirrors export_training_data.py) ─────────────────

def extract_trajectory(data: dict, task: str = "") -> dict:
    """Parse a cadnano JSON dict and return the action sequence to recreate it.

    Actions produced:
      1. createHelicesWithStrands   (once per strand type present)
      2. createHalfCrossover        (once per unique half-crossover)
      3. deleteExposedFragments     (once per strand type, after all crossovers)
    """
    vstrands = data.get("vstrands", [])
    if not vstrands:
        raise ValueError("No vstrands in design")

    part_size = len(vstrands[0]["scaf"])
    positions = [
        [vs["row"], vs["col"]]
        for vs in sorted(vstrands, key=lambda v: v["num"])
    ]

    def _has_content(strand_data):
        return any(any(x != -1 for x in s) for s in strand_data)

    has_scaf = any(_has_content(vs["scaf"]) for vs in vstrands)
    has_stap = any(_has_content(vs["stap"]) for vs in vstrands)

    actions = []

    # Step 1: createHelicesWithStrands for each strand type present
    for stype in (["scaffold"] if has_scaf else []) + (["staple"] if has_stap else []):
        actions.append(["createHelicesWithStrands", {
            "positions":   positions,
            "strand_type": stype,
            "length":      part_size - 1,
        }])

    # Step 2: extract deduplicated half-crossovers in position order
    for stype, key in [("scaffold", "scaf"), ("staple", "stap")]:
        if stype == "scaffold" and not has_scaf:
            continue
        if stype == "staple" and not has_stap:
            continue

        seen = set()
        xovers = []
        for vs in vstrands:
            num = vs["num"]
            for i, s in enumerate(vs[key]):
                _, _, next_vh, next_idx = s
                if next_vh in (-1, num):
                    continue
                canon = tuple(sorted([(num, i), (next_vh, next_idx)]))
                if canon in seen:
                    continue
                seen.add(canon)
                xovers.append({
                    "helix1":   num,
                    "idx1":     i,
                    "helix2":   next_vh,
                    "idx2":     next_idx,
                    "sort_idx": min(i, next_idx),
                })

        xovers.sort(key=lambda x: x["sort_idx"])
        for xo in xovers:
            actions.append(["createHalfCrossover", {
                "helix1":     xo["helix1"],
                "idx1":       xo["idx1"],
                "helix2":     xo["helix2"],
                "idx2":       xo["idx2"],
                "strand_type": stype,
            }])
        actions.append(["deleteExposedFragments", {"strand_type": stype}])

    n_xovers   = sum(1 for a in actions if a[0] == "createHalfCrossover")
    helix_count = len(vstrands)
    name       = data.get("name", "generated")
    resolved_task = task or data.get("_task") or (
        f"Create a {helix_count}-helix bundle with {part_size - 1}bp scaffold "
        f"and {n_xovers} crossovers."
    )

    return {
        "source":         name,
        "task":           resolved_task,
        "part_size":      part_size,
        "helix_count":    helix_count,
        "crossover_count": n_xovers,
        "action_count":   len(actions),
        "actions":        actions,
    }


def to_training_example(traj: dict) -> dict:
    """Convert a trajectory dict to an OpenAI messages-format training example."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": traj["task"]},
    ]

    for i, (method_name, params) in enumerate(traj["actions"]):
        call_id = f"call_{i}_{method_name}"
        messages.append({
            "role":    "assistant",
            "content": None,
            "tool_calls": [{
                "type": "function",
                "id":   call_id,
                "function": {
                    "name":      method_name,
                    "arguments": json.dumps(params),
                },
            }],
        })
        messages.append({
            "role":        "tool",
            "tool_call_id": call_id,
            "content":     "Success",
        })

    messages.append({
        "role": "assistant",
        "content": (
            f"Done. Built a {traj['helix_count']}-helix design "
            f"({traj['part_size']}bp part size, "
            f"{traj['crossover_count']} crossovers)."
        ),
    })

    return {
        "messages": messages,
        "metadata": {
            "source":          traj["source"],
            "helix_count":     traj["helix_count"],
            "action_count":    traj["action_count"],
            "crossover_count": traj["crossover_count"],
            "part_size":       traj["part_size"],
        },
    }


# ─── Validation ───────────────────────────────────────────────────────────────

def validate_design(data: dict) -> list[str]:
    """
    Run structural validity checks on a cadnano JSON dict.

    Returns a list of error strings. Empty list = design is valid.

    Checks:
      1. Bounds — every (vh, idx) reference is within the design.
      2. Bidirectionality — if A.next = B then B.prev = A (cadnano enforces this).
      3. Loop closure — following `next` pointers from every visited position
         returns to the start.
      4. Full coverage — every scaffold position that is non-(-1) is reached
         by following the loop (no orphaned or disconnected segments).
    """
    errors = []
    vstrands = data.get("vstrands", [])
    if not vstrands:
        return ["No vstrands found"]

    L = len(vstrands[0]["scaf"])
    vh_nums = {vs["num"] for vs in vstrands}
    vs_map  = {vs["num"]: vs for vs in vstrands}

    for strand_key in ("scaf", "stap"):
        # Collect all non-empty positions
        active = {}  # (vh, idx) -> [prev_vh, prev_idx, next_vh, next_idx]
        for vs in vstrands:
            num = vs["num"]
            for idx, s in enumerate(vs[strand_key]):
                if any(x != -1 for x in s):
                    active[(num, idx)] = s

        if not active:
            continue

        label = "scaffold" if strand_key == "scaf" else "staple"

        # 1. Bounds check
        for (num, idx), s in active.items():
            prev_vh, prev_idx, next_vh, next_idx = s
            for ref_vh, ref_idx, direction in [
                (prev_vh, prev_idx, "prev"),
                (next_vh, next_idx, "next"),
            ]:
                if ref_vh == -1:
                    continue
                if ref_vh not in vh_nums:
                    errors.append(
                        f"{label} H{num}[{idx}].{direction} refs unknown helix {ref_vh}"
                    )
                elif not (0 <= ref_idx < L):
                    errors.append(
                        f"{label} H{num}[{idx}].{direction} idx {ref_idx} out of bounds [0,{L})"
                    )

        # 2. Bidirectionality check
        for (num, idx), s in active.items():
            prev_vh, prev_idx, next_vh, next_idx = s
            # If this position has a next, the target's prev must point back here
            if next_vh != -1 and (next_vh, next_idx) in active:
                target_prev_vh, target_prev_idx = active[(next_vh, next_idx)][:2]
                if (target_prev_vh, target_prev_idx) != (num, idx):
                    errors.append(
                        f"{label} H{num}[{idx}].next = H{next_vh}[{next_idx}] "
                        f"but H{next_vh}[{next_idx}].prev = H{target_prev_vh}[{target_prev_idx}] "
                        f"(expected H{num}[{idx}])"
                    )
            # If this position has a prev, the source's next must point back here
            if prev_vh != -1 and (prev_vh, prev_idx) in active:
                source_next_vh, source_next_idx = active[(prev_vh, prev_idx)][2:]
                if (source_next_vh, source_next_idx) != (num, idx):
                    errors.append(
                        f"{label} H{num}[{idx}].prev = H{prev_vh}[{prev_idx}] "
                        f"but H{prev_vh}[{prev_idx}].next = H{source_next_vh}[{source_next_idx}] "
                        f"(expected H{num}[{idx}])"
                    )

        # 3 & 4. Loop closure + full coverage
        # Find a 5' start: position whose prev points to a different position
        # (i.e. the strand arrives here via a crossover or it is the true 5' end).
        # For a closed loop every position is equivalent — just pick any start.
        start = next(iter(active))
        visited = set()
        cur = start
        while True:
            if cur in visited:
                if cur != start:
                    errors.append(
                        f"{label}: loop rejoins at H{cur[0]}[{cur[1]}] instead of start "
                        f"H{start[0]}[{start[1]}] — strand is not a simple closed loop"
                    )
                break
            visited.add(cur)
            nxt_vh, nxt_idx = active[cur][2], active[cur][3]
            if nxt_vh == -1:
                errors.append(
                    f"{label}: strand terminates at H{cur[0]}[{cur[1]}] (not a closed loop)"
                )
                break
            cur = (nxt_vh, nxt_idx)
            if len(visited) > len(active) + 1:
                errors.append(f"{label}: traversal exceeded {len(active)} steps — infinite loop?")
                break

        unvisited = set(active) - visited
        if unvisited:
            examples = sorted(unvisited)[:3]
            errors.append(
                f"{label}: {len(unvisited)} positions not reached by the loop "
                f"(disconnected segments). Examples: {examples}"
            )

    return errors


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate cadnano training designs and export as JSONL"
    )
    parser.add_argument(
        "--output", default="",
        help="Output JSONL file path (default: stdout)",
    )
    parser.add_argument(
        "--expert", nargs="*", default=[], metavar="JSON",
        help="Expert cadnano JSON files to include as additional examples",
    )
    parser.add_argument(
        "--lengths", nargs="+", type=int, default=DEFAULT_LENGTHS,
        help=f"Scaffold lengths to generate (default: {DEFAULT_LENGTHS})",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Print generation statistics and exit without writing JSONL",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Run structural validity checks on every generated design",
    )
    parser.add_argument(
        "--save-json", metavar="DIR", default="",
        help="Save each generated design as an individual cadnano JSON file in DIR "
             "(useful for loading in the cadnano GUI to visually verify)",
    )
    args = parser.parse_args()

    examples = []
    raw_designs = []   # (design_dict, traj_dict) pairs for validation / JSON export

    # ── 2-Helix bundles ───────────────────────────────────────────────────────
    print(
        f"Generating 2HB designs: {len(TWO_HB_STARTS)} positions × "
        f"{len(args.lengths)} lengths = "
        f"{len(TWO_HB_STARTS) * len(args.lengths)} examples …",
        file=sys.stderr,
    )
    for row, col in TWO_HB_STARTS:
        for length in args.lengths:
            design = generate_2hb(row=row, col=col, length=length)
            traj   = extract_trajectory(design, task=design["_task"])
            examples.append(to_training_example(traj))
            raw_designs.append((design, traj))

    # ── 1×N linear chains (4HB, 6HB, 8HB) ──────────────────────────────────
    linear_sizes = [4, 6, 8]   # N helices in a row (must be even)
    linear_count = len(ONE_XN_STARTS) * len(linear_sizes) * len(args.lengths)
    print(
        f"Generating 1×N designs: {len(ONE_XN_STARTS)} positions × "
        f"{len(linear_sizes)} sizes × {len(args.lengths)} lengths = "
        f"{linear_count} examples …",
        file=sys.stderr,
    )
    for row, col in ONE_XN_STARTS:
        for N in linear_sizes:
            for length in args.lengths:
                try:
                    design = generate_1xN(N=N, row=row, col=col, length=length)
                    traj = extract_trajectory(design, task=design["_task"])
                    examples.append(to_training_example(traj))
                    raw_designs.append((design, traj))
                except (ValueError, AssertionError) as e:
                    print(
                        f"Skip 1×{N} at ({row},{col}) L={length}: {e}",
                        file=sys.stderr,
                    )

    # ── 2×N bundles (4HB, 6HB, 8HB, 10HB) ──────────────────────────────────
    grid_sizes = [2, 3, 4, 5]   # N columns → 4, 6, 8, 10 helices
    grid_count = len(TWO_XN_STARTS) * len(grid_sizes) * len(args.lengths)
    print(
        f"Generating 2×N designs: {len(TWO_XN_STARTS)} positions × "
        f"{len(grid_sizes)} sizes × {len(args.lengths)} lengths = "
        f"{grid_count} examples …",
        file=sys.stderr,
    )
    for row, col in TWO_XN_STARTS:
        for N in grid_sizes:
            for length in args.lengths:
                try:
                    design = generate_2xN(N=N, row=row, col=col, length=length)
                    traj = extract_trajectory(design, task=design["_task"])
                    examples.append(to_training_example(traj))
                    raw_designs.append((design, traj))
                except (ValueError, AssertionError) as e:
                    print(
                        f"Skip 2×{N} at ({row},{col}) L={length}: {e}",
                        file=sys.stderr,
                    )

    # ── Expert JSON files ─────────────────────────────────────────────────────
    for json_path in (args.expert or []):
        json_path = os.path.expanduser(json_path)
        if not os.path.exists(json_path):
            print(f"Warning: {json_path} not found, skipping", file=sys.stderr)
            continue
        with open(json_path) as f:
            data = json.load(f)
        n_helices = len(data.get("vstrands", []))
        task = (
            f"Create a {n_helices}-helix DNA nanostructure with scaffold "
            f"routing through all helices."
        )
        try:
            traj = extract_trajectory(data, task=task)
            examples.append(to_training_example(traj))
            raw_designs.append((data, traj))
            print(
                f"Loaded expert: {os.path.basename(json_path)} "
                f"({traj['action_count']} actions, "
                f"{traj['crossover_count']} crossovers)",
                file=sys.stderr,
            )
        except Exception as e:
            print(f"Error processing {json_path}: {e}", file=sys.stderr)

    # ── Statistics ────────────────────────────────────────────────────────────
    total_actions   = sum(e["metadata"]["action_count"]    for e in examples)
    total_xovers    = sum(e["metadata"]["crossover_count"] for e in examples)
    helix_counts: dict = {}
    for e in examples:
        n = e["metadata"]["helix_count"]
        helix_counts[n] = helix_counts.get(n, 0) + 1

    print(f"\nTotal examples : {len(examples)}", file=sys.stderr)
    print(f"Total actions  : {total_actions}",   file=sys.stderr)
    print(f"Total crossovers: {total_xovers}",   file=sys.stderr)
    print("Breakdown by helix count:",            file=sys.stderr)
    for n in sorted(helix_counts):
        print(f"  {n}-helix: {helix_counts[n]} examples", file=sys.stderr)

    # ── Validate ─────────────────────────────────────────────────────────────
    if args.validate:
        n_ok = n_fail = 0
        for design, traj in raw_designs:
            errs = validate_design(design)
            name = design.get("name", traj["source"])
            if errs:
                n_fail += 1
                print(f"FAIL  {name}", file=sys.stderr)
                for e in errs:
                    print(f"      {e}", file=sys.stderr)
            else:
                n_ok += 1
                print(f"OK    {name}", file=sys.stderr)
        print(f"\n{n_ok} passed, {n_fail} failed", file=sys.stderr)
        if n_fail:
            sys.exit(1)

    # ── Save individual JSON files for visual inspection in cadnano ───────────
    if args.save_json:
        save_dir = os.path.expanduser(args.save_json)
        os.makedirs(save_dir, exist_ok=True)
        for design, _ in raw_designs:
            name = design.get("name", "design")
            # Strip internal _task key before saving — cadnano doesn't expect it
            out = {k: v for k, v in design.items() if not k.startswith("_")}
            path = os.path.join(save_dir, f"{name}.json")
            with open(path, "w") as f:
                json.dump(out, f, indent=2)
        print(f"Saved {len(raw_designs)} JSON files to {save_dir}", file=sys.stderr)
        print("Open any of them in cadnano (File → Open) to visually verify.", file=sys.stderr)

    if args.stats:
        return

    # ── Write JSONL ───────────────────────────────────────────────────────────
    if args.output:
        output_path = os.path.expanduser(args.output)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w") as f:
            for ex in examples:
                f.write(json.dumps(ex) + "\n")
        print(f"\nWrote {len(examples)} examples → {output_path}", file=sys.stderr)
    else:
        for ex in examples:
            print(json.dumps(ex))


if __name__ == "__main__":
    main()
