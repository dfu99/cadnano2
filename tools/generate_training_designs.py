#!/usr/bin/env python3
"""
generate_training_designs.py

Programmatically generate valid cadnano honeycomb designs for LLM fine-tuning.
No cadnano GUI required. Outputs JSONL in the same format as export_training_data.py.

Designs generated (by default):
  - 2-helix bundles: 5 lengths × 6 starting positions = 30 examples
  - Additional expert JSON files (via --expert flag)

Usage:
    # Generate 2HB designs:
    python tools/generate_training_designs.py \\
        --output ~/.cadnano2/training_data.jsonl

    # Include expert designs too:
    python tools/generate_training_designs.py \\
        --output ~/.cadnano2/training_data.jsonl \\
        --expert agent-6hb-scaffoldonly.json

    # Check what will be generated:
    python tools/generate_training_designs.py --stats

    # Then fine-tune:
    python tools/finetune_unsloth.py --data ~/.cadnano2/training_data.jsonl

Design validity:
  - Scaffold forms a single closed loop through all helices
  - Even-parity helices: scaffold 5'->3' goes left-to-right (increasing index)
  - Odd-parity helices:  scaffold 5'->3' goes right-to-left (decreasing index)
  - Half-crossovers at helix endpoints connect the loop
"""

import argparse
import json
import os
import sys


SYSTEM_PROMPT = (
    "You are a cadnano DNA nanostructure design assistant. "
    "Use the provided tools to build the requested design step by step. "
    "Always start with createHelicesWithStrands, then add crossovers."
)

# Default lengths to generate (multiples of 21 = valid honeycomb scaffold lengths)
DEFAULT_LENGTHS = [42, 63, 84, 105, 126]

# Starting positions (row, col) for the first helix of each 2HB.
# Second helix is placed at (row, col+1).
# Uses varied positions to teach position-invariance.
TWO_HB_STARTS = [
    (0, 0),
    (0, 2),
    (0, 4),
    (2, 0),
    (2, 2),
    (4, 0),
]


# ─── Honeycomb helpers ────────────────────────────────────────────────────────

def is_even_parity(row: int, col: int) -> bool:
    """Cadnano honeycomb parity: even iff (row%2 == col%2).

    Even-parity helices carry scaffold 5'->3' left-to-right (increasing index).
    Odd-parity helices carry scaffold 5'->3' right-to-left (decreasing index).
    """
    return (row % 2) == (col % 2)


def make_vstrand(row: int, col: int, num: int, scaf: list, stap: list, length: int) -> dict:
    return {
        "row": row, "col": col, "num": num,
        "scaf": scaf,
        "stap": stap,
        "loop":     [0] * length,
        "skip":     [0] * length,
        "scafLoop": 0,
        "stapLoop": 0,
        "stap_colors": [],
        "scaf_colors": [],
    }


# ─── 2-Helix Bundle generator ─────────────────────────────────────────────────

def generate_2hb(row: int = 0, col: int = 0, length: int = 84) -> dict:
    """Generate a 2-helix bundle cadnano JSON dict.

    Helices:
        H0 at (row, col)
        H1 at (row, col+1)

    Scaffold routing (closed loop):
        Even helix goes L->R.  Odd helix goes R->L.
        Half-crossovers connect them at positions 0 (left) and length-1 (right).

    Returns a cadnano JSON dict (not serialised) with an extra '_task' key
    containing a natural-language task description.
    """
    L = length
    h0_even = is_even_parity(row, col)

    # Assign even / odd roles (helix numbers stay 0 and 1)
    if h0_even:
        en, od = 0, 1
        en_pos = (row, col)
        od_pos = (row, col + 1)
    else:
        en, od = 1, 0
        en_pos = (row, col + 1)
        od_pos = (row, col)

    # ── Even helix scaffold (5'->3' = L->R, increasing index) ─────────────
    # Left end  (pos 0):   5' enters from odd helix via half-crossover
    # Right end (pos L-1): 3' exits  to  odd helix via half-crossover
    scaf_en = [[-1, -1, -1, -1] for _ in range(L)]
    scaf_en[0]     = [od, 0,   en, 1]
    for i in range(1, L - 1):
        scaf_en[i] = [en, i-1, en, i+1]
    scaf_en[L - 1] = [en, L-2, od, L-1]

    # ── Odd helix scaffold (5'->3' = R->L, decreasing index) ──────────────
    # Right end (pos L-1): 5' enters from even helix via half-crossover
    # Left end  (pos 0):   3' exits  to  even helix via half-crossover
    scaf_od = [[-1, -1, -1, -1] for _ in range(L)]
    scaf_od[L - 1] = [en, L-1, od, L-2]
    for i in range(L - 2, 0, -1):
        scaf_od[i] = [od, i+1, od, i-1]
    scaf_od[0]     = [od, 1,   en, 0]

    stap_en = [[-1, -1, -1, -1] for _ in range(L)]
    stap_od = [[-1, -1, -1, -1] for _ in range(L)]

    vstrands = [None, None]
    vstrands[en] = make_vstrand(en_pos[0], en_pos[1], en, scaf_en, stap_en, L)
    vstrands[od] = make_vstrand(od_pos[0], od_pos[1], od, scaf_od, stap_od, L)

    task = (
        f"Create a 2-helix bundle with a {L}bp scaffold strand. "
        f"Place the helices at row {row}, columns {col} and {col + 1}."
    )

    return {
        "name":     f"2hb_r{row}c{col}_L{L}",
        "vstrands": vstrands,
        "_task":    task,
    }


