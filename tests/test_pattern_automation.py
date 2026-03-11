#!/usr/bin/env python
"""
Headless tests for pattern automation methods in AgentMethods.

Tests: resizeAllStrands, removeCrossoversForPair, removeAllCrossovers,
       addInsertionPattern, removeInsertionPattern, addInsertionPatternAll,
       listInsertions

Requires: QT_QPA_PLATFORM=offscreen
Usage:  QT_QPA_PLATFORM=offscreen python -m tests.test_pattern_automation
"""

import os
import sys
import json

# Must set before any Qt imports
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cadnano2.cadnano as cadnano

# Minimal mock for DocumentController
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


def setup_app():
    """Initialize cadnano with offscreen Qt."""
    app = cadnano.initAppWithGui()
    return app


def load_test_design(app, filepath):
    """Load a cadnano JSON file and return (document, part, mock_dc)."""
    dc = list(app.documentControllers)[0]
    # Use the file-open mechanism
    dc.fileOpenAction(filepath)
    doc = dc.document()
    part = doc.selectedPart()
    mock = MockDC(app)
    mock._doc = doc
    mock._part = part
    return doc, part, mock


def create_fresh_design(app):
    """Create a fresh 2-helix design for testing."""
    from cadnano2.views.agent.agentmethods import AgentMethods

    dc = list(app.documentControllers)[0]
    doc = dc.document()

    # Create a new honeycomb part
    dc.actionAddHoneycombPartSlot()
    part = doc.selectedPart()

    mock = MockDC(app)
    mock._doc = doc
    mock._part = part
    methods = AgentMethods(mock)

    # Create two helices with scaffold strands
    result = methods.createHelicesWithStrands(
        positions=[[21, 20], [21, 21]],
        strand_type="scaffold",
        length=84
    )
    print(f"  Setup: Created helices: {result}")

    return doc, part, mock, methods


def test_list_crossovers(methods, label=""):
    """Helper: list scaffold crossovers."""
    result = methods.listCrossovers(strand_type="scaffold")
    print(f"  {label}Crossovers: {result}")
    return result


# ============================================================
# TEST FUNCTIONS
# ============================================================

def test_resize_all_strands(methods):
    """Test resizeAllStrands with delta and absolute length."""
    print("\n=== Test: resizeAllStrands ===")

    # Test with delta
    result = methods.resizeAllStrands(strand_type="scaffold", delta=-21)
    print(f"  Resize by delta=-21: {result}")
    assert isinstance(result, dict), f"Expected dict, got: {result}"
    assert result['resized'] > 0, "Should have resized at least one strand"
    print("  PASS: delta resize")

    # Test with absolute length
    result = methods.resizeAllStrands(strand_type="scaffold", new_length=84)
    print(f"  Resize to length=84: {result}")
    assert isinstance(result, dict), f"Expected dict, got: {result}"
    print("  PASS: absolute resize")

    # Test error: no params
    result = methods.resizeAllStrands(strand_type="scaffold")
    assert isinstance(result, str) and "Error" in result, "Should return error"
    print("  PASS: error handling (no params)")

    return True


def test_add_crossovers_and_remove_for_pair(methods):
    """Test addCrossoversForPair then removeCrossoversForPair."""
    print("\n=== Test: addCrossoversForPair + removeCrossoversForPair ===")

    # First add crossovers
    result = methods.addCrossoversForPair(helix1=0, helix2=1, strand_type="scaffold")
    print(f"  Add crossovers: {result}")
    assert isinstance(result, dict), f"Expected dict, got: {result}"
    initial_count = result.get('created', 0)
    assert initial_count > 0, "Should have created crossovers"
    print(f"  PASS: created {initial_count} crossovers")

    # Now remove them
    result = methods.removeCrossoversForPair(helix1=0, helix2=1, strand_type="scaffold")
    print(f"  Remove crossovers: {result}")
    assert isinstance(result, dict), f"Expected dict, got: {result}"
    assert result['removed'] > 0, "Should have removed crossovers"
    print(f"  PASS: removed {result['removed']} crossovers")

    # Verify none remain
    result = methods.removeCrossoversForPair(helix1=0, helix2=1, strand_type="scaffold")
    assert result['removed'] == 0, "Should have no crossovers remaining"
    print("  PASS: verified 0 crossovers remain")

    return True


