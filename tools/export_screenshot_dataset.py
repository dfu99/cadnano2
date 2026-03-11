#!/usr/bin/env python3
"""
export_screenshot_dataset.py

Convert the cadnano screenshot library into a HuggingFace dataset
with (before_image, instruction, after_image) triples for vision-language
model training (SFT).

Usage:
    python tools/export_screenshot_dataset.py [--output results/hf_screenshot_dataset]

    # Then load:
    from datasets import load_from_disk
    ds = load_from_disk("results/hf_screenshot_dataset")
    print(ds[0])  # {'before_image': <PIL>, 'after_image': <PIL>, 'instruction': '...', ...}
"""

import argparse
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SCREENSHOTS_DIR = os.path.join(PROJECT_ROOT, "screenshots")


def collect_examples(screenshots_dir: str) -> list:
    """Walk screenshot directories and collect training examples."""
    examples = []
    for entry in sorted(os.listdir(screenshots_dir)):
        entry_path = os.path.join(screenshots_dir, entry)
        if not os.path.isdir(entry_path):
            continue

        before_path = os.path.join(entry_path, "before.png")
        after_path = os.path.join(entry_path, "after.png")
        meta_path = os.path.join(entry_path, "metadata.json")

        if not all(os.path.exists(p) for p in [before_path, after_path, meta_path]):
            print(f"  Skipping {entry}: missing files")
            continue

        with open(meta_path) as f:
            meta = json.load(f)

        examples.append({
            "operation_id": entry,
            "before_image": before_path,
            "after_image": after_path,
            "instruction": meta.get("natural_language", ""),
            "operation": meta.get("operation", ""),
            "description": meta.get("description", ""),
            "result": meta.get("result", ""),
            "params": json.dumps(meta.get("params", {})),
        })

    return examples


def categorize_operation(operation: str) -> str:
    """Map operation names to high-level categories."""
    if "Crossover" in operation or "crossover" in operation:
        if "move" in operation.lower():
            return "crossover_move"
        elif "remove" in operation.lower() or "delete" in operation.lower():
            return "crossover_remove"
        elif "add" in operation.lower() or "create" in operation.lower():
            return "crossover_add"
        return "crossover_other"
    elif "resize" in operation.lower() or "Resize" in operation:
        return "strand_resize"
    elif "Insertion" in operation or "insertion" in operation:
        return "insertion"
    elif "break" in operation.lower() or "split" in operation.lower() or "Break" in operation:
        return "strand_break"
    return "other"


def main():
    parser = argparse.ArgumentParser(
        description="Export screenshot library as HuggingFace dataset"
    )
    parser.add_argument("--screenshots", default=SCREENSHOTS_DIR,
                        help="Screenshots directory")
    parser.add_argument("--output", default=os.path.join(PROJECT_ROOT, "results", "hf_screenshot_dataset"),
                        help="Output directory")
    parser.add_argument("--split", type=float, default=0.0,
                        help="Validation split fraction (0 = no split)")
    args = parser.parse_args()

    print(f"Collecting examples from: {args.screenshots}")
    examples = collect_examples(args.screenshots)
    print(f"  Found {len(examples)} examples")

    if not examples:
        print("No examples found. Run generate_screenshot_library.py first.")
        sys.exit(1)

    # Add categories
    for ex in examples:
        ex["category"] = categorize_operation(ex["operation"])

    # Print stats
    from collections import Counter
    cat_counts = Counter(ex["category"] for ex in examples)
    op_counts = Counter(ex["operation"] for ex in examples)

    print(f"\nBy category:")
    for cat, count in cat_counts.most_common():
        print(f"  {cat}: {count}")
    print(f"\nBy operation:")
    for op, count in op_counts.most_common():
        print(f"  {op}: {count}")

    # Build HuggingFace dataset
    try:
        from datasets import Dataset, DatasetDict, Features, Value, Image
    except ImportError:
        print("\nERROR: 'datasets' package not installed.")
        print("Install: pip install datasets Pillow")
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
    })

    ds = Dataset.from_list(examples, features=features)

    if args.split > 0:
        split = ds.train_test_split(test_size=args.split, seed=42)
        dataset = DatasetDict({"train": split["train"], "validation": split["test"]})
        print(f"\n  Train: {len(split['train'])}, Validation: {len(split['test'])}")
    else:
        dataset = ds

    # Save
    os.makedirs(args.output, exist_ok=True)

    if isinstance(dataset, DatasetDict):
        dataset.save_to_disk(args.output)
    else:
        dataset.save_to_disk(args.output)
    print(f"\n  Arrow dataset saved → {args.output}")

    # Also save parquet
    parquet_path = os.path.join(args.output, "data.parquet")
    if isinstance(dataset, DatasetDict):
        dataset["train"].to_parquet(parquet_path)
    else:
        dataset.to_parquet(parquet_path)
    print(f"  Parquet saved → {parquet_path}")

    # Summary card
    card_path = os.path.join(args.output, "README.md")
    with open(card_path, "w") as f:
        f.write("---\n")
        f.write("dataset_info:\n")
        f.write(f"  num_examples: {len(examples)}\n")
        f.write("  features:\n")
        f.write("    - name: before_image\n      dtype: image\n")
        f.write("    - name: after_image\n      dtype: image\n")
        f.write("    - name: instruction\n      dtype: string\n")
        f.write("    - name: operation\n      dtype: string\n")
        f.write("    - name: category\n      dtype: string\n")
        f.write("task_categories:\n  - image-to-image\n  - visual-question-answering\n")
        f.write("---\n\n")
        f.write("# cadnano Screenshot Training Dataset\n\n")
        f.write(f"**{len(examples)} before/after pairs** of DNA nanostructure design operations.\n\n")
        f.write("Each example contains:\n")
        f.write("- `before_image`: Screenshot before the operation\n")
        f.write("- `after_image`: Screenshot after the operation\n")
        f.write("- `instruction`: Natural language description of what to do\n")
        f.write("- `operation`: Method name that was called\n")
        f.write("- `category`: High-level operation category\n\n")
        f.write("## Categories\n\n")
        for cat, count in cat_counts.most_common():
            f.write(f"- **{cat}**: {count} examples\n")
    print(f"  Dataset card → {card_path}")

    print(f"\nDone. Load with:")
    print(f"  from datasets import load_from_disk")
    print(f"  ds = load_from_disk('{args.output}')")
    print(f"  print(ds[0]['instruction'])  # natural language task")
    print(f"  ds[0]['before_image'].show()  # PIL Image")


if __name__ == "__main__":
    main()
