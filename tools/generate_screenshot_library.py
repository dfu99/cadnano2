#!/usr/bin/env python
"""
Generate a before/after screenshot library for crossover operations.

Renders the cadnano path view to PNG images before and after each operation.
Produces pairs like:
  screenshots/move_right_3/before.png
  screenshots/move_right_3/after.png

Operations covered:
  - Move crossover right/left by N bases
  - Delete a crossover
  - Create a crossover at a position
  - Add N evenly spaced crossovers
  - Remove all crossovers between a pair

Usage:
  QT_QPA_PLATFORM=offscreen python -m tools.generate_screenshot_library
"""

import os
import sys
import json
import time
import ast
import re

# Must set before any Qt imports
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cadnano2.cadnano as cadnano

from PyQt6.QtCore import QRectF, Qt, QMarginsF
from PyQt6.QtGui import QImage, QPainter, QColor
from PyQt6.QtWidgets import QApplication


def parse_crossover_list(result_str):
    """Parse the string output of listCrossovers into a list of dicts."""
    if not isinstance(result_str, str):
        return result_str if isinstance(result_str, list) else []
    # Format: "Crossovers (scaffold) (N total): [{...}, ...]"
    match = re.search(r'\[.*\]', result_str, re.DOTALL)
    if match:
        try:
            return ast.literal_eval(match.group())
        except:
            return []
    return []


def parse_valid_positions(result_str):
    """Parse the string output of getValidCrossoverPositions into a list of ints."""
    if not isinstance(result_str, str):
        return result_str if isinstance(result_str, list) else []
    # Format: "Valid scaffold crossover indices between helix 0 and 1: [4, 5, 15, ...]"
    match = re.search(r'\[.*\]', result_str)
    if match:
        try:
            return ast.literal_eval(match.group())
        except:
            return []
    return []

# Output directory
SCREENSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'screenshots')


def render_pathview(dc, label=""):
    """Render the path view scene to a QImage and return it."""
    win = dc.win
    scene = win.pathscene

    # Get the bounding rect of all items
    items_rect = scene.itemsBoundingRect()
    if items_rect.isEmpty():
        print(f"  [{label}] Warning: scene is empty")
        items_rect = QRectF(0, 0, 800, 200)

    # Add margins
    margin = 20
    items_rect = items_rect.marginsAdded(QMarginsF(margin, margin, margin, margin))

    # Scale factor for resolution
    scale = 2.0
    width = int(items_rect.width() * scale)
    height = int(items_rect.height() * scale)

    # Cap size to prevent massive images
    max_dim = 4000
    if width > max_dim:
        scale *= max_dim / width
        width = max_dim
        height = int(items_rect.height() * scale)
    if height > max_dim:
        scale *= max_dim / height
        height = max_dim
        width = int(items_rect.width() * scale)

    image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor(255, 255, 255))  # white background

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(painter, source=items_rect)
    painter.end()

    return image


def save_screenshot(image, dirpath, name):
    """Save a QImage to a file."""
    os.makedirs(dirpath, exist_ok=True)
    filepath = os.path.join(dirpath, f"{name}.png")
    image.save(filepath)
    print(f"  Saved: {filepath}")
    return filepath


def get_dc(app):
    """Get the DocumentController."""
    return list(app.documentControllers)[0]


def setup_two_helix_design(app, length=168, with_crossovers=True, strand_type="scaffold"):
    """
    Create a fresh 2-helix design and return (dc, methods).
    If with_crossovers, adds crossovers between the pair.
    """
    from cadnano2.views.agent.agentmethods import AgentMethods

    dc = get_dc(app)

    # Create new part
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    # Mock DC for AgentMethods
    class MockDC:
        def __init__(self, app, doc, part):
            self._app = app
            self._doc = doc
            self._part = part
        def document(self):
            return self._doc
        def activePart(self):
            return self._part
        def undoStack(self):
            return self._doc.undoStack()

    mock = MockDC(app, doc, part)
    methods = AgentMethods(mock)

    # Create helices with strands
    result = methods.createHelicesWithStrands(
        positions=[[21, 20], [21, 21]],
        strand_type=strand_type,
        length=length
    )
    print(f"  Setup: {result}")

    if with_crossovers:
        xresult = methods.addCrossoversForPair(0, 1, strand_type)
        print(f"  Setup crossovers: {xresult}")

    return dc, methods


def setup_three_helix_design(app, length=168, strand_type="scaffold"):
    """Create a 3-helix design for more complex operations."""
    from cadnano2.views.agent.agentmethods import AgentMethods

    dc = get_dc(app)
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    class MockDC:
        def __init__(self, app, doc, part):
            self._app = app
            self._doc = doc
            self._part = part
        def document(self):
            return self._doc
        def activePart(self):
            return self._part
        def undoStack(self):
            return self._doc.undoStack()

    mock = MockDC(app, doc, part)
    methods = AgentMethods(mock)

    result = methods.createHelicesWithStrands(
        positions=[[21, 20], [21, 21], [22, 20]],
        strand_type=strand_type,
        length=length
    )
    print(f"  Setup 3-helix: {result}")

    return dc, methods


