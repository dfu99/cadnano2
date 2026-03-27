#!/usr/bin/env python
"""Generate Figure 8: Targeted Design Edits — one-shot from natural language prompts.
Crop helix labels, center design content, center subcaptions."""
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

# Crop the orange helix label column from the left (~80px) and
# trim right white space. Then center all on a common canvas.
LABEL_CROP_LEFT = 80  # pixels to remove from left (helix number labels)

cropped = []
for path, title in shots:
    img = Image.open(path).convert('RGB')
    w, h = img.size
    # Crop left label column
    img = img.crop((LABEL_CROP_LEFT, 0, w, h))
    arr = np.array(img)
    # Find rightmost non-white column
    non_white_cols = np.where(np.any(arr < 240, axis=(0, 2)))[0]
    if len(non_white_cols) > 0:
        right_bound = non_white_cols[-1] + 10  # small margin
        img = img.crop((0, 0, min(right_bound, img.size[0]), img.size[1]))
    # Find topmost/bottommost non-white rows
    non_white_rows = np.where(np.any(np.array(img) < 240, axis=(1, 2)))[0]
    if len(non_white_rows) > 0:
        top = max(0, non_white_rows[0] - 5)
        bot = min(img.size[1], non_white_rows[-1] + 5)
        img = img.crop((0, top, img.size[0], bot))
    cropped.append((img, title))
    print(f'  {os.path.basename(path)}: cropped to {img.size}')

# Find max width, center each on common canvas
max_w = max(c.size[0] for c, _ in cropped)
centered_imgs = []
for c, title in cropped:
    w, h = c.size
    canvas = Image.new('RGB', (max_w, h), (255, 255, 255))
    paste_x = (max_w - w) // 2
    canvas.paste(c, (paste_x, 0))
    centered_imgs.append((np.array(canvas), title))

fig, axes = plt.subplots(3, 1, figsize=(14, 9))

for ax, (img_arr, title) in zip(axes, centered_imgs):
    ax.imshow(img_arr)
    ax.set_title(title, fontsize=10, fontweight='bold', loc='center')
    ax.axis('off')

plt.tight_layout()

out = 'results/paper_figures/fig_targeted_edits_sequence.png'
plt.savefig(out, dpi=150, bbox_inches='tight')
plt.close()

im = Image.open(out)
print(f'Saved: {out} ({im.size[0]}x{im.size[1]}px)')
