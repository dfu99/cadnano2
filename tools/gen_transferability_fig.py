#!/usr/bin/env python3
"""Generate transferability analysis figure for obj-025."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

fig, ax = plt.subplots(1, 1, figsize=(12, 7))

layers = [
    {'name': 'cadnano2 core\n(PyQt6 GUI + data model)', 'deps': 'PyQt6 only', 'y': 0, 'color': '#2ecc71'},
    {'name': 'Agent Methods Layer\n(85 ops, verifier, trajectory logger)', 'deps': 'stdlib only (no extra pip)', 'y': 1, 'color': '#2ecc71'},
    {'name': 'Agent Dialog + LLM Backends\n(Ollama HTTP, OpenAI HTTP, Claude HTTP)', 'deps': 'stdlib urllib (no pip)', 'y': 2, 'color': '#2ecc71'},
    {'name': 'Ollama Runtime\n(local LLM server)', 'deps': 'System install + model pull', 'y': 3, 'color': '#f39c12'},
    {'name': 'RLVR Fine-Tuning\n(rlvr_local_backend.py)', 'deps': 'torch (CUDA), transformers, peft', 'y': 4, 'color': '#e74c3c'},
]

bar_height = 0.7
bar_left = 0.5
bar_width = 8

for layer in layers:
    rect = mpatches.FancyBboxPatch(
        (bar_left, layer['y'] - bar_height / 2), bar_width, bar_height,
        boxstyle="round,pad=0.05",
        facecolor=layer['color'], edgecolor='white', linewidth=2, alpha=0.85,
    )
    ax.add_patch(rect)
    ax.text(
        bar_left + 0.3, layer['y'] + 0.05, layer['name'],
        fontsize=10, fontweight='bold', va='center', ha='left', color='white',
    )
    ax.text(
        bar_left + bar_width - 0.3, layer['y'], layer['deps'],
        fontsize=9, va='center', ha='right', color='white', style='italic',
    )

legend_items = [
    mpatches.Patch(facecolor='#2ecc71', label='Fully transferrable \u2014 pip install + git clone'),
    mpatches.Patch(facecolor='#f39c12', label='Needs external install \u2014 single command'),
    mpatches.Patch(facecolor='#e74c3c', label='Hard to transfer \u2014 CUDA + GPU + version pinning'),
]
ax.legend(handles=legend_items, loc='upper right', fontsize=9, framealpha=0.9)

annotations = [
    (0, 'pip install -e .'),
    (1, 'Zero extra deps'),
    (2, 'Zero extra deps'),
    (3, 'curl install + ollama pull'),
    (4, 'Needs Dockerfile'),
]
for y, text in annotations:
    ax.text(bar_left + bar_width + 0.3, y, text, fontsize=9, va='center', ha='left', color='#333')

ax.set_xlim(-0.5, 13)
ax.set_ylim(-0.8, 5.5)
ax.set_aspect('auto')
ax.axis('off')
ax.set_title('cadnano2 Agent Stack \u2014 Transferability Analysis', fontsize=14, fontweight='bold', pad=15)

insight = (
    "Key insight: The entire agent stack (GUI \u2192 methods \u2192 LLM backends) uses ONLY\n"
    "PyQt6 + stdlib. No pip ML dependencies until you hit RLVR training.\n"
    "A peer can pip install + install Ollama and have full AI-assisted cadnano."
)
props = dict(boxstyle='round,pad=0.5', facecolor='#eef', edgecolor='#aab', alpha=0.9)
ax.text(4.5, 5.1, insight, fontsize=9, va='center', ha='center', bbox=props)

plt.tight_layout()
out = 'results/obj-025-transferability-analysis.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
print(f'Saved {out}')
