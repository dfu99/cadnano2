# Parametric DNA Origami Design with AI-Assisted Source Code Integration

Daniel Fu, [Co-authors TBD]

## Abstract

We present a coding-agent approach to DNA origami design that integrates cadnano, tacoxDNA, and oxDNA through automated Python script generation. Unlike embedded tool-using LLMs that must reason about complex domain rules through a fixed API, our approach gives a coding agent direct access to the design software's source code. The agent reads implementation details, writes integration scripts, and produces end-to-end verified designs. We demonstrate this with a parametric rectangular origami pipeline that supports configurable dimensions, scaffold type, cavity placement, polyT brush extensions, and twist correction. A design modification that takes hours by hand — widening a cavity by 5 nm and recomputing all staples, edge treatments, and insertions — completes in seconds. We show results for solid rectangles and cavity-containing structures using the p8064 scaffold, with oxDNA molecular dynamics verification.

## 1. Introduction: Two Approaches to AI-Assisted DNA Origami

DNA origami design involves placing thousands of DNA strands on a lattice to fold a long scaffold strand into a target shape. The designer must reason about helix parity, crossover position tables, scaffold routing topology, staple break optimization, and twist correction — a process that is tedious and error-prone for complex structures.

We explored two approaches to automating this process with large language models. The first failed. The second succeeded.

### 1.1 The Embedded Agent Approach (What Failed)

We built an agent dialog directly into the cadnano GUI (Figure 1a). The user types a natural language command. An LLM (Ollama for local models, OpenAI API for cloud models) parses the intent and calls Python methods that modify the cadnano design. We implemented 85 methods covering helix creation, strand manipulation, crossover placement, staple breaking, and design verification.

This approach failed on complex tasks. Even GPT-class models achieved approximately 0% success on scaffold routing — the multi-step task of placing crossovers to create a single continuous scaffold loop through all helices. The model must reason about helix parity (even helices run left-to-right, odd run right-to-left), crossover position tables (different offsets for each neighbor direction), and routing topology (exactly one half-crossover per routing pair at the parity-determined turn position). These rules are encoded in the method layer, but the model cannot reliably compose them into correct sequences of actions.

We attempted to address this with reinforcement learning from verifier rewards (RLVR), training a local model (Qwen 1.7B) with shaped rewards from a design verifier. The reward signal existed — we could score partial progress on scaffold routing — but the success rate remained at 0%. The model could not discover correct action sequences through exploration alone.

### 1.2 The Coding Agent Approach (What Works)

The second approach abandons the embedded agent entirely. Instead, a general-purpose coding agent (Claude Code) reads the cadnano source code and writes Python scripts that call cadnano's internal APIs (Figure 1b).

The key difference is access to source code. When the standard `createXover` method failed for serpentine scaffold routing (it splits strands, breaking existing connections), the coding agent found `setConnection3p` and `setConnection5p` by reading the strand model implementation. When the autobreak plugin's import failed due to a legacy `__init__.py`, the agent traced the module system and used `importlib` to load it directly. These are debugging tasks, not DNA design tasks — and coding agents excel at them.

The agent also integrates tools that cadnano alone cannot access: tacoxDNA for conversion to oxDNA format, and oxDNA for molecular dynamics verification of the 3D structure. The result is an end-to-end pipeline from design specification to verified 3D geometry.

## 2. Proof of Concept: Rectangular DNA Origami

As an initial demonstration, we built a rectangular DNA origami using the m13mp18 scaffold (7,249 nt) on the honeycomb lattice (Figure 2).

The coding agent produced a 1,300-line Python script (`rectangular_origami_pipeline.py`) that:

1. Creates 24 helices on the honeycomb lattice (row 21, columns 4-27)
2. Routes the scaffold in a serpentine pattern using direct strand endpoint connections (`setConnection3p`/`setConnection5p`), producing a single continuous scaffold oligo
3. Places staple crossovers via cadnano's `autoStaple` method
4. Breaks long staples using the Dijkstra-optimized autobreak plugin (target: 32 nt, producing 120 staples with average length 60 nt)
5. Adds 487 single-base insertions for twist correction, consuming the full 7,249 nt scaffold
6. Exports to cadnano JSON format
7. Converts to oxDNA via tacoxDNA (honeycomb lattice mode)
8. Runs two-stage oxDNA simulation: energy minimization (CPU, DNA2 interaction, 10,000 steps) followed by MD relaxation (Langevin thermostat, 100,000 steps)

The resulting structure measures 56.2 x 27.1 x 2.5 nm by PCA analysis, consistent with a 24-helix flat sheet on honeycomb lattice.

