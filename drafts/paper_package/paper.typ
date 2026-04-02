#set document(title: "Coding Agents as a Mechanism for Formalizing and Transferring Domain Knowledge in DNA Origami Design")
#set page(margin: (top: 1in, bottom: 1in, right: 1in, left: 1.5in), numbering: "1")

// Line numbering: place numbers every line in the left margin
// Using fixed line height for consistent numbering
#let line-height = 18.15pt  // 11pt font + 0.65em (7.15pt) leading
#let lines-state = counter("lines")

#set page(
  background: context {
    let page-height = 11in - 2in  // total - top/bottom margins
    let num-lines = calc.floor(page-height / line-height)
    let page-num = counter(page).get().first()
    let offset = (page-num - 1) * num-lines
    for i in range(num-lines) {
      place(
        top + left,
        dx: 0.3in,
        dy: 1in + i * line-height,
        text(size: 8pt, fill: gray)[#(offset + i + 1)]
      )
    }
  },
)
#set text(font: "New Computer Modern", size: 11pt)
#set par(justify: true)
#set heading(numbering: none)
#show heading.where(level: 1): set text(size: 14pt)
#show heading.where(level: 2): set text(size: 12pt)
#show heading.where(level: 3): set text(size: 11pt)
#show link: underline
#show figure.caption: set align(left)

#align(center)[
  #text(size: 16pt, weight: "bold")[Coding Agents as a Mechanism for Formalizing and Transferring Domain Knowledge in DNA Origami Design]

  #v(0.5em)
  Daniel Fu, Yonggang Ke
]

#v(1em)

== Abstract

This work investigates the use of a coding agent to design and manipulate DNA origami structures through the caDNAno2 design interface. The design methodology produced by the agent is saved as transferable, repeatable text-file instructions interpretable by another coding agent, converting informal domain expertise into formalized, distributable protocols. We demonstrate this through a parametric pipeline for simple single and multi-layer designs, identifying several failure modes that each required explicit domain knowledge from the human designer. Once encoded, this knowledge enabled the agent to autonomously extend designs to arbitrary lattice dimensions, generate structures to physical specifications, execute targeted edits from natural language prompts, and run the full pipeline from design through molecular dynamics simulation.

== 1. Introduction

Modifying a DNA origami design requires re-routing the scaffold, re-placing staples, and re-verifying the structure for each parameter change #cite(<majikes2021>) #cite(<aksel2018>). A single redesign of a simple structure may be quick, taking several minutes, but multiple iterations or greater complexity accumulate to hours of repetitive, error-prone work. The knowledge required to correctly perform these tasks exists largely as informal expertise, consisting of conventions transmitted between designers, acquired through trial and error, and rarely documented in systematic or machine-readable form.

The effort to algorithmically accelerate the design process and eliminate design tedium has been approached from various angles. A substantial ecosystem of automated design tools now exists, spanning lattice-based design #cite(<douglas2009>), automated staple breaking #cite(<aksel2018>), curved and tubular structures #cite(<fu2024>), wireframe origami from 2D and 3D meshes #cite(<veneziano2016>) #cite(<benson2015>) #cite(<jun2019>) #cite(<jun2021>), and interactive 3D editing environments #cite(<levy2021>). However, there is little continuity between these tools. Each addresses a specific shape class or design subtask, embodying its own bespoke design principles and operating through a disconnected interface. When a new design principle or structural modality emerges, it typically requires building another proprietary tool from the ground up. If these methods were instead consolidated into a single accessible repository, could a coding agent serve as a unified front end, learning from all prior methods and applying the appropriate design logic to each new target? In this work, we initiate that investigation by retracing the DNA origami design chronology #cite(<rothemund2006>) #cite(<douglas2009_3d>) #cite(<ke2009>) #cite(<dietz2009>) #cite(<ke2012>), from the beginning; folding simple single and multi-layer designs, and developing the methodology for scaling toward greater structural complexity.

A coding agent is a large language model (LLM) that operates by reading files, writing and executing code, and iterating on the results within a command-line environment. Unlike chatbot-style LLMs that produce only text responses, coding agents take actions. They can navigate a codebase, call APIs, run scripts, inspect outputs, and modify files across multiple steps without human intervention between steps. Recent advances in LLM reasoning and tool use have made these agents capable of sustained, multi-step software engineering tasks #cite(<he2025>) #cite(<dong2025>), including navigating unfamiliar codebases, integrating independently developed software packages, and writing domain-specific scripts from documentation and source code alone. However, LLMs have no geometric understanding. They cannot reason about nucleotide positions in 3D space. caDNAno provides a layer of abstraction that makes this unnecessary. It encodes helix connectivity, crossover placement, and strand routing as structured data rather than spatial coordinates, reducing DNA origami design to operations on lists and indices. This abstraction makes caDNAno a tractable conduit for investigating whether a coding agent can acquire the domain knowledge needed to manipulate DNA origami designs through direct interaction with the software, rather than with the 3D structure itself.