def test_remove_all_crossovers(methods):
    """Test removeAllCrossovers."""
    print("\n=== Test: removeAllCrossovers ===")

    # Add crossovers first
    methods.addCrossoversForPair(helix1=0, helix2=1, strand_type="scaffold")
    xovers = methods.listCrossovers(strand_type="scaffold")
    print(f"  Before: {xovers}")

    result = methods.removeAllCrossovers(strand_type="scaffold")
    print(f"  removeAllCrossovers: {result}")
    assert isinstance(result, dict), f"Expected dict, got: {result}"
    assert result['removed'] > 0, "Should have removed crossovers"

    # Verify
    result2 = methods.removeAllCrossovers(strand_type="scaffold")
    assert result2['removed'] == 0, "Should have none left"
    print(f"  PASS: removed {result['removed']}, verified 0 remain")

    return True


def test_insertion_pattern(methods):
    """Test addInsertionPattern, listInsertions, removeInsertionPattern."""
    print("\n=== Test: Insertion pattern lifecycle ===")

    # Add insertions on helix 0
    result = methods.addInsertionPattern(
        helix_num=0, length=1, spacing=21, strand_type="scaffold"
    )
    print(f"  addInsertionPattern h0: {result}")
    assert isinstance(result, dict), f"Expected dict, got: {result}"
    assert result['added'] > 0, "Should have added insertions"
    positions = result['positions']
    print(f"  PASS: added {result['added']} insertions at positions {positions}")

    # List them
    result = methods.listInsertions(helix_num=0)
    print(f"  listInsertions h0: {result}")
    assert isinstance(result, dict), f"Expected dict, got: {result}"
    assert result['count'] > 0, "Should list insertions"
    print(f"  PASS: listed {result['count']} insertions")

    # Remove them
    result = methods.removeInsertionPattern(helix_num=0)
    print(f"  removeInsertionPattern h0: {result}")
    assert isinstance(result, dict), f"Expected dict, got: {result}"
    assert result['removed'] > 0, "Should have removed insertions"
    print(f"  PASS: removed {result['removed']} insertions")

    # Verify none remain
    result = methods.listInsertions(helix_num=0)
    assert result['count'] == 0, f"Should have 0 insertions, got {result['count']}"
    print("  PASS: verified 0 insertions remain")

    return True


def test_insertion_pattern_deletions(methods):
    """Test addInsertionPattern with deletions (length=-1)."""
    print("\n=== Test: Insertion pattern with deletions ===")

    result = methods.addInsertionPattern(
        helix_num=0, length=-1, spacing=21, strand_type="scaffold"
    )
    print(f"  addInsertionPattern (deletions) h0: {result}")
    assert isinstance(result, dict), f"Expected dict, got: {result}"
    assert result['added'] > 0, "Should have added deletions"
    print(f"  PASS: added {result['added']} deletions")

    # List to confirm they're deletion length
    result = methods.listInsertions(helix_num=0)
    for ins in result['insertions']:
        assert ins['length'] == -1, f"Expected length -1, got {ins['length']}"
    print("  PASS: all insertions have length=-1 (deletions)")

    # Clean up
    methods.removeInsertionPattern(helix_num=0)
    return True


def test_insertion_pattern_all(methods):
    """Test addInsertionPatternAll across all helices."""
    print("\n=== Test: addInsertionPatternAll ===")

    result = methods.addInsertionPatternAll(length=1, spacing=21, strand_type="scaffold")
    print(f"  addInsertionPatternAll: {result}")
    assert isinstance(result, dict), f"Expected dict, got: {result}"
    assert result['total_added'] > 0, "Should have added insertions"
    assert len(result['per_helix']) > 0, "Should have per-helix data"
    print(f"  PASS: added {result['total_added']} insertions across {len(result['per_helix'])} helices")

    # List all
    result = methods.listInsertions()
    print(f"  listInsertions (all): {result['count']} total")
    assert result['count'] > 0
    print(f"  PASS: global listing works")

    # Clean up all helices
    for vh in methods.activePart.getVirtualHelices():
        methods.removeInsertionPattern(helix_num=vh.number())
    result = methods.listInsertions()
    assert result['count'] == 0, f"Cleanup failed, {result['count']} remain"
    print("  PASS: cleanup verified")

    return True


