#!/usr/bin/env python
"""Generate side-by-side prompt/expected/reproduced figures for the caDNAgentic checklist."""

import os, sys, io, json
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Must init Qt app BEFORE matplotlib touches fonts
import cadnano2.cadnano as cadnano
_app = cadnano.initAppWithGui()

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np

plt.rcParams['font.family'] = 'Arial'

CADNAGENTIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           '..', 'caDNAgentic')
OUTDIR = '/tmp/checklist_screenshots'


def render_design(json_path, png_path, app, decode_fn):
    """Load a cadnano JSON and render path view to PNG."""
    from PyQt6.QtCore import QMarginsF, QRectF
    from PyQt6.QtGui import QImage, QPainter, QColor

    dc = list(app.documentControllers)[0]
    doc = dc.document()

    # Reset: undo everything
    us = doc.undoStack()
    while us.canUndo():
        us.undo()

    with io.open(json_path, 'r', encoding='utf-8') as fd:
        decode_fn(doc, fd.read())

    scene = dc.win.pathscene
    rect = scene.itemsBoundingRect()
    if rect.isEmpty():
        rect = QRectF(0, 0, 1600, 400)
    rect = rect.marginsAdded(QMarginsF(30, 30, 30, 30))

    scale = 2.0
    w, h = int(rect.width() * scale), int(rect.height() * scale)
    if w > 3000:
        scale *= 3000 / w
        w, h = int(rect.width() * scale), int(rect.height() * scale)

    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(p, source=rect)
    p.end()
    img.save(png_path)

    # Reset for next design
    while us.canUndo():
        us.undo()

    return png_path


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


