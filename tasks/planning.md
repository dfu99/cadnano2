# Planning — cadnano2

## Current Priorities

1. **PI review of DNA 32 paper draft** — `results/paper_draft_dna32.md`. Awaiting feedback on narrative, scope, and which figures to generate.
2. **Generate final paper figures** — 4 figures proposed in the draft. Need to create publication-quality versions. Cavity sweep figures (`results/cavity_variants/`) may replace or supplement Fig 4.
3. **Run oxDNA simulations on PACE GPU** — Submit the scaled cavity design for production relaxation.
4. **Automate the 4-step scaling process** — Turn the manual step1→step4 JSON manipulation into a single script that takes a template + target scaffold length and produces a verified scaled design.

## Next Steps (require user input)

- PI review of DNA 32 paper draft narrative and figure selection
- Conference submission deadline / format requirements
- PI review of cavity variant sweep results — all 7 configs fit p8064

## Recently Completed

- **Parametric cavity variant sweep** (2026-03-19): 7 design variants across gap sizes (20/30/40nm), layers (3×12, 4×12), and widths (2×14, 2×16). All fit p8064 scaffold (96.9–112.3%). Generated 4 figures: gap comparison, feasibility chart, grid schematics, dimensions table. Script: `tools/cavity_variant_sweep.py`, results: `results/cavity_variants/`.

- **DNA 32 paper draft** (2026-03-18): Single-narrative extended abstract for ISNSCE DNA 32 conference. Story: embedded agent failed → coding agent hit 8 domain knowledge walls → PI unblocked each → parametric pipeline emerged. At `results/paper_draft_dna32.md`.
- **4-step cavity template scale-up** (2026-03-18): Scaled PI's 2x12 template from 252→420bp in 4 verified steps. Fixed cavity gap filling, crossover alignment, stray staple references. Final: 1 scaffold oligo, 7688bp, cavity edges aligned to within 2bp between layers.
- **2-layer rectangle with 2×13 grid layout** (2026-03-17): Fixed helix layout from wrong 4×7 to correct 2×13 (2 rows × 13 columns). Perimeter scaffold routing: top row L→R, cross, bottom row R→L, cross back. 1 scaffold oligo, 26 helices, p8064.
- **Cavity scaffold routing with Hamiltonian cycle** (2026-03-17): Proper scaffold routing around cavity using DFS-based Hamiltonian cycle finder. On honeycomb lattice, 2-row cavity routing is impossible (cross-row connections at alternating columns → dead ends). Minimum 4-row grid needed. Demo: 4×13 grid, 10 helices removed, 42-node cycle found in <1ms. 1 scaffold oligo.
- **Parametric origami pipeline** (2026-03-17): Built `tools/parametric_origami_pipeline.py` with configurable scaffold type, helix count, cavity dimensions, polyT brushes, twist correction. Solid rectangle and staple-removal cavity both verified. "Widen cavity by 5nm" = one parameter change → 30 seconds.
- **Paper draft with 4 figures** (2026-03-17): 4-part narrative: (1) failed embedded agent vs working coding agent, (2) proof of concept rectangle, (3) cavity design, (4) parametric redesign. Figures at `results/paper_figures/`.
- **Rectangular DNA origami pipeline with oxDNA** (2026-03-16): End-to-end pipeline: 24 helices × 294 bp, serpentine scaffold routing consuming all 7249 nt of m13mp18, autoStaple + autoBreak for 120 staples, tacoxDNA conversion, oxDNA energy minimization + MD relaxation.
- **Fixed 4-helix sheet with direct createHalfCrossover** (2026-03-16)
- **Distribution strategy analysis** (2026-03-16)
- **Transferability audit for peer distribution** (2026-03-16)