# ─── Trajectory extraction (mirrors export_training_data.py) ─────────────────

def extract_trajectory(data: dict, task: str = "") -> dict:
    """Parse a cadnano JSON dict and return the action sequence to recreate it.

    Actions produced:
      1. createHelicesWithStrands (once per strand type present)
      2. createHalfCrossover     (once per unique half-crossover)
    """
    vstrands = data.get("vstrands", [])
    if not vstrands:
        raise ValueError("No vstrands in design")

    part_size = len(vstrands[0]["scaf"])
    positions = [
        [vs["row"], vs["col"]]
        for vs in sorted(vstrands, key=lambda v: v["num"])
    ]

    def _has_content(strand_data):
        return any(any(x != -1 for x in s) for s in strand_data)

    has_scaf = any(_has_content(vs["scaf"]) for vs in vstrands)
    has_stap = any(_has_content(vs["stap"]) for vs in vstrands)

    actions = []

    # Step 1: createHelicesWithStrands for each strand type present
    for stype in (["scaffold"] if has_scaf else []) + (["staple"] if has_stap else []):
        actions.append(["createHelicesWithStrands", {
            "positions":   positions,
            "strand_type": stype,
            "length":      part_size - 1,
        }])

    # Step 2: extract deduplicated half-crossovers in position order
    for stype, key in [("scaffold", "scaf"), ("staple", "stap")]:
        if stype == "scaffold" and not has_scaf:
            continue
        if stype == "staple" and not has_stap:
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
                    "helix1":   num,
                    "idx1":     i,
                    "helix2":   next_vh,
                    "idx2":     next_idx,
                    "sort_idx": min(i, next_idx),
                })

        xovers.sort(key=lambda x: x["sort_idx"])
        for xo in xovers:
            actions.append(["createHalfCrossover", {
                "helix1":     xo["helix1"],
                "idx1":       xo["idx1"],
                "helix2":     xo["helix2"],
                "idx2":       xo["idx2"],
                "strand_type": stype,
            }])

    n_xovers   = sum(1 for a in actions if a[0] == "createHalfCrossover")
    helix_count = len(vstrands)
    name       = data.get("name", "generated")
    resolved_task = task or data.get("_task") or (
        f"Create a {helix_count}-helix bundle with {part_size - 1}bp scaffold "
        f"and {n_xovers} crossovers."
    )

    return {
        "source":         name,
        "task":           resolved_task,
        "part_size":      part_size,
        "helix_count":    helix_count,
        "crossover_count": n_xovers,
        "action_count":   len(actions),
        "actions":        actions,
    }