def reset_design(app):
    """Close the current part so the next test starts fresh."""
    dc = get_dc(app)
    doc = dc.document()
    # Undo everything to clear the design
    us = doc.undoStack()
    while us.canUndo():
        us.undo()


# ============================================================
# Operation generators
# ============================================================

def setup_sparse_crossover_design(app, num_crossovers=1):
    """Create a 2-helix design with only a few crossovers, leaving room to move them."""
    from cadnano2.views.agent.agentmethods import AgentMethods

    dc = get_dc(app)
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    class MockDC:
        def __init__(self, app, doc, part):
            self._app = app
            self._doc = doc
            self._part = part
        def document(self):
            return self._doc
        def activePart(self):
            return self._part
        def undoStack(self):
            return self._doc.undoStack()

    mock = MockDC(app, doc, part)
    methods = AgentMethods(mock)

    # Create helices without crossovers
    result = methods.createHelicesWithStrands(
        positions=[[21, 20], [21, 21]],
        strand_type="scaffold",
        length=168
    )
    print(f"  Setup: {result}")

    # Get valid positions and pick just a few in the middle
    valid_indices = parse_valid_positions(
        methods.getValidCrossoverPositions(0, 1, "scaffold"))
    low_indices = valid_indices[::2]  # low positions

    if num_crossovers == 1:
        # Pick one in the middle
        chosen = [low_indices[len(low_indices) // 2]]
    elif num_crossovers == 2:
        # Pick two spaced apart
        q = len(low_indices) // 3
        chosen = [low_indices[q], low_indices[2 * q]]
    else:
        step = max(1, len(low_indices) // num_crossovers)
        chosen = [low_indices[i * step] for i in range(min(num_crossovers, len(low_indices)))]

    xresult = methods.addCrossoversForPair(0, 1, "scaffold", positions=chosen)
    print(f"  Setup sparse crossovers: {xresult}")

    return dc, methods


def gen_move_crossover_right(app, deltas=[1, 2, 3, 7]):
    """Generate before/after for moving a crossover right by N bases."""
    results = []
    for delta in deltas:
        print(f"\n--- move_crossover_right_{delta} ---")
        dc, methods = setup_sparse_crossover_design(app, num_crossovers=1)

        xovers = parse_crossover_list(methods.listCrossovers(strand_type="scaffold"))
        print(f"  Crossovers ({len(xovers)} total)")

        if xovers:
            xover = xovers[0]
            h1, h2 = xover['helix1'], xover['helix2']
            idx = xover['idx1']
        else:
            print(f"  SKIP: No crossovers found")
            reset_design(app)
            continue

        before_img = render_pathview(dc, "before")
        outdir = os.path.join(SCREENSHOT_DIR, f"move_crossover_right_{delta}")
        save_screenshot(before_img, outdir, "before")

        result = methods.moveCrossover(h1, h2, idx, "scaffold", delta)
        print(f"  moveCrossover result: {result}")

        after_img = render_pathview(dc, "after")
        save_screenshot(after_img, outdir, "after")

        meta = {
            "operation": "moveCrossover",
            "description": f"Move crossover right {delta} bases",
            "params": {"helix1": h1, "helix2": h2, "idx": idx,
                       "strand_type": "scaffold", "delta": delta},
            "result": str(result),
            "natural_language": f"Move the crossover at helix {h1} index {idx} to the right by {delta} bases"
        }
        with open(os.path.join(outdir, "metadata.json"), 'w') as f:
            json.dump(meta, f, indent=2)

        results.append(meta)
        reset_design(app)

    return results


def gen_move_crossover_left(app, deltas=[1, 2, 3, 7]):
    """Generate before/after for moving a crossover left by N bases."""
    results = []
    for delta in deltas:
        print(f"\n--- move_crossover_left_{delta} ---")
        dc, methods = setup_sparse_crossover_design(app, num_crossovers=1)

        xovers = parse_crossover_list(methods.listCrossovers(strand_type="scaffold"))
        if xovers:
            xover = xovers[-1]
            h1, h2 = xover['helix1'], xover['helix2']
            idx = xover['idx1']
        else:
            print(f"  SKIP: No crossovers found")
            reset_design(app)
            continue

        before_img = render_pathview(dc, "before")
        outdir = os.path.join(SCREENSHOT_DIR, f"move_crossover_left_{delta}")
        save_screenshot(before_img, outdir, "before")

        result = methods.moveCrossover(h1, h2, idx, "scaffold", -delta)
        print(f"  moveCrossover result: {result}")

        after_img = render_pathview(dc, "after")
        save_screenshot(after_img, outdir, "after")

        meta = {
            "operation": "moveCrossover",
            "description": f"Move crossover left {delta} bases",
            "params": {"helix1": h1, "helix2": h2, "idx": idx,
                       "strand_type": "scaffold", "delta": -delta},
            "result": str(result),
            "natural_language": f"Move the crossover at helix {h1} index {idx} to the left by {delta} bases"
        }
        with open(os.path.join(outdir, "metadata.json"), 'w') as f:
            json.dump(meta, f, indent=2)

        results.append(meta)
        reset_design(app)

    return results


def gen_delete_crossover(app):
    """Generate before/after for deleting crossovers."""
    results = []

    for which in ["first", "middle", "last"]:
        print(f"\n--- delete_crossover_{which} ---")
        dc, methods = setup_two_helix_design(app)

        xovers = parse_crossover_list(methods.listCrossovers(strand_type="scaffold"))
        if xovers:
            if which == "first":
                xover = xovers[0]
            elif which == "last":
                xover = xovers[-1]
            else:  # middle
                xover = xovers[len(xovers) // 2]
            h1 = xover['helix1']
            idx = xover['idx1']
        else:
            print(f"  SKIP: No crossovers found")
            reset_design(app)
            continue

        before_img = render_pathview(dc, "before")
        outdir = os.path.join(SCREENSHOT_DIR, f"delete_crossover_{which}")
        save_screenshot(before_img, outdir, "before")

        result = methods.removeCrossover(h1, idx, "scaffold")
        print(f"  removeCrossover result: {result}")

        after_img = render_pathview(dc, "after")
        save_screenshot(after_img, outdir, "after")

        meta = {
            "operation": "removeCrossover",
            "description": f"Delete the {which} crossover",
            "params": {"helix_num": h1, "idx": idx, "strand_type": "scaffold"},
            "result": str(result),
            "natural_language": f"Delete the {which} crossover between helix 0 and helix 1"
        }
        with open(os.path.join(outdir, "metadata.json"), 'w') as f:
            json.dump(meta, f, indent=2)

        results.append(meta)
        reset_design(app)

    return results


def gen_create_crossover(app):
    """Generate before/after for creating a crossover at specific positions."""
    results = []

    print(f"\n--- create_crossover_at_position ---")
    dc, methods = setup_two_helix_design(app, with_crossovers=False)

    # Get valid positions (returns list of ints)
    valid_indices = parse_valid_positions(
        methods.getValidCrossoverPositions(0, 1, "scaffold"))
    print(f"  Valid positions: {valid_indices}")

    if valid_indices:
        # Create at a few different positions
        for i, pos_label in enumerate(["near_start", "middle", "near_end"]):
            if i == 0:
                idx = valid_indices[0]
            elif i == 1:
                idx = valid_indices[len(valid_indices) // 2]
            else:
                idx = valid_indices[-1]

            before_img = render_pathview(dc, "before")
            outdir = os.path.join(SCREENSHOT_DIR, f"create_crossover_{pos_label}")
            save_screenshot(before_img, outdir, "before")

            result = methods.createCrossover(0, idx, 1, idx, "scaffold")
            print(f"  createCrossover at {idx}: {result}")

            after_img = render_pathview(dc, "after")
            save_screenshot(after_img, outdir, "after")

            meta = {
                "operation": "createCrossover",
                "description": f"Create crossover {pos_label} (idx {idx})",
                "params": {"helix1": 0, "idx1": idx, "helix2": 1, "idx2": idx,
                           "strand_type": "scaffold"},
                "result": str(result),
                "natural_language": f"Create a scaffold crossover between helix 0 and helix 1 at index {idx}"
            }
            with open(os.path.join(outdir, "metadata.json"), 'w') as f:
                json.dump(meta, f, indent=2)

            results.append(meta)

    reset_design(app)
    return results


def gen_add_evenly_spaced(app, counts=[2, 3, 4, 6]):
    """Generate before/after for adding N evenly spaced crossovers."""
    results = []

    for n in counts:
        print(f"\n--- add_{n}_evenly_spaced_crossovers ---")
        dc, methods = setup_two_helix_design(app, with_crossovers=False)

        before_img = render_pathview(dc, "before")
        outdir = os.path.join(SCREENSHOT_DIR, f"add_{n}_evenly_spaced_crossovers")
        save_screenshot(before_img, outdir, "before")

        # Get valid positions and pick N evenly spaced ones
        # Valid positions come in Low/High pairs; pick every other for Low indices
        all_valid = parse_valid_positions(
            methods.getValidCrossoverPositions(0, 1, "scaffold"))
        # Filter to just low indices (even-indexed in the sorted list, or use suggestCrossovers)
        # For simplicity, take every other index as a "slot"
        low_indices = all_valid[::2]  # approximate: take alternating as low positions
        if len(low_indices) >= n:
            step = max(1, len(low_indices) // n)
            chosen_idxs = [low_indices[i * step] for i in range(n)]

            result = methods.addCrossoversForPair(0, 1, "scaffold",
                                                   positions=chosen_idxs)
            print(f"  addCrossoversForPair ({n}): {result}")
        elif low_indices:
            result = methods.addCrossoversForPair(0, 1, "scaffold")
            chosen_idxs = "auto"
            print(f"  addCrossoversForPair (auto, wanted {n}): {result}")
        else:
            result = "Error: No valid positions"
            chosen_idxs = []

        after_img = render_pathview(dc, "after")
        save_screenshot(after_img, outdir, "after")

        meta = {
            "operation": "addCrossoversForPair",
            "description": f"Add {n} evenly spaced crossovers",
            "params": {"helix1": 0, "helix2": 1, "strand_type": "scaffold",
                       "positions": chosen_idxs if isinstance(chosen_idxs, list) else chosen_idxs},
            "result": str(result),
            "natural_language": f"Add {n} evenly spaced scaffold crossovers between helix 0 and helix 1"
        }
        with open(os.path.join(outdir, "metadata.json"), 'w') as f:
            json.dump(meta, f, indent=2)

        results.append(meta)
        reset_design(app)

    return results


def gen_remove_all_crossovers(app):
    """Generate before/after for removing all crossovers between a pair."""
    results = []

    print(f"\n--- remove_all_crossovers_pair ---")
    dc, methods = setup_two_helix_design(app, with_crossovers=True)

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "remove_all_crossovers_pair")
    save_screenshot(before_img, outdir, "before")

    result = methods.removeCrossoversForPair(0, 1, "scaffold")
    print(f"  removeCrossoversForPair: {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "removeCrossoversForPair",
        "description": "Remove all crossovers between helix 0 and 1",
        "params": {"helix1": 0, "helix2": 1, "strand_type": "scaffold"},
        "result": str(result),
        "natural_language": "Remove all scaffold crossovers between helix 0 and helix 1"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)

    results.append(meta)
    reset_design(app)

    # Also test removing all crossovers in design
    print(f"\n--- remove_all_crossovers_design ---")
    dc, methods = setup_two_helix_design(app, with_crossovers=True)

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "remove_all_crossovers_design")
    save_screenshot(before_img, outdir, "before")

    result = methods.removeAllCrossovers("scaffold")
    print(f"  removeAllCrossovers: {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "removeAllCrossovers",
        "description": "Remove all scaffold crossovers in the entire design",
        "params": {"strand_type": "scaffold"},
        "result": str(result),
        "natural_language": "Remove all scaffold crossovers in the design"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)

    results.append(meta)
    reset_design(app)

    return results


def gen_staple_operations(app):
    """Generate before/after for staple crossover operations."""
    results = []

    # Add staple crossovers
    print(f"\n--- add_staple_crossovers ---")
    dc, methods = setup_two_helix_design(app, strand_type="both", with_crossovers=False)

    # First add scaffold crossovers
    methods.addCrossoversForPair(0, 1, "scaffold")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "add_staple_crossovers")
    save_screenshot(before_img, outdir, "before")

    result = methods.addCrossoversForPair(0, 1, "staple")
    print(f"  addCrossoversForPair(staple): {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "addCrossoversForPair",
        "description": "Add staple crossovers between helix 0 and 1",
        "params": {"helix1": 0, "helix2": 1, "strand_type": "staple"},
        "result": str(result),
        "natural_language": "Add staple crossovers between helix 0 and helix 1"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)

    results.append(meta)
    reset_design(app)

    return results


def gen_move_crossover_staple(app):
    """Generate before/after for moving a staple crossover."""
    results = []

    for delta, label in [(2, "right_2"), (-2, "left_2")]:
        print(f"\n--- move_staple_crossover_{label} ---")
        dc, methods = setup_two_helix_design(app, strand_type="both", with_crossovers=False)

        # Add just one staple crossover in the middle
        valid_staple = parse_valid_positions(
            methods.getValidCrossoverPositions(0, 1, "staple"))
        if valid_staple:
            mid = valid_staple[len(valid_staple) // 2]
            methods.addCrossoversForPair(0, 1, "staple", positions=[mid])

        xovers = parse_crossover_list(methods.listCrossovers(strand_type="staple"))
        if xovers:
            xover = xovers[1] if len(xovers) > 1 else xovers[0]
            h1, h2 = xover['helix1'], xover['helix2']
            idx = xover['idx1']
        else:
            print(f"  SKIP: No staple crossovers")
            reset_design(app)
            continue

        before_img = render_pathview(dc, "before")
        outdir = os.path.join(SCREENSHOT_DIR, f"move_staple_crossover_{label}")
        save_screenshot(before_img, outdir, "before")

        result = methods.moveCrossover(h1, h2, idx, "staple", delta)
        print(f"  moveCrossover(staple): {result}")

        after_img = render_pathview(dc, "after")
        save_screenshot(after_img, outdir, "after")

        meta = {
            "operation": "moveCrossover",
            "description": f"Move staple crossover {label}",
            "params": {"helix1": h1, "helix2": h2, "idx": idx,
                       "strand_type": "staple", "delta": delta},
            "result": str(result),
            "natural_language": f"Move the staple crossover at helix {h1} index {idx} {'right' if delta > 0 else 'left'} by {abs(delta)} bases"
        }
        with open(os.path.join(outdir, "metadata.json"), 'w') as f:
            json.dump(meta, f, indent=2)

        results.append(meta)
        reset_design(app)

    return results


# ============================================================
# New operations: resize, insertions, strand breaks
# ============================================================

def gen_resize_strands(app):
    """Generate before/after for resizing strands."""
    results = []

    for delta, label in [(21, "extend_21"), (42, "extend_42"), (-21, "shrink_21")]:
        print(f"\n--- resize_strands_{label} ---")
        dc, methods = setup_two_helix_design(app, length=126, with_crossovers=True)

        before_img = render_pathview(dc, "before")
        outdir = os.path.join(SCREENSHOT_DIR, f"resize_strands_{label}")
        save_screenshot(before_img, outdir, "before")

        result = methods.resizeAllStrands("scaffold", delta=delta)
        print(f"  resizeAllStrands: {result}")

        after_img = render_pathview(dc, "after")
        save_screenshot(after_img, outdir, "after")

        meta = {
            "operation": "resizeAllStrands",
            "description": f"Resize all scaffold strands by {delta}bp",
            "params": {"strand_type": "scaffold", "delta": delta},
            "result": str(result),
            "natural_language": f"{'Extend' if delta > 0 else 'Shrink'} all scaffold strands by {abs(delta)} bases"
        }
        with open(os.path.join(outdir, "metadata.json"), 'w') as f:
            json.dump(meta, f, indent=2)

        results.append(meta)
        reset_design(app)

    return results


def gen_insertion_pattern(app):
    """Generate before/after for adding insertion/deletion patterns."""
    results = []

    # Insertion (length=1)
    for length, label in [(1, "insertion_1"), (-1, "deletion_1"), (3, "insertion_3")]:
        print(f"\n--- insertion_pattern_{label} ---")
        dc, methods = setup_two_helix_design(app, length=168, with_crossovers=True)

        before_img = render_pathview(dc, "before")
        outdir = os.path.join(SCREENSHOT_DIR, f"insertion_pattern_{label}")
        save_screenshot(before_img, outdir, "before")

        result = methods.addInsertionPattern(0, length=length, spacing=21)
        print(f"  addInsertionPattern: {result}")

        after_img = render_pathview(dc, "after")
        save_screenshot(after_img, outdir, "after")

        meta = {
            "operation": "addInsertionPattern",
            "description": f"Add {'insertion' if length > 0 else 'deletion'} pattern (length={length}) on helix 0",
            "params": {"helix_num": 0, "length": length, "spacing": 21},
            "result": str(result),
            "natural_language": f"Add {'insertions' if length > 0 else 'deletions'} of length {abs(length)} every 21 bases on helix 0"
        }
        with open(os.path.join(outdir, "metadata.json"), 'w') as f:
            json.dump(meta, f, indent=2)

        results.append(meta)
        reset_design(app)

    # Insertions on all helices
    print(f"\n--- insertion_pattern_all ---")
    dc, methods = setup_two_helix_design(app, length=168, with_crossovers=True)

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "insertion_pattern_all")
    save_screenshot(before_img, outdir, "before")

    result = methods.addInsertionPatternAll(length=1, spacing=21)
    print(f"  addInsertionPatternAll: {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "addInsertionPatternAll",
        "description": "Add insertions on all helices",
        "params": {"length": 1, "spacing": 21},
        "result": str(result),
        "natural_language": "Add single-base insertions every 21 bases on all helices"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)

    results.append(meta)
    reset_design(app)

    return results


def gen_strand_breaks(app):
    """Generate before/after for strand breaking operations."""
    results = []

    # Split a single strand
    print(f"\n--- split_strand_at ---")
    dc, methods = setup_two_helix_design(app, strand_type="both", with_crossovers=False)
    methods.addCrossoversForPair(0, 1, "scaffold")
    methods.addCrossoversForPair(0, 1, "staple")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "split_strand_at")
    save_screenshot(before_img, outdir, "before")

    result = methods.splitStrandAt(0, "staple", 42)
    print(f"  splitStrandAt: {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "splitStrandAt",
        "description": "Split staple strand at helix 0 index 42",
        "params": {"helix_num": 0, "strand_type": "staple", "idx": 42},
        "result": str(result),
        "natural_language": "Split the staple strand on helix 0 at position 42"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)

    results.append(meta)
    reset_design(app)

    # Break staple pattern
    print(f"\n--- break_staple_pattern ---")
    dc, methods = setup_two_helix_design(app, strand_type="both", with_crossovers=False)
    methods.addCrossoversForPair(0, 1, "scaffold")
    methods.addCrossoversForPair(0, 1, "staple")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "break_staple_pattern")
    save_screenshot(before_img, outdir, "before")

    result = methods.breakStaplePattern(spacing=21)
    print(f"  breakStaplePattern: {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "breakStaplePattern",
        "description": "Break staples every 21 bases",
        "params": {"spacing": 21},
        "result": str(result),
        "natural_language": "Break all staple strands at intervals of 21 bases"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)

    results.append(meta)
    reset_design(app)

    # Auto-break staples (Dijkstra optimized)
    print(f"\n--- auto_break_staples ---")
    dc, methods = setup_two_helix_design(app, strand_type="both", with_crossovers=False)
    methods.addCrossoversForPair(0, 1, "scaffold")
    methods.addCrossoversForPair(0, 1, "staple")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "auto_break_staples")
    save_screenshot(before_img, outdir, "before")

    result = methods.autoBreakStaples()
    print(f"  autoBreakStaples: {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "autoBreakStaples",
        "description": "Auto-break staples (Dijkstra optimized)",
        "params": {},
        "result": str(result),
        "natural_language": "Automatically break all staple strands into optimal lengths"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)

    results.append(meta)
    reset_design(app)

    return results


