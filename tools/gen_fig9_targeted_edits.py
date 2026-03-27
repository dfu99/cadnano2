#!/usr/bin/env python
"""Generate Figure 8: Targeted Design Edits — one-shot from natural language prompts."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np
import os

shots = [
    ('results/integrin_cavity/screenshot_2x22_26x40nm.png',
     'Step 1: Shrink structure (moved edge crossovers inward, 7412bp, 1 oligo)'),
    ('results/integrin_cavity/screenshot_2x22_centered_v2.png',
     'Step 2: Move H5-H6, H13-H14, H15-H16 xovers away from cavity + center cavity (7432bp, 1 oligo)'),
    ('results/integrin_cavity/screenshot_2x22_stapled_x3.png',
     'Step 3: AutoStaple + AutoBreak x3 (220+ staples, minLegLen=3)'),
]

# Load all images to find the max width for centering
images = []
for path, title in shots:
    img = Image.open(path)
    images.append((np.array(img), title, img.size[0], img.size[1]))

max_w = max(w for _, _, w, _ in images)

fig, axes = plt.subplots(3, 1, figsize=(14, 9))

for ax, (img_arr, title, w, h) in zip(axes, images):
    # Pad image to max_w, centered
    if w < max_w:
        pad_left = (max_w - w) // 2
        pad_right = max_w - w - pad_left
        # White padding
        padded = np.ones((h, max_w, img_arr.shape[2]), dtype=img_arr.dtype) * 255
        padded[:, pad_left:pad_left+w, :] = img_arr
        ax.imshow(padded)
    else:
        ax.imshow(img_arr)
    ax.set_title(title, fontsize=10, fontweight='bold', loc='left')
    ax.axis('off')

plt.tight_layout()

out = 'results/paper_figures/fig_targeted_edits_sequence.png'
plt.savefig(out, dpi=120, bbox_inches='tight')
plt.close()

im = Image.open(out)
print(f'Saved: {out} ({im.size[0]}x{im.size[1]}px)')