def to_training_example(traj: dict) -> dict:
    """Convert a trajectory dict to an OpenAI messages-format training example."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": traj["task"]},
    ]

    for i, (method_name, params) in enumerate(traj["actions"]):
        call_id = f"call_{i}_{method_name}"
        messages.append({
            "role":    "assistant",
            "content": None,
            "tool_calls": [{
                "type": "function",
                "id":   call_id,
                "function": {
                    "name":      method_name,
                    "arguments": json.dumps(params),
                },
            }],
        })
        messages.append({
            "role":        "tool",
            "tool_call_id": call_id,
            "content":     "Success",
        })

    messages.append({
        "role": "assistant",
        "content": (
            f"Done. Built a {traj['helix_count']}-helix design "
            f"({traj['part_size']}bp part size, "
            f"{traj['crossover_count']} crossovers)."
        ),
    })

    return {
        "messages": messages,
        "metadata": {
            "source":          traj["source"],
            "helix_count":     traj["helix_count"],
            "action_count":    traj["action_count"],
            "crossover_count": traj["crossover_count"],
            "part_size":       traj["part_size"],
        },
    }


# ─── Validation ───────────────────────────────────────────────────────────────

def validate_design(data: dict) -> list[str]:
    """
    Run structural validity checks on a cadnano JSON dict.

    Returns a list of error strings. Empty list = design is valid.

    Checks:
      1. Bounds — every (vh, idx) reference is within the design.
      2. Bidirectionality — if A.next = B then B.prev = A (cadnano enforces this).
      3. Loop closure — following `next` pointers from every visited position
         returns to the start.
      4. Full coverage — every scaffold position that is non-(-1) is reached
         by following the loop (no orphaned or disconnected segments).
    """
    errors = []
    vstrands = data.get("vstrands", [])
    if not vstrands:
        return ["No vstrands found"]

    L = len(vstrands[0]["scaf"])
    vh_nums = {vs["num"] for vs in vstrands}
    vs_map  = {vs["num"]: vs for vs in vstrands}

    for strand_key in ("scaf", "stap"):
        # Collect all non-empty positions
        active = {}  # (vh, idx) -> [prev_vh, prev_idx, next_vh, next_idx]
        for vs in vstrands:
            num = vs["num"]
            for idx, s in enumerate(vs[strand_key]):
                if any(x != -1 for x in s):
                    active[(num, idx)] = s

        if not active:
            continue

        label = "scaffold" if strand_key == "scaf" else "staple"

        # 1. Bounds check
        for (num, idx), s in active.items():
            prev_vh, prev_idx, next_vh, next_idx = s
            for ref_vh, ref_idx, direction in [
                (prev_vh, prev_idx, "prev"),
                (next_vh, next_idx, "next"),
            ]:
                if ref_vh == -1:
                    continue
                if ref_vh not in vh_nums:
                    errors.append(
                        f"{label} H{num}[{idx}].{direction} refs unknown helix {ref_vh}"
                    )
                elif not (0 <= ref_idx < L):
                    errors.append(
                        f"{label} H{num}[{idx}].{direction} idx {ref_idx} out of bounds [0,{L})"
                    )

        # 2. Bidirectionality check
        for (num, idx), s in active.items():
            prev_vh, prev_idx, next_vh, next_idx = s
            # If this position has a next, the target's prev must point back here
            if next_vh != -1 and (next_vh, next_idx) in active:
                target_prev_vh, target_prev_idx = active[(next_vh, next_idx)][:2]
                if (target_prev_vh, target_prev_idx) != (num, idx):
                    errors.append(
                        f"{label} H{num}[{idx}].next = H{next_vh}[{next_idx}] "
                        f"but H{next_vh}[{next_idx}].prev = H{target_prev_vh}[{target_prev_idx}] "
                        f"(expected H{num}[{idx}])"
                    )
            # If this position has a prev, the source's next must point back here
            if prev_vh != -1 and (prev_vh, prev_idx) in active:
                source_next_vh, source_next_idx = active[(prev_vh, prev_idx)][2:]
                if (source_next_vh, source_next_idx) != (num, idx):
                    errors.append(
                        f"{label} H{num}[{idx}].prev = H{prev_vh}[{prev_idx}] "
                        f"but H{prev_vh}[{prev_idx}].next = H{source_next_vh}[{source_next_idx}] "
                        f"(expected H{num}[{idx}])"
                    )

        # 3 & 4. Loop closure + full coverage
        # Find a 5' start: position whose prev points to a different position
        # (i.e. the strand arrives here via a crossover or it is the true 5' end).
        # For a closed loop every position is equivalent — just pick any start.
        start = next(iter(active))
        visited = set()
        cur = start
        while True:
            if cur in visited:
                if cur != start:
                    errors.append(
                        f"{label}: loop rejoins at H{cur[0]}[{cur[1]}] instead of start "
                        f"H{start[0]}[{start[1]}] — strand is not a simple closed loop"
                    )
                break
            visited.add(cur)
            nxt_vh, nxt_idx = active[cur][2], active[cur][3]
            if nxt_vh == -1:
                errors.append(
                    f"{label}: strand terminates at H{cur[0]}[{cur[1]}] (not a closed loop)"
                )
                break
            cur = (nxt_vh, nxt_idx)
            if len(visited) > len(active) + 1:
                errors.append(f"{label}: traversal exceeded {len(active)} steps — infinite loop?")
                break

        unvisited = set(active) - visited
        if unvisited:
            examples = sorted(unvisited)[:3]
            errors.append(
                f"{label}: {len(unvisited)} positions not reached by the loop "
                f"(disconnected segments). Examples: {examples}"
            )

    return errors


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate cadnano training designs and export as JSONL"
    )
    parser.add_argument(
        "--output", default="",
        help="Output JSONL file path (default: stdout)",
    )
    parser.add_argument(
        "--expert", nargs="*", default=[], metavar="JSON",
        help="Expert cadnano JSON files to include as additional examples",
    )
    parser.add_argument(
        "--lengths", nargs="+", type=int, default=DEFAULT_LENGTHS,
        help=f"Scaffold lengths to generate (default: {DEFAULT_LENGTHS})",
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Print generation statistics and exit without writing JSONL",
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Run structural validity checks on every generated design",
    )
    parser.add_argument(
        "--save-json", metavar="DIR", default="",
        help="Save each generated design as an individual cadnano JSON file in DIR "
             "(useful for loading in the cadnano GUI to visually verify)",
    )
    args = parser.parse_args()

    examples = []
    raw_designs = []   # (design_dict, traj_dict) pairs for validation / JSON export

    # ── 2-Helix bundles ───────────────────────────────────────────────────────
    print(
        f"Generating 2HB designs: {len(TWO_HB_STARTS)} positions × "
        f"{len(args.lengths)} lengths = "
        f"{len(TWO_HB_STARTS) * len(args.lengths)} examples …",
        file=sys.stderr,
    )
    for row, col in TWO_HB_STARTS:
        for length in args.lengths:
            design = generate_2hb(row=row, col=col, length=length)
            traj   = extract_trajectory(design, task=design["_task"])
            examples.append(to_training_example(traj))
            raw_designs.append((design, traj))

    # ── Expert JSON files ─────────────────────────────────────────────────────
    for json_path in (args.expert or []):
        json_path = os.path.expanduser(json_path)
        if not os.path.exists(json_path):
            print(f"Warning: {json_path} not found, skipping", file=sys.stderr)
            continue
        with open(json_path) as f:
            data = json.load(f)
        n_helices = len(data.get("vstrands", []))
        task = (
            f"Create a {n_helices}-helix DNA nanostructure with scaffold "
            f"routing through all helices."
        )
        try:
            traj = extract_trajectory(data, task=task)
            examples.append(to_training_example(traj))
            raw_designs.append((data, traj))
            print(
                f"Loaded expert: {os.path.basename(json_path)} "
                f"({traj['action_count']} actions, "
                f"{traj['crossover_count']} crossovers)",
                file=sys.stderr,
            )
        except Exception as e:
            print(f"Error processing {json_path}: {e}", file=sys.stderr)

    # ── Statistics ────────────────────────────────────────────────────────────
    total_actions   = sum(e["metadata"]["action_count"]    for e in examples)
    total_xovers    = sum(e["metadata"]["crossover_count"] for e in examples)
    helix_counts: dict = {}
    for e in examples:
        n = e["metadata"]["helix_count"]
        helix_counts[n] = helix_counts.get(n, 0) + 1

    print(f"\nTotal examples : {len(examples)}", file=sys.stderr)
    print(f"Total actions  : {total_actions}",   file=sys.stderr)
    print(f"Total crossovers: {total_xovers}",   file=sys.stderr)
    print("Breakdown by helix count:",            file=sys.stderr)
    for n in sorted(helix_counts):
        print(f"  {n}-helix: {helix_counts[n]} examples", file=sys.stderr)

    # ── Validate ─────────────────────────────────────────────────────────────
    if args.validate:
        n_ok = n_fail = 0
        for design, traj in raw_designs:
            errs = validate_design(design)
            name = design.get("name", traj["source"])
            if errs:
                n_fail += 1
                print(f"FAIL  {name}", file=sys.stderr)
                for e in errs:
                    print(f"      {e}", file=sys.stderr)
            else:
                n_ok += 1
                print(f"OK    {name}", file=sys.stderr)
        print(f"\n{n_ok} passed, {n_fail} failed", file=sys.stderr)
        if n_fail:
            sys.exit(1)

    # ── Save individual JSON files for visual inspection in cadnano ───────────
    if args.save_json:
        save_dir = os.path.expanduser(args.save_json)
        os.makedirs(save_dir, exist_ok=True)
        for design, _ in raw_designs:
            name = design.get("name", "design")
            # Strip internal _task key before saving — cadnano doesn't expect it
            out = {k: v for k, v in design.items() if not k.startswith("_")}
            path = os.path.join(save_dir, f"{name}.json")
            with open(path, "w") as f:
                json.dump(out, f, indent=2)
        print(f"Saved {len(raw_designs)} JSON files to {save_dir}", file=sys.stderr)
        print("Open any of them in cadnano (File → Open) to visually verify.", file=sys.stderr)

    if args.stats:
        return

    # ── Write JSONL ───────────────────────────────────────────────────────────
    if args.output:
        output_path = os.path.expanduser(args.output)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w") as f:
            for ex in examples:
                f.write(json.dumps(ex) + "\n")
        print(f"\nWrote {len(examples)} examples → {output_path}", file=sys.stderr)
    else:
        for ex in examples:
            print(json.dumps(ex))


if __name__ == "__main__":
    main()