In the current work, we demonstrate how a coding agent with direct access to caDNAno's source code can read internal data models, write and execute Python scripts, and integrate external tools, like tacoxDNA #cite(<suma2019>) and oxDNA #cite(<ouldridge2011>) #cite(<sulc2012>) #cite(<snodin2015>) #cite(<rovigatti2015>), into an end-to-end pipeline. Critically, the methodology that emerges from this process is not ephemeral. It is saved as verifier functions, parametric scripts, and documented failure catalogs, all of which are transferable, repeatable text-file instructions interpretable by another coding agent. This converts _ad hoc_ design tasks into repeatable, iterable procedures and provides a mechanism for formalizing design principles that have previously lacked systematic documentation.

As a proof of concept, we demonstrate the construction of a parametric pipeline for a 2-layer rectangular origami with a tunable cavity using a coding agent (Claude Code). Achieving functional usage required iterating through 10 distinct failure modes, each corresponding to domain knowledge invisible in the source code (e.g., honeycomb grid-to-layer mapping, crossover parity rules, cavity orientation conventions). Each failure was resolved by explicit correction from the human designer, after which the agent did not repeat that error class. Once this knowledge was encoded, the agent autonomously extended the base template to arbitrary lattice dimensions, generated designs to physical specifications, executed targeted structural edits from natural language prompts, and ran the full pipeline from design through stapling to oxDNA molecular dynamics simulation.

#figure(
  image("figures/fig1_architecture.png", width: 90%),
  caption: [Architecture comparison. (A) Embedded tool-using LLM achieved 0% success on multi-step design tasks because the model could not resolve contextual constraints (helix parity, crossover directionality) from tool schemas alone. (B) Coding agent with source code access produced end-to-end verified designs by reading caDNAno internals, writing Python scripts, and integrating external simulation tools. (C) Knowledge formalization workflow. The user specifies a design target; the agent writes and executes scripts; the user evaluates the result. On failure, the user identifies the failure mode and provides a correction, which the agent formalizes as pipeline scripts, verifier checks, and persistent lessons. The agent retries with this formalized knowledge until the design is correct. On success, working artifacts pass through verification to become persistent, distributable outputs: parametric pipelines, an automated design verifier, a failure catalog, and text-file instructions interpretable by any agent.],
) <fig1>

== 2. Tool-Calling LLM: Insufficient Domain Knowledge from Schemas

Before describing the established pipeline, we distinguish two architectures for applying an LLM to a software tool. In tool-calling, the model selects from predefined functions. In code generation, the model reads source code and writes scripts. This section and the next describe our experience with each. The distinction determines what kinds of domain knowledge the model can acquire and apply.

Our initial approach was to embed an LLM directly into the caDNAno GUI as a tool-calling agent (@fig1, A): the user types a natural language command, the model parses the intent, and calls predefined Python methods that modify the design. The premise was that if we could decompose DNA origami manipulation into a sufficient set of primitives (identify crossovers, move them, place strands, break staples), the model would be able to compose these primitives to execute arbitrary design instructions.

In practice, each primitive required contextual parameters that the model could not resolve from the tool schema. A "place crossover" function must distinguish half-crossovers from full crossovers, left-edge from right-edge from interior positions, and 5#sym.prime#sym.arrow 3#sym.prime from 3#sym.prime#sym.arrow 5#sym.prime scaffold direction on the target helix. Attempts to encode these distinctions into the API surface produced a combinatorial expansion of tool variants without improving task success. Multi-step instructions such as scaffold routing (placing crossovers to form one continuous scaffold loop) achieved 0% success across GPT-class models. The model could invoke individual tools but could not satisfy the inter-step constraints that govern valid compositions. Reinforcement learning with a design verifier as reward signal #cite(<deepseek2025>) also failed. A local model (Qwen 1.7B) could not discover correct action sequences through exploration, which is unsurprising given that substantially more capable GPT-class models achieved 0% success on the same tasks. The GPT-class failure also precluded distillation, as no successful trajectories were available to serve as training data for the local model. Human-demonstrated trajectories were not evaluated as a data source; the volume of demonstrations required to cover the constraint space may be intractable, though we did not confirm this empirically.

