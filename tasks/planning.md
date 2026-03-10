# Planning — cadnano2

## Current Priorities

1. **Pattern automation focus** — Shift from long-form reasoning (6-helix bundle from scratch) to automating tedious repetitive user interactions: crossover patterns, insertion/deletion patterns, bulk strand operations
2. **Export training data in fine-tuning format** — Phase 4 requires (state, action) pairs for LoRA/QLoRA training
3. **Set up fine-tuning pipeline** — LoRA fine-tune on Qwen3-1.7B using generated + expert trajectories

## Next Steps

- Test new pattern automation methods in the GUI (addInsertionPattern, removeCrossoversForPair, etc.)
- Add staple break pattern automation methods
- Add sequence assignment methods
- Export training examples in HuggingFace datasets format for SFT
- Set up LoRA fine-tuning script using peft + transformers
- Generate irregular layouts (L-shapes, T-shapes)

## Recently Completed

- **Pattern automation methods** (2026-03-10): Added 6 new batch methods — `removeCrossoversForPair`, `removeAllCrossovers`, `addInsertionPattern`, `removeInsertionPattern`, `addInsertionPatternAll`, `listInsertions`. All wrap in single undo macros. Added corresponding Claude API tool schemas. Updated README with agentic fork overview.
- **Scaled to 252 training examples** (2026-03-09): Added 1×N linear chain generator (even N: 4,6,8), expanded 2×N to N=2..7 (up to 14 helices), added lengths 147/168bp. Refactored core routing into reusable `_route_and_build()`. All 252 designs validate.
- **2×N grid bundle generator** (2026-03-09): Added `generate_2xN()` to `tools/generate_training_designs.py`. Uses Hamiltonian path through honeycomb neighbor graph, greedy constrained crossover placement.
