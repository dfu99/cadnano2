# Planning — cadnano2

## Current Priorities

1. **oxDNA geometric verification for diverse shapes** — Extend the cadnano-to-oxDNA pipeline to test tubes, L-shapes, and multi-layer structures
2. **Generate screenshot pairs for 6-helix designs** — Larger designs with more complex operations
3. **Scale dataset** — More operation variants, more helix counts, augment with paraphrased instructions

## Next Steps

- Test oxDNA pipeline on tube (closed) and multi-row designs
- Generate 6-helix design screenshot pairs with more complex multi-step operations
- Add instruction paraphrasing / augmentation to grow dataset beyond 33 examples
- Explore pushing dataset to HuggingFace Hub

## Recently Completed

- **HuggingFace screenshot dataset export** (2026-03-11): Built `tools/export_screenshot_dataset.py` — exports 33 before/after image pairs as HuggingFace Dataset (Arrow + Parquet). 5 categories, 7 features per example including PIL Images. 3.5MB total.
- **Expanded screenshot library to 33 pairs** (2026-03-11): Added resize strands (3), insertion patterns (4), strand breaks (3), three-helix operations (2) to `tools/generate_screenshot_library.py`. Now 11 operation categories, 57% growth from initial 21 pairs.
- **cadnano-to-oxDNA flat sheet pipeline** (2026-03-11): Built `tools/oxdna_flat_sheet.py` — creates 6-helix flat sheet in cadnano, converts to oxDNA via tacoxDNA, parses 3D coordinates, fits rectilinear prism via PCA. Result: 41.5 x 10.5 x 2.4 nm, flatness ratio 0.058, planarity RMS 0.63 nm. Validates that automated cadnano designs produce geometrically correct 3D structures.
- **Screenshot library for crossover operations** (2026-03-11): Built `tools/generate_screenshot_library.py` — headless path view rendering to PNG. 21 before/after pairs covering: move crossover right/left (1,2,3,7 bases), delete crossover (first/middle/last), create crossover (start/middle/end), add N evenly spaced crossovers (2,3,4,6), remove all crossovers (pair/design), add staple crossovers. Fixed `moveCrossover` co-moving strand overlap bug.
- **Staple break automation methods** (2026-03-10): Added 4 methods — `autoBreakStaples` (Dijkstra-optimized), `splitStrandAt`, `breakStaplePattern` (interval-based), `listStaples`. 12/12 tests pass.
- **Headless test suite for pattern automation** (2026-03-10): 8/8 tests pass covering all 7 pattern automation methods (resizeAllStrands, removeCrossoversForPair, removeAllCrossovers, addInsertionPattern, removeInsertionPattern, addInsertionPatternAll, listInsertions). Tests run with QT_QPA_PLATFORM=offscreen.
- **Pattern automation methods** (2026-03-10): Added 6 new batch methods — `removeCrossoversForPair`, `removeAllCrossovers`, `addInsertionPattern`, `removeInsertionPattern`, `addInsertionPatternAll`, `listInsertions`. All wrap in single undo macros. Added corresponding Claude API tool schemas. Updated README with agentic fork overview.
- **Scaled to 252 training examples** (2026-03-09): Added 1×N linear chain generator (even N: 4,6,8), expanded 2×N to N=2..7 (up to 14 helices), added lengths 147/168bp. Refactored core routing into reusable `_route_and_build()`. All 252 designs validate.
- **2×N grid bundle generator** (2026-03-09): Added `generate_2xN()` to `tools/generate_training_designs.py`. Uses Hamiltonian path through honeycomb neighbor graph, greedy constrained crossover placement.
