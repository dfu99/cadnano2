# Domain Knowledge Transfer in AI-Assisted DNA Origami Design

Daniel Fu, [Co-authors TBD]

*Target: ISNSCE DNA 32, Track B (Extended Abstract) or Poster*

## Abstract

We report on using a general-purpose coding agent (Claude Code) to design DNA origami structures in cadnano. We describe two approaches: an embedded tool-using LLM that achieved 0% success on multi-step scaffold routing because the model could not resolve contextual constraints from tool schemas alone, and a coding agent with source code access that produced verified designs by reading implementation details and writing integration scripts. The agent's bottleneck was not code generation but domain knowledge: each class of design error required explicit correction from the human designer before the agent could proceed. We detail the specific errors, the domain knowledge that unblocked each one, and the capabilities that emerged after unblocking.

## 1. The Problem

Modifying a DNA origami design is slow. When a cavity is too narrow by 5 nm, the designer must re-route the scaffold, re-place staples, re-apply edge treatments, and re-verify the structure. This process takes hours and must be repeated for every design iteration. We investigate whether an AI agent can automate this redesign.

## 2. Embedded LLM Agent

We built an agent dialog into the cadnano GUI. The user types a natural language command; an LLM parses the intent and calls Python methods that modify the design. We implemented 85 methods covering helix creation, strand manipulation, crossover placement, and staple breaking.

This approach achieved 0% success on scaffold routing, the multi-step task of placing crossovers to create one continuous scaffold loop. Scaffold routing requires simultaneous reasoning about helix parity, crossover position tables, and routing topology. GPT-class models could not compose these constraints into correct action sequences. We attempted reinforcement learning with a design verifier as reward signal, but the local model (Qwen 1.7B) could not discover correct action sequences through exploration.

The 85-method API encodes necessary but insufficient domain knowledge. The model must compose methods into correct sequences without access to the underlying mechanisms that determine correctness.

## 3. Coding Agent with Source Code Access

We switched to a coding agent (Claude Code) that reads cadnano's source code and writes Python scripts. This resolved several problems the embedded agent could not address:

- When `createXover` broke scaffold continuity by splitting strands, the agent found `setConnection3p/5p` by reading the strand model internals.
- When the autobreak plugin failed to import, the agent traced the module system and used `importlib` to bypass a legacy `__init__.py`.
- The agent integrated cadnano with tacoxDNA (format conversion) and oxDNA (molecular dynamics), creating an end-to-end pipeline no single tool provides.

The first verified design was a rectangular origami with the m13mp18 scaffold (7,249 nt): 24 helices, serpentine routing, autoStaple, autoBreak, twist correction, tacoxDNA conversion, and oxDNA relaxation. This design is routine for an experienced designer but validated the end-to-end pipeline.

## 4. Domain Knowledge Blockers and Unblockers

Scaling from the initial rectangle to a production-ready cavity design required the user to diagnose and correct 10 classes of error. Table 2 summarizes each blocker, the domain knowledge that resolved it, and the resulting capability.

### Table 2: Blockers and Unblockers

| # | Blocker | Unblocker | Resulting Capability |
|---|---------|-----------|-----------|
| 1 | **Agent built a 4x7 grid instead of 2x12.** The mapping from "2-layer" to 2 grid rows on the honeycomb lattice depends on understanding how honeycomb parity creates the physical layer structure. | User explained the grid-to-layer correspondence: 2 grid rows = 1 physical layer = "2-layer" rectangle. | Agent correctly builds 2xN grids. |
| 2 | **Agent used serpentine routing (1 crossover per helix pair), producing 65 scaffold oligos instead of 1 (Figure 2).** The agent had no concept of dense crossover routing, the standard pattern where the scaffold weaves between helices with multiple double crossovers per pair. | User provided a description of half crossovers vs full crossovers, their placement relative to scaffold routing, and how they differ at edge vs interior positions. User also provided a hand-designed template showing the correct crossover pattern (Figure 3). | Agent uses the template as basis for all subsequent designs. |
| 3 | **Agent placed the cavity by removing helices from the XY cross-section.** The cavity should be a gap along the helix length axis (Z direction), not a hole in the grid. | User specified that the cavity cuts through the helix length, not the helix arrangement. | All cavity designs use Z-direction gaps. |
| 4 | **Agent placed scaffold strands on the staple strand set and vice versa** when building from scratch. | User inspected the design in cadnano and identified the swap. | |
| 5 | **Agent's scaling script left 5,036 stray staple entries with broken crossover references.** cadnano crashed on load. | User traced the crash to `legacydecoder.py` and identified the stray staple crossover references as the cause. | Agent developed a 4-step scaling process, validated at each step. |
| 6 | **When extending the design, the agent filled the cavity gap with continuous scaffold,** destroying the cavity. | User manually cleared the cavity positions and returned the corrected file. | |
| 7 | **Agent's scaling logic moved crossover positions independently per helix,** creating skewed crossovers (e.g., H16[337] vs H17[338]). | User aligned the crossovers at the same index on both helices. | |
| 8 | **Cavity edges were not aligned between layers:** position 270 in one layer vs 338 in the other. | Agent computed valid crossover positions for each honeycomb direction and selected the closest match. User confirmed the approach. | Cavity boundaries snap to valid honeycomb lattice positions. |
| 9 | **Agent could not determine the correct helix placement for a rectangle** on the honeycomb lattice from the cadnano 2D view alone. | Agent solved this autonomously by using tacoxDNA to convert candidate designs to 3D, then analyzing cross-sectional slices to verify the arrangement matched the target shape (Figure 4). | Agent verifies helix placement geometrically using oxDNA coordinates. |
| 10 | **After adding the cavity, the scaffold split into multiple oligos** because the agent did not distinguish half-crossovers at cavity boundaries from interior full crossovers. Cavity edge pairs require single half-crossovers for scaffold turns; interior pairs use double crossovers. | User provided iterative corrections on half-crossover placement: valid positions for half vs full crossovers, how scaffold direction (parity-dependent) determines the routing turn end, and how cavity boundary crossovers connect the two scaffold halves (Figure 6). | Agent achieves 1 scaffold oligo on cavity designs. Rules encoded in `cadnano_verifier.py`. |

