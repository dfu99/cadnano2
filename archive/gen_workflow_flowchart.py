#!/usr/bin/env python
"""
Generate a workflow flowchart showing the knowledge formalization loop.

Three-column layout:
  Left: failure/correction path
  Center: main flow (target → attempt → evaluate → decision)
  Right: success/verified artifacts path

Retry loop arrow routes around the left edge, outside all blocks.

Usage:
    python -m tools.gen_workflow_flowchart
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(PROJECT_ROOT, 'results', 'paper_figure_assets')


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    os.makedirs(RESULTS_DIR, exist_ok=True)

    fig, ax = plt.subplots(figsize=(30, 18))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    ax.axis('off')
    ax.set_xlim(0, 30)
    ax.set_ylim(-1, 19)

    # Colors
    C_USER = '#2563eb'
    C_AGENT = '#7c3aed'
    C_ARTIFACT = '#059669'
    C_FAIL = '#dc2626'
    C_SUCCESS = '#16a34a'
    C_VERIFY = '#d97706'
    C_NEUTRAL = '#64748b'

    BW = 3.0   # box width
    BH = 1.2   # box height
    GAP = 1.2  # horizontal gap between boxes

    def box(x, y, w, h, text, color, fontsize=9, textcolor='white'):
        rect = FancyBboxPatch((x - w/2, y - h/2), w, h,
                               boxstyle='round,pad=0.3',
                               facecolor=color, edgecolor='none',
                               alpha=0.9, zorder=3)
        ax.add_patch(rect)
        ax.text(x, y, text, ha='center', va='center', fontsize=fontsize,
                fontweight='bold', color=textcolor, zorder=4,
                linespacing=1.4)

    def arrow(x1, y1, x2, y2, color='#374151', lw=1.5):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color=color, lw=lw),
                    zorder=2)

    def arrow_h(y, x1, x2, color='#374151', lw=1.5):
        arrow(x1, y, x2, y, color=color, lw=lw)

    def arrow_v(x, y1, y2, color='#374151', lw=1.5):
        arrow(x, y1, x, y2, color=color, lw=lw)

    def label(x, y, text, color='#6b7280', fontsize=8, ha='center', va='center'):
        ax.text(x, y, text, ha=ha, va=va, fontsize=fontsize,
                color=color, fontstyle='italic', zorder=5)

    def line(x1, y1, x2, y2, color='#374151', lw=1.5):
        ax.plot([x1, x2], [y1, y2], color=color, lw=lw, zorder=2)

    # =========================================================================
    # Row positions (Y)
    # =========================================================================
    ROW_MAIN = 14.0    # main flow
    ROW_FAIL = 7.0     # failure path
    ROW_BOTTOM = 1.5   # retry loop bottom channel

    # =========================================================================
    # MAIN FLOW (top row, left to right)
    # =========================================================================
    x0 = 2.5
    box(x0, ROW_MAIN, BW, BH, 'User specifies\ndesign target', C_USER, fontsize=10)

    x1 = x0 + BW/2 + GAP + BW/2
    arrow_h(ROW_MAIN, x0 + BW/2, x1 - BW/2)
    box(x1, ROW_MAIN, BW, BH, 'Agent writes &\nexecutes scripts', C_AGENT, fontsize=10)

    x2 = x1 + BW/2 + GAP + BW/2
    arrow_h(ROW_MAIN, x1 + BW/2, x2 - BW/2)
    box(x2, ROW_MAIN, BW, BH, 'Design produced\n(cadnano JSON)', C_NEUTRAL, fontsize=10)

    x3 = x2 + BW/2 + GAP + BW/2
    arrow_h(ROW_MAIN, x2 + BW/2, x3 - BW/2)
    box(x3, ROW_MAIN, BW, BH, 'User evaluates\nin cadnano GUI', C_USER, fontsize=10)

    # Decision diamond
    ds = 0.6
    xd = x3 + BW/2 + GAP + ds
    arrow_h(ROW_MAIN, x3 + BW/2, xd - ds)
    diamond = plt.Polygon([
        [xd, ROW_MAIN + ds], [xd + ds, ROW_MAIN],
        [xd, ROW_MAIN - ds], [xd - ds, ROW_MAIN],
    ], closed=True, facecolor='#f8fafc', edgecolor='#374151', lw=2, zorder=3)
    ax.add_patch(diamond)
    ax.text(xd, ROW_MAIN, 'Correct?', ha='center', va='center', fontsize=9,
            fontweight='bold', color='#374151', zorder=4)

    # =========================================================================
    # SUCCESS PATH (right, continues horizontally then down)
    # =========================================================================
    xs1 = xd + ds + GAP + BW/2
    arrow_h(ROW_MAIN, xd + ds, xs1 - BW/2, color=C_SUCCESS, lw=2.5)
    label(xd + ds + 0.5, ROW_MAIN + 0.45, 'Yes', color=C_SUCCESS, fontsize=11)
    box(xs1, ROW_MAIN, BW, BH, 'Working artifacts\n(conversation ctx)', '#94a3b8', fontsize=9)

    xs2 = xs1 + BW/2 + GAP + BW/2
    arrow_h(ROW_MAIN, xs1 + BW/2, xs2 - BW/2, color=C_SUCCESS)
    box(xs2, ROW_MAIN, BW, BH, 'Verification\n(verifier + user)', C_VERIFY, fontsize=9)

    # Verified artifacts box below verification
    ys_v = ROW_MAIN - BH/2 - GAP - 0.5
    arrow_v(xs2, ROW_MAIN - BH/2, ys_v + 0.5, color=C_SUCCESS)
    box(xs2, ys_v, 3.5, 1.0, 'Verified, persistent\nartifacts', C_SUCCESS, fontsize=10)

    # Verified sub-items (horizontal row below)
    verified_items = [
        'Pipeline\nscripts',
        'Design\nverifier',
        'Failure\ncatalog',
        'Distributable\ninstructions',
    ]
    vi_y = ys_v - 0.5 - GAP - 0.4
    vi_w = 2.4
    vi_gap = 0.2
    total_w = len(verified_items) * vi_w + (len(verified_items)-1) * vi_gap
    vi_start = xs2 - total_w / 2 + vi_w / 2
    arrow_v(xs2, ys_v - 0.5, vi_y + 0.4, color=C_SUCCESS, lw=1.0)
    for i, txt in enumerate(verified_items):
        vx = vi_start + i * (vi_w + vi_gap)
        box(vx, vi_y, vi_w, 0.8, txt, C_SUCCESS, fontsize=7.5)
        if i > 0:
            line(vi_start + (i-1) * (vi_w + vi_gap) + vi_w/2, vi_y,
                 vx - vi_w/2, vi_y, color=C_SUCCESS, lw=1.0)

    # =========================================================================
    # FAILURE PATH (down from diamond, then left-to-right row below)
    # =========================================================================
    arrow_v(xd, ROW_MAIN - ds, ROW_FAIL + BH/2, color=C_FAIL, lw=2.5)
    label(xd + 0.4, ROW_MAIN - ds - 0.4, 'No', color=C_FAIL, fontsize=11, ha='left')

    # Failure row (left to right)
    xf0 = 2.5
    box(xd, ROW_FAIL, BW, BH, 'User identifies\nfailure mode', C_USER, fontsize=10)

    xf1 = xd - BW/2 - GAP - BW/2
    arrow_h(ROW_FAIL, xd - BW/2, xf1 + BW/2, color=C_FAIL)
    box(xf1, ROW_FAIL, BW + 0.5, BH, 'User provides correction\n(prompt, examples,\ncorrected file)', C_USER, fontsize=8.5)

    xf2 = xf1 - (BW+0.5)/2 - GAP - BW/2
    arrow_h(ROW_FAIL, xf1 - (BW+0.5)/2, xf2 + BW/2)
    box(xf2, ROW_FAIL, BW, BH, 'Agent formalizes\ndomain knowledge', C_AGENT, fontsize=10)

    # Formalization artifacts (below the formalize box)
    art_y = ROW_FAIL - BH/2 - 0.8 - 0.4
    art_items = [
        'Pipeline scripts\n(parametric Python)',
        'Verifier checks\n(cadnano_verifier.py)',
        'Lessons & memory\n(tasks/lessons.md)',
    ]
    arrow_v(xf2, ROW_FAIL - BH/2, art_y + 0.4, color=C_ARTIFACT, lw=1.2)
    for i, txt in enumerate(art_items):
        ax_pos = xf2 - 3.5 + i * 3.5
        box(ax_pos, art_y, 3.2, 0.7, txt, C_ARTIFACT, fontsize=7.5)
        if ax_pos != xf2:
            arrow(xf2, art_y, ax_pos, art_y, color=C_ARTIFACT, lw=1.0)
    label(xf2, ROW_FAIL - BH/2 - 0.35, 'produces', color=C_ARTIFACT, fontsize=7.5)

    xf3 = xf2 - BW/2 - GAP - BW/2
    arrow_h(ROW_FAIL, xf2 - BW/2, xf3 + BW/2)
    box(xf3, ROW_FAIL, BW, BH, 'Agent retries with\nformalized knowledge', C_AGENT, fontsize=9)

    # =========================================================================
    # RETRY LOOP — goes down from retry, along bottom, back up to "Design produced"
    # =========================================================================
    line(xf3, ROW_FAIL - BH/2, xf3, ROW_BOTTOM, color=C_AGENT, lw=2)
    line(xf3, ROW_BOTTOM, x2, ROW_BOTTOM, color=C_AGENT, lw=2)
    arrow_v(x2, ROW_BOTTOM, ROW_MAIN - BH/2, color=C_AGENT, lw=2)
    label((xf3 + x2) / 2, ROW_BOTTOM + 0.4, 'retry loop', color=C_AGENT, fontsize=9)

    # =========================================================================
    # Legend
    # =========================================================================
    legend_y = 0.0
    legend_items = [
        (C_USER, 'User action'),
        (C_AGENT, 'Agent action'),
        (C_ARTIFACT, 'Intermediate artifact'),
        (C_SUCCESS, 'Verified output'),
        (C_VERIFY, 'Verification gate'),
    ]
    for i, (color, lbl) in enumerate(legend_items):
        lx = 2.5 + i * 2.6
        rect = FancyBboxPatch((lx - 0.3, legend_y - 0.15), 0.6, 0.3,
                               boxstyle='round,pad=0.05',
                               facecolor=color, edgecolor='none', alpha=0.9)
        ax.add_patch(rect)
        ax.text(lx + 0.5, legend_y, lbl, ha='left', va='center',
                fontsize=7.5, color='#374151')

    path = os.path.join(RESULTS_DIR, 'workflow_flowchart.png')
    plt.savefig(path, dpi=300, facecolor='white', bbox_inches='tight', pad_inches=0.3)
    plt.close()
    print(f"Flowchart saved: {path}")
    return path


if __name__ == '__main__':
    main()
