# Project Instructions

## Environment Setup

Activate the conda environment before running commands:

```bash
conda activate cn24-agentic
```

**Note:** PyQt6 is already installed in the cn24-agentic environment.

## Project Overview

cadnano is a DNA nanostructure design tool that currently lacks functionality such as:
- Regularly creating crossovers
- Copy+paste for selected sections of the design

This project adds **agentic workflows** to cadnano to implement these functions and scale toward automatically creating large-scale edits of DNA nanostructures.

## Architecture

### Frontend: Agent Dialog Overlay

- **Keyboard Shortcut:** `Cmd+I` (Mac) or `Ctrl+I` (Linux/Windows) opens a dialog box overlay
- Similar to VS Code's inline chat interface
- The dialog box includes a toggle button for switching between **Edit** and **Developer** modes

### Agent Backend

- **Local execution** using [Ollama](https://ollama.ai/)
- **Model:** Qwen-4B (or similar small model)
- Runs entirely on-device for privacy and speed

### Methods Layer (Core Functionality)

The agent does **not** edit the JSON file format directly. Instead:

1. A **"methods" layer** consists of Python scripts that:
   - Open the cadnano JSON file
   - Apply a constrained set of modifications (e.g., adding crossovers)
   - Accept arguments for quantity, position, etc.

2. The **agent parses parameters** from human natural language input

3. The agent **executes the appropriate method script** with parsed parameters to make targeted, controlled changes

### Operating Modes

#### Edit Mode (Default)
- User describes desired changes in natural language
- Agent parses intent and parameters
- Agent executes existing method scripts on the JSON

#### Developer Mode
- Toggled via button in the dialog overlay
- Allows users to design and test **new method scripts**
- Use when existing scripts do not satisfy the required functionality

## Development Guidelines

### Adding New Methods

Methods should be Python scripts that:
1. Accept well-defined arguments (position, quantity, strand info, etc.)
2. Load the cadnano JSON structure
3. Apply atomic, reversible modifications
4. Return success/failure status and any relevant output

### Agent Integration

The agent should:
1. Understand the available methods and their parameters
2. Parse natural language into structured method calls
3. Handle ambiguous requests by asking clarifying questions
4. Provide feedback on operation results

## Implementation Progress

### Completed Components

#### Agent Dialog (`cadnano2/views/agent/agentdialog.py`)
- VS Code-style overlay triggered by Ctrl+I (Cmd+I on Mac)
- Text input with mode toggle (Edit/Developer)
- Fade animations, drop shadow, escape to close
- Mode persistence via QSettings

#### Agent Backend (`cadnano2/views/agent/agentbackend.py`)
- **Dual backend support**: Ollama (local) and OpenAI API
- Backend selection dropdown in dialog
- System prompt with DNA nanostructure design rules
- Handles qwen3 `</think>` tags and GPT-style responses
- Improved JSON extraction for method calls
- MAX_ITERATIONS (50) safety limit

#### Agent Methods (`cadnano2/views/agent/agentmethods.py`)

Methods are organized in two tiers. **Level 2 tools are preferred** — they encode DNA domain rules so the model expresses design intent without computing parity, crossover positions, or neighbor geometry. Level 1 primitives remain available for fine-grained control.

**Level 2 — Constraint-Aware Query Tools:**
- `describeHelix(helix_num)`: Rich single-call description — parity, directions, neighbors, strands, valid crossover positions
- `analyzeDesign()`: Complete state dump — all helices, strands, crossovers, issues, score
- `suggestCrossovers(helix1, helix2, strand_type, min_spacing?)`: Annotated crossover positions (occupied, available, recommended)
- `getNeighborPairs()`: All neighbor pairs in the design with direction labels

**Level 2 — Batch Execution Tools** (each wraps in one undo macro for atomic undo):
- `createHelicesWithStrands(positions, strand_type, length)`: Create multiple helices with strands. Auto-extends part size. strand_type can be "scaffold", "staple", or "both"
- `addCrossoversForPair(helix1, helix2, strand_type, positions?, spacing?)`: Add crossovers between two helices. Auto-computes positions if not specified
- `addAllNeighborCrossovers(strand_type, spacing?)`: Wire up all neighbor pairs with crossovers
- `removeCrossoversForPair(helix1, helix2, strand_type)`: Remove all crossovers between two helices
- `removeAllCrossovers(strand_type)`: Remove all crossovers of a given strand type
- `resizeAllStrands(strand_type, new_length?, delta?, helix_num?)`: Resize strands in bulk. Respects parity for which end to resize
- `addInsertionPattern(helix_num, length, spacing?, start_idx?, end_idx?, strand_type?)`: Add insertions/deletions at regular intervals along a helix
- `addInsertionPatternAll(length, spacing?, strand_type?)`: Add insertions/deletions across all helices
- `removeInsertionPattern(helix_num, strand_type?)`: Remove all insertions/deletions from a helix
- `listInsertions(helix_num?, strand_type?)`: List all insertions/deletions in the design
- `autoBreakStaples(min_staple_len?, max_staple_len?, tgt_staple_len?, min_leg_len?)`: Dijkstra-optimized staple breaking
- `splitStrandAt(helix_num, strand_type, idx)`: Split a single strand at a specific index
- `breakStaplePattern(helix_num?, spacing?, min_staple_len?, max_staple_len?)`: Interval-based staple breaking
- `listStaples(helix_num?)`: List all staple oligos with lengths and spans

**Level 1 — Primitives** (fine-grained control):
- **Geometry**: `getActivePartInfo`, `getHelixInfo`, `getHelixDirection`, `getHoneycombPositions`, `listHelices`, `getPartSize`
- **Part Size**: `extendPartSize(min_length_needed)`
- **Helix**: `createHelix(row, col)`
- **Strands**: `createScaffoldStrand`, `createStapleStrand`, `createFullLengthStrands`
- **Selection**: `getSelectedStrands`, `selectStrand`, `selectEndpoint`, `selectCrossover`, `moveSelection`, `clearSelection`
- **Crossovers**: `createCrossover` (double, default), `createHalfCrossover` (single), `moveCrossover` (free movement, no lattice snap), `getPotentialCrossovers`, `getValidCrossoverPositions`, `listCrossovers`
- **Insertions**: `addInsertion`, `removeInsertion`
- **Verification**: `verifyDesign`, `verify6HelixBundle`

#### Design Verifier (`cadnano2/views/agent/agentverifier.py`)
- Pre-execution validation (checks params before execution)
- Validates helix positions, strand bounds, crossover alignment (mod 21 rules)
- Post-execution verification with reward scores (0-1)
- Crossover position rules derived from `honeycombpart.Crossovers` (single source of truth)

#### Trajectory Logger (`cadnano2/views/agent/trajectorylogger.py`)
- Records agent sessions: task, actions, results, verification scores
- Saves to `~/.cadnano2/trajectories/{success|partial|failed}/`
- `exportForVerlTool()` for RLVR training data export
- **Replay support**: `getReplayActions()`, `getTrajectoryInfo()`
- Statistics and listing methods

### Integration Points

The DocumentController (`cadnano2/controllers/documentcontroller.py`) integrates all components:
- Creates agent components in `_initAgentDialog()`
- Handles command flow: user → backend → methods → feedback loop
- Pre-validates actions before execution
- Logs trajectories for Edit mode sessions
- **Trajectory replay**: `/replay <trajectory_id>` and `/list` commands
- **Human-in-the-loop approval**: After modifying actions execute, shows approval buttons

#### Approval Flow

1. User issues command → agent processes → method executes
2. For modifying actions (not queries), approval buttons appear:
   - **Approve**: Logs positive signal, continues agent loop
   - **Approve All**: Sets auto-approve for remaining actions in this trajectory
   - **Reject & Correct**: Undoes the action (atomic undo for double crossovers), snapshots state, user demonstrates the correct action in GUI, describes it, agent infers the correct method call and logs it in the trajectory
3. Query methods (listHelices, getStrandAt, Level 2 queries, etc.) auto-continue without approval
4. Batch methods (`createHelicesWithStrands`, `addCrossoversForPair`, etc.) use one undo macro — a single approval prompt covers the entire batch, and [Reject & Correct] undoes everything atomically

### Special Commands

In the agent dialog:
- `/list` or `/trajectories` - List saved trajectories
- `/replay <trajectory_id>` - Replay a saved trajectory step-by-step
- `/rlvr [episodes] [max_steps] [update_every]` - Start RLVR training loop (local model)
  - `/rlvr 20 15 1` — 20 episodes, 15 steps max, train after every episode (default)
  - `/rlvr 20 15 4` — train after every 4 episodes (batch update)
- `/rlvr-stop` - Halt RLVR after current episode

### Crossover Nomenclature
In DNA origami, "crossover" means **double crossover** (two half-crossovers at adjacent Low/High positions). `createCrossover` creates a double crossover by default. Use `createHalfCrossover` only when a single half-crossover is explicitly needed. Double crossovers are wrapped in a single undo macro for atomic undo.

### Known Issues
- Timeout errors may occur with slow model responses (current timeout: 120s)
- Verifier needs more test coverage with successful trajectories
- Agent sometimes places double crossover half-pairs at non-adjacent positions (training needed)

---

## Training Roadmap

### Current Challenge
The local model (qwen3:1.7b) cannot reliably produce correct 6-helix bundles. Complex multi-step tasks like 6-helix bundles require many correct decisions in sequence. **New approach**: Start with simpler, single-action tasks that are easier to succeed at and verify.

### Simpler Task Examples
Instead of "create a 6-helix bundle", start with:
- "Move the selected strand 3 bp to the right"
- "Extend this helix by 21 bases"
- "Add a crossover between helix 0 and helix 1 at position 11"
- "Select the scaffold strand on helix 0"

These simpler tasks:
1. Have shorter trajectories (1-3 actions)
2. Are easier to verify correct/incorrect
3. Build toward complex operations compositionally

### Phase 1: Expert Trajectory Collection (Complete)
**Goal:** Validate pipeline and collect successful trajectories using a capable model.

- [x] Implement Ollama backend for local models
- [x] Add OpenAI API backend for stronger models (gpt-5, etc.)
- [x] Add selection methods (`getSelectedStrands`, `moveSelection`, etc.)
- [x] Add trajectory replay (`/replay`, `/list` commands)
- [x] Add primitive-based composable operations (`listStrands`, `resizeStrand`, etc.)
- [x] Validate methods layer works with simple tasks

#### Using the OpenAI Backend

1. Launch cadnano and open the agent dialog (Ctrl+I)

2. Use the dropdown in the dialog to select "OpenAI API"

3. If no API key is found, the dialog prompts for one and saves it to `~/.cadnano2/.env.cadnano`
   - Alternatively, set `OPENAI_API_KEY` as an environment variable

4. The backend will use `gpt-5` by default

#### Replaying Trajectories

1. `/list` - Show recent trajectories
2. `/replay traj_20260128_...` - Replay a specific trajectory

### Phase 2: Human-in-the-Loop Approval (Complete)
**Goal:** Add human feedback loop to improve data quality and catch errors.

**Approach:** Execute first, then let user approve/correct based on visual result in GUI.
This is better than pre-approval because users can't easily map helix IDs to the GUI.

- [x] Add post-execution approval UI to agent dialog
  - After each action executes, show [Approve] / [Reject & Correct] buttons
  - User sees result in GUI, then decides
- [x] [Approve] continues the agent loop, logs positive signal
- [x] [Reject & Correct] undoes the action, captures state, lets user demonstrate the correct action (see Phase 3)
- [x] Log human decisions as training signals in trajectory
- [ ] Track where the model makes mistakes (analysis tooling)

### Phase 3: Recording Mode for Corrections (Complete)
**Goal:** When human corrects the agent, capture the correct action.

- [x] Implement "record mode" in the dialog
  - [Reject & Correct] undoes the wrong action, snapshots design state, waits for user to demonstrate
- [x] When human clicks [Reject & Correct], enter demonstration mode
  - User makes correction in GUI, then describes what they did and presses Enter
- [x] Capture (context, wrong_action, correct_action) tuples
  - Pre/post state diff sent to agent; agent infers the correct method call for the trajectory
- [x] Save correction data for training
  - Wrong action logged as failed; agent's inferred correct action logged via trajectory logger

### Phase 4: Distillation & Fine-tuning
**Goal:** Train local model on expert + corrected trajectories.

- [ ] Export successful trajectories in training format
- [ ] Fine-tune qwen3 (or similar) using LoRA/QLoRA
- [ ] Supervised learning on (state, action) pairs
- [ ] Evaluate on held-out test tasks

### Phase 5: RLVR Training
**Goal:** Use verifier rewards to further improve the fine-tuned model.

- [ ] Implement RLVR training loop
- [ ] Use DesignVerifier scores as reward signal
- [ ] Iterate: generate trajectories → score → update model
- [ ] Curriculum: start with 2-helix, work up to 6-helix

### Architecture Decision: Tiered Models
Consider a hybrid approach for production:
- **Tier 1 (Planning):** Cloud model for complex reasoning
- **Tier 2 (Execution):** Local model for individual steps
- **Tier 3 (Review):** Human approval for critical decisions

This balances cost, latency, and quality.

---

## RLVR Architecture Decisions (Do Not Re-Litigate)

### The RLVR loop does actual in-process weight updates
`RLVRRunner` uses `LocalTrainableBackend` (rlvr_local_backend.py) which loads a local
HuggingFace model (default: Qwen/Qwen2.5-1.5B-Instruct) with a LoRA adapter and handles
BOTH inference and gradient steps in the same process. Weights update after each episode
(or every N episodes, configurable). LoRA checkpoint saved to `~/.cadnano2/rlvr_lora/`.

`LocalTrainableBackend` is swapped in as `dc._agentBackend` during the loop so all
existing DocumentController wiring (method dispatch, feedbackToAgent) works unchanged.

Default model: `Qwen/Qwen3-1.7B` (HuggingFace). This is the same weights as the
`qwen3:1.7b` Ollama model — Ollama uses GGUF format which cannot be trained with
transformers/peft. Download once with `AutoModelForCausalLM.from_pretrained('Qwen/Qwen3-1.7B')`.

Cloud APIs (Claude, OpenAI) are for expert trajectory collection only — they cannot be
trained. Do not use them as the RLVR inference backend.

### Cloud APIs cannot succeed at scaffold routing without sufficient domain knowledge
Even with the best prompt, Claude/OpenAI API models hit a ~0% success rate on scaffold routing
because the agentic methods do not encode enough domain knowledge for the model to reason
through the full solution. Cloud APIs are not the right target for the RLVR training loop.
The correct target is a local model that can be iteratively fine-tuned.

### Shaped intermediate reward — avoids the 0% success rate wall
Binary reward (0 or 1) gives no learning signal when success rate is 0%.
The reward for `scaffold_routing` is shaped continuously (implemented in `getRewardSignal`).
Two tiers ensure any all-closed state always ranks above any open-terminus state:
- Single closed loop → 1.0 (perfect)
- K closed loops, no open ends → 0.5 + 0.5/K  (2→0.75, 10→0.55) — range [0.5, 1.0]
- Open termini → 0.5 × (n_loops / n_total) — range [0, 0.5)

This ensures "2 loops is better than 10 loops" and any all-closed state (floor 0.5)
always outranks any open-terminus state (ceiling approaches 0.5 but never reaches it),
giving a gradient signal even at 0% full success.

### Active learning: update frequently, not after N failures
Do NOT collect 1000 episodes against a 0% success rate wall and then fine-tune.
Instead, update the local model **after every episode** (`update_every=1`, the default).
More frequent weight updates → model explores more effectively → success rate rises faster.
This is online RL, not offline batch distillation.

`/rlvr [episodes] [max_steps] [update_every]` — update_every defaults to 1.
Current algorithm: Reward-Weighted Regression (RWR). GRPO (group-relative advantages
across K rollouts per starting state) is the upgrade path when RWR plateaus.

### Required ML dependencies (cn24-agentic env)
torch (CUDA), transformers, peft, accelerate, bitsandbytes
Install: `pip install torch --index-url https://download.pytorch.org/whl/cu121 && pip install transformers peft accelerate bitsandbytes`

## Task Files

| File | When to consult |
|------|----------------|
| `tasks/planning.md` | Starting any session, checking priorities |
| `tasks/lessons.md` | Before touching subsystems they cover |
