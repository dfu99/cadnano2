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