The limitation was architectural. A predefined tool API encodes necessary but insufficient domain knowledge. The model can see the available actions but not the reasoning that governs when and how to compose them. Wang et al. demonstrated that tool-calling architectures are systematically inferior to code-generating agents for complex multi-step tasks, precisely because code provides arbitrary composition through control flow, state management, and dynamic parameter construction, capabilities that fixed function schemas cannot express #cite(<wang2024>). Where a tool-calling agent must select from a predetermined menu of operations, a coding agent can read source code to understand _why_ an operation exists, discover undocumented methods, and compose novel sequences that no API designer anticipated.

== 3. Code-Generating Agent: Domain Knowledge from Source Code

We replaced the tool-calling architecture with a coding agent (Claude Code) that reads caDNAno's source code directly and writes Python scripts (@fig1, B). Source code access provided two capabilities absent from the tool-calling approach.

- *Discovery through code reading.* The agent identified internal methods not exposed through any public API by reading the strand model source. For example, when the public `createXover` method broke scaffold continuity by splitting strands, the agent located `setConnection3p/5p` in the strand model internals, which preserves connectivity.
- *End-to-end pipeline construction.* The agent integrated caDNAno with tacoxDNA (format conversion) and oxDNA (molecular dynamics) into a single automated pipeline. Each tool is open-source and individually straightforward, but manually shepherding a design through the full sequence (export, convert, configure simulation parameters, submit, parse results) is tedious and error-prone. The agent automated this by reading each tool's documentation and source code, resolving format requirements, and writing wrapper scripts.

However, source code access alone was not sufficient. Building a correct DNA origami design required domain knowledge that is not encoded in the codebase, such as lattice geometry conventions, crossover placement rules, and scaffold routing patterns. Acquiring this knowledge required iterative human correction. The following sections describe three categories of domain knowledge the agent could not derive from code, the process by which each was resolved, and the artifacts that formalized each correction.

== 4. Formalizing Helix Placement on the Honeycomb Lattice

The agent's earliest outputs were structurally incoherent (@fig2, A). Helices were placed at arbitrary grid positions, crossovers were sparse or absent, there were many short and disconnected strands, primarily due to not understanding polarity within the design space, and the resulting designs bore little resemblance to valid DNA origami. These failures established the baseline. The agent could read caDNAno's source code and execute its API, but had no understanding of the geometric conventions that govern helix placement on the honeycomb lattice.

=== 4.1 The "Layer" Ambiguity

The first obstacle was the relationship between grid rows and physical layers on the honeycomb lattice. On the honeycomb lattice, helices are arranged in a hexagonal packing where adjacent rows are offset vertically. A single row of hexagonally packed helices occupies two distinct y-coordinates, because the vertices of a hexagon do not lie on a single horizontal line. The agent interpreted these two y-coordinates as two physical layers, and therefore constructed a 4-by-7 grid (4 rows, 7 columns) when instructed to build a "2-layer" rectangle. In fact, a 2-layer structure corresponds to 2 grid rows on the honeycomb lattice (yielding a 2-by-12 grid), because one physical layer comprises helices at both y-coordinates of a single hexagonal row.

This ambiguity could not be resolved from the source code. The agent independently generated a multiple-choice diagram of 1-layer, 2-layer, 3-layer, and 4-layer cross-sections and asked the user to identify which arrangement corresponded to "2-layer" (@fig2, B). The user labeled the correct option, and the agent did not repeat this error in any subsequent session. The correction was formalized as a constraint in the pipeline, where N-layer corresponds to N grid rows on the honeycomb lattice.

=== 4.2 Autonomous Geometric Verification via tacoxDNA

With the layer definition resolved, the agent independently developed geometric verification through the end-to-end pipeline (@fig2, C). caDNAno's 2D path view provides no spatial information about the 3D conformation of a design. However, with tacoxDNA integrated, the agent could convert candidate designs to 3D coordinates and analyze the resulting geometry. The agent used this to determine whether a helix arrangement was physically "flat": it generated candidate grid layouts, converted each to oxDNA format, computed cross-sectional slices by PCA decomposition of the 3D nucleotide coordinates, and evaluated whether the resulting profile matched a flat rectangle. By measuring cross-sectional circularity (flat sheet: aspect ratio #sym.approx 0.05; incorrect 2-by-3 grid: #sym.approx 0.84), the agent could reject wrong helix arrangements without human feedback. This process, integration of a 3D simulation tool to compensate for geometric information absent from the design tool, was not anticipated in the original system design.

