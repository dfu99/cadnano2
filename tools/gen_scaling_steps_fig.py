#!/usr/bin/env python
"""Regenerate the 4-step scaling figure with clean labels."""
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from PIL import Image
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), '..')
STEPS_DIR = os.path.join(ROOT, 'results', 'scale_steps')
OUT = os.path.join(ROOT, 'drafts', 'paper_package', 'figures', 'fig_scaling_steps.png')

steps = [
    ('Step 1: Scaffold only', 'step1_screenshot.png'),
    ('Step 2: Right side extended', 'step2_screenshot.png'),
    ('Step 3: Midseam moved to center', 'step3_screenshot.png'),
    ('Step 4: Cavity expanded and aligned', 'step4_screenshot.png'),
]

fig, axes = plt.subplots(2, 2, figsize=(14, 8))
fig.patch.set_facecolor('white')

for idx, (label, fname) in enumerate(steps):
    ax = axes[idx // 2][idx % 2]
    img = Image.open(os.path.join(STEPS_DIR, fname))
    arr = np.array(img)

    # Auto-crop whitespace
    if arr.ndim == 3:
        non_white = np.any(arr[:, :, :3] < 245, axis=2)
    else:
        non_white = arr < 245
    rows = np.where(non_white.any(axis=1))[0]
    cols = np.where(non_white.any(axis=0))[0]
    if len(rows) > 0 and len(cols) > 0:
        pad = 10
        r0 = max(0, rows[0] - pad)
        r1 = min(arr.shape[0], rows[-1] + pad)
        c0 = max(0, cols[0] - pad)
        c1 = min(arr.shape[1], cols[-1] + pad)
        arr = arr[r0:r1, c0:c1]

    ax.imshow(arr)
    ax.axis('off')
    ax.set_title(label, fontsize=12, fontweight='bold', color='#111827', pad=8)

plt.tight_layout(pad=1.5)
plt.savefig(OUT, dpi=300, facecolor='white', bbox_inches='tight')
plt.close()
print(f'Saved: {OUT}')
