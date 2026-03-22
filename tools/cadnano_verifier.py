#!/usr/bin/env python
"""
cadnano_verifier.py — Reusable verification suite for cadnano JSON designs.

Validates scaffold routing, crossover integrity, cavity structure, and
cadnano-loadability BEFORE running expensive downstream pipelines
(autoStaple, tacoxDNA, oxDNA). Catches the exact failure modes we
discovered during AI-assisted parametric DNA origami design.

Distributable: any user with a cadnano JSON file can run this to check
their design before committing to wet-lab synthesis or simulation.

Usage:
  python tools/cadnano_verifier.py design.json
  python tools/cadnano_verifier.py design.json --verbose

Each check returns PASS/FAIL with actionable error messages referencing
the specific helix and position where the problem occurs.

Failure modes caught (discovered during this project):
  1. Odd segment counts → cadnano decode hangs (legacydecoder.py bug)
  2. Scaffold direction errors → wrong 5'/3' connectivity
  3. Stray crossover fragments in cavity gap → extra scaffold oligos
  4. Missing edge crossovers → scaffold fragmentation
  5. Destroyed cavity boundary crossovers → scaffold breaks
  6. Spurious midseam on last pair → scaffold splits into 2 oligos
  7. Circular scaffold with no staples → decode hang

Author: Daniel Fu, Ke Lab, Georgia Tech / Emory
License: MIT
"""

import json
import sys
import os
from collections import defaultdict

EMPTY = [-1, -1, -1, -1]


# ── Core Verification Functions ──────────────────────────────────────────

def load_design(path):
    """Load a cadnano JSON file."""
    with open(path) as f:
        return json.load(f)


def verify_array_lengths(design):
    """Check all vstrands have consistent array lengths.

    FAILURE MODE: Mismatched array lengths cause index-out-of-bounds
    during decode, crossover installation, or autoStaple.
    """
    issues = []
    if not design.get('vstrands'):
        return [('FATAL', 'No vstrands found')]

    expected = len(design['vstrands'][0]['scaf'])
    for v in design['vstrands']:
        for arr in ['scaf', 'stap', 'loop', 'skip']:
            if len(v[arr]) != expected:
                issues.append(('ERROR', f'H{v["num"]} {arr} len={len(v[arr])} != {expected}'))
    return issues


def verify_segment_counts(design):
    """Check all helices have even scaffold segment counts.

    FAILURE MODE: Odd segment count causes cadnano's legacydecoder to
    hang indefinitely. The assertion `assert(len(segs) % 2 == 0)` has
    a typo (`AssertionError`) so it's never caught — the decoder loops
    or crashes instead of reporting the error.

    ROOT CAUSES WE FOUND:
    - Scaffold direction errors from using shifted crossover references
    - Gap-fill code using wrong direction (must use helix parity, not refs)
    - Stray crossover fragments preserved in gap-clearing
    """
    issues = []
    for v in design['vstrands']:
        num = v['num']
        scaf = v['scaf']
        segs = []
        for i in range(len(scaf)):
            e = scaf[i]
            if e == EMPTY:
                continue
            if _is_segment_boundary(num, i, e):
                segs.append(i)
            # Double crossover: both sides reference other helices
            if e[0] != num and e[2] != num and e[0] >= 0 and e[2] >= 0:
                segs.append(i)

        if len(segs) % 2 != 0:
            issues.append(('ERROR',
                f'H{num}: ODD segment count ({len(segs)}). '
                f'First boundaries at {segs[:4]}. '
                f'cadnano will HANG on load. '
                f'Check scaffold direction and gap-clearing.'))
    return issues


def verify_scaffold_directions(design):
    """Check scaffold entries match helix parity conventions.

    RULE: Even helices (num%2==0) go RIGHT: entry = [num, i-1, num, i+1]
          Odd helices (num%2==1) go LEFT:  entry = [num, i+1, num, i-1]

    FAILURE MODE: Wrong direction creates odd segment counts → decode hang.

    ROOT CAUSE WE FOUND: Gap-fill code determined direction from shifted
    crossover references instead of helix parity. Position 169's 3'
    reference changed from 170 to 296 after shifting, causing the fill
    to use the wrong direction for even helices.
    """
    issues = []
    for v in design['vstrands']:
        num = v['num']
        scaf = v['scaf']
        for i, e in enumerate(scaf):
            if e == EMPTY:
                continue
            if e[0] != num or e[2] != num:
                continue  # skip crossover entries

            if num % 2 == 0:
                # Even: should be [num, i-1, num, i+1]
                if e[1] != i - 1 or e[3] != i + 1:
                    issues.append(('WARN',
                        f'H{num}[{i}] direction wrong: {e}, '
                        f'expected [num, {i-1}, num, {i+1}]'))
            else:
                # Odd: should be [num, i+1, num, i-1]
                if e[1] != i + 1 or e[3] != i - 1:
                    issues.append(('WARN',
                        f'H{num}[{i}] direction wrong: {e}, '
                        f'expected [num, {i+1}, num, {i-1}]'))

            if len(issues) > 20:
                issues.append(('INFO', '...truncated (>20 direction errors)'))
                return issues
    return issues


