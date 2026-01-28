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
Primitive methods for DNA design manipulation:
- **Geometry**: `getActivePartInfo`, `getHelixInfo`, `getHoneycombPositions`, `listHelices`, `getPartSize`
- **Part Size**: `extendPartSize(min_length_needed)`
- **Helix**: `createHelix(row, col)`
- **Strands**: `createScaffoldStrand`, `createStapleStrand`, `createFullLengthStrands`
- **Selection**: `getSelectedStrands`, `selectStrand`, `moveSelection`, `clearSelection`
- **Crossovers**: `createCrossover`, `getPotentialCrossovers`, `getValidCrossoverPositions`
- **Insertions**: `addInsertion`, `removeInsertion`
- **Verification**: `verifyDesign`, `verify6HelixBundle`

#### Design Verifier (`cadnano2/views/agent/agentverifier.py`)
- Pre-execution validation (checks params before execution)
- Validates helix positions, strand bounds, crossover alignment (mod 21 rules)
- Post-execution verification with reward scores (0-1)
- Honeycomb lattice crossover position rules encoded

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
   - **Undo**: Reverts via undo stack, logs negative signal, agent retries
   - **Correct**: Pauses for user to type clarification
3. Query methods (listHelices, getStrandAt, etc.) auto-continue without approval

### Special Commands

In the agent dialog:
- `/list` or `/trajectories` - List saved trajectories
- `/replay <trajectory_id>` - Replay a saved trajectory step-by-step

### Known Issues
- Timeout errors may occur with slow model responses (current timeout: 120s)
- Verifier needs more test coverage with successful trajectories

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

1. Set your API key as an environment variable:
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

2. Launch cadnano and open the agent dialog (Ctrl+I)

3. Use the dropdown in the dialog to select "OpenAI API"

4. The backend will use `gpt-5` by default

#### Replaying Trajectories

1. `/list` - Show recent trajectories
2. `/replay traj_20260128_...` - Replay a specific trajectory

### Phase 2: Human-in-the-Loop Approval (Complete)
**Goal:** Add human feedback loop to improve data quality and catch errors.

**Approach:** Execute first, then let user approve/correct based on visual result in GUI.
This is better than pre-approval because users can't easily map helix IDs to the GUI.

- [x] Add post-execution approval UI to agent dialog
  - After each action executes, show [Approve] / [Undo] / [Correct] buttons
  - User sees result in GUI, then decides
- [x] [Approve] continues the agent loop, logs positive signal
- [x] [Undo] reverts the action using cadnano undo stack, logs negative signal, agent retries
- [x] [Correct] pauses agent loop for user to type correction/clarification
- [x] Log human decisions as training signals in trajectory
- [ ] Track where the model makes mistakes (analysis tooling)

### Phase 3: Recording Mode for Corrections
**Goal:** When human corrects the agent, capture the correct action.

- [ ] Implement "record mode" in the dialog
- [ ] When human clicks [Correct], enter demonstration mode
- [ ] Capture (context, wrong_action, correct_action) tuples
- [ ] Save correction data for training

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
