# Planning — cadnano2

## Current Priorities

1. **Add staple break pattern automation** — Auto-place staple breaks at standard intervals (e.g., every 7 or 8 bases)
2. **Export training data in fine-tuning format** — Phase 4 requires (state, action) pairs for LoRA/QLoRA training
3. **Add sequence assignment methods** — Enable scaffold sequence assignment through agent methods

## Next Steps

- Add staple break pattern automation methods
- Add sequence assignment methods
- Export training examples in HuggingFace datasets format for SFT
- Set up LoRA fine-tuning script using peft + transformers
- Generate irregular layouts (L-shapes, T-shapes)

## Recently Completed

- **Headless test suite for pattern automation** (2026-03-10): 8/8 tests pass covering all 7 pattern automation methods (resizeAllStrands, removeCrossoversForPair, removeAllCrossovers, addInsertionPattern, removeInsertionPattern, addInsertionPatternAll, listInsertions). Tests run with QT_QPA_PLATFORM=offscreen.
- **Pattern automation methods** (2026-03-10): Added 6 new batch methods — `removeCrossoversForPair`, `removeAllCrossovers`, `addInsertionPattern`, `removeInsertionPattern`, `addInsertionPatternAll`, `listInsertions`. All wrap in single undo macros. Added corresponding Claude API tool schemas. Updated README with agentic fork overview.
- **Scaled to 252 training examples** (2026-03-09): Added 1×N linear chain generator (even N: 4,6,8), expanded 2×N to N=2..7 (up to 14 helices), added lengths 147/168bp. Refactored core routing into reusable `_route_and_build()`. All 252 designs validate.
- **2×N grid bundle generator** (2026-03-09): Added `generate_2xN()` to `tools/generate_training_designs.py`. Uses Hamiltonian path through honeycomb neighbor graph, greedy constrained crossover placement.