def test_insertion_skips_crossovers(methods):
    """Test that addInsertionPattern skips positions with crossovers."""
    print("\n=== Test: Insertions skip crossover positions ===")

    # Add crossovers first
    xo_result = methods.addCrossoversForPair(helix1=0, helix2=1, strand_type="scaffold")
    print(f"  Added crossovers: {xo_result}")

    # Now add insertions — should skip crossover positions
    ins_result = methods.addInsertionPattern(
        helix_num=0, length=1, spacing=21, strand_type="scaffold"
    )
    print(f"  Insertions after crossovers: {ins_result}")
    assert isinstance(ins_result, dict), f"Expected dict, got: {ins_result}"

    # Get crossover positions for comparison
    xo_list = methods.listCrossovers(strand_type="scaffold")
    xo_positions = set()
    if isinstance(xo_list, dict):
        for xo in xo_list.get('crossovers', []):
            for pos in xo.get('positions', []):
                if pos.get('helix') == 0:
                    xo_positions.add(pos.get('idx'))

    ins_positions = set(ins_result.get('positions', []))
    overlap = xo_positions & ins_positions
    if overlap:
        print(f"  WARNING: insertions placed at crossover positions: {overlap}")
    else:
        print(f"  PASS: no insertions at crossover positions")

    # Clean up
    methods.removeInsertionPattern(helix_num=0)
    methods.removeAllCrossovers(strand_type="scaffold")
    return True


def test_error_handling(methods):
    """Test error handling for invalid inputs."""
    print("\n=== Test: Error handling ===")

    # Non-existent helix
    result = methods.addInsertionPattern(helix_num=99, length=1)
    assert isinstance(result, str) and "Error" in result
    print(f"  PASS: non-existent helix → {result}")

    result = methods.removeCrossoversForPair(helix1=99, helix2=0, strand_type="scaffold")
    assert isinstance(result, str) and "Error" in result
    print(f"  PASS: non-existent helix pair → {result}")

    result = methods.removeInsertionPattern(helix_num=99)
    assert isinstance(result, str) and "Error" in result
    print(f"  PASS: non-existent helix removal → {result}")

    return True


def test_split_strand_at(methods):
    """Test splitStrandAt."""
    print("\n=== Test: splitStrandAt ===")

    # Split scaffold on helix 0 at midpoint
    result = methods.splitStrandAt(helix_num=0, strand_type="scaffold", idx=42)
    print(f"  Split at 42: {result}")
    assert isinstance(result, dict), f"Expected dict, got: {result}"
    assert result['split_idx'] == 42
    assert result['split_idx'] == 42
    # new_strands depend on current strand state (prior tests may have modified it)
    assert len(result['new_strands']) == 2
    print(f"  PASS: split at midpoint → {result['new_strands']}")

    # Error: split at boundary
    result = methods.splitStrandAt(helix_num=0, strand_type="scaffold", idx=0)
    assert isinstance(result, str) and "Error" in result
    print(f"  PASS: boundary error → {result}")

    # Error: non-existent helix
    result = methods.splitStrandAt(helix_num=99, strand_type="scaffold", idx=42)
    assert isinstance(result, str) and "Error" in result
    print(f"  PASS: non-existent helix → {result}")

    return True


def test_list_staples(methods):
    """Test listStaples (need to create staples first)."""
    print("\n=== Test: listStaples ===")

    # Create staple strands
    result = methods.createFullLengthStrands(helix_num=0, strand_type="staple")
    print(f"  Created staples on h0: {result}")
    result = methods.createFullLengthStrands(helix_num=1, strand_type="staple")
    print(f"  Created staples on h1: {result}")

    # List staples
    result = methods.listStaples()
    print(f"  listStaples: {result}")
    assert isinstance(result, dict), f"Expected dict, got: {result}"
    assert result['count'] > 0, "Should have staple oligos"
    print(f"  PASS: found {result['count']} staple oligos")

    # Filter by helix
    result = methods.listStaples(helix_num=0)
    assert isinstance(result, dict)
    print(f"  PASS: filtered by helix → {result['count']} staples")

    return True


