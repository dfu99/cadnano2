#!/usr/bin/env python3
"""
export_hf_dataset.py

Convert cadnano training data (JSONL) to HuggingFace datasets format.
Produces both Arrow (datasets.Dataset) and Parquet formats for fine-tuning.

Usage:
    python tools/export_hf_dataset.py \
        --input ~/.cadnano2/training_data.jsonl \
        --output ~/.cadnano2/hf_dataset \
        --format all

    # Then use in training:
    from datasets import load_from_disk
    ds = load_from_disk("~/.cadnano2/hf_dataset")
"""

import argparse
import json
import os
import sys
from collections import Counter


def load_jsonl(path: str) -> list:
    examples = []
    with open(os.path.expanduser(path)) as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def messages_to_chatml(messages: list) -> str:
    """Convert OpenAI messages format to ChatML text (Qwen-style)."""
    parts = []
    for msg in messages:
        role = msg["role"]
        if role == "assistant" and msg.get("tool_calls"):
            tc = msg["tool_calls"][0]
            fn = tc["function"]
            content = f'<tool_call>\n{{"name": "{fn["name"]}", "arguments": {fn["arguments"]}}}\n</tool_call>'
        elif role == "tool":
            role = "user"
            content = f"<tool_result>{msg['content']}</tool_result>"
        else:
            content = msg.get("content", "")
        if content:
            parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
    return "\n".join(parts)


def extract_features(example: dict) -> dict:
    """Extract structured features from a training example."""
    messages = example.get("messages", [])
    metadata = example.get("metadata", {})

    # Extract user task
    task = ""
    for msg in messages:
        if msg["role"] == "user" and not msg.get("content", "").startswith("<tool_result>"):
            task = msg["content"]
            break

    # Count tool calls
    tool_calls = []
    for msg in messages:
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            tc = msg["tool_calls"][0]
            tool_calls.append(tc["function"]["name"])

    # Extract final assistant response
    final_response = ""
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            final_response = msg["content"]
            break

    return {
        "messages_json": json.dumps(messages),
        "text": messages_to_chatml(messages),
        "task": task,
        "tool_call_names": json.dumps(tool_calls),
        "num_tool_calls": len(tool_calls),
        "num_messages": len(messages),
        "final_response": final_response,
        "source": metadata.get("source", ""),
        "helix_count": metadata.get("helix_count", 0),
        "action_count": metadata.get("action_count", 0),
        "crossover_count": metadata.get("crossover_count", 0),
        "part_size": metadata.get("part_size", 0),
    }


def print_stats(features_list: list):
    """Print dataset statistics."""
    print("\n" + "=" * 60)
    print("DATASET STATISTICS")
    print("=" * 60)
    print(f"  Total examples: {len(features_list)}")

    helix_counts = Counter(f["helix_count"] for f in features_list)
    print("\n  By helix count:")
    for hc in sorted(helix_counts):
        print(f"    {hc}-helix: {helix_counts[hc]}")

    tool_counts = Counter()
    for f in features_list:
        for tc in json.loads(f["tool_call_names"]):
            tool_counts[tc] += 1
    print(f"\n  Tool call distribution:")
    for tool, count in tool_counts.most_common():
        print(f"    {tool}: {count}")

    action_counts = [f["num_tool_calls"] for f in features_list]
    text_lengths = [len(f["text"]) for f in features_list]
    print(f"\n  Actions per example: min={min(action_counts)}, "
          f"max={max(action_counts)}, avg={sum(action_counts)/len(action_counts):.1f}")
    print(f"  Text length (chars): min={min(text_lengths)}, "
          f"max={max(text_lengths)}, avg={sum(text_lengths)/len(text_lengths):.0f}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Convert cadnano JSONL to HuggingFace datasets format"
    )
    parser.add_argument("--input", required=True,
                        help="Input JSONL file")
    parser.add_argument("--output", default="~/.cadnano2/hf_dataset",
                        help="Output directory for HuggingFace dataset")
    parser.add_argument("--format", choices=["arrow", "parquet", "all"],
                        default="all", help="Output format(s)")
    parser.add_argument("--stats-only", action="store_true",
                        help="Only print statistics, don't save")
    parser.add_argument("--split", type=float, default=0.0,
                        help="Fraction for validation split (0 = no split)")
    args = parser.parse_args()

    print(f"Loading: {args.input}")
    raw = load_jsonl(args.input)
    print(f"  {len(raw)} examples loaded")

    features_list = [extract_features(ex) for ex in raw]
    print_stats(features_list)

    if args.stats_only:
        return

    try:
        from datasets import Dataset, DatasetDict
    except ImportError:
        print("\nERROR: 'datasets' package not installed.")
        print("Install: pip install datasets")
        sys.exit(1)

    ds = Dataset.from_list(features_list)

    if args.split > 0:
        split = ds.train_test_split(test_size=args.split, seed=42)
        dataset = DatasetDict({
            "train": split["train"],
            "validation": split["test"]
        })
        print(f"\n  Train: {len(split['train'])}, Validation: {len(split['test'])}")
    else:
        dataset = ds

    output_dir = os.path.expanduser(args.output)
    os.makedirs(output_dir, exist_ok=True)

    if args.format in ("arrow", "all"):
        arrow_path = output_dir
        if isinstance(dataset, DatasetDict):
            dataset.save_to_disk(arrow_path)
        else:
            dataset.save_to_disk(arrow_path)
        print(f"\n  Arrow dataset saved → {arrow_path}")

    if args.format in ("parquet", "all"):
        parquet_path = os.path.join(output_dir, "data.parquet")
        if isinstance(dataset, DatasetDict):
            dataset["train"].to_parquet(parquet_path)
        else:
            dataset.to_parquet(parquet_path)
        print(f"  Parquet saved → {parquet_path}")

    # Also save the raw text-only format for SFTTrainer
    text_path = os.path.join(output_dir, "training_texts.jsonl")
    with open(text_path, "w") as f:
        for feat in features_list:
            f.write(json.dumps({"text": feat["text"]}) + "\n")
    print(f"  Text-only JSONL → {text_path}")

    print(f"\nDone. Load with:")
    print(f"  from datasets import load_from_disk")
    print(f"  ds = load_from_disk('{output_dir}')")


if __name__ == "__main__":
    main()