This design is straightforward — any experienced DNA nanotechnology graduate student can produce it manually in cadnano. The value is not in the design itself, but in the pipeline: the entire process from specification to oxDNA-verified 3D structure runs without human intervention.

## 3. Parametric Design: Configurable Structures with Cavities

The real utility of the coding-agent approach emerges when the design must be modified. We built a parametric pipeline (`parametric_origami_pipeline.py`) where every design parameter is configurable: scaffold type, number of helices, helix length, cavity dimensions, polyT brush length, and staple break parameters.

### 3.1 Design Parameterization

The pipeline accepts parameters through a dataclass:

```
scaffold_type:          p8064 (8,064 nt)
n_helices:              26
helix_length_bp:        294 (auto-computed to fit scaffold)
cavity_width_bp:        126 (~43 nm)
cavity_height_helices:  8 (~21 nm)
polyt_length:           4 nt
```

The helix length is automatically computed from the scaffold length, number of helices, and desired insertion density for twist correction.

### 3.2 Cavity Implementation

The cavity is implemented by staple removal: the scaffold serpentines through all helices normally, and staples within the cavity region (helices 9-16, base pairs 84-210) are removed after autoStaple placement. In the cavity region, the scaffold remains as single-stranded DNA, which is flexible and does not maintain the rigid double-helix structure. This approach is used in real DNA origami when a window or opening is needed in the structure.

Figure 3 shows the cavity design schematic and the comparison between the solid rectangle and the cavity variant. The cavity design removes 6 staples from the interior, while preserving all structural staples outside the cavity.

### 3.3 PolyT Brush Extensions

At structure edges, exposed staple strand endpoints are extended by 4 nucleotides. These extensions form single-stranded polyT brushes that prevent blunt-end stacking between adjacent origami structures. The pipeline detects exposed 5' and 3' endpoints on staple strands and extends them in the correct direction based on helix parity.

### 3.4 Results

For the p8064 scaffold (8,064 nt), the parametric pipeline produces:
- **Solid rectangle**: 26 helices x 294 bp, 113 staples (avg 65 nt), 224 polyT extensions, 750 twist-correction insertions
- **With cavity** (126 bp x 8 helices): same scaffold routing, 107 staples (6 removed from cavity), 212 polyT extensions, 750 insertions
- Scaffold: 1 continuous oligo in both cases (8,064 nt)

Both designs convert to oxDNA format (16,328 nucleotides, 38 strands) and pass energy minimization and MD relaxation.

## 4. Parametric Redesign: The Real Value of Automation

The strongest argument for AI-assisted design is not creating a structure once, but modifying it efficiently. In manual cadnano design, widening a cavity by 5 nm requires the designer to:

1. Identify which staples overlap the new cavity boundary
2. Remove those staples
3. Re-examine edge staples for correct break points
4. Re-apply polyT brush extensions to newly exposed endpoints
5. Adjust insertion patterns near the cavity
6. Re-export and re-verify

This process takes 1-4 hours depending on the structure complexity, and must be repeated for every design iteration.

### 4.1 Automated Redesign

With the parametric pipeline, the same modification is a single parameter change:

```
--cavity-width 126  →  --cavity-width 147   (5 nm wider)
```

The pipeline automatically:
- Recomputes staple placement around the wider cavity (107 → 122 staples)
- Re-applies polyT extensions (212 → 242 extensions)
- Adjusts twist correction insertions
- Regenerates the cadnano JSON, oxDNA files, and verification figures

Total time: approximately 30 seconds on a laptop CPU.

### 4.2 Parameter Sweep

Because each design variant is a single command, systematic parameter sweeps become trivial. For example, sweeping cavity width from 84 to 168 bp in 21-bp increments produces 5 design variants, each with automatically computed staples, edge treatments, and insertions. Running oxDNA verification on all 5 variants takes under 10 minutes on CPU, producing quantitative comparisons of structural stability across the sweep.

This kind of systematic exploration is impractical by hand but routine with the parametric pipeline. The designer specifies the sweep range; the pipeline handles everything else.

## 5. Discussion

### 5.1 Why the Coding Agent Succeeds Where the Embedded Agent Fails

The embedded agent operates through a fixed API: 85 methods with defined parameters. The model must compose these methods into correct sequences without seeing the implementation. When a method doesn't work as expected (e.g., `createXover` splitting strands), the model has no way to diagnose the issue or find alternatives.

