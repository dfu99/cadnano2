#!/usr/bin/env python
"""Generate appendix figures: prompt / before / after table from screenshots library."""

import json
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np

plt.rcParams['font.family'] = 'Arial'

SCREENSHOTS = 'screenshots'

# Curated examples — one per operation type × design context, for diversity
EXAMPLES = [
    # --- 2-helix basic operations ---
    'add_3_evenly_spaced_crossovers',
    'move_crossover_right_5',
    'move_staple_crossover_left_3',
    'delete_crossover_middle',
    'resize_strands_extend_21',
    'resize_strands_shrink_7',
    'insertion_pattern_insertion_3',
    'insertion_pattern_deletion_1',
    'split_strand_at_63',
    'auto_break_staples',
    'add_staple_crossovers',
    'remove_all_crossovers_pair',
    # --- Multi-helix designs ---
    'three_helix_add_all_crossovers',
    'six_helix_add_both_crossovers',
    'six_helix_move_crossover_right_3',
    'six_helix_auto_break',
    'six_helix_insertion_pattern_all',
    'six_helix_delete_crossover_edge_pair',
    'grid_add_both_crossovers',
    'grid_insertion_pattern',
    'l_shape_add_both_crossovers',
    'l_shape_remove_bend_pair',
    't_shape_add_both_crossovers',
    't_shape_remove_stem_pair',
]


def load_example(name):
    """Load metadata + images for one example."""
    d = os.path.join(SCREENSHOTS, name)
    with open(os.path.join(d, 'metadata.json')) as f:
        meta = json.load(f)
    before = mpimg.imread(os.path.join(d, 'before.png'))
    after = mpimg.imread(os.path.join(d, 'after.png'))
    prompt = meta.get('natural_language', meta.get('description', name))
    return prompt, before, after


def crop_whitespace(img, pad=5):
    """Crop white/near-white border from RGBA or RGB image."""
    if img.ndim == 3 and img.shape[2] == 4:
        # RGBA — treat alpha < 0.5 as white
        gray = np.mean(img[:, :, :3], axis=2)
        mask = (gray < 0.95) & (img[:, :, 3] > 0.5)
    else:
        gray = np.mean(img, axis=2) if img.ndim == 3 else img
        mask = gray < 0.95
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any() or not cols.any():
        return img
    r0, r1 = np.where(rows)[0][[0, -1]]
    c0, c1 = np.where(cols)[0][[0, -1]]
    r0 = max(0, r0 - pad)
    r1 = min(img.shape[0], r1 + pad + 1)
    c0 = max(0, c0 - pad)
    c1 = min(img.shape[1], c1 + pad + 1)
    return img[r0:r1, c0:c1]


def make_page(examples, page_num, total_pages):
    """Create one page/figure with up to 12 rows."""
    n = len(examples)
    # Load and crop all images
    rows_data = []
    for name in examples:
        prompt, before, after = load_example(name)
        before = crop_whitespace(before)
        after = crop_whitespace(after)
        rows_data.append((prompt, before, after))

    # Figure: each row has prompt text + before + after
    row_height = 1.0
    fig_width = 10.0
    fig_height = n * row_height + 0.6  # extra for title

    fig, axes = plt.subplots(n, 2, figsize=(fig_width, fig_height))
    if n == 1:
        axes = axes.reshape(1, 2)

    fig.suptitle(f'Appendix: Agent Operations Library ({page_num}/{total_pages})',
                 fontsize=11, fontweight='bold', y=1.0)

    # Column headers
    header_y = 1.0 - 0.25 / fig_height
    fig.text(0.30, header_y, 'Before', ha='center', fontsize=9,
             fontweight='bold', color='#444444')
    fig.text(0.74, header_y, 'After', ha='center', fontsize=9,
             fontweight='bold', color='#444444')

    for i, (prompt, before, after) in enumerate(rows_data):
        ax_b = axes[i, 0]
        ax_a = axes[i, 1]

        # Before image
        ax_b.imshow(before, aspect='auto')
        ax_b.set_xticks([])
        ax_b.set_yticks([])
        for spine in ax_b.spines.values():
            spine.set_edgecolor('#CCCCCC')
            spine.set_linewidth(0.5)

        # After image
        ax_a.imshow(after, aspect='auto')
        ax_a.set_xticks([])
        ax_a.set_yticks([])
        for spine in ax_a.spines.values():
            spine.set_edgecolor('#CCCCCC')
            spine.set_linewidth(0.5)

        # Prompt as row label on the left
        # Wrap long prompts
        wrapped = prompt
        if len(prompt) > 55:
            # Break at a space near the middle
            mid = len(prompt) // 2
            space_pos = prompt.rfind(' ', 0, mid + 10)
            if space_pos > 10:
                wrapped = prompt[:space_pos] + '\n' + prompt[space_pos + 1:]

        ax_b.set_ylabel(wrapped, fontsize=5.5, rotation=0, labelpad=5,
                        ha='right', va='center', color='#222222',
                        fontstyle='italic')

    fig.subplots_adjust(left=0.22, right=0.98, top=1.0 - 0.5 / fig_height,
                        bottom=0.02, hspace=0.3, wspace=0.04)

    return fig


def main():
    # Filter to existing examples
    valid = [e for e in EXAMPLES if os.path.isdir(os.path.join(SCREENSHOTS, e))]
    print(f"Found {len(valid)}/{len(EXAMPLES)} examples")

    # Split into pages of 12
    per_page = 12
    pages = [valid[i:i + per_page] for i in range(0, len(valid), per_page)]
    total = len(pages)

    os.makedirs('results/paper_figures', exist_ok=True)
    saved = []

    for p_idx, page_examples in enumerate(pages):
        fig = make_page(page_examples, p_idx + 1, total)
        png_path = f'results/paper_figures/appendix_operations_p{p_idx + 1}.png'
        pdf_path = f'results/paper_figures/appendix_operations_p{p_idx + 1}.pdf'
        fig.savefig(png_path, dpi=200, bbox_inches='tight', facecolor='white')
        fig.savefig(pdf_path, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        print(f"Saved: {png_path}")
        saved.append((png_path, pdf_path))

    return saved


if __name__ == '__main__':
    main()