## 5. Capabilities After Each Unblocking

After each correction, the agent incorporated the lesson and did not repeat that error class.

1. **After Blocker 1** (grid layout): The agent correctly built 2x12 grids for all subsequent designs.
2. **After Blocker 2** (dense crossovers): The agent used the user's template as the basis for all subsequent designs instead of building from scratch.
3. **After Blockers 5 through 8** (scaling): The agent developed a 4-step scaling process validated at each step: (1) remove staples, (2) extend helix arrays and shift crossovers, (3) move midseam crossovers to center, (4) expand cavity by moving boundary crossovers. Each step produced a cadnano JSON that loads without errors.
4. **After Blocker 9** (helix placement): The agent autonomously verified design geometry through tacoxDNA conversion and cross-section analysis.
5. **After Blocker 10** (cavity routing): The agent achieved 1 scaffold oligo on all cavity designs and encoded the validation rules in a distributable verifier.

The final design was a 2x12 rectangular origami with an aligned cavity, 1 continuous scaffold loop (7,688 bp), scaled from the user's 252 bp template to 420 bp helices.

## 6. Autonomous Design at Scale

After the user provided guidance through all 10 blockers, the agent operated without further human intervention on four classes of task:

1. **Template extension to arbitrary widths** (2x14, 2x16, 2x18, 2x20, 2x22) by adding column pairs to both sides of the 2x12 template, maintaining 1 scaffold oligo at each step.
2. **Design to specification:** Given the constraint "26 nm x 40 nm cavity, centered, 6-helix padding, scaffold <= 8,064 bp," the agent selected a 2x22 grid (44 helices x 225 bp), computed the cavity dimensions (10 columns x 117 bp gap), and built the design: 7,432 bp scaffold, 1 oligo.
3. **Targeted edits from natural language prompts:** When instructed to move crossovers at H5-H6 and H33-H34 away from the cavity edge, the agent identified the positions ([64,65] and [183,184], both 4 bp from the cavity), found valid alternative lattice positions ([43,44] and [204,205], 25 bp clearance), and moved them while preserving the single scaffold oligo (Figure 5).
4. **Full pipeline execution:** autoStaple (222 staples), autoBreak (minLegLen=3), tacoxDNA conversion, oxDNA PACE GPU relaxation.

## 7. Distributable Design Intelligence

Each of the 10 blockers represents a piece of domain knowledge with three properties:

1. **Invisible in source code.** The rule "LOW position = crossover IN, HIGH = crossover OUT" cannot be deduced from cadnano's codebase. It must be taught by a human who has internalized years of design experience.
2. **Immediately reusable.** Once the agent learns a rule, it does not repeat that class of error. The learning is encoded in verifier functions, lessons files, and pipeline logic that persist across sessions.
3. **Distributable.** The verifier (`cadnano_verifier.py`) catches all 10 failure modes automatically. A new user or a new AI agent can skip these failures entirely. The failure catalog (`failure_analysis.md`) explains each one with symptom, root cause, fix, and verifier check.

### Table 1: Distributable Artifacts

