#!/usr/bin/env python
"""
Tests for edge vs interior crossover classification.

Validates that:
1. suggestCrossovers annotates first/last positions as is_edge=True
2. addCrossoversForPair with crossover_type="auto" creates half-crossovers
   at edge positions for scaffold
3. crossover_type="double" forces all double crossovers
4. Staple crossovers in auto mode are always double

Requires: QT_QPA_PLATFORM=offscreen
Usage:  QT_QPA_PLATFORM=offscreen python tests/test_edge_crossover.py
"""

import os
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cadnano2.cadnano as cadnano


class MockDC:
    def __init__(self, app):
        self._app = app
        self._doc = None
        self._part = None

    def document(self):
        return self._doc

    def activePart(self):
        return self._part

    def undoStack(self):
        return self._doc.undoStack()


def setup():
    app = cadnano.initAppWithGui()
    from cadnano2.views.agent.agentmethods import AgentMethods

    dc = list(app.documentControllers)[0]
    doc = dc.document()
    dc.actionAddHoneycombPartSlot()
    part = doc.selectedPart()

    mock = MockDC(app)
    mock._doc = doc
    mock._part = part
    methods = AgentMethods(mock)
    return app, doc, part, mock, methods


def main():
    print("=" * 60)
    print("Edge vs Interior Crossover — Test Suite")
    print("=" * 60)

    app, doc, part, mock, methods = setup()
    passed = 0
    failed = 0

    # Create two helices with scaffold strands
    result = methods.createHelicesWithStrands(
        positions=[[21, 20], [21, 21]],
        strand_type="scaffold",
        length=84
    )
    print(f"Setup: {result}")

    # Test 1: suggestCrossovers edge annotations
    print("\n--- Test 1: suggestCrossovers edge annotations ---")
    try:
        suggestions = methods.suggestCrossovers(0, 1, "scaffold")
        positions = suggestions['positions']
        edges = [p for p in positions if p.get('is_edge')]
        interiors = [p for p in positions if not p.get('is_edge')]
        print(f"  Total: {len(positions)}, Edge: {len(edges)}, Interior: {len(interiors)}")
        print(f"  Edge indices: {[(p['low_idx'], p['high_idx']) for p in edges]}")
        assert len(edges) == 2, f"Expected 2 edge positions, got {len(edges)}"
        assert edges[0] == positions[0], "First position should be edge"
        assert edges[1] == positions[-1], "Last position should be edge"
        assert 'edge_note' in suggestions, "Missing edge_note"
        print("  PASS")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Test 2: auto mode creates half-crossovers at edges for scaffold
    print("\n--- Test 2: addCrossoversForPair auto mode (scaffold) ---")
    try:
        result = methods.addCrossoversForPair(0, 1, "scaffold", crossover_type="auto")
        assert isinstance(result, dict), f"Expected dict, got: {result}"
        created = result.get('crossovers', [])
        half_count = sum(1 for c in created if c.get('type') == 'half')
        double_count = sum(1 for c in created if c.get('type') == 'double')
        print(f"  Created: {len(created)} total, {half_count} half, {double_count} double")
        assert half_count >= 1, f"Expected ≥1 half crossover, got {half_count}"
        print("  PASS")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Test 3: double mode forces all double
    print("\n--- Test 3: crossover_type='double' forces all double ---")
    try:
        # Undo the crossover macro from test 2
        doc.undoStack().undo()
        result = methods.addCrossoversForPair(0, 1, "scaffold", crossover_type="double")
        assert isinstance(result, dict), f"Expected dict, got: {result}"
        created = result.get('crossovers', [])
        half_count = sum(1 for c in created if c.get('type') == 'half')
        double_count = sum(1 for c in created if c.get('type') == 'double')
        print(f"  Created: {len(created)} total, {half_count} half, {double_count} double")
        assert half_count == 0, f"Expected 0 half with double mode, got {half_count}"
        assert double_count > 0, "Expected at least 1 double crossover"
        print("  PASS")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Test 4: staple crossovers in auto mode always double
    print("\n--- Test 4: staple auto mode always double ---")
    try:
        # Undo crossovers from test 3
        doc.undoStack().undo()
        # Add staple strands on existing helices
        methods.createFullLengthStrands(0, "staple")
        methods.createFullLengthStrands(1, "staple")
        result = methods.addCrossoversForPair(0, 1, "staple", crossover_type="auto")
        assert isinstance(result, dict), f"Expected dict, got: {result}"
        created = result.get('crossovers', [])
        half_count = sum(1 for c in created if c.get('type') == 'half')
        double_count = sum(1 for c in created if c.get('type') == 'double')
        print(f"  Created: {len(created)} total, {half_count} half, {double_count} double")
        assert half_count == 0, f"Staple auto should not produce half crossovers, got {half_count}"
        assert double_count > 0, "Expected at least 1 double crossover"
        print("  PASS")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Test 5: half mode forces all half
    print("\n--- Test 5: crossover_type='half' forces all half ---")
    try:
        # Undo: staple crossovers, staple strand 1, staple strand 0
        doc.undoStack().undo()  # staple crossovers
        doc.undoStack().undo()  # staple strand on helix 1
        doc.undoStack().undo()  # staple strand on helix 0
        result = methods.addCrossoversForPair(0, 1, "scaffold", crossover_type="half")
        assert isinstance(result, dict), f"Expected dict, got: {result}"
        created = result.get('crossovers', [])
        half_count = sum(1 for c in created if c.get('type') == 'half')
        double_count = sum(1 for c in created if c.get('type') == 'double')
        print(f"  Created: {len(created)} total, {half_count} half, {double_count} double")
        assert double_count == 0, f"Expected 0 double with half mode, got {double_count}"
        assert half_count > 0, "Expected at least 1 half crossover"
        print("  PASS")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"Total: {passed} passed, {failed} failed out of {passed + failed}")
    print("=" * 60)
    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
