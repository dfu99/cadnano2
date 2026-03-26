#!/usr/bin/env python
"""Generate Figure 9: Targeted Design Edits — one-shot from natural language prompts."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
import os

shots = [
    ('results/integrin_cavity/screenshot_2x22_26x40nm.png',
     'Step 1: Shrink structure (moved edge crossovers inward, 7412bp, 1 oligo)'),
    ('results/integrin_cavity/screenshot_2x22_centered_v2.png',
     'Step 2: Move H5-H6, H13-H14, H15-H16 xovers away from cavity + center cavity (7432bp, 1 oligo)'),
    ('results/integrin_cavity/screenshot_2x22_stapled_x3.png',
     'Step 3: AutoStaple + AutoBreak x3 (220+ staples, minLegLen=3)'),
]

fig, axes = plt.subplots(3, 1, figsize=(14, 9))

for ax, (path, title) in zip(axes, shots):
    if os.path.exists(path):
        img = Image.open(path)
        ax.imshow(img)
    ax.set_title(title, fontsize=10, fontweight='bold', loc='left')
    ax.axis('off')

fig.suptitle('Figure 9: Targeted Design Edits from Natural Language Prompts\n'
             '2x22 integrin cavity design, p8064 scaffold',
             fontsize=12, fontweight='bold')
plt.tight_layout(rect=[0, 0, 1, 0.94])

out = 'results/paper_figures/fig_targeted_edits_sequence.png'
plt.savefig(out, dpi=120, bbox_inches='tight')
plt.close()

im = Image.open(out)
print(f'Saved: {out} ({im.size[0]}x{im.size[1]}px)')
