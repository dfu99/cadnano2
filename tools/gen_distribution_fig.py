#!/usr/bin/env python3
"""Generate distribution strategy figure for obj-027."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe

fig, axes = plt.subplots(1, 2, figsize=(16, 8), gridspec_kw={'width_ratios': [3, 2]})

# --- Left panel: What's in the box vs what's not ---
ax = axes[0]
ax.set_xlim(0, 10)
ax.set_ylim(-0.5, 7.5)
ax.axis('off')
ax.set_title("What ships with the repo vs what doesn't", fontsize=13, fontweight='bold', pad=10)

# Shipped items (green)
shipped = [
    ("85 agent methods (deterministic Python)", 6.5),
    ("Tool schemas (agenttools.py, 950 lines)", 5.7),
    ("System prompts (domain rules baked in)", 4.9),
    ("3 LLM backends (Ollama/OpenAI/Claude HTTP)", 4.1),
    ("Verifier + trajectory logger", 3.3),
    ("CLAUDE.md (lessons, architecture, rules)", 2.5),
    ("Approval flow + reject & correct UI", 1.7),
]

not_shipped = [
    ("Trained LoRA weights (model-specific)", 6.5),
    ("Claude Code memory (machine-local)", 5.7),
    ("Conversation history / context", 4.9),
    ("Your conda env (OS/CUDA-specific)", 4.1),
    ("Ollama models (must pull separately)", 3.3),
]

for label, y in shipped:
    ax.annotate(label, xy=(0.3, y), fontsize=10, color='#1a7a3a',
                va='center', fontweight='bold')
    ax.plot(0.15, y, 'o', color='#2ecc71', markersize=10)

ax.text(0.15, 7.2, "SHIPS WITH REPO", fontsize=11, fontweight='bold', color='#1a7a3a')

ax.axhline(y=0.9, color='#ccc', linewidth=1, linestyle='--', xmin=0.01, xmax=0.99)
ax.text(0.15, 0.5, "DOES NOT SHIP", fontsize=11, fontweight='bold', color='#c0392b')

for i, (label, y) in enumerate(not_shipped):
    actual_y = 0.5 - 0.6 * (i + 1) + 0.1
    ax.annotate(label, xy=(0.3, actual_y), fontsize=10, color='#c0392b', va='center')
    ax.plot(0.15, actual_y, 'x', color='#e74c3c', markersize=10, markeredgewidth=2)

ax.set_ylim(-2.8, 7.8)

# --- Right panel: What a peer needs ---
ax2 = axes[1]
ax2.set_xlim(0, 10)
ax2.set_ylim(-0.5, 9)
ax2.axis('off')
ax2.set_title("What a peer actually needs to do", fontsize=13, fontweight='bold', pad=10)

steps = [
    ("1. git clone + pip install -e .", "#2ecc71", "Gets GUI + all 85 methods + backends"),
    ("2. Install Ollama + pull model", "#f39c12", "curl + ollama pull qwen3:1.7b"),
    ("3. Open cadnano, Ctrl+I, type", "#2ecc71", "System prompt teaches the model DNA rules"),
    ("", "", ""),
    ("The key insight:", "#3498db", ""),
    ("Domain knowledge lives in CODE,", "#3498db", "not in model weights or memory files"),
    ("", "", ""),
    ("System prompts = domain rules", "#95a5a6", "Checked into repo, version-controlled"),
    ("Tool schemas = method contracts", "#95a5a6", "950 lines of structured API definitions"),
    ("Level 2 methods = encoded rules", "#95a5a6", "Model says WHAT, code knows HOW"),
    ("Verifier = correctness oracle", "#95a5a6", "Catches mistakes regardless of model"),
]

for i, (text, color, subtext) in enumerate(steps):
    y = 8.0 - i * 0.75
    if text:
        ax2.text(0.3, y, text, fontsize=10, fontweight='bold', color=color, va='center')
    if subtext:
        ax2.text(0.5, y - 0.3, subtext, fontsize=8.5, color='#666', va='center', style='italic')

plt.tight_layout()
plt.savefig('results/obj-027-distribution-strategy.png', dpi=150, bbox_inches='tight')
print('Saved results/obj-027-distribution-strategy.png')