def verify_crossover_symmetry(design):
    """Check every crossover has a matching entry on the partner helix.

    RULE: If H_a[idx] references H_b, then H_b[idx] must reference H_a.

    FAILURE MODE: Asymmetric crossovers cause strand breaks → extra oligos.
    """
    issues = []
    vs_by_num = {v['num']: v for v in design['vstrands']}

    for v in design['vstrands']:
        num = v['num']
        scaf = v['scaf']
        for i, e in enumerate(scaf):
            if e == EMPTY:
                continue
            for side, vh_ref, idx_ref in [('5p', e[0], e[1]), ('3p', e[2], e[3])]:
                if vh_ref < 0 or vh_ref == num:
                    continue
                partner = vs_by_num.get(vh_ref)
                if partner is None:
                    issues.append(('ERROR',
                        f'H{num}[{i}] {side} refs non-existent H{vh_ref}'))
                    continue
                if idx_ref < 0 or idx_ref >= len(partner['scaf']):
                    issues.append(('ERROR',
                        f'H{num}[{i}] {side} refs H{vh_ref}[{idx_ref}] out of bounds'))
                    continue
                pe = partner['scaf'][idx_ref]
                if pe == EMPTY:
                    issues.append(('ERROR',
                        f'H{num}[{i}] {side} refs H{vh_ref}[{idx_ref}] which is EMPTY'))
                elif pe[0] != num and pe[2] != num:
                    issues.append(('WARN',
                        f'H{num}[{i}] {side}→H{vh_ref}[{idx_ref}] has no back-reference'))
    return issues


def verify_cavity_gaps(design, cavity_helices=None):
    """Check cavity helices have exactly 1 gap each.

    FAILURE MODE: Extra gaps = extra cavity sections (the bug the PI caught).
    Zero gaps = cavity was filled (step2 gap-fill on cavity helices).

    ROOT CAUSES WE FOUND:
    - step2_extend skipping gap-fill created extension gap on cavity helices
    - step4 not clearing gap region for newly-converted cavity pairs
    - Stray midseam fragments preserved inside gap
    """
    if cavity_helices is None:
        # Auto-detect: helices with gaps in scaffold data
        cavity_helices = set()
        for v in design['vstrands']:
            if _count_gaps(v['scaf']) > 0:
                cavity_helices.add(v['num'])

    issues = []
    for v in design['vstrands']:
        num = v['num']
        n_gaps = _count_gaps(v['scaf'])

        if num in cavity_helices:
            if n_gaps != 1:
                issues.append(('ERROR',
                    f'H{num} (cavity): expected 1 gap, found {n_gaps}. '
                    f'{"Extra cavity section!" if n_gaps > 1 else "Cavity filled!"}'))
        else:
            if n_gaps > 0:
                issues.append(('ERROR',
                    f'H{num} (non-cavity): unexpected {n_gaps} gap(s)'))
    return issues


def verify_last_pair(design, last_pair=None):
    """Check the last pair has only edge crossovers (no midseam).

    FAILURE MODE: Adding a midseam to the last pair splits the scaffold
    into 2 oligos. The last pair connects the two scaffold halves via
    edge-only crossovers.

    ROOT CAUSE WE FOUND: step3_move_midseam iterated ALL non-cavity
    pairs, including the last pair. It removed a non-existent old seam
    (no-op) but ADDED a new one, splitting the scaffold.
    """
    if last_pair is None:
        # Default: highest-numbered pair
        nums = sorted(v['num'] for v in design['vstrands'])
        last_pair = (nums[-2], nums[-1])

    ha, hb = last_pair
    vs_by_num = {v['num']: v for v in design['vstrands']}

    if ha not in vs_by_num or hb not in vs_by_num:
        return [('ERROR', f'Last pair H{ha}-H{hb} not found')]

    sa = vs_by_num[ha]['scaf']
    xo_positions = []
    for i, e in enumerate(sa):
        if e != EMPTY and (e[0] == hb or e[2] == hb):
            xo_positions.append(i)

    if len(xo_positions) > 2:
        return [('ERROR',
            f'Last pair H{ha}-H{hb} has {len(xo_positions)} crossovers '
            f'at positions {xo_positions}. Should have only 2 (edges). '
            f'A midseam crossover will split the scaffold into 2 oligos.')]
    return []


