# Planning — cadnano2

## Current Priorities

1. **Re-export augmented HuggingFace dataset** — Re-run augmentation with expanded 85-operation library
2. **Push dataset to HuggingFace Hub** — Make training data publicly available (requires `huggingface-cli login`)
3. **Begin VLM fine-tuning experiments** — Use expanded dataset across 6 layouts

## Next Steps (require user input)

- Push augmented dataset to HuggingFace Hub (needs `huggingface-cli login`)
- Begin VLM fine-tuning experiments with the augmented dataset

## Recently Completed

- **Edge vs interior crossover decision logic** (2026-03-14): Added `crossover_type` parameter ("auto"/"double"/"half") to `addCrossoversForPair` and `addAllNeighborCrossovers`. In auto mode, scaffold edge positions (first/last valid crossover) use half-crossovers, interior positions use double. `suggestCrossovers` now annotates each position with `is_edge`. Updated system prompts and tool schemas. 5 new tests + 12 original tests pass.
- **oxDNA investigation report** (2026-03-13): Comprehensive report on tacoxDNA conversion pipeline with 4 purposeful figures: format anatomy, conversion pipeline, planarity/helix analysis, training reward integration. 6-helix flat sheet: 41.5x10.5x2.4 nm, flatness 0.058, combined reward 0.76. Report at `results/oxdna_investigation/report.md`.
- **Checkpoint: queue cleanup & obj-002 docs** (2026-03-13): Completed obj-002 methodology/conclusions for 2×N grid bundle generator. Marked tacoxDNA investigation and documentation queue items as completed. All queue items resolved except half-crossover edge logic (pending).
- **tacoxDNA investigation report** (2026-03-13): Generated 4-figure investigation report (`results/oxdna_investigation/`) covering oxDNA format anatomy, conversion pipeline, planarity analysis, and training integration. Full report in `report.md` with metrics.
- **Objective backfill: obj-001 documentation** (2026-03-13): Completed methodology, metrics, conclusions for "Scaled to 252 training examples". Generated proper distribution visualization (3-panel: generator types, helix counts, growth). Fixed duplicate obj-018 → renumbered to obj-019.
- **Rectilinear prism fit metric** (2026-03-13): Built `tools/oxdna_prism_fit.py` — PCA-aligned bounding box analysis of oxDNA 3D coordinates. Composite prism_fit_score (0.793 for 6-helix flat sheet) from uniformity, rectangularity, and slice consistency. Score ceiling ~0.8 due to cylindrical helix geometry. 3 diagnostic figures: wireframe overlay, cross-sectional slices, density heatmap.
- **Geometric reward scorer for RLVR training** (2026-03-13): Built `tools/oxdna_geometric_reward.py` — cadnano JSON → tacoxDNA → oxDNA → PCA → reward [0,1]. Discriminates shape classes (flat sheet 0.95 vs grid 0.42) but not crossover connectivity (tacoxDNA places by lattice, not connectivity). Orthogonal to structural verifier — recommended combined reward: 0.7×structural + 0.3×geometric.
- **Expanded screenshot library to 85 operations** (2026-03-13): Added 36 new variations filling gaps in move distances (4-6), staple crossover moves, additional delete/create positions, more evenly-spaced counts (1,5,8), insertion spacings (7,14,42), split points, resize increments, and multi-helix move/delete operations. Now 85 operations across 13 method types and 6 design layouts.
- **T-shape design screenshots** (2026-03-11): Added 3 T-shaped operations (5 helices, symmetric branching). Final dataset: 49 image pairs, 244 augmented examples across 6 design layouts. 11.6× growth from initial.
- **L-shape design screenshots** (2026-03-11): Added 3 L-shaped operations (5 helices, asymmetric). Dataset now 46 image pairs, 228 augmented examples across 5 design layouts.
- **2×3 grid design screenshots** (2026-03-11): Added 4 multi-row grid operations (add scaffold, add both, remove cross-row pair, insertion pattern). Dataset now 43 image pairs, 212 augmented examples across 4 design layouts.
- **oxDNA verification extended to 6 shapes** (2026-03-11): Added L-shape (5 helices, asymmetric) and wide sheet (10 helices) to `tools/oxdna_shape_verify.py`. L-shape shows expected thickening (4.6 nm) at bend. Wide sheet scales to 18.0 nm width. Pipeline distinguishes all 6 geometric classes.
- **Instruction augmentation to 192 examples** (2026-03-11): Built `tools/augment_instructions.py` — template-based paraphrasing generates 3-5 variants per instruction. 39 images × ~4.9 instructions = 192 training examples. Exported as augmented HuggingFace dataset.
- **6-helix design screenshots** (2026-03-11): Added 6 new 6-helix operations to screenshot library (39 total pairs). Covers add scaffold/both crossovers, remove middle pair, resize, insertions, auto-break across 2/3/6-helix designs. Re-exported HuggingFace dataset.
- **oxDNA shape verification for 4 geometries** (2026-03-11): Built `tools/oxdna_shape_verify.py` — tests tube, 2×3 grid, long sheet against flat sheet reference. All shapes produce expected 3D geometries: grid has near-square cross-section (circularity 0.84), long sheet doubles length to 83.3 nm.
- **HuggingFace screenshot dataset export** (2026-03-11): Built `tools/export_screenshot_dataset.py` — exports 33 before/after image pairs as HuggingFace Dataset (Arrow + Parquet). 5 categories, 7 features per example including PIL Images. 3.5MB total.
- **Expanded screenshot library to 33 pairs** (2026-03-11): Added resize strands (3), insertion patterns (4), strand breaks (3), three-helix operations (2) to `tools/generate_screenshot_library.py`. Now 11 operation categories, 57% growth from initial 21 pairs.
- **cadnano-to-oxDNA flat sheet pipeline** (2026-03-11): Built `tools/oxdna_flat_sheet.py` — creates 6-helix flat sheet in cadnano, converts to oxDNA via tacoxDNA, parses 3D coordinates, fits rectilinear prism via PCA. Result: 41.5 x 10.5 x 2.4 nm, flatness ratio 0.058, planarity RMS 0.63 nm. Validates that automated cadnano designs produce geometrically correct 3D structures.
- **Screenshot library for crossover operations** (2026-03-11): Built `tools/generate_screenshot_library.py` — headless path view rendering to PNG. 21 before/after pairs covering: move crossover right/left (1,2,3,7 bases), delete crossover (first/middle/last), create crossover (start/middle/end), add N evenly spaced crossovers (2,3,4,6), remove all crossovers (pair/design), add staple crossovers. Fixed `moveCrossover` co-moving strand overlap bug.
- **Staple break automation methods** (2026-03-10): Added 4 methods — `autoBreakStaples` (Dijkstra-optimized), `splitStrandAt`, `breakStaplePattern` (interval-based), `listStaples`. 12/12 tests pass.
- **Headless test suite for pattern automation** (2026-03-10): 8/8 tests pass covering all 7 pattern automation methods (resizeAllStrands, removeCrossoversForPair, removeAllCrossovers, addInsertionPattern, removeInsertionPattern, addInsertionPatternAll, listInsertions). Tests run with QT_QPA_PLATFORM=offscreen.
- **Pattern automation methods** (2026-03-10): Added 6 new batch methods — `removeCrossoversForPair`, `removeAllCrossovers`, `addInsertionPattern`, `removeInsertionPattern`, `addInsertionPatternAll`, `listInsertions`. All wrap in single undo macros. Added corresponding Claude API tool schemas. Updated README with agentic fork overview.
- **Scaled to 252 training examples** (2026-03-09): Added 1×N linear chain generator (even N: 4,6,8), expanded 2×N to N=2..7 (up to 14 helices), added lengths 147/168bp. Refactored core routing into reusable `_route_and_build()`. All 252 designs validate.
- **2×N grid bundle generator** (2026-03-09): Added `generate_2xN()` to `tools/generate_training_designs.py`. Uses Hamiltonian path through honeycomb neighbor graph, greedy constrained crossover placement.