| Artifact | Purpose | Reusability |
|----------|---------|-------------|
| `cadnano_verifier.py` | Pre-flight design validation | Run on any cadnano JSON before committing to synthesis |
| `failure_analysis.md` | Documented failure modes | Read before starting AI-assisted design; avoid 10 known pitfalls |
| `cavity_variant_sweep.py` | Parametric cavity pipeline | Change gap size/width; design recomputes automatically |
| Template extension functions | Add columns to existing designs | Extend any 2xN template to 2x(N+2) with 1 scaffold oligo |
| Crossover move pattern | LOW=IN, HIGH=OUT template | Apply to any targeted crossover edit on any honeycomb design |
| Renumbering procedure | JSON helix renumbering | Essential for any template extension; ensures parity correctness |

The pipeline from user's template to verified design to oxDNA simulation requires no manual cadnano GUI interaction. A researcher specifies a cavity design in terms of physical dimensions (nm x nm, scaffold length, padding) and receives a validated JSON, stapled design, and oxDNA files ready for simulation.

The verifier was not designed top-down; it emerged from 10 specific debugging sessions. Each failure produced a check that prevents the same failure for every future user.

## 8. One-Shot Targeted Edits

In the final session, the user issued three successive modification requests on a 2x22 integrin cavity design. The agent executed each correctly on the first attempt.

**Edit 1: "Shrink the structure."** The 2x22 design was wider than needed. The agent moved edge crossovers inward by one step (from positions 246/242 to 225/221) and cleared scaffold data beyond the new edges, preserving all crossover connectivity while reducing the effective helix length from 252 bp to 225 bp. Result: 7,412 bp scaffold, 1 oligo.

**Edit 2: "Move the full crossovers away from the cavity edge, and center the cavity."** The agent identified 5 inter-pair crossovers 3 to 5 bp from cavity boundary half-crossovers (H5-H6 at [64,65], H13-H14 at [53,54], H15-H16 at [64,65], H27-H28 at [183,184], H37-H38 at [183,184]). It moved each to a safe lattice position 26+ bp from the cavity, then recomputed centered cavity boundaries: R12 gap [59,171] with 54 bp on each side, R13 gap [55,168] with 53 bp on each side. Result: 7,432 bp scaffold, 1 oligo, cavity centered to within 1 bp.

**Edit 3: "Now autoStaple and autoBreak it."** The agent ran autoStaple (82 initial staples) and autoBreak with minStapleLegLen=3 (220+ broken staples, 18 to 279 bp range, preserving full crossovers). Result: complete stapled design ready for tacoxDNA conversion (Figure 7).

Each edit required combining domain knowledge transferred across previous sessions: crossover lattice positions, parity-dependent scaffold direction, cavity boundary half-crossover placement, and honeycomb valid offsets. None of these were re-taught. The agent applied lessons encoded in `tasks/lessons.md`, verifier checks in `cadnano_verifier.py`, and pipeline functions in `cavity_variant_sweep.py` (Figure 8).

## Figures

- **Figure 1:** Architecture comparison. (a) Embedded agent: LLM parses natural language and calls a fixed 85-method API; achieved 0% success on multi-step scaffold routing because the model could not resolve contextual constraints from tool schemas. (b) Coding agent: reads cadnano source code, writes Python scripts, integrates tacoxDNA and oxDNA; produces end-to-end verified designs.
- **Figure 2:** Agent's from-scratch scaffold routing attempt, which produced 65 scaffold oligos using serpentine routing (1 crossover per helix pair). cadnano2 path view.
- **Figure 3:** User's hand-designed template with correct dense crossover routing and cavity gap, 1 scaffold oligo (5,036 bp). cadnano2 path view.
- **Figure 4:** Helix placement discovery. The agent used tacoxDNA to convert candidate designs to 3D coordinates and analyzed cross-sectional slices, fitting rectangles to helix positions to verify the arrangement matched the target shape. Five cross-section panels show a uniform rectangular profile.
- **Figure 5:** Targeted crossover edit. (a) Before: H5-H6 crossovers at [64,65], 4 bp from cavity edge. (b) After: crossovers moved to [43,44], 25 bp clearance. cadnano2 path view.
- **Figure 6:** Correctly routed 30 nm cavity design with 1 scaffold oligo. Half-crossovers at cavity boundaries provide scaffold turns; full crossovers in the interior provide structural stability. cadnano2 path view.
- **Figure 7:** Final stapled product: 2x22 integrin cavity design after autoStaple and autoBreak (220+ staples, minLegLen=3). cadnano2 path view.
- **Figure 8:** One-shot targeted edits. (a) Structure shrink: edge crossovers moved inward. (b) Crossover repositioning and cavity centering. (c) autoStaple and autoBreak applied. Each edit executed correctly on the first attempt. cadnano2 path view.