# Define the test cases
TESTS = [
    # (name, prompt, expected_json, reproduced_json, verifier_expect)
    # Templates
    {
        'name': 'Template: 2x12 rectangle with cavity',
        'prompt': 'PI-provided 2x12 rectangle with 4-column cavity\n(24 helices, 5036bp scaffold, 1 oligo)',
        'expected': os.path.join(CADNAGENTIC, 'templates', '2x12_rectangle_cavity.json'),
        'reproduced': None,  # template only, no reproduction
        'verify': '24 helices, 5036bp, 1 oligo',
    },
    {
        'name': 'Template: 2x22 extended with cavity',
        'prompt': 'Extended 2x22 rectangle with 10-column centered cavity\n(44 helices, 7432bp scaffold, 1 oligo)',
        'expected': os.path.join(CADNAGENTIC, 'templates', 'design_2x22_centered_v2.json'),
        'reproduced': None,
        'verify': '44 helices, 7432bp, 1 oligo',
    },
    # Cavity variants
    {
        'name': 'Cavity 20nm (2x12)',
        'prompt': 'Create a 2x12 DNA origami rectangle\nwith a 20nm cavity\n(24 helices, 8368bp, 1 oligo)',
        'expected': os.path.join(CADNAGENTIC, 'designs', 'cavity_variants', 'cavity_20nm_2x12_8064bp.json'),
        'reproduced': os.path.join(CADNAGENTIC, 'results', 'cavity_variants', 'cavity_20nm_2x12_8064bp.json'),
        'verify': '24 helices, 8368bp, 1 oligo',
    },
    {
        'name': 'Cavity 30nm (2x12)',
        'prompt': 'Create a 2x12 DNA origami rectangle\nwith a 30nm cavity\n(24 helices, 8616bp, 1 oligo)',
        'expected': os.path.join(CADNAGENTIC, 'designs', 'cavity_variants', 'cavity_30nm_2x12_8064bp.json'),
        'reproduced': os.path.join(CADNAGENTIC, 'results', 'cavity_variants', 'cavity_30nm_2x12_8064bp.json'),
        'verify': '24 helices, 8616bp, 1 oligo',
    },
    {
        'name': 'Cavity 40nm (2x12)',
        'prompt': 'Create a 2x12 DNA origami rectangle\nwith a 40nm cavity\n(24 helices, 8404bp, 1 oligo)',
        'expected': os.path.join(CADNAGENTIC, 'designs', 'cavity_variants', 'cavity_40nm_2x12_8064bp.json'),
        'reproduced': os.path.join(CADNAGENTIC, 'results', 'cavity_variants', 'cavity_40nm_2x12_8064bp.json'),
        'verify': '24 helices, 8404bp, 1 oligo',
    },
    # Cavity sweep
    {
        'name': 'Cavity 40x26nm (2x22)',
        'prompt': 'Create a 2x22 origami with\n40nm x 26nm cavity\n(44 helices, 7402bp, 1 oligo)',
        'expected': os.path.join(CADNAGENTIC, 'designs', 'cavity_sweep', 'cavity_40x26nm_2x22_pad6.json'),
        'reproduced': os.path.join(CADNAGENTIC, 'results', 'cavity_sweep', 'cavity_40x26nm_2x22_pad6.json'),
        'verify': '44 helices, 7402bp, 1 oligo',
    },
    {
        'name': 'Cavity 45x26nm (2x22)',
        'prompt': 'Create a 2x22 origami with\n45nm x 26nm cavity\n(44 helices, 7102bp, 1 oligo)',
        'expected': os.path.join(CADNAGENTIC, 'designs', 'cavity_sweep', 'cavity_45x26nm_2x22_pad6.json'),
        'reproduced': os.path.join(CADNAGENTIC, 'results', 'cavity_sweep', 'cavity_45x26nm_2x22_pad6.json'),
        'verify': '44 helices, 7102bp, 1 oligo',
    },
    {
        'name': 'Cavity 50x26nm (2x22)',
        'prompt': 'Create a 2x22 origami with\n50nm x 26nm cavity\n(44 helices, 6882bp, 1 oligo)',
        'expected': os.path.join(CADNAGENTIC, 'designs', 'cavity_sweep', 'cavity_50x26nm_2x22_pad6.json'),
        'reproduced': os.path.join(CADNAGENTIC, 'results', 'cavity_sweep', 'cavity_50x26nm_2x22_pad6.json'),
        'verify': '44 helices, 6882bp, 1 oligo',
    },
    # Stapled design
    {
        'name': 'Stapled 2x22 with cavity',
        'prompt': 'Create a 2x22 origami with centered\ncavity, add staples and break them\n(44 helices, 7432bp, 1 oligo, ~245 staples)',
        'expected': os.path.join(CADNAGENTIC, 'designs', 'integrin_cavity', 'design_2x22_stapled_x3.json'),
        'reproduced': None,  # requires cadnano2 autostaple, can't reproduce purely
        'verify': '44 helices, 7432bp, 1 oligo',
    },
]


