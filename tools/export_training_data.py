#!/usr/bin/env python3
"""
export_training_data.py

Converts cadnano expert JSON designs into JSONL training data for LLM fine-tuning.
Run this outside cadnano — no GUI required.

Usage:
    python tools/export_training_data.py agent-6hb-scaffoldonly.json \
        --task "Create a 6-helix bundle with 105bp scaffold routing" \
        --output ~/.cadnano2/training_data.jsonl

Then fine-tune with Unsloth:
    pip install unsloth
    python tools/finetune_unsloth.py ~/.cadnano2/training_data.jsonl

Or evaluate the extracted trajectory:
    python tools/export_training_data.py agent-6hb-scaffoldonly.json --show-actions
"""

import argparse
import json
import os
import sys


def extract_trajectory(json_path: str, task: str = "") -> dict:
    """
    Parse a cadnano JSON and produce a sequence of agentmethods calls
    that recreates the design from scratch.

    Returns dict with 'actions' (list of [method_name, params]).
    """
    json_path = os.path.expanduser(json_path)
    with open(json_path) as f:
        data = json.load(f)

    vstrands = data.get("vstrands", [])
    if not vstrands:
        raise ValueError(f"No vstrands in {json_path}")

    part_size = len(vstrands[0]["scaf"])
    positions = [[vs["row"], vs["col"]] for vs in sorted(vstrands, key=lambda v: v["num"])]

    def _has_content(strand_data):
        return any(any(x != -1 for x in s) for s in strand_data)

    has_scaf = any(_has_content(vs["scaf"]) for vs in vstrands)
    has_stap = any(_has_content(vs["stap"]) for vs in vstrands)

    actions = []

    # Step 1: create helices with strands
    for stype in (["scaffold"] if has_scaf else []) + (["staple"] if has_stap else []):
        actions.append(["createHelicesWithStrands", {
            "positions": positions,
            "strand_type": stype,
            "length": part_size - 1
        }])

    # Step 2: extract half-crossovers (deduplicated, sorted by position)
    for stype, key in [("scaffold", "scaf"), ("staple", "stap")]:
        if (stype == "scaffold" and not has_scaf) or (stype == "staple" and not has_stap):
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
                    "helix1": num, "idx1": i,
                    "helix2": next_vh, "idx2": next_idx,
                    "sort_idx": min(i, next_idx)
                })

        xovers.sort(key=lambda x: x["sort_idx"])
        for xo in xovers:
            actions.append(["createHalfCrossover", {
                "helix1": xo["helix1"], "idx1": xo["idx1"],
                "helix2": xo["helix2"], "idx2": xo["idx2"],
                "strand_type": stype
            }])

    n_xovers = sum(1 for a in actions if a[0] == "createHalfCrossover")
    return {
        "source_file": json_path,
        "task": task or f"Recreate design from {os.path.basename(json_path)}",
        "part_size": part_size,
        "helix_count": len(vstrands),
        "strand_types": (["scaffold"] if has_scaf else []) + (["staple"] if has_stap else []),
        "crossover_count": n_xovers,
        "action_count": len(actions),
        "actions": actions
    }


SYSTEM_PROMPT = (
    "You are a cadnano DNA nanostructure design assistant. "
    "Use the provided tools to build the requested design step by step. "
    "Always start with createHelicesWithStrands, then add crossovers."
)


def to_training_example(traj: dict) -> dict:
    """
    Convert an extracted trajectory into a training example in the
    OpenAI messages format (compatible with Unsloth / LlamaFactory).

    Format: system → user → (assistant tool_call → tool result) × N → assistant summary
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": traj["task"]}
    ]

    for i, (method_name, params) in enumerate(traj["actions"]):
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "type": "function",
                "id": f"call_{i}_{method_name}",
                "function": {
                    "name": method_name,
                    "arguments": json.dumps(params)
                }
            }]
        })
        messages.append({
            "role": "tool",
            "tool_call_id": f"call_{i}_{method_name}",
            "content": "Success"
        })

    messages.append({
        "role": "assistant",
        "content": (
            f"Done. Built a {traj['helix_count']}-helix design with "
            f"{traj['crossover_count']} scaffold crossovers."
        )
    })

    return {
        "messages": messages,
        "metadata": {
            "source": traj["source_file"],
            "helix_count": traj["helix_count"],
            "action_count": traj["action_count"],
            "crossover_count": traj["crossover_count"],
            "part_size": traj["part_size"]
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Export cadnano expert designs as LLM training data")
    parser.add_argument("json_files", nargs="+", help="Cadnano JSON files to process")
    parser.add_argument("--task", default="", help="Task description (used as user message)")
    parser.add_argument("--output", default="", help="Output JSONL path (default: print to stdout)")
    parser.add_argument("--show-actions", action="store_true", help="Print extracted actions and exit")
    args = parser.parse_args()

    for json_path in args.json_files:
        print(f"Processing: {json_path}", file=sys.stderr)
        try:
            traj = extract_trajectory(json_path, args.task)
        except Exception as e:
            print(f"  ERROR: {e}", file=sys.stderr)
            continue

        if args.show_actions:
            print(f"\n{'='*60}")
            print(f"Source: {traj['source_file']}")
            print(f"Task:   {traj['task']}")
            print(f"Helices: {traj['helix_count']}, Part size: {traj['part_size']}bp")
            print(f"Actions ({traj['action_count']} total, {traj['crossover_count']} crossovers):")
            for i, (method, params) in enumerate(traj["actions"]):
                print(f"  {i+1:2d}. {method}({params})")
            continue

        example = to_training_example(traj)
        line = json.dumps(example)

        if args.output:
            output_path = os.path.expanduser(args.output)
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            with open(output_path, "a") as f:
                f.write(line + "\n")
            print(f"  Appended to {output_path} ({traj['action_count']} actions)", file=sys.stderr)
        else:
            print(line)


if __name__ == "__main__":
    main()