def gen_three_helix_operations(app):
    """Generate before/after for 3-helix design operations."""
    results = []

    # Add all neighbor crossovers on 3-helix design
    print(f"\n--- three_helix_add_all_crossovers ---")
    dc, methods = setup_three_helix_design(app, length=126)

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "three_helix_add_all_crossovers")
    save_screenshot(before_img, outdir, "before")

    result = methods.addAllNeighborCrossovers("scaffold")
    print(f"  addAllNeighborCrossovers: {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "addAllNeighborCrossovers",
        "description": "Add scaffold crossovers to all neighbor pairs (3-helix)",
        "params": {"strand_type": "scaffold"},
        "result": str(result),
        "natural_language": "Add scaffold crossovers between all neighboring helices in a 3-helix design"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)

    results.append(meta)
    reset_design(app)

    # Remove crossovers from one pair in 3-helix design
    print(f"\n--- three_helix_remove_one_pair ---")
    dc, methods = setup_three_helix_design(app, length=126)
    methods.addAllNeighborCrossovers("scaffold")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "three_helix_remove_one_pair")
    save_screenshot(before_img, outdir, "before")

    result = methods.removeCrossoversForPair(0, 1, "scaffold")
    print(f"  removeCrossoversForPair(0,1): {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "removeCrossoversForPair",
        "description": "Remove crossovers between helix 0 and 1 in 3-helix design",
        "params": {"helix1": 0, "helix2": 1, "strand_type": "scaffold"},
        "result": str(result),
        "natural_language": "Remove all scaffold crossovers between helix 0 and helix 1 (keep helix 1-2 crossovers)"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)

    results.append(meta)
    reset_design(app)

    return results