def main():
    from cadnano2.model.io.decoder import decode

    app = _app
    os.makedirs(OUTDIR, exist_ok=True)

    # Render all designs
    print("Rendering designs...")
    for i, t in enumerate(TESTS):
        tag = t['name'].replace(' ', '_').replace(':', '').replace('(', '').replace(')', '')

        # Render expected
        exp_png = os.path.join(OUTDIR, f'{i:02d}_expected.png')
        render_design(t['expected'], exp_png, app, decode)
        t['expected_png'] = exp_png
        print(f"  [{i+1}/{len(TESTS)}] Expected: {os.path.basename(t['expected'])}")

        # Render reproduced (if available)
        if t['reproduced'] and os.path.exists(t['reproduced']):
            rep_png = os.path.join(OUTDIR, f'{i:02d}_reproduced.png')
            render_design(t['reproduced'], rep_png, app, decode)
            t['reproduced_png'] = rep_png

            # Check if they match
            with open(t['expected']) as f: ej = json.load(f)
            with open(t['reproduced']) as f: rj = json.load(f)
            t['match'] = json.dumps(ej, sort_keys=True) == json.dumps(rj, sort_keys=True)
            print(f"           Reproduced: {'MATCH' if t['match'] else 'MISMATCH'}")
        else:
            t['reproduced_png'] = None
            t['match'] = None

    # Build figures - Page 1: Templates + Cavity Variants (5 tests)
    # Page 2: Cavity Sweep + Stapled (4 tests)
    pages = [TESTS[:5], TESTS[5:]]

    saved = []
    for p_idx, page in enumerate(pages):
        n = len(page)
        has_repro = any(t.get('reproduced_png') for t in page)
        ncols = 3 if has_repro else 2  # prompt | expected | reproduced

        fig_w = 16
        row_h = 3.0
        fig_h = n * row_h + 1.0

        fig, axes = plt.subplots(n, ncols, figsize=(fig_w, fig_h),
                                  gridspec_kw={'width_ratios': [1.2, 2, 2][:ncols]})
        if n == 1:
            axes = [axes]

        for i, t in enumerate(page):
            row = axes[i] if n > 1 else axes

            # Prompt column
            ax_p = row[0]
            ax_p.set_xlim(0, 1)
            ax_p.set_ylim(0, 1)
            ax_p.text(0.5, 0.5, t['prompt'], fontsize=11, ha='center', va='center',
                      wrap=True, fontstyle='italic', color='#333333',
                      transform=ax_p.transAxes)
            ax_p.set_xticks([])
            ax_p.set_yticks([])
            for s in ax_p.spines.values():
                s.set_edgecolor('#CCCCCC')
                s.set_linewidth(0.5)

            # Header for first row
            if i == 0:
                ax_p.set_title('Prompt', fontsize=14, fontweight='bold', pad=10)

            # Expected column
            ax_e = row[1]
            exp_img = mpimg.imread(t['expected_png'])
            exp_img = crop_whitespace(exp_img)
            ax_e.imshow(exp_img, aspect='auto')
            ax_e.set_xticks([])
            ax_e.set_yticks([])
            for s in ax_e.spines.values():
                s.set_edgecolor('#CCCCCC')
                s.set_linewidth(0.5)
            if i == 0:
                ax_e.set_title('Expected (stored design)', fontsize=14, fontweight='bold', pad=10)

            # Reproduced column (if applicable)
            if ncols == 3:
                ax_r = row[2]
                if t.get('reproduced_png'):
                    rep_img = mpimg.imread(t['reproduced_png'])
                    rep_img = crop_whitespace(rep_img)
                    ax_r.imshow(rep_img, aspect='auto')

                    # Match indicator
                    if t['match']:
                        ax_r.text(0.98, 0.02, 'MATCH', fontsize=10,
                                  ha='right', va='bottom', color='green',
                                  fontweight='bold', transform=ax_r.transAxes,
                                  bbox=dict(boxstyle='round,pad=0.3',
                                            facecolor='#e6ffe6', edgecolor='green'))
                else:
                    ax_r.text(0.5, 0.5, '(template only\n— no reproduction)',
                              fontsize=10, ha='center', va='center',
                              color='#999999', fontstyle='italic',
                              transform=ax_r.transAxes)
                ax_r.set_xticks([])
                ax_r.set_yticks([])
                for s in ax_r.spines.values():
                    s.set_edgecolor('#CCCCCC')
                    s.set_linewidth(0.5)
                if i == 0:
                    ax_r.set_title('Reproduced (from tool)', fontsize=14, fontweight='bold', pad=10)

            # Row label on left
            global_idx = (p_idx * 5) + i + 1
            ax_p.text(-0.05, 0.5, f'{global_idx}.', fontsize=14, fontweight='bold',
                      ha='right', va='center', transform=ax_p.transAxes)

        fig.subplots_adjust(left=0.08, right=0.98, top=0.93, bottom=0.02,
                            hspace=0.4, wspace=0.1)

        page_title = ['Templates & Cavity Variants (2x12)', 'Cavity Sweep (2x22) & Stapled'][p_idx]
        fig.suptitle(f'Reproduction Checklist — {page_title}', fontsize=16, fontweight='bold', y=0.98)

        png = f'/tmp/checklist_p{p_idx+1}.png'
        fig.savefig(png, dpi=200, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        print(f"Saved: {png}")
        saved.append(png)

    return saved


if __name__ == '__main__':
    saved = main()
    print(f"\nGenerated {len(saved)} checklist pages")