#figure(
  image("figures/fig2_lattice.png", width: 100%),
  caption: [Formalizing helix placement on the honeycomb lattice. (A) Early agent output: a 4-by-7 grid, the agent's incorrect interpretation of "2-layer," producing 28 helices with fragmented scaffold routing. (B) Multiple-choice diagram the agent generated to resolve the "layer" ambiguity. When instructed to build a "2-layer" structure, the agent could not determine the mapping between grid rows and physical layers from the source code, and prompted the user to identify the correct correspondence. The user labeled the 2-grid-row option, and the agent retained this for all subsequent designs. (C) With the layer definition resolved, the agent independently developed geometric verification by converting candidate designs to 3D coordinates via tacoxDNA and computing PCA cross-sections. This allowed the agent to distinguish correct flat sheets (aspect ratio #sym.approx 0.05) from incorrect grid arrangements (#sym.approx 0.84) without human feedback.],
) <fig2>

== 5. Formalizing Scaffold Routing Rules

With lattice geometry resolved, the next class of errors concerned scaffold routing, specifically how crossovers connect the scaffold strand into a single continuous loop across all helices.

=== 5.1 Early Attempts

The agent's first task was to understand the width of the path design space: how many helices, how long, and where strands begin and end (@fig3, A, top). After the user introduced the concepts of full crossovers (double crossovers connecting adjacent helices in the interior) and half crossovers (single crossovers at the edges serving as scaffold turns), the agent attempted to place them (@fig3, A, bottom). However, without knowledge of where these crossovers should go, the agent produced disconnected scaffold fragments rather than a single continuous strand.

=== 5.2 User Correction

The user provided a hand-designed 2-by-6 rectangle with correct dense crossover routing (@fig3, B), along with an explanation of the placement rules. The key distinction is that at each helix pair boundary, the scaffold turns via a single half-crossover (left edge or right edge, determined by helix parity), while the interior is connected by double crossovers at every valid honeycomb position. This creates a "single midseam" pattern that produces one continuous scaffold oligo.

Additional errors in this phase included scaffold/staple strand assignment (the agent placed scaffold strands on the staple strand set and vice versa), which the user identified by inspecting the design in caDNAno.

=== 5.3 Generalization

After learning the pattern of where full crossovers create the midseam and how half crossovers alternate with full crossovers to maintain a single continuous scaffold routing, the agent generalized to different lattice dimensions without further instruction (@fig3, C). The 2-by-6 template from the user (B) was sufficient for the agent to produce a correct 2-by-8 routing (C), and subsequently 2-by-14, 2-by-18, and other dimensions, each with 1 scaffold oligo. The 2-by-14 rectangle served as the first end-to-end validation of the pipeline from design through molecular dynamics simulation.

#figure(
  image("figures/fig3_scaffold_routing.png", width: 100%),
  caption: [Formalizing scaffold routing. (A) Early agent attempts. Top: the agent explores the path design space, placing strands at various lengths across helices. Bottom: after being told about full and half crossovers, the agent attempts to place them but has no knowledge of where they should go to produce a single continuous scaffold. (B) User-provided 2-by-6 rectangle template with correct dense crossover routing, 1 scaffold oligo. The half-crossover vs full-crossover distinction and the "single midseam" routing pattern were explained alongside this template. (C) After learning the midseam and half-crossover placement rules from (B), the agent generalizes to a 2-by-8 rectangle with correct routing, 1 scaffold oligo, without further instruction.],
) <fig3>

== 6. Formalizing Cavity Design

With scaffold routing established for simple rectangles, we introduced a more complex design goal, a 2-layer rectangle with a rectangular cavity. The cavity is a gap in the interior of the structure along the helix length axis. This design used the p8064 scaffold (8,064 nt) and introduced a second set of failure modes.

=== 6.1 Initial Attempt

The agent's first cavity attempt (@fig4, A) correctly identified where strands should be absent, leaving a gap in the helix length axis. However, the knowledge acquired for simple rectangle routing (Section 5) did not transfer to the cavity case. The routing pattern changes at cavity boundaries. The single midseam must be interrupted, full crossover seams run down the left side, right side, and middle of the structure, and half-crossovers at the cavity edges define the scaffold turn points. The agent had no basis for placing these half-crossovers, and the bottom helix pair requires the midseam to be omitted entirely. The result was a fragmented scaffold with broken routing at the cavity boundaries.

