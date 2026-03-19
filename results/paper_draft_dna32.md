# Teaching a Coding Agent to Design DNA Origami: What Worked, What Didn't, and What It Took to Get There

Daniel Fu, [Co-authors TBD]

*Target: ISNSCE DNA 32 — Track B (Extended Abstract) or Poster*

## Abstract

We report on our experience using a general-purpose coding agent (Claude Code) to design DNA origami structures in cadnano. We describe two approaches — an embedded tool-using LLM that failed, and a coding agent with source code access that succeeded — and trace the path from initial failure to a working parametric pipeline for a 2-layer rectangular origami with a cavity. The key finding is that the agent's bottleneck was not code generation but domain knowledge: each class of design error required explicit correction from the human designer before the agent could proceed. We detail the specific errors, the domain knowledge that unblocked each one, and the capabilities that emerged after unblocking.

## 1. The Problem

Modifying a DNA origami design is slow. When a cavity is too narrow by 5 nm, the designer must re-route the scaffold, re-place staples, re-apply edge treatments, and re-verify the structure. This process takes hours and must be repeated for every design iteration. We asked: can an AI agent handle this redesign automatically?

## 2. First Attempt: Embed an LLM Inside cadnano (Failed)

We built an agent dialog into the cadnano GUI. The user types a natural language command; an LLM parses the intent and calls Python methods that modify the design. We implemented 85 methods covering helix creation, strand manipulation, crossover placement, and staple breaking.

This failed on anything beyond single-step operations. Scaffold routing — the task of placing crossovers to create one continuous scaffold loop — requires reasoning about helix parity, crossover position tables, and routing topology simultaneously. Even GPT-class models achieved 0% success. We attempted reinforcement learning with a design verifier as reward signal, but the local model (Qwen 1.7B) could not discover correct action sequences through exploration.

**What we learned:** The 85-method API encodes necessary but insufficient domain knowledge. The model must compose methods into correct sequences without understanding why each step matters. The API is a keyhole — the model can see the actions but not the mechanism.

## 3. Second Attempt: A Coding Agent with Source Code Access (Worked, Then Didn't, Then Did)

We switched to a coding agent (Claude Code) that reads cadnano's source code and writes Python scripts. This immediately solved several problems the embedded agent could not:

- When `createXover` broke scaffold continuity by splitting strands, the agent found `setConnection3p/5p` by reading the strand model internals.
- When the autobreak plugin failed to import, the agent traced the module system and used `importlib` to bypass a legacy `__init__.py`.
- The agent integrated cadnano with tacoxDNA (format conversion) and oxDNA (molecular dynamics), creating an end-to-end pipeline no single tool provides.

**First success:** A rectangular origami with the m13mp18 scaffold (7,249 nt). 24 helices, serpentine routing, autoStaple, autoBreak, twist correction, tacoxDNA conversion, oxDNA relaxation. This is trivial for a human designer — but it proved the pipeline worked.

## 4. Scaling Up: Where Domain Knowledge Became the Bottleneck

We then attempted a 2-layer rectangle with a rectangular cavity using the p8064 scaffold (8,064 nt). This is where the agent's limitations became clear. Each step forward required the human designer to diagnose and correct a specific class of error.

### Error 1: Wrong grid layout
The agent built a 4×7 grid (4 rows, 7 columns). A 2-layer rectangle should be 2×12 (2 grid rows, 12 columns). The agent did not know that "2-layer" means 2 grid rows on the honeycomb lattice, because this mapping depends on understanding how honeycomb parity creates the physical layer structure. **Unblocked by:** the PI explaining the grid-to-layer correspondence.

### Error 2: Serpentine routing instead of dense crossovers
The agent routed the scaffold with one crossover per helix pair (serpentine). Real DNA origami uses multiple double crossovers per pair — the scaffold weaves back and forth between adjacent helices. This is a fundamental design convention the agent had no way to discover from the source code alone. **Unblocked by:** the PI providing a hand-designed template (`2x12_rectangle_cavity.json`) showing the correct crossover pattern.