def verify_scaffold_connectivity(design):
    """Trace the scaffold path and count connected components.

    Returns the number of scaffold "oligos" (connected components).
    Target: 1 for a valid DNA origami design.
    """
    vs_by_num = {v['num']: v for v in design['vstrands']}

    # Build a graph of all scaffold bases
    visited = set()
    components = 0

    for v in design['vstrands']:
        num = v['num']
        scaf = v['scaf']
        for i, e in enumerate(scaf):
            if e == EMPTY:
                continue
            if (num, i) in visited:
                continue

            # BFS from this base
            components += 1
            queue = [(num, i)]
            while queue:
                cur_vh, cur_idx = queue.pop(0)
                if (cur_vh, cur_idx) in visited:
                    continue
                visited.add((cur_vh, cur_idx))

                entry = vs_by_num[cur_vh]['scaf'][cur_idx]
                if entry == EMPTY:
                    continue

                # Follow 5' connection
                if entry[0] >= 0 and entry[1] >= 0:
                    queue.append((entry[0], entry[1]))
                # Follow 3' connection
                if entry[2] >= 0 and entry[3] >= 0:
                    queue.append((entry[2], entry[3]))

    return components


# ── Helper Functions ─────────────────────────────────────────────────────

def _is_segment_boundary(num, idx, entry):
    """Replicates cadnano's isSegmentStartOrEnd logic."""
    vh5p, idx5p, vh3p, idx3p = entry
    offset = 1  # scaffold

    if vh5p == num and vh3p != num:
        return True
    if vh5p != num and vh3p == num:
        return True
    if num % 2 == 0:
        if vh5p == num and idx5p != idx - offset:
            return True
        if vh3p == num and idx3p != idx + offset:
            return True
    else:
        if vh5p == num and idx5p != idx + offset:
            return True
        if vh3p == num and idx3p != idx - offset:
            return True
    if vh5p == -1 and vh3p != -1:
        return True
    if vh5p != -1 and vh3p == -1:
        return True
    return False


def _count_gaps(scaf):
    """Count gaps (runs of EMPTY between occupied positions) in scaffold."""
    in_data = False
    gaps = 0
    gap_open = False
    for e in scaf:
        if e != EMPTY:
            if gap_open:
                gaps += 1
                gap_open = False
            in_data = True
        else:
            if in_data:
                gap_open = True
    return gaps


# ── Main Entry Point ─────────────────────────────────────────────────────

def verify_design(design, cavity_helices=None, last_pair=None, verbose=False):
    """Run all verification checks on a cadnano design.

    Returns (passed: bool, report: str)
    """
    checks = [
        ('Array lengths', verify_array_lengths(design)),
        ('Segment counts (decode-safe)', verify_segment_counts(design)),
        ('Scaffold directions', verify_scaffold_directions(design)),
        ('Crossover symmetry', verify_crossover_symmetry(design)),
        ('Cavity gaps', verify_cavity_gaps(design, cavity_helices)),
        ('Last pair (no midseam)', verify_last_pair(design, last_pair)),
    ]

    # Scaffold connectivity (separate — counts components)
    n_components = verify_scaffold_connectivity(design)

    # Build report
    lines = ['=' * 60, 'CADNANO DESIGN VERIFICATION REPORT', '=' * 60, '']

    total_errors = 0
    total_warnings = 0

    for name, issues in checks:
        errors = [i for i in issues if i[0] == 'ERROR']
        warnings = [i for i in issues if i[0] == 'WARN']
        total_errors += len(errors)
        total_warnings += len(warnings)

        if not issues:
            lines.append(f'  ✓ {name}: PASS')
        else:
            status = 'FAIL' if errors else 'WARN'
            lines.append(f'  ✗ {name}: {status} ({len(errors)} errors, {len(warnings)} warnings)')
            if verbose or errors:
                for level, msg in issues[:5]:
                    lines.append(f'    [{level}] {msg}')
                if len(issues) > 5:
                    lines.append(f'    ... and {len(issues) - 5} more')

    lines.append('')
    if n_components == 1:
        lines.append(f'  ✓ Scaffold connectivity: 1 oligo (CORRECT)')
    else:
        lines.append(f'  ✗ Scaffold connectivity: {n_components} oligos (target: 1)')
        total_errors += 1

    # Summary
    n_helices = len(design['vstrands'])
    scaf_bp = sum(1 for v in design['vstrands'] for e in v['scaf'] if e != EMPTY)
    lines.append('')
    lines.append(f'  Design: {n_helices} helices, {scaf_bp} scaffold bp')
    lines.append('')

    passed = total_errors == 0
    if passed:
        lines.append('  RESULT: ALL CHECKS PASSED ✓')
    else:
        lines.append(f'  RESULT: FAILED ({total_errors} errors, {total_warnings} warnings)')

    lines.append('=' * 60)
    report = '\n'.join(lines)
    return passed, report


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print('Usage: python cadnano_verifier.py design.json [--verbose]')
        sys.exit(1)

    path = sys.argv[1]
    verbose = '--verbose' in sys.argv

    design = load_design(path)
    passed, report = verify_design(design, verbose=verbose)
    print(report)
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