=== 6.2 User Correction

The user provided a 2-by-12 template with correct cavity routing (@fig4, B), demonstrating the full crossover seam pattern and the half-crossover placement rules at cavity edges. This template, along with an explanation of how the routing differs from the simple rectangle case, was sufficient for the agent to incorporate the new pattern.

=== 6.3 Scaling and End-to-End Validation

With cavity routing understood, the agent developed a 4-step process for resizing and re-aligning the cavity (@fig4, C):
  + Remove staples (keep scaffold only). Verified loads.
  + Extend helix arrays and shift right-side crossovers. Verified loads.
  + Move midseam crossovers to center. Verified loads.
  + Expand cavity by moving boundary crossovers and re-aligning to the center. Verified loads.

Additional failures arose during scaling: the agent's script left stray staple entries with broken crossover references, causing caDNAno to crash; the agent filled the cavity gap with continuous scaffold, destroying the cavity; and the scaling logic moved crossover positions independently per helix, creating skewed crossovers where both sides must share the same index. Each was resolved by user correction, and the agent did not repeat any of these error classes.

The resulting design was a 2-by-12 rectangular origami with an aligned cavity, 1 continuous scaffold loop (7,688 bp), scaled from the user's 252 bp template to 420 bp helices.

#figure(
  image("figures/fig4_cavity.png", width: 100%),
  caption: [Formalizing cavity design. (A) Agent's initial attempt at cavity routing. The agent correctly left a gap where strands should be absent, but could not place the half-crossovers needed to maintain scaffold continuity at the cavity boundaries. Knowledge from simple rectangle routing failed to transfer to the cavity case. (B) User-provided 2-by-12 template demonstrating correct cavity routing: full crossover seams on the left, right, and center of the structure, with the midseam omitted on the bottom helix pair, and half-crossovers defining the cavity edges. (C) After incorporating the user's template, the agent developed a 4-step scaling process (scaffold only #sym.arrow extend right side #sym.arrow move midseam to center #sym.arrow expand and align cavity) to resize the structure and re-center the cavity at arbitrary dimensions.],
) <fig4>

== 7. Cumulative Capability and Targeted Edits

Each correction was retained across subsequent sessions; the agent did not repeat any resolved error class. The cumulative effect on agent capability was observed at each stage.

+ *After lattice geometry correction* (Section 4): All subsequent designs used correct 2-by-N grid dimensions.
+ *After scaffold routing correction* (Section 5): The agent adopted the user's template as the basis for all designs, replacing from-scratch construction.
+ *After cavity orientation correction* (Section 6): All cavity designs placed the gap along the helix length axis.
+ *After scaling corrections* (Section 6): The agent developed a validated 4-step scaling process.

After correction of all failure modes, the agent operated autonomously on the following tasks without further human intervention.

+ *Extended the template to arbitrary lattice dimensions* (2-by-16, 2-by-18, 2-by-20, 2-by-22) by adding column pairs to both sides of the base template, maintaining 1 scaffold oligo at each step.
+ *Designed to specification:* Given the constraint "20 nm #sym.times 40 nm cavity, centered, 6-helix padding, scaffold #sym.lt.eq 8,064 bp," the agent independently selected a 2-by-20 grid (40 helices, 252 bp), computed the cavity dimensions (8 columns, 117 bp gap), and built the complete design: 7,828 bp scaffold, 1 oligo.

=== Targeted Edits and Autonomous Pipeline Execution

On a 2-by-22 integrin cavity design, we observed that several scaffold crossovers were positioned too close to the cavity edge (3--5 bp from the boundary half-crossovers). We explicitly prompted the agent to move them, and it identified 5 inter-pair crossovers, relocated each to a valid lattice position 26+ bp from the cavity, and recomputed centered cavity boundaries (@fig5, A). The agent then read the caDNAno source for AutoStaple and AutoBreak and applied both: autoStaple (82 initial staples) followed by autoBreak with minStapleLegLen=3 (220+ broken staples, 18--279 bp range), producing a complete stapled design.

=== Parametric Cavity Variants

With the pipeline fully operational, the agent autonomously generated cavity variants at three widths (20 nm, 30 nm, and 40 nm) without user interaction (@fig5, B--D). For each variant, the agent computed the cavity dimensions from physical specifications, built the caDNAno design, ran autoStaple and autoBreak, converted to oxDNA format via tacoxDNA, and submitted molecular dynamics relaxation on the PACE GPU cluster. The resulting oxDNA structures maintained the cavity shape after relaxation, confirming structural validity.

Each of these tasks required the agent to apply domain knowledge transferred in previous sessions: crossover lattice positions, parity-dependent scaffold direction, cavity boundary half-crossover placement, and honeycomb valid offsets. None were re-taught. The corrections from prior sessions accumulated as reusable code (verifier checks in `cadnano_verifier.py`, pipeline functions in `cavity_variant_sweep.py`, lessons in `tasks/lessons.md`) that the agent applied automatically in new design contexts.

#figure(
  image("figures/fig5_edits.png", width: 100%),
  caption: [Autonomous targeted edits and end-to-end pipeline execution. (A) Crossover repositioning: the user prompted the agent to move scaffold crossovers away from the cavity edge, followed by autoStaple and autoBreak, producing a complete stapled design. (B--D) Parametric cavity variants at 20 nm, 30 nm, and 40 nm widths, each produced autonomously: caDNAno design (left), tacoxDNA-converted initial 3D structure (center), and oxDNA-relaxed structure (right). The agent computed cavity dimensions from physical specifications, built each design, stapled, converted, and ran molecular dynamics without user interaction.],
) <fig5>

