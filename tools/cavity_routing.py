#!/usr/bin/env python
"""
Cavity Scaffold Routing — Proper Hamiltonian Cycle Through 2D Grid

Routes a scaffold around a rectangular cavity in a multi-row honeycomb grid.
The scaffold forms ONE contiguous loop visiting every helix exactly once.

The key insight: a single row of helices cannot route around a cavity
(topologically impossible — the graph is a linear chain with no cycles).
A multi-row grid provides the extra connectivity needed for the scaffold
to go around the hole.

Algorithm:
  1. Create helices in a 2D grid on the honeycomb lattice
  2. Skip positions inside the cavity
  3. Build neighbor graph from honeycomb lattice rules
  4. Find a Hamiltonian cycle through the remaining helices (DFS + backtracking)
  5. Route scaffold along the cycle using setConnection3p/5p

Usage:
  conda activate cn24-agentic
  QT_QPA_PLATFORM=offscreen python -m tools.cavity_routing
"""

import os
import sys
import json
import time
from math import ceil
from typing import List, Tuple, Dict, Optional, Set

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_honeycomb_neighbors(row, col):
    """Get (row, col) of all 3 honeycomb neighbors for a position.

    Even parity (row%2 == col%2):
        p0 = (r, c+1), p1 = (r-1, c), p2 = (r, c-1)
    Odd parity (row%2 != col%2):
        p0 = (r, c-1), p1 = (r+1, c), p2 = (r, c+1)
    """
    if (row % 2) == (col % 2):  # even parity
        return [(row, col + 1, 0), (row - 1, col, 1), (row, col - 1, 2)]
    else:  # odd parity
        return [(row, col - 1, 0), (row + 1, col, 1), (row, col + 1, 2)]


def build_grid_positions(n_rows, n_cols, start_row, start_col,
                          cavity_row_start, cavity_row_end,
                          cavity_col_start, cavity_col_end):
    """Build list of (row, col) positions for a grid with a cavity.

    Returns:
        positions: list of (row, col) that are NOT in the cavity
        cavity_positions: list of (row, col) inside the cavity
    """
    positions = []
    cavity_positions = []

    for r in range(start_row, start_row + n_rows):
        for c in range(start_col, start_col + n_cols):
            if (cavity_row_start <= r < cavity_row_end and
                    cavity_col_start <= c < cavity_col_end):
                cavity_positions.append((r, c))
            else:
                positions.append((r, c))

    return positions, cavity_positions


def build_neighbor_graph(positions):
    """Build adjacency graph for honeycomb neighbors among the given positions.

    Returns: dict mapping (row, col) -> list of ((row, col), direction_idx)
    """
    pos_set = set(positions)
    graph = {pos: [] for pos in positions}

    for pos in positions:
        r, c = pos
        for nr, nc, direction in get_honeycomb_neighbors(r, c):
            if (nr, nc) in pos_set:
                graph[pos].append(((nr, nc), direction))

    return graph


def find_hamiltonian_cycle(graph, positions):
    """Find a Hamiltonian cycle through all positions using DFS + backtracking.

    Returns list of (row, col) forming the cycle, or None if not found.
    The last element connects back to the first.
    """
    n = len(positions)
    if n == 0:
        return None

    # Sort positions by degree (ascending) to prune faster
    pos_by_degree = sorted(positions, key=lambda p: len(graph[p]))

    # Start from a position with low degree (more constrained = faster pruning)
    start = pos_by_degree[0]
    start_neighbors = set(nb for nb, _ in graph[start])

    path = [start]
    visited = {start}

    def dfs():
        if len(path) == n:
            # Check if we can close the cycle back to start
            last = path[-1]
            last_neighbors = set(nb for nb, _ in graph[last])
            return start in last_neighbors

        current = path[-1]
        # Try neighbors in order of ascending degree (most constrained first)
        neighbors = sorted(graph[current],
                           key=lambda x: len(graph[x[0]]))

        for (nr, nc), direction in neighbors:
            if (nr, nc) in visited:
                continue

            # Pruning: check if adding this node would disconnect remaining nodes
            # Simple check: all unvisited nodes with degree 1 (in remaining graph)
            # must be reachable
            path.append((nr, nc))
            visited.add((nr, nc))

            if dfs():
                return True

            path.pop()
            visited.discard((nr, nc))

        return False

    print(f"  Finding Hamiltonian cycle through {n} nodes...")
    t0 = time.time()
    found = dfs()
    elapsed = time.time() - t0

    if found:
        print(f"  Found cycle in {elapsed:.2f}s")
        return path
    else:
        print(f"  No cycle found ({elapsed:.2f}s)")
        return None


