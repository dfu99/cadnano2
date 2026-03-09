# Planning — cadnano2

## Current Priorities

1. **Export training data in fine-tuning format** — Phase 4 requires (state, action) pairs for LoRA/QLoRA training
2. **Set up fine-tuning pipeline** — LoRA fine-tune on Qwen3-1.7B using generated + expert trajectories
3. **Generate irregular layouts** — L-shapes, T-shapes for more topological diversity

## Next Steps

- Export training examples in HuggingFace datasets format for SFT
- Set up LoRA fine-tuning script using peft + transformers
- Add irregular layout generators (L-shape, T-shape, etc.)
- Evaluate fine-tuned model on held-out designs
- Try 3×N grids (3-row layouts) for wider bundles

## Recently Completed

- **Scaled to 252 training examples** (2026-03-09): Added 1×N linear chain generator (even N: 4,6,8), expanded 2×N to N=2..7 (up to 14 helices), added lengths 147/168bp. Refactored core routing into reusable `_route_and_build()`. All 252 designs validate.
- **2×N grid bundle generator** (2026-03-09): Added `generate_2xN()` to `tools/generate_training_designs.py`. Uses Hamiltonian path through honeycomb neighbor graph, greedy constrained crossover placement.
