#!/usr/bin/env python3
"""
augment_instructions.py

Generate paraphrased natural language instructions for each screenshot pair.
Uses template-based augmentation to create multiple instruction variants
per operation, expanding the training dataset for VLM SFT.

Each original instruction gets 3-5 paraphrases that vary:
  - Formality (casual vs technical)
  - Specificity (with/without exact indices)
  - Phrasing (imperative, request, description)

Usage:
    python tools/augment_instructions.py [--output results/hf_augmented_dataset]
"""

import json
import os
import random
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, "screenshots")

random.seed(42)

# ---- Paraphrase templates by operation type ----

def _move_paraphrases(params, original):
    """Generate paraphrases for moveCrossover operations."""
    delta = params.get("delta", 1)
    helix = params.get("helix1", 0)
    idx = params.get("idx", 0)
    direction = "right" if delta > 0 else "left"
    n = abs(delta)

    return [
        original,
        f"Shift the crossover {n} {'base' if n == 1 else 'bases'} to the {direction}",
        f"Move crossover at position {idx} on helix {helix} {direction} by {n}bp",
        f"Nudge the crossover {direction} {n} positions",
        f"Reposition the scaffold crossover {n} bases {direction}ward",
    ]


def _remove_xover_paraphrases(params, original):
    """Generate paraphrases for removeCrossover / removeCrossoversForPair."""
    h1 = params.get("helix1", 0)
    h2 = params.get("helix2", 1)
    st = params.get("strand_type", "scaffold")

    variants = [
        original,
        f"Delete the {st} crossover between helices {h1} and {h2}",
        f"Remove the crossover connecting helix {h1} to helix {h2}",
        f"Get rid of the {st} crossover between h{h1} and h{h2}",
    ]

    if "all" in original.lower() or params.get("n_helices"):
        variants.append(f"Clear all {st} crossovers between helix {h1} and helix {h2}")
        variants.append(f"Strip {st} crossovers from the helix {h1}-{h2} pair")

    return variants


def _create_xover_paraphrases(params, original):
    """Generate paraphrases for createCrossover."""
    h1 = params.get("helix1", 0)
    h2 = params.get("helix2", 1)
    idx = params.get("idx", 0)
    st = params.get("strand_type", "scaffold")

    return [
        original,
        f"Add a {st} crossover at index {idx} between helix {h1} and helix {h2}",
        f"Place a crossover connecting helices {h1} and {h2} at position {idx}",
        f"Create a new {st} crossover at bp {idx} between h{h1} and h{h2}",
        f"Insert a {st} crossover between helix {h1} and {h2} at index {idx}",
    ]


def _add_batch_xover_paraphrases(params, original):
    """Generate paraphrases for addCrossoversForPair / addAllNeighborCrossovers."""
    st = params.get("strand_type", "scaffold")
    n_helices = params.get("n_helices")

    variants = [original]

    if "all neighbor" in original.lower() or (n_helices and "neighbor" in original.lower()):
        variants.extend([
            f"Wire up {st} crossovers across all neighboring helix pairs",
            f"Add {st} crossovers between every pair of adjacent helices",
            f"Connect all neighbor pairs with {st} crossovers",
            f"Place {st} crossovers on all available neighbor pairs",
        ])
    else:
        h1 = params.get("helix1", 0)
        h2 = params.get("helix2", 1)
        # Extract count from original instruction if present
        import re as _re
        count_match = _re.search(r'(\d+) evenly', original)
        count_str = f"{count_match.group(1)} " if count_match else ""
        variants.extend([
            f"Add {count_str}evenly spaced {st} crossovers between helix {h1} and helix {h2}",
            f"Place {count_str}{st} crossovers at regular intervals between h{h1} and h{h2}",
            f"Wire helix {h1} to helix {h2} with {count_str}evenly distributed {st} crossovers",
            f"Create {count_str}regularly-spaced {st} crossovers between helices {h1} and {h2}",
        ])

    if "both" in original.lower() or st == "both":
        variants.append("Add both scaffold and staple crossovers to all pairs")
        variants.append("Fully wire all helix pairs with scaffold and staple crossovers")

    return variants