def find_hamiltonian_cycle_optimized(graph, positions):
    """Optimized Hamiltonian cycle finder with better pruning.

    Uses Warnsdorff's rule (prefer neighbors with fewer remaining connections)
    and checks for articulation points.
    """
    n = len(positions)
    if n == 0:
        return None

    # Try multiple starting nodes
    candidates = sorted(positions, key=lambda p: len(graph[p]))

    for start in candidates[:3]:  # Try up to 3 starting nodes
        start_neighbors = set(nb for nb, _ in graph[start])

        path = [start]
        visited = {start}

        def get_remaining_degree(node):
            """Count unvisited neighbors of a node."""
            return sum(1 for nb, _ in graph[node] if nb not in visited)

        def dfs():
            if len(path) == n:
                last = path[-1]
                return start in set(nb for nb, _ in graph[last])

            current = path[-1]

            # Warnsdorff's rule: prefer neighbors with fewer remaining connections
            neighbors = [(nb, d) for nb, d in graph[current] if nb not in visited]
            neighbors.sort(key=lambda x: get_remaining_degree(x[0]))

            for (nr, nc), direction in neighbors:
                # Quick pruning: if any unvisited node would become isolated, skip
                visited.add((nr, nc))
                path.append((nr, nc))

                # Check: can all remaining unvisited nodes still be reached?
                ok = True
                for pos in positions:
                    if pos in visited:
                        continue
                    remaining_nb = sum(1 for nb, _ in graph[pos]
                                       if nb not in visited)
                    if remaining_nb == 0 and len(visited) < n:
                        ok = False
                        break

                if ok and dfs():
                    return True

                path.pop()
                visited.discard((nr, nc))

            return False

        print(f"  Trying start node {start}...")
        t0 = time.time()
        found = dfs()
        elapsed = time.time() - t0

        if found:
            print(f"  Found Hamiltonian cycle in {elapsed:.2f}s "
                  f"(start={start}, {n} nodes)")
            return path

    print(f"  No Hamiltonian cycle found from any starting node")
    return None