def setup_six_helix_design(app, length=126, strand_type="both"):
    """Create a 6-helix single-row design (flat sheet)."""
    from cadnano2.views.agent.agentmethods import AgentMethods

    dc = get_dc(app)
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    class MockDC:
        def __init__(self, app, doc, part):
            self._app = app
            self._doc = doc
            self._part = part
        def document(self):
            return self._doc
        def activePart(self):
            return self._part
        def undoStack(self):
            return self._doc.undoStack()

    mock = MockDC(app, doc, part)
    methods = AgentMethods(mock)

    positions = [[21, 20 + i] for i in range(6)]
    result = methods.createHelicesWithStrands(
        positions=positions,
        strand_type=strand_type,
        length=length
    )
    print(f"  Setup 6-helix: {result}")
    return dc, methods


def gen_six_helix_operations(app):
    """Generate screenshots for 6-helix design operations."""
    results = []

    # 1. Add all scaffold crossovers to 6-helix design
    print(f"\n--- six_helix_add_scaffold_crossovers ---")
    dc, methods = setup_six_helix_design(app, length=126, strand_type="both")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "six_helix_add_scaffold_crossovers")
    save_screenshot(before_img, outdir, "before")

    result = methods.addAllNeighborCrossovers("scaffold")
    print(f"  addAllNeighborCrossovers(scaffold): {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "addAllNeighborCrossovers",
        "description": "Add scaffold crossovers to all pairs in 6-helix design",
        "params": {"strand_type": "scaffold", "n_helices": 6},
        "result": str(result),
        "natural_language": "Add scaffold crossovers between all neighboring helices in a 6-helix flat sheet"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)
    results.append(meta)
    reset_design(app)

    # 2. Add both scaffold and staple crossovers
    print(f"\n--- six_helix_add_both_crossovers ---")
    dc, methods = setup_six_helix_design(app, length=126, strand_type="both")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "six_helix_add_both_crossovers")
    save_screenshot(before_img, outdir, "before")

    result1 = methods.addAllNeighborCrossovers("scaffold")
    result2 = methods.addAllNeighborCrossovers("staple")
    print(f"  scaffold: {result1}")
    print(f"  staple: {result2}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "addAllNeighborCrossovers",
        "description": "Add scaffold and staple crossovers to 6-helix design",
        "params": {"strand_type": "both", "n_helices": 6},
        "result": f"scaffold: {result1}, staple: {result2}",
        "natural_language": "Add both scaffold and staple crossovers to all neighboring helices in a 6-helix design"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)
    results.append(meta)
    reset_design(app)

    # 3. Remove crossovers from middle pair in 6-helix design
    print(f"\n--- six_helix_remove_middle_pair ---")
    dc, methods = setup_six_helix_design(app, length=126, strand_type="both")
    methods.addAllNeighborCrossovers("scaffold")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "six_helix_remove_middle_pair")
    save_screenshot(before_img, outdir, "before")

    result = methods.removeCrossoversForPair(2, 3, "scaffold")
    print(f"  removeCrossoversForPair(2,3): {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "removeCrossoversForPair",
        "description": "Remove scaffold crossovers between middle pair in 6-helix design",
        "params": {"helix1": 2, "helix2": 3, "strand_type": "scaffold", "n_helices": 6},
        "result": str(result),
        "natural_language": "Remove all scaffold crossovers between helix 2 and helix 3 in a 6-helix design"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)
    results.append(meta)
    reset_design(app)

    # 4. Resize all strands in 6-helix design
    print(f"\n--- six_helix_resize_extend ---")
    dc, methods = setup_six_helix_design(app, length=126, strand_type="both")
    methods.addAllNeighborCrossovers("scaffold")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "six_helix_resize_extend")
    save_screenshot(before_img, outdir, "before")

    result = methods.resizeAllStrands("scaffold", delta=21)
    print(f"  resizeAllStrands(scaffold, delta=21): {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "resizeAllStrands",
        "description": "Extend all scaffold strands by 21bp in 6-helix design",
        "params": {"strand_type": "scaffold", "delta": 21, "n_helices": 6},
        "result": str(result),
        "natural_language": "Extend all scaffold strands by 21 bases in a 6-helix design"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)
    results.append(meta)
    reset_design(app)

    # 5. Add insertion pattern to all helices in 6-helix design
    print(f"\n--- six_helix_insertion_pattern_all ---")
    dc, methods = setup_six_helix_design(app, length=126, strand_type="both")
    methods.addAllNeighborCrossovers("scaffold")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "six_helix_insertion_pattern_all")
    save_screenshot(before_img, outdir, "before")

    result = methods.addInsertionPatternAll(length=1, spacing=21)
    print(f"  addInsertionPatternAll(1, spacing=21): {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "addInsertionPatternAll",
        "description": "Add insertion pattern across all 6 helices",
        "params": {"length": 1, "spacing": 21, "n_helices": 6},
        "result": str(result),
        "natural_language": "Add single-base insertions every 21 bases across all helices in a 6-helix design"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)
    results.append(meta)
    reset_design(app)

    # 6. Auto-break staples in fully-wired 6-helix design
    print(f"\n--- six_helix_auto_break ---")
    dc, methods = setup_six_helix_design(app, length=126, strand_type="both")
    methods.addAllNeighborCrossovers("scaffold")
    methods.addAllNeighborCrossovers("staple")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "six_helix_auto_break")
    save_screenshot(before_img, outdir, "before")

    result = methods.autoBreakStaples()
    print(f"  autoBreakStaples(): {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "autoBreakStaples",
        "description": "Auto-break staples in fully-wired 6-helix design",
        "params": {"n_helices": 6},
        "result": str(result),
        "natural_language": "Automatically break all staple strands into optimal lengths in a 6-helix design"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)
    results.append(meta)
    reset_design(app)

    return results


