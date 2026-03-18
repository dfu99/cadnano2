# Planning — cadnano2

## Current Priorities

1. **Scale up PI's cavity template to p8064** — Two approaches in progress: (a) load `2x12_rectangle_cavity.json`, scale helix lengths from 252→420bp, re-route; (b) build from scratch matching the dense crossover pattern. Compare screenshots. Key learning: PI's design uses *dense scaffold crossovers* (multiple double crossovers per helix pair), NOT serpentine (one per pair).
2. **Run oxDNA simulations on PACE GPU** — Submit designs to PACE for 1e7-step GPU relaxation.
3. **Update paper draft** — Revise with correct 2-layer cavity design and dense crossover routing.

## Next Steps (require user input)

- PI review of scaled-up vs from-scratch comparison screenshots
- oxDNA simulation length for paper-quality results

## Recently Completed

- **2-layer rectangle with 2×13 grid layout** (2026-03-17): Fixed helix layout from wrong 4×7 to correct 2×13 (2 rows × 13 columns). Perimeter scaffold routing: top row L→R, cross, bottom row R→L, cross back. 1 scaffold oligo, 26 helices, p8064.
- **Cavity scaffold routing with Hamiltonian cycle** (2026-03-17): Proper scaffold routing around cavity using DFS-based Hamiltonian cycle finder. On honeycomb lattice, 2-row cavity routing is impossible (cross-row connections at alternating columns → dead ends). Minimum 4-row grid needed. Demo: 4×13 grid, 10 helices removed, 42-node cycle found in <1ms. 1 scaffold oligo.
- **Parametric origami pipeline** (2026-03-17): Built `tools/parametric_origami_pipeline.py` with configurable scaffold type, helix count, cavity dimensions, polyT brushes, twist correction. Solid rectangle and staple-removal cavity both verified. "Widen cavity by 5nm" = one parameter change → 30 seconds.
- **Paper draft with 4 figures** (2026-03-17): 4-part narrative: (1) failed embedded agent vs working coding agent, (2) proof of concept rectangle, (3) cavity design, (4) parametric redesign. Figures at `results/paper_figures/`.
- **Rectangular DNA origami pipeline with oxDNA** (2026-03-16): End-to-end pipeline: 24 helices × 294 bp, serpentine scaffold routing consuming all 7249 nt of m13mp18, autoStaple + autoBreak for 120 staples, tacoxDNA conversion, oxDNA energy minimization + MD relaxation.
- **Fixed 4-helix sheet with direct createHalfCrossover** (2026-03-16)
- **Distribution strategy analysis** (2026-03-16)
- **Transferability audit for peer distribution** (2026-03-16)