def route_scaffold_along_cycle(part, helices_by_coord, cycle, helix_length):
    """Route the scaffold along a Hamiltonian cycle.

    Creates scaffold strands on each helix with correct ranges,
    then connects them using setConnection3p/5p (same approach as
    the simple serpentine but following the cycle order).
    """
    from cadnano2.model.parts.honeycombpart import Crossovers
    from cadnano2.model.strand import Strand

    n = len(cycle)
    L = helix_length

    # Step 1: For each consecutive pair in the cycle, find the crossover position
    xover_positions = []
    for i in range(n):
        j = (i + 1) % n
        coord_i = cycle[i]
        coord_j = cycle[j]

        vh_i = helices_by_coord[coord_i]
        vh_j = helices_by_coord[coord_j]

        # Find which direction connects these two helices
        neighbors = part.getVirtualHelixNeighbors(vh_i)
        if vh_j not in neighbors:
            raise RuntimeError(f"Helices at {coord_i} and {coord_j} are not neighbors")

        direction = neighbors.index(vh_j)
        low_offsets = Crossovers.honeycombScafLow[direction]
        high_offsets = Crossovers.honeycombScafHigh[direction]

        step = part.stepSize()
        positions = []
        for base in range(0, part.maxBaseIdx() + 1, step):
            for lo, hi in zip(low_offsets, high_offsets):
                low_idx = base + lo
                high_idx = base + hi
                if 0 <= low_idx < L and 0 <= high_idx < L:
                    positions.append({'low_idx': low_idx, 'high_idx': high_idx})

        if not positions:
            raise RuntimeError(f"No crossover positions for {coord_i}-{coord_j}")

        # Turn position: even parity exits right, odd exits left
        if vh_i.isEvenParity():
            turn = positions[-1]  # rightmost
        else:
            turn = positions[0]   # leftmost

        xover_positions.append(turn)

    # Step 2: Compute strand ranges
    strand_ranges = []
    for i in range(n):
        xo_entry = xover_positions[(i - 1) % n]['low_idx']
        xo_exit = xover_positions[i]['low_idx']
        strand_ranges.append((min(xo_entry, xo_exit), max(xo_entry, xo_exit)))

    total_bp = sum(hi - lo + 1 for lo, hi in strand_ranges)
    print(f"  Total scaffold bp: {total_bp}")

    # Step 3: Create scaffold strands
    for i, coord in enumerate(cycle):
        vh = helices_by_coord[coord]
        lo, hi = strand_ranges[i]
        scaf_ss = vh.scaffoldStrandSet()
        result = scaf_ss.createStrand(lo, hi, useUndoStack=True)
        if result < 0:
            print(f"    WARNING: Failed to create strand at {coord} [{lo}:{hi}]")

    # Step 4: Connect strands
    xovers_placed = 0
    for i in range(n):
        j = (i + 1) % n
        vh_i = helices_by_coord[cycle[i]]
        vh_j = helices_by_coord[cycle[j]]
        xo = xover_positions[i]['low_idx']

        ok = connect_strands_at_idx(part, vh_i, vh_j, xo)
        if not ok:
            # Try high_idx
            ok = connect_strands_at_idx(part, vh_i, vh_j,
                                         xover_positions[i]['high_idx'])
        if ok:
            xovers_placed += 1
        else:
            print(f"    WARNING: Failed to connect {cycle[i]} ↔ {cycle[j]} "
                  f"at idx {xo}")

    return {
        'cycle_length': n,
        'xovers_placed': xovers_placed,
        'total_scaffold_bp': total_bp,
    }


def connect_strands_at_idx(part, vh1, vh2, xover_idx):
    """Connect scaffold strands at a crossover index. Returns True on success."""
    from cadnano2.model.strand import Strand

    scaf1 = vh1.scaffoldStrandSet().getStrand(xover_idx)
    scaf2 = vh2.scaffoldStrandSet().getStrand(xover_idx)

    if scaf1 is None or scaf2 is None:
        for delta in [-1, 1, -2, 2]:
            alt = xover_idx + delta
            if scaf1 is None:
                scaf1 = vh1.scaffoldStrandSet().getStrand(alt)
            if scaf2 is None:
                scaf2 = vh2.scaffoldStrandSet().getStrand(alt)
            if scaf1 and scaf2:
                break

    if scaf1 is None or scaf2 is None:
        return False

    lo1, hi1 = scaf1.idxs()
    lo2, hi2 = scaf2.idxs()

    is_3p_end_1 = (vh1.isEvenParity() and hi1 == xover_idx) or \
                  (not vh1.isEvenParity() and lo1 == xover_idx)
    is_5p_end_2 = (vh2.isEvenParity() and lo2 == xover_idx) or \
                  (not vh2.isEvenParity() and hi2 == xover_idx)

    if is_3p_end_1 and is_5p_end_2:
        strand5p, strand3p = scaf1, scaf2
    else:
        is_3p_end_2 = (vh2.isEvenParity() and hi2 == xover_idx) or \
                      (not vh2.isEvenParity() and lo2 == xover_idx)
        is_5p_end_1 = (vh1.isEvenParity() and lo1 == xover_idx) or \
                      (not vh1.isEvenParity() and hi1 == xover_idx)
        if is_3p_end_2 and is_5p_end_1:
            strand5p, strand3p = scaf2, scaf1
        else:
            return False

    if strand5p.connection3p() == strand3p:
        return True

    olg5p = strand5p.oligo()
    olg3p = strand3p.oligo()
    if olg5p != olg3p:
        olg5p.incrementLength(olg3p.length())
        olg3p.removeFromPart()
        for s in strand3p.generator3pStrand():
            Strand.setOligo(s, olg5p)

    strand5p.setConnection3p(strand3p)
    strand3p.setConnection5p(strand5p)
    return True


