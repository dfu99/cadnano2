# Planning — cadnano2

## Current Priorities

1. **Generate more diverse training data** — Expand beyond 2×N grids to irregular layouts (L-shapes, T-shapes, custom neighbor graphs)
2. **Export training data in fine-tuning format** — Phase 4 requires (state, action) pairs for LoRA/QLoRA training
3. **Set up fine-tuning pipeline** — LoRA fine-tune on Qwen3-1.7B using generated + expert trajectories

## Next Steps

- Add 1×N (linear chain) bundle generator for simpler topologies
- Add irregular layout generators (L-shape, T-shape, etc.)
- Sweep parameters: try lengths [42, 63, 84, 105, 126, 147, 168] and more starting positions
- Export training examples in HuggingFace datasets format for SFT
- Set up LoRA fine-tuning script using peft + transformers
- Evaluate fine-tuned model on held-out designs

## Recently Completed

- **2×N grid bundle generator** (2026-03-09): Added `generate_2xN()` to `tools/generate_training_designs.py`. Generates 4/6/8/10-helix designs with correct scaffold routing. Uses Hamiltonian path through honeycomb neighbor graph, greedy constrained crossover placement. 90 total designs (30 2HB + 60 2×N), all validate as single closed loops.
