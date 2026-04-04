# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Directory Is

`drafts/` contains the academic paper for the DNA 32 (ISNSCE) Track B conference. The paper is titled "Coding Agents as a Mechanism for Formalizing and Transferring Domain Knowledge in DNA Origami Design." The active working copy is in `paper_package/`.

## Build Commands

Compile the paper (Typst):
```bash
typst compile paper_package/paper.typ paper_package/output/paper.pdf
```

Typst auto-recompile on save:
```bash
typst watch paper_package/paper.typ paper_package/output/paper.pdf
```

## File Layout

- `paper_package/paper.typ` — the paper source (Typst format)
- `paper_package/references.yml` — bibliography
- `paper_package/figures/` — all figure images (PNG)
- `paper_package/output/` — compiled PDF output
- `tasks/` — writing lessons, tone guide, change log (consult before editing)

## Writing Rules

These rules are mandatory. Violating them will require re-revision.

**Style:** Analytic and declarative only. No narrative-illustrative or narraustrative writing. State what happened, what was measured, what it demonstrates. Use declarative sentences with concrete subjects and verbs.

**Banned patterns:**
- Emdashes (`---`) anywhere. Use commas, semicolons, colons, or restructure.
- AI-slop headings: "What we learned:", "The key insight:", "Why this matters:"
- Narrative framing: "This is where...", "The strongest evidence came...", "Early in this project..."
- Low-information descriptors: "(failed)", "(succeeded)" without causal explanation
- Sentence fragment corrections: "_Correction:_ the user did X"
- Informal/quirky language in captions or titles

**Structure:** Each section follows statement, supporting evidence, conclusion. Transitions are logical, not clever. Section titles are descriptive and plain.

**Voice:** Direct, objective, scientific. First person plural ("we") for our own work. No hedging, no filler.

**Figures:** Captions with subfigures must reference labels: "(a) description... (b) description..." When removing/replacing figures, update image path AND caption, check for dangling `@fig` references in body text.

**Citations:** Cite where observations agree with literature. Do not overclaim. The agent is not the designer; the human provides the domain knowledge.

**Entity chronology:** No concept should be referenced before it is introduced.

## Before Editing the Paper

1. Read `tasks/tone.md` and `tasks/lessons.md` for accumulated writing feedback
2. Read `tasks/changes.md` for recent revision history
3. These files record PI corrections that must not be repeated
