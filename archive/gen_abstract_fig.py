#!/usr/bin/env python
"""
Generate a single composite figure for the 1-page abstract.

Layout:
  Top row (A): Early failure → User correction → Autonomous result
  Bottom row (B): Three parametric cavity variants (20/30/40nm)
                  each showing caDNAno, tacoxDNA 3D, oxDNA relaxed

Usage:
    python -m tools.gen_abstract_fig
"""
import os
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from PIL import Image
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGURES = os.path.join(ROOT, 'drafts', 'paper_package', 'figures')
ASSETS = os.path.join(ROOT, 'results', 'paper_figure_assets')
OUT = os.path.join(FIGURES, 'fig_abstract.png')


def load_crop(path, pad=5):
    """Load image and auto-crop whitespace."""
    img = np.array(Image.open(path))
    if img.ndim == 3:
        non_white = np.any(img[:, :, :3] < 245, axis=2)
    else:
        non_white = img < 245
    rows = np.where(non_white.any(axis=1))[0]
    cols = np.where(non_white.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return img
    r0 = max(0, rows[0] - pad)
    r1 = min(img.shape[0], rows[-1] + pad)
    c0 = max(0, cols[0] - pad)
    c1 = min(img.shape[1], cols[-1] + pad)
    return img[r0:r1, c0:c1]


def main():
    fig = plt.figure(figsize=(16, 10))
    fig.patch.set_facecolor('white')

    # Top row: 3 columns (early failure, user template, autonomous result)
    # Bottom row: 3 columns (20nm, 30nm, 40nm variants)
    gs = GridSpec(2, 3, figure=fig, height_ratios=[1, 1],
                  hspace=0.25, wspace=0.15,
                  left=0.03, right=0.97, top=0.95, bottom=0.02)

    # === Top row (A): The journey ===
    # A1: Early failure
    ax1 = fig.add_subplot(gs[0, 0])
    img = load_crop(os.path.join(FIGURES, 'abstract_components', 'early_2x14_naive_path.png'))
    ax1.imshow(img)
    ax1.axis('off')
    ax1.set_title('Early agent output\n(2-by-14, 65 scaffold oligos)', fontsize=9,
                  fontweight='bold', color='#dc2626', pad=6)

    # A2: User-provided template
    ax2 = fig.add_subplot(gs[0, 1])
    img = load_crop(os.path.join(FIGURES, 'fig4b_cavity_template_scaffonly_path.png'))
    ax2.imshow(img)
    ax2.axis('off')
    ax2.set_title('User-provided template\n(2-by-12 with cavity, 1 scaffold oligo)', fontsize=9,
                  fontweight='bold', color='#2563eb', pad=6)

    # A3: Autonomous result
    ax3 = fig.add_subplot(gs[0, 2])
    img = load_crop(os.path.join(FIGURES, 'fig4d_stapled_path.png'))
    ax3.imshow(img)
    ax3.axis('off')
    ax3.set_title('Autonomous output\n(2-by-22 stapled, 220+ staples)', fontsize=9,
                  fontweight='bold', color='#16a34a', pad=6)

    # Arrows between top panels
    for x in [0.34, 0.66]:
        fig.text(x, 0.72, '\u2192', fontsize=28, ha='center', va='center',
                color='#374151', fontweight='bold')

    # Row label
    fig.text(0.01, 0.72, 'A', fontsize=14, fontweight='bold', va='center', ha='left')

    # === Bottom row (B): Parametric cavity variants ===
    variants = [
        ('20 nm cavity', 'cavity_20nm_initial.png', 'cavity_20nm_relaxed.png'),
        ('30 nm cavity', 'cavity_30nm_initial.png', 'cavity_30nm_relaxed.png'),
        ('40 nm cavity', 'cavity_40nm_initial.png', 'cavity_40nm_relaxed.png'),
    ]

    for col, (label, initial_fn, relaxed_fn) in enumerate(variants):
        ax = fig.add_subplot(gs[1, col])

        # Compose initial (top) and relaxed (bottom) side by side
        img_init = load_crop(os.path.join(ASSETS, initial_fn))
        img_relax = load_crop(os.path.join(ASSETS, relaxed_fn))

        # Stack vertically
        # Resize to same width
        target_w = max(img_init.shape[1], img_relax.shape[1])
        def resize_to_width(img, w):
            h = int(img.shape[0] * w / img.shape[1])
            return np.array(Image.fromarray(img).resize((w, h), Image.LANCZOS))

        img_init = resize_to_width(img_init, target_w)
        img_relax = resize_to_width(img_relax, target_w)

        # Add small gap
        gap = np.ones((10, target_w, img_init.shape[2]), dtype=np.uint8) * 255
        combined = np.vstack([img_init, gap, img_relax])

        ax.imshow(combined)
        ax.axis('off')
        ax.set_title(f'{label}\ntacoxDNA initial (top), oxDNA relaxed (bottom)', fontsize=9,
                    fontweight='bold', color='#374151', pad=6)

    # Row label
    fig.text(0.01, 0.25, 'B', fontsize=14, fontweight='bold', va='center', ha='left')

    plt.savefig(OUT, dpi=300, facecolor='white', bbox_inches='tight', pad_inches=0.1)
    plt.close()
    print(f'Saved: {OUT}')


if __name__ == '__main__':
    main()
