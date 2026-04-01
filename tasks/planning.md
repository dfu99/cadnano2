# Planning — cadnano2

## Current Priorities

1. **Anisotropic designs + tacoxDNA 3D (ongoing)** — 15 designs built (added 3 new cross variants). Shapes: 6HB, L-shape, hex ring, 2x8, 4x4, 3x6, T-shape, cross/plus, 2x10, 24HB, 2x12+cavity, cross+cavity, cross_thin_16h, cross_wide_24h, cross_xl_28h. Topology limits documented (triangle, H, U, stepped shapes blocked by degree-1 constraints; symmetric crosses blocked by dead-end constraints). Summary: `results/stress_test/cross_sections_comparison.png`.
2. **DNA 32 Track B paper** — Draft revised, figures under PI review. Autobreak sweep + scaffold routing demos complete.

**BLOCKED:** PACE resources exhausted for the month. All new designs stop at cadnano2 JSON + screenshot stage.
**CLOSED:** RLVR local model training. The pipeline + verifier approach is the DNA 32 story.

## Checkpoint State (2026-03-29)

All work committed and pushed. Archive: `tasks/archive/planning_2026-03-29.md`

Capabilities demonstrated to date:
1. Template scaling with centered cavity (variable gap width)
2. One-shot targeted edits (shrink, move crossovers, center, staple)
3. From-scratch scaffold routing (simple alternating pattern)
4. Full pipeline: cadnano → autoStaple → autoBreak → tacoxDNA → oxDNA
5. Autonomous design to specification (nm dimensions → verified JSON)

## Next Steps (require user input)

- PI direction on intelligence exploration tasks
- DNA 32 Track B submission format/deadline

## Distributable Artifacts

- `tools/cadnano_verifier.py` — standalone design verification (catches 8 failure modes)
- `results/failure_analysis.md` — documented failure modes with root causes + fixes
- `tools/cavity_variant_sweep.py` — parametric cavity pipeline (variable gap, width, height)
- `tools/build_single_integrin.py` — end-to-end integrin cavity builder

## Recently Completed

- **Cross design variants** (2026-04-01): 3 new cross shapes via build_shape.py: thin 16h (2-col arms, 6-col bar), wide 24h (4-col arms, 8-col bar), XL 28h (4-col arms, 10-col bar). All 1 scaffold oligo, full pipeline (autoStaple+autoBreak+tacoxDNA). Key finding: symmetric crosses not routable with alternating scaffold on honeycomb (dead-end constraints). Cross-sections at `results/stress_test/cross_sections_comparison.png`.
- **Autobreak parameter sweep** (2026-03-27): 6 configs (minLeg 3/5 x target 28/32/42) on 30nm cavity design. minLeg=3: 0 unsolvable, good target adherence. minLeg=5: 6-13 unsolvable, many >50bp staples. Summary figure + 6 screenshots + 6 JSONs at `results/autobreak_sweep/`.
- **Academic writing revision** (2026-03-27): Fixed 45 violations across 3 paper drafts. Narrative→declarative, emdashes→commas, AI-slop headings removed, PI→User, figure captions fixed.
- **Major paper revision: Blocker/Unblocker table, new figures, PI→User** (2026-03-27): Removed Figs 2-4,6-8. Added Fig 2 (ugly mess), Fig 3 (user template), Fig 4 (cross-section), Fig 6 (cavity routing), Fig 7 (stapled product). Added Table 2 with 10 blockers/unblockers. All PI→User.
- **Paper Section 8 + Figure 9: one-shot targeted edits** (2026-03-26): Added concluding example documenting 3 successive one-shot modifications (shrink structure, move crossovers + center cavity, autoStaple+autoBreak). Figure 9 shows 3-panel screenshot progression. Draft sent to PI for review.
- **2×22 integrin cavity: shrink, fix crossovers, center, staple** (2026-03-26): Complete sequence: moved edge crossovers inward (252→225bp), moved 5 inter-pair crossovers away from cavity (3bp→26bp clearance), centered cavity (54bp/54bp segments), autoStaple+autoBreak x3 (220+ staples). All edits one-shot from PI prompts.
- **2×20 centered cavity design (20nm×40nm)** (2026-03-24): Full pipeline: 2×20 template extension (4 LEFT + 4 RIGHT cols), 4-step cavity scaling (8 cols, 117bp gap), autoStaple+autoBreak (238 staples), tacoxDNA (17320 nt). Scaffold: 8660bp, 1 oligo. PACE min completed; GPU relax pending.
- **Production oxDNA for all 3 cavity variants** (2026-03-23): 20nm and 40nm submitted and completed on PACE. All 3 variants (20/30/40nm) maintain cavity shape after 20M MD steps. Figure: `results/paper_figures/fig_all_cavities_oxdna.png`.
- **Failure analysis figures for DNA 32 paper** (2026-03-22): 3 publication figures: oligo journey bar chart (65→1), failure mode table (8 failures with symptoms/fixes), verifier before/after comparison. At `results/paper_figures/fig_*.png`.
- **Distributable verifier + failure analysis** (2026-03-22): `tools/cadnano_verifier.py` catches 8 failure modes. `results/failure_analysis.md` documents each with symptom→root cause→fix. Both the integrin design and PI template pass all checks.
- **Integrin cavity: 1 scaffold oligo, full pipeline** (2026-03-22): 8-column cavity (20.8nm×15.0nm) in 2×12 template. Fixed edge crossover destruction, stray midseam fragments, boundary search order. 208 staples, 17,176 nt. Submitted to PACE (jobs 5357952/5357953).
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