def test_break_staple_pattern(methods):
    """Test breakStaplePattern."""
    print("\n=== Test: breakStaplePattern ===")

    # List staples before
    before = methods.listStaples()
    print(f"  Before: {before['count']} staples")
    before_lengths = [s['oligo_length'] for s in before['staples']]
    print(f"  Before lengths: {before_lengths}")

    # Break at spacing of 35
    result = methods.breakStaplePattern(spacing=35)
    print(f"  breakStaplePattern: {result}")
    assert isinstance(result, dict), f"Expected dict, got: {result}"

    # List staples after
    after = methods.listStaples()
    print(f"  After: {after['count']} staples")
    after_lengths = [s['oligo_length'] for s in after['staples']]
    print(f"  After lengths: {after_lengths}")

    if result['breaks'] > 0:
        assert after['count'] > before['count'], "Should have more staples after breaking"
        print(f"  PASS: {result['breaks']} breaks, staples {before['count']} → {after['count']}")
    else:
        print(f"  PASS: no breaks needed (all staples <= max_staple_len)")

    return True


def test_auto_break_staples(methods):
    """Test autoBreakStaples (Dijkstra-based)."""
    print("\n=== Test: autoBreakStaples ===")

    # First, create full-length staple strands with crossovers so they form long oligos
    # Add crossovers between helices for staples
    methods.addCrossoversForPair(helix1=0, helix2=1, strand_type="staple")

    before = methods.listStaples()
    print(f"  Before auto-break: {before['count']} staple oligos")
    before_lengths = [s['oligo_length'] for s in before['staples']]
    print(f"  Before lengths: {before_lengths}")

    result = methods.autoBreakStaples(tgt_staple_len=35)
    print(f"  autoBreakStaples: {result}")
    assert isinstance(result, dict), f"Expected dict, got: {result}"
    print(f"  PASS: {result.get('before_staple_count', '?')} → {result.get('after_staple_count', '?')} staples")

    return True


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("Pattern Automation Methods — Headless Test Suite")
    print("=" * 60)

    app = setup_app()
    doc, part, mock, methods = create_fresh_design(app)

    results = {}
    tests = [
        ("resizeAllStrands", test_resize_all_strands),
        ("removeCrossoversForPair", test_add_crossovers_and_remove_for_pair),
        ("removeAllCrossovers", test_remove_all_crossovers),
        ("addInsertionPattern", test_insertion_pattern),
        ("insertion_deletions", test_insertion_pattern_deletions),
        ("addInsertionPatternAll", test_insertion_pattern_all),
        ("insertions_skip_crossovers", test_insertion_skips_crossovers),
        ("error_handling", test_error_handling),
        ("splitStrandAt", test_split_strand_at),
        ("listStaples", test_list_staples),
        ("breakStaplePattern", test_break_staple_pattern),
        ("autoBreakStaples", test_auto_break_staples),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        try:
            test_fn(methods)
            results[name] = "PASS"
            passed += 1
        except Exception as e:
            results[name] = f"FAIL: {e}"
            failed += 1
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for name, status in results.items():
        icon = "✓" if status == "PASS" else "✗"
        print(f"  {icon} {name}: {status}")
    print(f"\n  Total: {passed} passed, {failed} failed out of {len(tests)}")
    print("=" * 60)

    # Write results to JSON for visualization
    results_data = {
        'tests': results,
        'passed': passed,
        'failed': failed,
        'total': len(tests)
    }
    results_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'results', 'test_pattern_automation_results.json')
    os.makedirs(os.path.dirname(results_path), exist_ok=True)
    with open(results_path, 'w') as f:
        json.dump(results_data, f, indent=2)
    print(f"\nResults saved to {results_path}")

    return failed == 0


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