def setup_grid_2x3_design(app, length=126, strand_type="both"):
    """Create a 2×3 grid design (6 helices in 2 rows of 3)."""
    from cadnano2.views.agent.agentmethods import AgentMethods

    dc = get_dc(app)
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    class MockDC:
        def __init__(self, app, doc, part):
            self._app = app
            self._doc = doc
            self._part = part
        def document(self):
            return self._doc
        def activePart(self):
            return self._part
        def undoStack(self):
            return self._doc.undoStack()

    mock = MockDC(app, doc, part)
    methods = AgentMethods(mock)

    positions = [[21, 20], [21, 21], [21, 22],
                 [22, 20], [22, 21], [22, 22]]
    result = methods.createHelicesWithStrands(
        positions=positions,
        strand_type=strand_type,
        length=length
    )
    print(f"  Setup 2×3 grid: {result}")
    return dc, methods


def gen_grid_operations(app):
    """Generate screenshots for 2×3 grid (multi-row) operations."""
    results = []

    # 1. Add all scaffold crossovers to 2×3 grid
    print(f"\n--- grid_add_scaffold_crossovers ---")
    dc, methods = setup_grid_2x3_design(app, length=126, strand_type="both")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "grid_add_scaffold_crossovers")
    save_screenshot(before_img, outdir, "before")

    result = methods.addAllNeighborCrossovers("scaffold")
    print(f"  addAllNeighborCrossovers(scaffold): {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "addAllNeighborCrossovers",
        "description": "Add scaffold crossovers to all pairs in 2×3 grid",
        "params": {"strand_type": "scaffold", "n_helices": 6, "layout": "2x3_grid"},
        "result": str(result),
        "natural_language": "Add scaffold crossovers between all neighboring helices in a 2×3 grid design"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)
    results.append(meta)
    reset_design(app)

    # 2. Add both crossover types to 2×3 grid
    print(f"\n--- grid_add_both_crossovers ---")
    dc, methods = setup_grid_2x3_design(app, length=126, strand_type="both")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "grid_add_both_crossovers")
    save_screenshot(before_img, outdir, "before")

    r1 = methods.addAllNeighborCrossovers("scaffold")
    r2 = methods.addAllNeighborCrossovers("staple")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "addAllNeighborCrossovers",
        "description": "Add scaffold and staple crossovers to 2×3 grid",
        "params": {"strand_type": "both", "n_helices": 6, "layout": "2x3_grid"},
        "result": f"scaffold: {r1}, staple: {r2}",
        "natural_language": "Add both scaffold and staple crossovers to all pairs in a 2×3 grid design"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)
    results.append(meta)
    reset_design(app)

    # 3. Remove one row's crossovers in grid
    print(f"\n--- grid_remove_cross_row_pair ---")
    dc, methods = setup_grid_2x3_design(app, length=126, strand_type="both")
    methods.addAllNeighborCrossovers("scaffold")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "grid_remove_cross_row_pair")
    save_screenshot(before_img, outdir, "before")

    # Get helix numbers — find a cross-row pair
    neighbor_result = methods.getNeighborPairs()
    print(f"  Neighbors: {neighbor_result}")
    # Remove crossovers between first cross-row pair (typically helix 1 and 2 or similar)
    result = methods.removeCrossoversForPair(1, 2, "scaffold")
    print(f"  removeCrossoversForPair(1,2): {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "removeCrossoversForPair",
        "description": "Remove cross-row scaffold crossovers in 2×3 grid",
        "params": {"helix1": 1, "helix2": 2, "strand_type": "scaffold", "layout": "2x3_grid"},
        "result": str(result),
        "natural_language": "Remove scaffold crossovers between helix 1 and helix 2 in a 2×3 grid (cross-row pair)"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)
    results.append(meta)
    reset_design(app)

    # 4. Insertion pattern on grid
    print(f"\n--- grid_insertion_pattern ---")
    dc, methods = setup_grid_2x3_design(app, length=126, strand_type="both")
    methods.addAllNeighborCrossovers("scaffold")

    before_img = render_pathview(dc, "before")
    outdir = os.path.join(SCREENSHOT_DIR, "grid_insertion_pattern")
    save_screenshot(before_img, outdir, "before")

    result = methods.addInsertionPatternAll(length=1, spacing=21)
    print(f"  addInsertionPatternAll: {result}")

    after_img = render_pathview(dc, "after")
    save_screenshot(after_img, outdir, "after")

    meta = {
        "operation": "addInsertionPatternAll",
        "description": "Add insertion pattern across all helices in 2×3 grid",
        "params": {"length": 1, "spacing": 21, "layout": "2x3_grid"},
        "result": str(result),
        "natural_language": "Add single-base insertions every 21 bases across all helices in a 2×3 grid design"
    }
    with open(os.path.join(outdir, "metadata.json"), 'w') as f:
        json.dump(meta, f, indent=2)
    results.append(meta)
    reset_design(app)

    return results


