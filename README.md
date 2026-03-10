# Cadnano2 DNA Origami Design Software

## Overview
[Cadnano](http://cadnano.org/) is computer-aided design software for DNA origami nanostructures. The original citation is [here](https://academic.oup.com/nar/article/37/15/5001/2409858).

---

## Agentic Design Assistant (Experimental)

This fork adds an AI-powered design assistant to cadnano2, enabling natural-language automation of repetitive DNA origami design tasks. Instead of replacing the GUI, the agent works alongside it — users describe what they want, and the agent executes precise, undoable operations through a controlled methods layer.

### Key Features

- **Agent Dialog Overlay** — Press `Ctrl+I` (`Cmd+I` on Mac) to open an inline chat, similar to VS Code's Copilot interface
- **Pattern Automation** — Automate tedious repetitive tasks: add crossovers at every full turn between two helices, apply insertion/deletion patterns across all helices, bulk resize strands
- **Dual Backend** — Use local models (Ollama/Qwen) for privacy or cloud APIs (OpenAI, Claude) for stronger reasoning
- **Atomic Undo** — Every agent action (including batch operations) is wrapped in a single undo macro, so `Ctrl+Z` reverts the entire operation
- **Human-in-the-Loop** — After each modifying action, approve, reject, or correct the result directly in the GUI
- **Trajectory Recording** — All agent sessions are logged for training data collection and replay

### How It Works

```
User: "Add scaffold crossovers between helices 0 and 1 at every full turn"
  → Agent calls: addCrossoversForPair(helix1=0, helix2=1, strand_type="scaffold", spacing=21)
  → Result: 5 crossovers created at positions [11,32], [32,33], [53,54], [74,75], [95,96]
  → User sees result in GUI → [Approve] / [Reject & Correct]
```

The agent never edits JSON directly. All modifications go through a constrained **methods layer** that enforces DNA origami design rules (crossover positions, helix parity, lattice geometry).

### Current Progress

| Milestone | Status |
|-----------|--------|
| Agent dialog UI with mode toggle | Done |
| Methods layer (Level 1 primitives) | Done |
| Level 2 constraint-aware batch tools | Done |
| Pattern automation (crossovers, insertions, deletions) | Done |
| Human-in-the-loop approval flow | Done |
| Trajectory recording & replay | Done |
| Expert trajectory collection (cloud APIs) | Done |
| Training data generation (252 designs) | Done |
| Local model fine-tuning (LoRA/QLoRA) | Planned |
| RLVR training loop | Planned |

### Available Agent Commands

**Pattern Automation (most useful for daily work):**
- Add crossovers between two helices at every full turn
- Add crossovers between all neighbor pairs
- Add/remove insertions or deletions at regular intervals
- Bulk resize strands

**Query Tools:**
- Analyze the full design state
- Describe a specific helix (parity, neighbors, strands, valid crossovers)
- List all crossovers, insertions, or neighbor pairs
- Suggest optimal crossover positions

**Special Commands:**
- `/list` — Show saved trajectories
- `/replay <id>` — Replay a trajectory step-by-step
- `/rlvr` — Start reinforcement learning training loop

### Future Directions

- Fine-tune local models on collected expert trajectories
- Expand pattern automation to staple break patterns and sequence assignment
- Multi-step task planning (e.g., "create a 6-helix bundle with scaffold routing")
- Copy+paste for selected design regions

---

## Installation

**macOS**
* Install [homebrew](https://brew.sh/)
* Install python3: `brew install python3`
* Create a virtualenv: `python3 -m venv ~/virtualenvs/cn24x` 
* Activate virtualenv: `source ~/virtualenvs/cn24x/bin/activate`
* Install via pip: `pip3 install cadnano2`

**Linux**
* Create a virtual env: `python3 -m venv ~/virtualenvs/cn24x`
* Activate the venv: `source ~/virtualenvs/cn24x/bin/activate`
* Install from PyPI: `pip3 install cadnano2`

**Windows** (tested for Python 3.10.4)
* Download and install latest [python3](https://www.python.org/downloads/)
* Use "Manage app execution aliases" to disable launching "App Installer" via any python executables.
* Add python app folder to your system path, e.g. `C:\Users\shawn\AppData\Local\Programs\Python\Python310\`
* Add scripts folder to your system path, e.g. `C:\Users\shawn\AppData\Local\Programs\Python\Python310\Scripts\`
* Open command prompt (cmd.exe) and confirm you can run "python" and "pip". 
* Install Cadnano via pip: `pip install cadnano2`

## Running

**macOS or Linux**
* Open the Terminal
* (macOS or Linux) Activate virtual env: 
  - `source ~/virtualenvs/cn24x/bin/activate`
* Run the app: `cadnano2`

**Windows**
* Open the Command Prompt
* Run the app: `cadnano2`

**macOS alias**
* Add to `~/.zprofile`: `alias cn2="source ~/virtualenvs/cn24x/bin/activate && cadnano2"`
* Open new Terminal and run: `cn2`

## Upgrading
* Open the Terminal
* Activate virtual env: `source ~/virtualenvs/cn24x/bin/activate`
* Upgrade via pip: `pip install --upgrade cadnano2`


## Development

**Setup a dev environment (Mac or Linux)**

* Create a virtualenv: `python3 -m venv ~/virtualenvs/cn24dev` 
* Activate virtualenv: `source ~/virtualenvs/cn24dev/bin/activate`
* Install build dependencies: `pip install setuptools wheel pyqt6`
* Clone repo: `git clone git@github.com:douglaslab/cadnano2.git`
* Change directory: `cd cadnano2`
* Make desired code edits
* Build and install: `pip install -e .`
* Test: `cadnano2`
* Repeat previous 3 steps as needed

**Setup a dev environment (Windows)**

* Install venv: `pip install virtualenv`
* Create a virtualenv: `python -m venv virtualenvs\cn24dev` (e.g. in %homepath%)
* Activate virtualenv: `virtualenvs\cn24dev\Scripts\activate`
* Install build dependencies: `pip install setuptools wheel pyqt6`
* Clone repo: `git clone git@github.com:douglaslab/cadnano2.git`
* Change directory: `cd cadnano2`
* Make desired code edits
* Build and install: `pip install -e .`
* Test: `cadnano2`
* Repeat previous 3 steps as needed


**Build new dist and upload to PyPi**

* `pip install build twine` <- install [build](https://pypi.org/project/build/) and [twine](https://pypi.org/project/twine/)
* `cd /path/to/cadnano2/` 
* `python3 -m build`  creates dist/cadnano2-x.y.z.tar.gz and cadnano2-x.y.z-py3-none-any.whl
* `python3 -m twine upload dist/cadnano2-x.y.z*` 

## Version notes

This version of Cadnano2 is maintained by the [Douglas Lab](http://bionano.ucsf.edu/). It is derived from [cadnano/cadnano2](https://github.com/cadnano/cadnano2).

If you wish to use the Cadnano Python API for scripting, see [cadnano2.5](https://github.com/douglaslab/cadnano2.5/).

## License

This version of Cadnano2 is available under the MIT License. GUI code that uses PyQt6 is GPLv3 as [required](http://pyqt.sourceforge.net/Docs/PyQt6/introduction.html#license) by Riverbank Computing.
