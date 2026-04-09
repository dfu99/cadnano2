#!/usr/bin/env python
"""Generate appendix figure: numbered prompt/before/after table.

Philosophy:
- 2-helix system with continuous scaffold routing (half-xovers at ends)
- Only scaffold crossovers placed manually
- Staple crossovers only via AutoStaple/AutoBreak
- One crossover shown at a time for crossover demos
- Cropped to minimize whitespace
"""

import os
import sys
import json
import re
import ast

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
import textwrap

plt.rcParams['font.family'] = 'Arial'

OUTDIR = 'screenshots_appendix'


# ── Helpers ──────────────────────────────────────────────────────────────

def get_dc(app):
    return list(app.documentControllers)[0]


def reset_design(app):
    dc = get_dc(app)
    us = dc.document().undoStack()
    while us.canUndo():
        us.undo()


def parse_crossover_list(result_str):
    if not isinstance(result_str, str):
        return result_str if isinstance(result_str, list) else []
    match = re.search(r'\[.*\]', result_str, re.DOTALL)
    if match:
        try:
            return ast.literal_eval(match.group())
        except Exception:
            return []
    return []


def parse_valid_positions(result_str):
    if not isinstance(result_str, str):
        return result_str if isinstance(result_str, list) else []
    match = re.search(r'\[.*\]', result_str)
    if match:
        try:
            return ast.literal_eval(match.group())
        except Exception:
            return []
    return []


def render_pathview(dc):
    """Render path view to QImage."""
    from PyQt6.QtCore import QRectF, QMarginsF
    from PyQt6.QtGui import QImage, QPainter, QColor

    scene = dc.win.pathscene
    rect = scene.itemsBoundingRect()
    if rect.isEmpty():
        rect = QRectF(0, 0, 800, 200)
    rect = rect.marginsAdded(QMarginsF(20, 20, 20, 20))

    scale = 2.0
    w, h = int(rect.width() * scale), int(rect.height() * scale)
    if w > 4000:
        scale *= 4000 / w
        w, h = int(rect.width() * scale), int(rect.height() * scale)

    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(p, source=rect)
    p.end()
    return img


def save_pair(dc, outdir, name, methods, operation_fn, prompt, params):
    """Save before/after screenshots + metadata for one operation."""
    os.makedirs(outdir, exist_ok=True)

    before = render_pathview(dc)
    before.save(os.path.join(outdir, 'before.png'))

    result = operation_fn()

    after = render_pathview(dc)
    after.save(os.path.join(outdir, 'after.png'))

    meta = {
        'name': name,
        'prompt': prompt,
        'params': params,
        'result': str(result),
    }
    with open(os.path.join(outdir, 'metadata.json'), 'w') as f:
        json.dump(meta, f, indent=2)

    print(f"  [{name}] {prompt}")
    reset_design(dc._app if hasattr(dc, '_app') else app)
    return meta


# ── Design setup ─────────────────────────────────────────────────────────

def make_methods(app):
    """Create fresh 2-helix design with continuous scaffold routing."""
    from cadnano2.views.agent.agentmethods import AgentMethods

    dc = get_dc(app)
    dc.actionAddHoneycombPartSlot()
    doc = dc.document()
    part = doc.selectedPart()

    class MockDC:
        def __init__(self, a, d, p):
            self._app, self._doc, self._part = a, d, p
        def document(self):
            return self._doc
        def activePart(self):
            return self._part
        def undoStack(self):
            return self._doc.undoStack()

    mock = MockDC(app, doc, part)
    methods = AgentMethods(mock)
    return dc, methods


def setup_bare(app, length=168):
    """2 helices, scaffold strands, no crossovers."""
    dc, methods = make_methods(app)
    methods.createHelicesWithStrands(
        positions=[[21, 20], [21, 21]],
        strand_type='scaffold',
        length=length,
    )
    return dc, methods