# ============================================================
# Main
# ============================================================

def main():
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    print("Initializing cadnano...")
    app = cadnano.initAppWithGui()

    all_results = []
    generators = [
        ("Move crossover right", gen_move_crossover_right),
        ("Move crossover left", gen_move_crossover_left),
        ("Delete crossover", gen_delete_crossover),
        ("Create crossover", gen_create_crossover),
        ("Add evenly spaced crossovers", gen_add_evenly_spaced),
        ("Remove all crossovers", gen_remove_all_crossovers),
        ("Staple operations", gen_staple_operations),
        ("Resize strands", gen_resize_strands),
        ("Insertion patterns", gen_insertion_pattern),
        ("Strand breaks", gen_strand_breaks),
        ("Three-helix operations", gen_three_helix_operations),
        ("Six-helix operations", gen_six_helix_operations),
        ("2×3 grid operations", gen_grid_operations),
    ]

    for name, gen_fn in generators:
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}")
        try:
            results = gen_fn(app)
            all_results.extend(results)
        except Exception as e:
            print(f"  ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            try:
                reset_design(app)
            except:
                pass

    # Save summary
    summary_path = os.path.join(SCREENSHOT_DIR, "library_summary.json")
    with open(summary_path, 'w') as f:
        json.dump({
            "total_operations": len(all_results),
            "operations": all_results,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  DONE: Generated {len(all_results)} before/after pairs")
    print(f"  Screenshots: {SCREENSHOT_DIR}/")
    print(f"  Summary: {summary_path}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