### Error 3: Cavity in the wrong dimension
The agent placed the cavity by removing helices from the XY cross-section (changing the grid). The cavity should be in the Z direction — a gap along the helix length axis, visible in the side view. **Unblocked by:** the PI specifying that the cavity cuts through the helix length, not the helix arrangement.

### Error 4: Scaffold/staple confusion
When building from scratch, the agent placed scaffold strands on the staple strand set and vice versa. **Unblocked by:** the PI inspecting the design in cadnano and identifying the swap.

### Error 5: Scaling broke file format
When scaling the PI's template from 252 to 420 bp, the agent's scaling script left 5,036 stray staple entries with broken crossover references. cadnano crashed on load. **Unblocked by:** tracing the crash to `legacydecoder.py` line 205, identifying the staple crossover references as the cause, and clearing them.

### Error 6: Cavity gaps filled incorrectly
When extending the design, the agent filled the cavity gap with continuous scaffold — destroying the cavity. **Unblocked by:** the PI manually clearing positions 75–337 on the cavity helices and returning the corrected file.

### Error 7: Crossover misalignment
The agent's scaling logic moved crossover positions independently per helix, creating skewed crossovers (e.g., H16[337] vs H17[338]). Both sides of a crossover must be at the same base pair index. **Unblocked by:** the PI aligning the crossovers at index 338 on both helices.

### Error 8: Cavity edges not aligned between layers
The cavity right edge was at position 270 in one layer and 338 in the other. The PI requested they be aligned. The nearest valid honeycomb position on each layer differs by 2 bp (340 vs 338) due to different crossover direction offsets. **Resolved by:** the agent computing valid crossover positions for each honeycomb direction and selecting the closest match.

## 5. What the Agent Could Do After Each Unblocking

After each correction, the agent incorporated the lesson and did not repeat that specific error class. The progression:

1. **After Error 1** (grid layout): Correctly built 2×12 grids from then on.
2. **After Error 2** (dense crossovers): Used the PI's template as the basis for all subsequent designs instead of building from scratch.
3. **After Error 3** (cavity orientation): All cavity designs used Z-direction gaps.
4. **After Errors 5–7** (scaling): Developed a 4-step scaling process that the PI validated step-by-step:
   - Step 1: Remove staples (keep scaffold only). Verified loads.
   - Step 2: Extend helix arrays and shift right-side crossovers. Verified loads.
   - Step 3: Move midseam crossovers to center. Verified loads.
   - Step 4: Expand cavity by moving boundary crossovers. Verified loads.

The final result: a 2×12 rectangular origami with an aligned cavity, 1 continuous scaffold loop (7,688 bp), scaled from the PI's 252 bp template to 420 bp helices. Each step produced a valid cadnano JSON that loads without errors.

## 6. What This Tells Us

The agent is not a designer. It is a fast, tireless assistant that can manipulate files, trace code, and automate repetitive operations — but it cannot independently determine the correct design. Every non-trivial design decision required human domain knowledge.

The value is in what happens *after* the human provides the knowledge. Once shown the correct pattern (the PI's template), the agent could scale it, modify it, and verify each step in seconds. The 4-step scaling process that took an afternoon of back-and-forth would take days if done entirely by hand for each new scaffold length.

**For DNA nanotechnologists:** A coding agent is most useful not as an autonomous designer, but as a parametric design tool. You design the template; the agent scales, modifies, and verifies. The bottleneck shifts from clicking in cadnano to communicating design intent clearly.

**What remains difficult:** The agent cannot discover design conventions from source code alone. Honeycomb layer counting, dense crossover patterns, cavity orientation, crossover alignment rules — these are domain knowledge that must be taught explicitly. Each new design feature risks a new class of error that requires human diagnosis.

## Figures

- **Figure 1:** Architecture comparison — embedded agent (failed) vs coding agent with source code access (succeeded).
- **Figure 2:** The PI's template (`2x12_rectangle_cavity.json`) showing correct scaffold routing with dense crossovers and cavity gap.
- **Figure 3:** The 4-step scaling process: (a) scaffold only, (b) extended right side, (c) midseam moved, (d) cavity expanded and aligned between layers.
- **Figure 4:** Scaffold routing visualization of the final scaled design (420 bp, 7,688 bp scaffold, 1 oligo).