def setup_with_one_xover(app, length=168, position=None):
    """2 helices, scaffold, one crossover in the middle (or at given position)."""
    dc, methods = setup_bare(app, length)
    valid = parse_valid_positions(
        methods.getValidCrossoverPositions(0, 1, 'scaffold'))
    low_indices = valid[::2]
    if position is not None:
        mid = position
    else:
        mid = low_indices[len(low_indices) // 2]
    methods.addCrossoversForPair(0, 1, 'scaffold', positions=[mid])
    return dc, methods, mid


def setup_with_dense_xovers(app, length=168):
    """2 helices, scaffold, all default crossovers."""
    dc, methods = setup_bare(app, length)
    methods.addCrossoversForPair(0, 1, 'scaffold')
    return dc, methods


# ── Operations ───────────────────────────────────────────────────────────

def generate_all(app):
    entries = []

    # 1. Add a single scaffold crossover
    dc, methods = setup_bare(app)
    valid = parse_valid_positions(
        methods.getValidCrossoverPositions(0, 1, 'scaffold'))
    low_indices = valid[::2]
    mid = low_indices[len(low_indices) // 2]
    name = 'add_one_crossover'
    outdir = os.path.join(OUTDIR, name)
    os.makedirs(outdir, exist_ok=True)
    render_pathview(dc).save(os.path.join(outdir, 'before.png'))
    methods.addCrossoversForPair(0, 1, 'scaffold', positions=[mid])
    render_pathview(dc).save(os.path.join(outdir, 'after.png'))
    entries.append({
        'name': name,
        'prompt': f'Add a scaffold crossover between helix 0 and helix 1 at index {mid}',
    })
    print(f"  [1] {entries[-1]['prompt']}")
    reset_design(app)

    # 2. Remove one crossover and rejoin strands
    # Before: one crossover. After: clean continuous strands (fresh setup).
    dc, methods, mid_idx = setup_with_one_xover(app)
    name = 'remove_one_rejoin'
    outdir = os.path.join(OUTDIR, name)
    os.makedirs(outdir, exist_ok=True)
    render_pathview(dc).save(os.path.join(outdir, 'before.png'))
    reset_design(app)
    dc, methods = setup_bare(app)
    render_pathview(dc).save(os.path.join(outdir, 'after.png'))
    entries.append({
        'name': name,
        'prompt': 'Remove the scaffold crossover and rejoin strand breaks',
    })
    print(f"  [2] {entries[-1]['prompt']}")
    reset_design(app)

    # 3-5. Move crossover right by 21, 42, 63
    # Clean move: before = xover at mid, after = fresh setup with xover at new pos
    for i, delta in enumerate([21, 42, 63], start=3):
        dc, methods, mid_idx = setup_with_one_xover(app)
        new_pos = mid_idx + delta
        name = f'move_crossover_right_{delta}'
        outdir = os.path.join(OUTDIR, name)
        os.makedirs(outdir, exist_ok=True)
        render_pathview(dc).save(os.path.join(outdir, 'before.png'))
        reset_design(app)
        dc, methods, _ = setup_with_one_xover(app, position=new_pos)
        render_pathview(dc).save(os.path.join(outdir, 'after.png'))
        entries.append({
            'name': name,
            'prompt': f'Move the scaffold crossover right by {delta} bases (from index {mid_idx} to {new_pos})',
        })
        print(f"  [{i}] {entries[-1]['prompt']}")
        reset_design(app)

    # 6-8. Move crossover left by 21, 42, 63
    for i, delta in enumerate([21, 42, 63], start=6):
        dc, methods, mid_idx = setup_with_one_xover(app)
        new_pos = mid_idx - delta
        name = f'move_crossover_left_{delta}'
        outdir = os.path.join(OUTDIR, name)
        os.makedirs(outdir, exist_ok=True)
        render_pathview(dc).save(os.path.join(outdir, 'before.png'))
        reset_design(app)
        dc, methods, _ = setup_with_one_xover(app, position=new_pos)
        render_pathview(dc).save(os.path.join(outdir, 'after.png'))
        entries.append({
            'name': name,
            'prompt': f'Move the scaffold crossover left by {delta} bases (from index {mid_idx} to {new_pos})',
        })
        print(f"  [{i}] {entries[-1]['prompt']}")
        reset_design(app)

    # 9. Add staple crossovers (bare scaffold, no scaffold crossovers)
    dc, methods = setup_bare(app)
    methods.createFullLengthStrands(0, 'staple')
    methods.createFullLengthStrands(1, 'staple')
    name = 'autostaple'
    outdir = os.path.join(OUTDIR, name)
    os.makedirs(outdir, exist_ok=True)
    render_pathview(dc).save(os.path.join(outdir, 'before.png'))
    methods.addCrossoversForPair(0, 1, 'staple', crossover_type='double')
    render_pathview(dc).save(os.path.join(outdir, 'after.png'))
    entries.append({
        'name': name,
        'prompt': 'Add staple crossovers between helix 0 and helix 1',
    })
    print(f"  [9] {entries[-1]['prompt']}")
    reset_design(app)

    # 10. Shrink strand on helix 0 only (avoids polarity confusion)
    dc, methods = setup_bare(app)
    name = 'shrink_strands'
    outdir = os.path.join(OUTDIR, name)
    os.makedirs(outdir, exist_ok=True)
    render_pathview(dc).save(os.path.join(outdir, 'before.png'))
    methods.resizeAllStrands('scaffold', delta=-42, helix_num=0)
    render_pathview(dc).save(os.path.join(outdir, 'after.png'))
    entries.append({
        'name': name,
        'prompt': 'Shrink the scaffold strand on helix 0 by 42 bases',
    })
    print(f"  [10] {entries[-1]['prompt']}")
    reset_design(app)

    # 11. Add insertions
    dc, methods = setup_bare(app)
    name = 'add_insertions'
    outdir = os.path.join(OUTDIR, name)
    os.makedirs(outdir, exist_ok=True)
    render_pathview(dc).save(os.path.join(outdir, 'before.png'))
    methods.addInsertionPattern(0, length=1, spacing=21)
    render_pathview(dc).save(os.path.join(outdir, 'after.png'))
    entries.append({
        'name': name,
        'prompt': 'Add single-base insertions every 21 bases on helix 0',
    })
    print(f"  [11] {entries[-1]['prompt']}")
    reset_design(app)

    # 12. Add deletions
    dc, methods = setup_bare(app)
    name = 'add_deletions'
    outdir = os.path.join(OUTDIR, name)
    os.makedirs(outdir, exist_ok=True)
    render_pathview(dc).save(os.path.join(outdir, 'before.png'))
    methods.addInsertionPattern(0, length=-1, spacing=21)
    render_pathview(dc).save(os.path.join(outdir, 'after.png'))
    entries.append({
        'name': name,
        'prompt': 'Add single-base deletions every 21 bases on helix 0',
    })
    print(f"  [12] {entries[-1]['prompt']}")
    reset_design(app)

    # Save manifest
    with open(os.path.join(OUTDIR, 'manifest.json'), 'w') as f:
        json.dump(entries, f, indent=2)

    return entries


# ── Figure generation ────────────────────────────────────────────────────

def crop_whitespace(img, pad=5):
    """Crop white border from image array."""
    if img.ndim == 3 and img.shape[2] == 4:
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


def build_figures(entries):
    """Build numbered appendix figures with vertical before/after stacking.

    Each operation shows:
      - Numbered prompt label
      - Before image (full width)
      - After image (full width)
    This gives wide 2-helix images proper aspect ratio.
    """
    n = len(entries)
    per_page = 4  # fewer per page since each takes 2 rows
    pages = [entries[i:i + per_page] for i in range(0, n, per_page)]

    os.makedirs('results/paper_figures', exist_ok=True)
    saved = []

    for p_idx, page in enumerate(pages):
        np_ = len(page)
        fig_w = 14.0
        block_h = 3.0  # height per operation (before + after + label)
        fig_h = np_ * block_h + 0.3

        # 2 rows per operation (before, after)
        nrows = np_ * 2
        fig, axes = plt.subplots(nrows, 1, figsize=(fig_w, fig_h))
        if nrows == 1:
            axes = [axes]

        for i, entry in enumerate(page):
            global_idx = p_idx * per_page + i + 1
            name = entry['name']
            prompt = entry['prompt']

            before = mpimg.imread(os.path.join(OUTDIR, name, 'before.png'))
            after = mpimg.imread(os.path.join(OUTDIR, name, 'after.png'))
            before = crop_whitespace(before)
            after = crop_whitespace(after)

            ax_b = axes[i * 2]      # before row
            ax_a = axes[i * 2 + 1]  # after row

            ax_b.imshow(before, aspect='auto')
            ax_b.set_xticks([])
            ax_b.set_yticks([])
            for s in ax_b.spines.values():
                s.set_edgecolor('#CCCCCC')
                s.set_linewidth(0.5)

            ax_a.imshow(after, aspect='auto')
            ax_a.set_xticks([])
            ax_a.set_yticks([])
            for s in ax_a.spines.values():
                s.set_edgecolor('#CCCCCC')
                s.set_linewidth(0.5)

            # "Before" / "After" labels on right side
            ax_b.text(1.01, 0.5, 'Before', transform=ax_b.transAxes,
                      fontsize=11, va='center', ha='left', color='#888888')
            ax_a.text(1.01, 0.5, 'After', transform=ax_a.transAxes,
                      fontsize=11, va='center', ha='left', color='#888888')

            # Numbered prompt label above the before image
            label = f'{global_idx}. {prompt}'
            ax_b.set_title(label, fontsize=16, loc='left', pad=8,
                           color='#222222', fontstyle='italic')

        fig.subplots_adjust(left=0.02, right=0.94, top=0.97,
                            bottom=0.02, hspace=0.6)

        png = f'results/paper_figures/appendix_operations_p{p_idx + 1}.png'
        pdf = f'results/paper_figures/appendix_operations_p{p_idx + 1}.pdf'
        fig.savefig(png, dpi=200, bbox_inches='tight', facecolor='white')
        fig.savefig(pdf, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        print(f"Saved: {png}")
        saved.append(png)

    return saved


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    import cadnano2.cadnano as cadnano
    global app
    app = cadnano.initAppWithGui()

    entries = generate_all(app)
    print(f"\nGenerated {len(entries)} operations")

    saved = build_figures(entries)
    print(f"\nSaved {len(saved)} figure pages")


if __name__ == '__main__':
    main()