def _remove_all_xover_paraphrases(params, original):
    """Generate paraphrases for removeAllCrossovers."""
    st = params.get("strand_type", "scaffold")
    return [
        original,
        f"Remove every {st} crossover in the entire design",
        f"Clear all {st} crossovers from the design",
        f"Strip all {st} crossovers",
        f"Delete all {st} crossover connections",
    ]


def _resize_paraphrases(params, original):
    """Generate paraphrases for resizeAllStrands."""
    st = params.get("strand_type", "scaffold")
    delta = params.get("delta", 0)
    action = "extend" if delta > 0 else "shrink"
    n = abs(delta)

    variants = [
        original,
        f"{'Lengthen' if delta > 0 else 'Shorten'} all {st} strands by {n} bases",
        f"Resize {st} strands: {'+' if delta > 0 else '-'}{n}bp",
        f"{'Grow' if delta > 0 else 'Trim'} every {st} strand by {n} bases",
        f"Bulk {action} all {st} strands by {n}bp",
    ]

    if params.get("n_helices"):
        variants.append(f"{action.capitalize()} all {st} strands by {n} bases across {params['n_helices']} helices")

    return variants


def _insertion_paraphrases(params, original):
    """Generate paraphrases for addInsertionPattern / addInsertionPatternAll."""
    length = params.get("length", 1)
    spacing = params.get("spacing", 21)
    helix = params.get("helix_num")
    insert_type = "deletions" if length < 0 else "insertions"

    variants = [original]

    if helix is not None:
        variants.extend([
            f"Add {abs(length)}-base {insert_type} every {spacing} positions on helix {helix}",
            f"Place {insert_type} at {spacing}bp intervals along helix {helix}",
            f"Pattern helix {helix} with {insert_type} every {spacing} bases",
        ])
    else:
        variants.extend([
            f"Add {abs(length)}-base {insert_type} every {spacing} bases on all helices",
            f"Apply a {insert_type} pattern ({spacing}bp spacing) across the entire design",
            f"Pattern all helices with {insert_type} at {spacing}-base intervals",
        ])

    if params.get("n_helices"):
        variants.append(f"Add {insert_type} pattern across all {params['n_helices']} helices")

    return variants


def _strand_break_paraphrases(params, original):
    """Generate paraphrases for splitStrandAt / breakStaplePattern / autoBreakStaples."""
    operation = params.get("_operation", "")

    variants = [original]

    if "auto" in operation.lower():
        variants.extend([
            "Optimize staple break positions automatically",
            "Run the auto-break algorithm on all staple strands",
            "Let the Dijkstra optimizer find the best staple break points",
            "Auto-break staples into optimal lengths",
        ])
    elif "split" in operation.lower():
        helix = params.get("helix_num", 0)
        idx = params.get("idx", 0)
        variants.extend([
            f"Split the strand on helix {helix} at index {idx}",
            f"Break the staple at position {idx} on helix {helix}",
            f"Cut the strand at bp {idx} on helix {helix}",
        ])
    elif "pattern" in operation.lower():
        spacing = params.get("spacing", 21)
        variants.extend([
            f"Break staples at regular {spacing}-base intervals",
            f"Split all staples every {spacing} bases",
            f"Apply interval-based staple breaks at {spacing}bp spacing",
        ])

    return variants


def get_paraphrases(operation, params, original):
    """Route to the appropriate paraphrase generator."""
    # Add operation name to params for strand_break handler
    params_with_op = dict(params)
    params_with_op["_operation"] = operation

    if operation == "moveCrossover":
        return _move_paraphrases(params, original)
    elif operation in ("removeCrossover", "removeCrossoversForPair"):
        return _remove_xover_paraphrases(params, original)
    elif operation == "createCrossover":
        return _create_xover_paraphrases(params, original)
    elif operation in ("addCrossoversForPair", "addAllNeighborCrossovers"):
        return _add_batch_xover_paraphrases(params, original)
    elif operation == "removeAllCrossovers":
        return _remove_all_xover_paraphrases(params, original)
    elif operation == "resizeAllStrands":
        return _resize_paraphrases(params, original)
    elif operation in ("addInsertionPattern", "addInsertionPatternAll"):
        return _insertion_paraphrases(params, original)
    elif operation in ("splitStrandAt", "breakStaplePattern", "autoBreakStaples"):
        return _strand_break_paraphrases(params_with_op, original)
    else:
        # Fallback: just return the original
        return [original]


