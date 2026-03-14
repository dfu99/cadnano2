#!/usr/bin/env python
"""
Tests for edge vs interior crossover classification and routing-aware
half-crossover placement.

Validates that:
1. suggestCrossovers annotates positions with is_edge and is_routing_turn
2. Only the parity-determined routing turn gets a half-crossover in auto mode
3. crossover_type="double" forces all double crossovers
4. Staple crossovers in auto mode are always double
5. crossover_type="half" forces all half-crossovers
6. inferScaffoldRoute returns a valid Hamiltonian cycle with turn positions
7. addAllNeighborCrossovers in auto mode is routing-aware
8. inferScaffoldRoute works for 6-helix bundles

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

    # Test 1: suggestCrossovers edge and routing_turn annotations
    print("\n--- Test 1: suggestCrossovers routing_turn annotations ---")
    try:
        suggestions = methods.suggestCrossovers(0, 1, "scaffold")
        positions = suggestions['positions']
        edges = [p for p in positions if p.get('is_edge')]
        routing_turns = [p for p in positions if p.get('is_routing_turn')]
        print(f"  Total: {len(positions)}, Edge: {len(edges)}, Routing turns: {len(routing_turns)}")
        print(f"  Edge indices: {[(p['low_idx'], p['high_idx']) for p in edges]}")
        print(f"  Routing turn: {[(p['low_idx'], p['high_idx']) for p in routing_turns]}")
        assert len(edges) == 2, f"Expected 2 edge positions, got {len(edges)}"
        assert len(routing_turns) == 1, f"Expected 1 routing turn, got {len(routing_turns)}"
        assert 'routing_turn_idx' in suggestions, "Missing routing_turn_idx"
        # Routing turn should be one of the edge positions
        rt = routing_turns[0]
        assert rt['is_edge'], "Routing turn should also be an edge"
        print("  PASS")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Test 2: auto mode creates exactly one half-crossover (at routing turn)
    print("\n--- Test 2: addCrossoversForPair auto mode — one half at routing turn ---")
    try:
        result = methods.addCrossoversForPair(0, 1, "scaffold", crossover_type="auto")
        assert isinstance(result, dict), f"Expected dict, got: {result}"
        created = result.get('crossovers', [])
        half_count = sum(1 for c in created if c.get('type') == 'half')
        double_count = sum(1 for c in created if c.get('type') == 'double')
        print(f"  Created: {len(created)} total, {half_count} half, {double_count} double")
        assert half_count == 1, f"Expected exactly 1 half crossover, got {half_count}"
        assert double_count >= 1, f"Expected ≥1 double crossover, got {double_count}"
        print("  PASS")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Test 3: double mode forces all double
    print("\n--- Test 3: crossover_type='double' forces all double ---")
    try:
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
        doc.undoStack().undo()
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

    # Test 6: inferScaffoldRoute returns valid routing for 2 helices
    print("\n--- Test 6: inferScaffoldRoute for 2 helices ---")
    try:
        doc.undoStack().undo()  # undo half crossovers from test 5
        route = methods.inferScaffoldRoute()
        assert isinstance(route, dict), f"Expected dict, got: {route}"
        assert 'error' not in route, f"Got error: {route.get('error')}"
        assert 'path' in route, "Missing path"
        assert 'turns' in route, "Missing turns"
        assert 'routing_pairs' in route, "Missing routing_pairs"
        assert 'non_routing_pairs' in route, "Missing non_routing_pairs"
        path = route['path']
        turns = route['turns']
        print(f"  Path: {path}")
        print(f"  Is cycle: {route.get('is_cycle')}")
        print(f"  Turns: {len(turns)}")
        for t in turns:
            print(f"    H{t['helix_from']}→H{t['helix_to']} at idx {t.get('turn_idx')} "
                  f"({t.get('parity')} parity, exit {t.get('exit_end')})")
        assert len(path) == 2, f"Expected 2 helices in path, got {len(path)}"
        assert route['is_cycle'], "Expected a cycle for 2 helices"
        # Each turn should have a turn_idx
        for t in turns:
            assert 'turn_idx' in t, f"Turn missing turn_idx: {t}"
        print("  PASS")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Test 7: inferScaffoldRoute for 6-helix bundle
    print("\n--- Test 7: inferScaffoldRoute for 6-helix bundle ---")
    try:
        # Create fresh document
        from cadnano2.views.agent.agentmethods import AgentMethods
        dc = list(app.documentControllers)[0]
        dc.newDocument()
        doc = dc.document()
        dc.actionAddHoneycombPartSlot()
        part = doc.selectedPart()
        mock._doc = doc
        mock._part = part
        methods = AgentMethods(mock)

        result = methods.createHelicesWithStrands(
            num_helices=6, strand_type="scaffold", length=84
        )
        assert isinstance(result, dict), f"Setup failed: {result}"

        route = methods.inferScaffoldRoute()
        assert isinstance(route, dict), f"Expected dict, got: {route}"
        assert 'error' not in route, f"Got error: {route.get('error')}"
        path = route['path']
        turns = route['turns']
        print(f"  Path: {path}")
        print(f"  Is cycle: {route.get('is_cycle')}")
        print(f"  Routing pairs: {route.get('routing_pairs')}")
        print(f"  Non-routing pairs: {route.get('non_routing_pairs')}")
        print(f"  Turns: {len(turns)}")
        for t in turns:
            print(f"    H{t['helix_from']}→H{t['helix_to']} at idx {t.get('turn_idx')} "
                  f"({t.get('parity')} parity, exit {t.get('exit_end')})")
        assert len(path) == 6, f"Expected 6 helices in path, got {len(path)}"
        # All helices should appear exactly once
        assert len(set(path)) == 6, "Not all helices in path"
        # Should have turns for each pair in the cycle
        n_turns = len(path) if route['is_cycle'] else len(path) - 1
        assert len(turns) == n_turns, f"Expected {n_turns} turns, got {len(turns)}"
        print("  PASS")
        passed += 1
    except Exception as e:
        print(f"  FAIL: {e}")
        failed += 1

    # Test 8: addAllNeighborCrossovers routing-aware auto mode
    print("\n--- Test 8: addAllNeighborCrossovers routing-aware auto mode ---")
    try:
        result = methods.addAllNeighborCrossovers("scaffold", crossover_type="auto")
        assert isinstance(result, dict), f"Expected dict, got: {result}"
        total = result.get('total_created', 0)
        print(f"  Total crossovers created: {total}")
        print(f"  Routing pairs used: {result.get('routing_pairs')}")
        # Should have created some crossovers
        assert total > 0, "Expected at least some crossovers"
        # routing_pairs should be set in auto mode
        assert result.get('routing_pairs') is not None, "Expected routing_pairs in result"
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