== 8. Agents as a Substrate for Shared Design Intelligence

The agent cannot design DNA origami independently. However, the failure modes documented in this work each encode domain knowledge with three properties.

+ *Invisible in source code.* Rules such as "LOW position = crossover IN, HIGH = crossover OUT" cannot be deduced from caDNAno's codebase. They require explicit transfer from an experienced designer.
+ *Retained after single correction.* Once corrected, the agent does not repeat that error class. The correction is encoded in verifier functions, lessons files, and pipeline logic that persist across sessions.
+ *Distributable.* The verifier (`cadnano_verifier.py`) checks all 10 failure modes automatically. The failure catalog (`failure_analysis.md`) documents each with symptom, root cause, fix, and verifier check. A new user or agent can apply these checks without repeating the original debugging.

The agent functions not as a designer but as a substrate for accumulating and distributing design knowledge (@fig1, C). Each user-agent interaction produces reusable verification and pipeline tools in addition to the design itself.

The following artifacts (@artifacts_table) are distributable to any DNA origami researcher working with caDNAno:

#figure(
  table(
    columns: 3,
    align: (left, left, left),
    table.header[*Artifact*][*Purpose*][*Reusability*],
    [`cadnano_verifier.py`], [Pre-flight design validation], [Run on any caDNAno JSON before committing to synthesis],
    [`failure_analysis.md`], [Documented failure modes], [Read before starting AI-assisted design; avoid 10 known pitfalls],
    [`cavity_variant_sweep.py`], [Parametric cavity pipeline], [Change gap size/width #sym.arrow design recomputes automatically],
    [Template extension functions], [Add columns to existing designs], [Extend any 2-by-N template to 2-by-(N+2) with 1 scaffold oligo],
    [Crossover move pattern], [LOW=IN, HIGH=OUT template], [Apply to any targeted crossover edit on any honeycomb design],
    [Renumbering procedure], [JSON helix renumbering], [Essential for any template extension; ensures parity correctness],
  ),
  caption: [Distributable artifacts from this work.],
) <artifacts_table>

The pipeline from the user's template to verified design to oxDNA simulation is end-to-end: no manual caDNAno GUI interaction required. A researcher can describe a cavity design in terms of physical dimensions (nm #sym.times nm, scaffold length, padding) and receive a validated JSON, stapled design, and oxDNA files ready for submission.

Initial agent outputs (a flat sheet, a simple rectangle) demonstrated pipeline functionality but contained no transferable design knowledge. The transition to knowledge transfer occurred when the agent began generating verification tools from its own failure modes. The verifier was not designed top-down; it emerged from 10 specific debugging sessions, each producing a check that prevents the corresponding failure for any subsequent user.

== References

#bibliography("references.yml", title: none, style: "american-chemical-society")

#pagebreak()

== Appendix A: Agent Operations Library

Examples of natural language prompt instructions and the corresponding agent output for targeted modifications on a 6-helix design. Each row shows the before state (left) and after state (right) for a single operation. Operations include crossover creation, crossover movement, crossover deletion, strand extension and shrinking, insertion and deletion placement, strand splitting, automatic staple breaking, and bulk crossover operations.

#image("figures/appendix_operations_p1.png", width: 100%)

#image("figures/appendix_operations_p2.png", width: 100%)

#image("figures/appendix_operations_p3.png", width: 100%)