def collect_and_augment(screenshots_dir):
    """Collect examples and generate paraphrased instructions."""
    examples = []

    for entry in sorted(os.listdir(screenshots_dir)):
        entry_path = os.path.join(screenshots_dir, entry)
        if not os.path.isdir(entry_path):
            continue

        before_path = os.path.join(entry_path, "before.png")
        after_path = os.path.join(entry_path, "after.png")
        meta_path = os.path.join(entry_path, "metadata.json")

        if not all(os.path.exists(p) for p in [before_path, after_path, meta_path]):
            continue

        with open(meta_path) as f:
            meta = json.load(f)

        operation = meta.get("operation", "")
        params = meta.get("params", {})
        original_instruction = meta.get("natural_language", "")

        paraphrases = get_paraphrases(operation, params, original_instruction)

        for i, instruction in enumerate(paraphrases):
            examples.append({
                "operation_id": entry,
                "before_image": before_path,
                "after_image": after_path,
                "instruction": instruction,
                "operation": operation,
                "description": meta.get("description", ""),
                "result": meta.get("result", ""),
                "params": json.dumps(params),
                "is_paraphrase": i > 0,
                "original_instruction": original_instruction,
            })

    return examples


def categorize(operation):
    if "Crossover" in operation or "crossover" in operation:
        if "move" in operation.lower():
            return "crossover_move"
        elif "remove" in operation.lower() or "delete" in operation.lower():
            return "crossover_remove"
        elif "add" in operation.lower() or "create" in operation.lower():
            return "crossover_add"
        return "crossover_other"
    elif "resize" in operation.lower():
        return "strand_resize"
    elif "Insertion" in operation or "insertion" in operation:
        return "insertion"
    elif "break" in operation.lower() or "split" in operation.lower():
        return "strand_break"
    return "other"


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Augment screenshot dataset with paraphrased instructions")
    parser.add_argument("--screenshots", default=SCREENSHOTS_DIR)
    parser.add_argument("--output", default=os.path.join(PROJECT_ROOT, "results", "hf_augmented_dataset"))
    args = parser.parse_args()

    print(f"Collecting and augmenting from: {args.screenshots}")
    examples = collect_and_augment(args.screenshots)

    for ex in examples:
        ex["category"] = categorize(ex["operation"])

    originals = sum(1 for e in examples if not e["is_paraphrase"])
    paraphrases = sum(1 for e in examples if e["is_paraphrase"])
    print(f"  Original examples: {originals}")
    print(f"  Paraphrased: {paraphrases}")
    print(f"  Total: {len(examples)} ({paraphrases/originals:.1f}x augmentation)")

    # Stats
    from collections import Counter
    cat_counts = Counter(ex["category"] for ex in examples)
    print(f"\nBy category:")
    for cat, count in cat_counts.most_common():
        print(f"  {cat}: {count}")

    # Build HuggingFace dataset
    try:
        from datasets import Dataset, Features, Value, Image
    except ImportError:
        print("ERROR: pip install datasets Pillow")
        sys.exit(1)

    features = Features({
        "operation_id": Value("string"),
        "before_image": Image(),
        "after_image": Image(),
        "instruction": Value("string"),
        "operation": Value("string"),
        "description": Value("string"),
        "result": Value("string"),
        "params": Value("string"),
        "category": Value("string"),
        "is_paraphrase": Value("bool"),
        "original_instruction": Value("string"),
    })

    ds = Dataset.from_list(examples, features=features)

    os.makedirs(args.output, exist_ok=True)
    ds.save_to_disk(args.output)
    print(f"\n  Arrow dataset → {args.output}")

    parquet_path = os.path.join(args.output, "data.parquet")
    ds.to_parquet(parquet_path)
    print(f"  Parquet → {parquet_path}")

    print(f"\nDone. Load with:")
    print(f"  from datasets import load_from_disk")
    print(f"  ds = load_from_disk('{args.output}')")
    print(f"  # {len(examples)} examples ({originals} unique images × ~{len(examples)//originals} instructions each)")


if __name__ == "__main__":
    main()
