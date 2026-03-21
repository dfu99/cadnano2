# Planning — cadnano2

## Current Priorities

1. **Integrin cavity — fix scaffold to 1 oligo** — 8-column cavity in 2×12 template, correct shape (20.8×15.0nm), 8 scaffold oligos remaining. Fix midseam-to-cavity conversion breaks, then run full pipeline through oxDNA PACE.
2. **PI review of DNA 32 paper draft** — `results/paper_draft_dna32.md`. Awaiting feedback.
3. **Autobreak parameter exploration** — PI noted this as a good AI paper use case.
4. **Generate final paper figures** — Cavity sweep + integrin + oxDNA figures available.

## Next Steps (require user input)

- PI review of integrin cavity design once scaffold is 1 oligo
- PI review of DNA 32 paper draft narrative and figure selection
- Conference submission deadline / format requirements

## Recently Completed

- **Full pipeline on 30nm cavity variant** (2026-03-20): Complete end-to-end: autoStaple (69 staples) → autoBreak all3 minLegLen=3 (207 staples, 18-50bp target) → tacoxDNA (17,232 nt, 208 strands) → oxDNA 3-stage PACE GPU relaxation (min 28min + gentle 2h25m + production 2h30m). Structure maintained cavity shape after 20M MD steps. Results: `results/cavity_variants/oxdna_30nm/`.
- **Parametric cavity width sweep with centered crossovers** (2026-03-19): Fixed 5 bugs in the 4-step template scaling pipeline to achieve 1 scaffold oligo with centered, variable-width cavities. All 3 gap sizes (20/30/40nm) load correctly in cadnano. Key bugs: step2 direction detection from shifted refs, step4 crossover on EMPTY positions, step3 spurious midseam on H22-H23. Script: `tools/cavity_variant_sweep.py`, screenshots: `results/cavity_variants/screenshot_{20,30,40}nm.png`.
- **Parametric cavity variant feasibility analysis** (2026-03-19): 7 design variants across gap sizes (20/30/40nm), layers (3×12, 4×12), and widths (2×14, 2×16). All fit p8064 scaffold (96.9–112.3%). 4 analytical figures generated.

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