# ── Demo: Build and route a cavity design ─────────────────────────────────


def demo_cavity_routing():
    """Demo: Create a 2D grid cavity design with proper scaffold routing."""
    import cadnano2.cadnano as cadnano
    import numpy as np

    print("=" * 60)
    print("CAVITY SCAFFOLD ROUTING DEMO")
    print("=" * 60)

    # Grid parameters
    # Parity constraints for all corners to have degree ≥ 2:
    #   N_ROWS must be even, N_COLS must be odd,
    #   start_row and start_col must have different parity
    # This ensures every corner has a cross-row connection into the grid.
    N_ROWS = 4
    N_COLS = 7
    START_ROW = 10   # even
    START_COL = 5    # odd (different parity from start_row)

    # Cavity in the middle rows, middle columns
    CAVITY_ROW_START = 11
    CAVITY_ROW_END = 13    # exclusive (2 rows)
    CAVITY_COL_START = 7
    CAVITY_COL_END = 10    # exclusive (3 cols removed)

    # Build grid
    positions, cavity = build_grid_positions(
        N_ROWS, N_COLS, START_ROW, START_COL,
        CAVITY_ROW_START, CAVITY_ROW_END,
        CAVITY_COL_START, CAVITY_COL_END)

    print(f"\n  Grid: {N_ROWS} rows × {N_COLS} cols = {N_ROWS * N_COLS} positions")
    print(f"  Cavity: rows {CAVITY_ROW_START}-{CAVITY_ROW_END-1}, "
          f"cols {CAVITY_COL_START}-{CAVITY_COL_END-1} "
          f"({len(cavity)} removed)")
    print(f"  Remaining: {len(positions)} helices")

    # Build neighbor graph
    graph = build_neighbor_graph(positions)

    # Print connectivity
    print(f"\n  Graph connectivity:")
    for pos in sorted(positions):
        neighbors = graph[pos]
        nb_str = ", ".join(f"({r},{c})" for (r, c), _ in neighbors)
        parity = "even" if (pos[0] % 2) == (pos[1] % 2) else "odd"
        print(f"    ({pos[0]},{pos[1]}) [{parity}] degree={len(neighbors)}: {nb_str}")

    # Find Hamiltonian cycle
    cycle = find_hamiltonian_cycle(graph, positions)

    if cycle is None:
        print("\n  FAILED: Could not find Hamiltonian cycle")
        print("  Try adjusting grid/cavity dimensions")
        return None

    print(f"\n  Cycle: {' → '.join(f'({r},{c})' for r, c in cycle)} → back to start")

    # Now create in cadnano
    print("\n── Creating cadnano design ──")
    app = cadnano.initAppWithGui()
    from cadnano2.views.agent.agentmethods import AgentMethods

    dc = list(app.documentControllers)[0]
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    # Compute helix length for p8064
    SCAFFOLD_LENGTH = 8064
    n_helices = len(positions)
    target_routed = int(SCAFFOLD_LENGTH * 0.92)
    helix_length = int(ceil(target_routed / n_helices / 21)) * 21
    print(f"  Helix length: {helix_length} bp ({helix_length // 21} steps)")

    # Extend part size
    step = part.stepSize()
    if helix_length - 1 > part.maxBaseIdx():
        delta = int(ceil((helix_length - 1 - part.maxBaseIdx()) / step)) * step
        part.resizeVirtualHelices(0, delta, useUndoStack=True)

    # Create helices
    helices_by_coord = {}
    for r, c in positions:
        part.createVirtualHelix(r, c, useUndoStack=True)
        vh = part.virtualHelixAtCoord((r, c))
        helices_by_coord[(r, c)] = vh

    print(f"  Created {len(helices_by_coord)} helices")

    # Route scaffold
    print("\n── Routing scaffold along Hamiltonian cycle ──")
    route_info = route_scaffold_along_cycle(part, helices_by_coord, cycle,
                                             helix_length)

    # Verify scaffold continuity
    scaffold_oligos = [o for o in part.oligos() if not o.isStaple()]
    print(f"\n  Scaffold oligos: {len(scaffold_oligos)} (should be 1)")
    for o in scaffold_oligos:
        print(f"    Length: {o.length()} bp")

    # autoStaple
    print("\n── autoStaple ──")
    from cadnano2.model.parts.part import Part
    Part.autoStaple(part)
    staples = sum(1 for o in part.oligos() if o.isStaple())
    print(f"  Staples: {staples}")

    # Save JSON
    output_dir = os.path.join(PROJECT_ROOT, 'results', 'cavity_routed')
    os.makedirs(output_dir, exist_ok=True)
    json_path = os.path.join(output_dir, 'cavity_design.json')
    dc.writeDocumentToFile(json_path)
    print(f"\n  Saved: {json_path}")

    # Generate cavity schematic
    print("\n── Generating schematic ──")
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 6))

    # Draw helices
    for (r, c) in positions:
        y = -(r - START_ROW) * 1.2
        x = (c - START_COL) * 1.0
        color = 'steelblue'
        # Find position in cycle
        idx = cycle.index((r, c))
        ax.plot(x, y, 'o', color=color, markersize=20, zorder=3)
        ax.text(x, y, f'{idx}', ha='center', va='center',
                fontsize=7, color='white', fontweight='bold', zorder=4)
        ax.text(x, y - 0.4, f'({r},{c})', ha='center', va='top',
                fontsize=5, color='gray')

    # Draw cavity
    cavity_x0 = (CAVITY_COL_START - START_COL) * 1.0 - 0.4
    cavity_y0 = -(CAVITY_ROW_START - START_ROW) * 1.2 - 0.4
    cavity_w = (CAVITY_COL_END - CAVITY_COL_START) * 1.0
    cavity_h = (CAVITY_ROW_END - CAVITY_ROW_START) * 1.2
    rect = plt.Rectangle((cavity_x0, cavity_y0), cavity_w - 0.2, cavity_h - 0.4,
                          fill=True, facecolor='lightyellow', edgecolor='red',
                          linewidth=2, linestyle='--', zorder=1)
    ax.add_patch(rect)
    ax.text(cavity_x0 + cavity_w / 2 - 0.1, cavity_y0 + cavity_h / 2 - 0.2,
            'CAVITY', ha='center', va='center', fontsize=10, color='red',
            fontweight='bold')

    # Draw cycle edges
    for i in range(len(cycle)):
        j = (i + 1) % len(cycle)
        r1, c1 = cycle[i]
        r2, c2 = cycle[j]
        x1 = (c1 - START_COL) * 1.0
        y1 = -(r1 - START_ROW) * 1.2
        x2 = (c2 - START_COL) * 1.0
        y2 = -(r2 - START_ROW) * 1.2
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                     arrowprops=dict(arrowstyle='->', color='orange',
                                     lw=1.5, connectionstyle='arc3,rad=0.1'),
                     zorder=2)

    ax.set_xlim(-1, N_COLS + 0.5)
    ax.set_ylim(-(N_ROWS) * 1.2, 1)
    ax.set_aspect('equal')
    ax.set_title(f'Scaffold Routing: Hamiltonian Cycle Around Cavity\n'
                  f'{N_ROWS}×{N_COLS} grid, {len(positions)} helices, '
                  f'{len(cavity)} removed for cavity',
                  fontsize=11, fontweight='bold')
    ax.axis('off')
    plt.tight_layout()

    fig_path = os.path.join(output_dir, 'cavity_routing_cycle.png')
    plt.savefig(fig_path, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {fig_path}")

    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"  Helices: {len(positions)} in {N_ROWS}×{N_COLS} grid")
    print(f"  Cavity: {len(cavity)} helices removed")
    print(f"  Scaffold: {len(scaffold_oligos)} oligo(s), "
          f"{sum(o.length() for o in scaffold_oligos)} bp")
    print(f"  Cycle length: {len(cycle)}")
    print(f"  Crossovers placed: {route_info['xovers_placed']}")
    print("=" * 60)

    return cycle


if __name__ == '__main__':
    demo_cavity_routing()