The coding agent operates at the source code level. It reads how methods work, discovers internal APIs, debugs import issues, and writes custom integration code. The domain knowledge it needs — crossover tables, parity rules, scaffold routing constraints — is in the code, not in the model's training data. This is a fundamental architectural advantage: the agent doesn't need to memorize DNA origami rules; it reads them from the implementation.

### 5.2 Limitations

The staple-removal cavity approach produces a single-stranded scaffold window, not a true structural hole. For applications requiring a rigid cavity boundary, the scaffold must route around the cavity, which requires a 2D helix arrangement (multiple rows on the honeycomb lattice) or a seam-based approach. This is an active area of development.

The pipeline currently handles flat-sheet geometries on the honeycomb lattice. Three-dimensional structures (boxes, curved surfaces) require multi-layer helix arrangements and more complex scaffold routing that we have not yet implemented.

oxDNA simulations in this work use short relaxation runs (100,000 MD steps) on CPU. Production-quality verification requires longer runs (10^7 steps) on GPU, which we have configured for the PACE cluster but do not report here.

### 5.3 Future Directions

The parametric pipeline establishes the foundation for several extensions:

- **Inverse design**: Given target dimensions and a cavity specification, automatically compute the helix count, scaffold type, and routing strategy.
- **Multi-objective optimization**: Sweep staple break parameters to minimize predicted aggregate strain while maintaining target staple lengths.
- **Complex geometries**: Extend to 2D helix grids, enabling true closed cavities, L-shapes, and T-shapes.
- **Integration with experimental workflows**: Export staple sequences for ordering, generate plate maps, and track design versions.

## 6. Methods

### 6.1 Software

- **cadnano2** (modified fork): Python/PyQt6 DNA origami design tool with 85 agent methods for programmatic access
- **tacoxDNA**: Converts cadnano JSON to oxDNA format (honeycomb lattice mode)
- **oxDNA**: Coarse-grained molecular dynamics simulator for DNA (DNA2 interaction model)
- **Coding agent**: Claude Code (Anthropic), general-purpose coding agent with source code access

### 6.2 Design Parameters

All designs use the honeycomb lattice with step size 21 bp. The p8064 scaffold (8,064 nt) is used for the parametric designs. Staple breaking uses the Dijkstra-optimized autobreak algorithm with target length 32 nt, minimum 18 nt, maximum 50 nt, minimum leg length 5 nt. PolyT brush extensions are 4 nt. Twist correction uses single-base insertions distributed evenly across helices, avoiding positions within 3 bp of crossovers.

### 6.3 oxDNA Simulation

Energy minimization: CPU backend, DNA2 interaction, steepest descent, 10,000 steps, dt=0.005, backbone force cap 5.0/10.0, salt 1.0 M. MD relaxation: CPU backend, DNA2, Langevin thermostat (John, diff_coeff=2.5, newtonian_steps=103), 100,000 steps, dt=0.003, backbone force cap 5.0/0.1, salt 0.5 M.

### 6.4 Reproducibility

All pipeline code is available at [repository URL]. Each design is fully reproducible from a single command:

```bash
# Solid rectangle
python -m tools.parametric_origami_pipeline --scaffold p8064

# Rectangle with cavity
python -m tools.parametric_origami_pipeline --scaffold p8064 \
    --cavity-width 126 --cavity-height 8

# Widened cavity (+5 nm)
python -m tools.parametric_origami_pipeline --scaffold p8064 \
    --cavity-width 147 --cavity-height 8
```

## Figures

- **Figure 1**: Architecture comparison. (a) Embedded agent approach: LLM parses natural language and calls fixed method API. Fails on complex multi-step tasks. (b) Coding agent approach: reads source code, writes integration scripts, produces end-to-end verified designs.

- **Figure 2**: Proof of concept. Rectangular DNA origami with m13mp18 scaffold (7,249 nt), 24 helices x 294 bp on honeycomb lattice. (a) Initial 3D structure from tacoxDNA conversion. (b) Energy convergence during oxDNA minimization and relaxation. (c) Relaxation comparison showing structural dimensions.

- **Figure 3**: Cavity design. (a) Schematic of helix layout with cavity region (126 bp x 8 helices). Scaffold serpentines through all helices; staples are removed from the cavity region. (b) Design parameter comparison between solid rectangle and cavity variant.

- **Figure 4**: Parametric redesign. Widening the cavity from 126 bp (~43 nm) to 147 bp (~50 nm) triggers automatic recomputation of staple placement, polyT brush extensions, and twist correction insertions. (a) Side-by-side cavity schematics. (b) Quantitative comparison of design metrics. (c) Cascade of automated changes from a single parameter modification.
