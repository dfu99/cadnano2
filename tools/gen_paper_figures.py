#!/usr/bin/env python
"""Generate publication-quality figures for AI-assisted DNA origami paper."""

import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

plt.rcParams['font.family'] = 'Arial'


def draw_rounded_box(ax, xy, width, height, text, facecolor, edgecolor='#333333',
                     fontsize=7, fontweight='normal', textcolor='black',
                     linewidth=0.8, alpha=1.0, zorder=2, fontstyle='normal',
                     text_offset_y=0):
    """Draw a rounded rectangle with centered text."""
    x, y = xy
    box = FancyBboxPatch(
        (x, y), width, height,
        boxstyle="round,pad=0.02",
        facecolor=facecolor, edgecolor=edgecolor,
        linewidth=linewidth, alpha=alpha, zorder=zorder
    )
    ax.add_patch(box)
    ax.text(x + width / 2, y + height / 2 + text_offset_y, text,
            ha='center', va='center', fontsize=fontsize,
            fontweight=fontweight, color=textcolor, fontstyle=fontstyle,
            zorder=zorder + 1, wrap=True,
            linespacing=1.2)
    return box


def draw_arrow(ax, start, end, color='#555555', linewidth=1.0,
               arrowstyle='->', mutation_scale=10, zorder=1):
    """Draw an arrow between two points."""
    arrow = FancyArrowPatch(
        start, end,
        arrowstyle=arrowstyle,
        mutation_scale=mutation_scale,
        color=color,
        linewidth=linewidth,
        zorder=zorder,
        connectionstyle="arc3,rad=0"
    )
    ax.add_patch(arrow)
    return arrow


def fig1():
    """Figure 1: Architecture comparison — embedded agent vs coding agent."""

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(7.0, 4.2))

    for ax in (ax_a, ax_b):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_aspect('equal')
        ax.axis('off')

    # =========================================================================
    # Color palettes
    # =========================================================================
    # Left (red/pink tones — what didn't work)
    red_light = '#FDECEC'
    red_mid = '#F8C4C4'
    red_dark = '#E57373'
    red_border = '#C62828'
    red_arrow = '#B71C1C'
    red_annot = '#B71C1C'

    # Right (green/blue tones — what works)
    green_light = '#E8F5E9'
    green_mid = '#A5D6A7'
    blue_light = '#E3F2FD'
    blue_mid = '#90CAF9'
    teal_light = '#E0F2F1'
    teal_mid = '#80CBC4'
    good_border = '#1B5E20'
    good_arrow = '#2E7D32'
    good_annot = '#1B5E20'

    # =========================================================================
    # (a) Embedded Agent Approach — LEFT
    # =========================================================================
    ax = ax_a

    # Title
    ax.text(0.50, 0.97, 'Embedded Agent Approach',
            ha='center', va='top', fontsize=8.5, fontweight='bold',
            color=red_border)

    # Boxes — top to bottom flow
    bw = 0.60  # box width
    bh = 0.065  # box height
    bx = 0.20  # left edge x

    # User
    y_user = 0.85
    draw_rounded_box(ax, (bx, y_user), bw, bh, 'User',
                     facecolor='#F5F5F5', edgecolor='#666666',
                     fontsize=7, fontweight='bold')

    # Agent Dialog
    y_dialog = 0.74
    draw_rounded_box(ax, (bx, y_dialog), bw, bh,
                     'Agent Dialog (Ctrl+I)',
                     facecolor=red_light, edgecolor=red_border, fontsize=6.5)

    # LLM
    y_llm = 0.63
    draw_rounded_box(ax, (bx, y_llm), bw, bh,
                     'LLM  (Ollama / OpenAI)',
                     facecolor=red_mid, edgecolor=red_border,
                     fontsize=6.5, fontweight='bold')

    # Parse intent
    y_parse = 0.52
    draw_rounded_box(ax, (bx, y_parse), bw, bh,
                     'Parse intent + parameters',
                     facecolor=red_light, edgecolor=red_border, fontsize=6.5)

    # Call methods
    y_methods = 0.41
    draw_rounded_box(ax, (bx, y_methods), bw, bh,
                     'Call agentmethods.py',
                     facecolor=red_light, edgecolor=red_border, fontsize=6.5)

    # cadnano modifications
    y_mod = 0.30
    draw_rounded_box(ax, (bx, y_mod), bw, bh,
                     'cadnano JSON modifications',
                     facecolor=red_mid, edgecolor=red_border, fontsize=6.5)

    # Arrows
    cx = bx + bw / 2
    gap = 0.012
    for y_top, y_bot in [(y_user, y_dialog), (y_dialog, y_llm),
                          (y_llm, y_parse), (y_parse, y_methods),
                          (y_methods, y_mod)]:
        draw_arrow(ax, (cx, y_top - gap), (cx, y_bot + bh + gap),
                   color=red_arrow, linewidth=1.0)

    # Side annotation box: what the LLM must reason about
    sb_x, sb_y, sb_w, sb_h = 0.02, 0.42, 0.17, 0.28
    draw_rounded_box(ax, (sb_x, sb_y), sb_w, sb_h,
                     '',
                     facecolor='#FFF3E0', edgecolor='#E65100',
                     fontsize=5.5, linewidth=0.6)
    ax.text(sb_x + sb_w / 2, sb_y + sb_h - 0.015,
            'LLM must\nreason about:',
            ha='center', va='top', fontsize=5, fontweight='bold',
            color='#BF360C')
    items = ['Helix parity', 'Crossover tables', 'Scaffold routing',
             'Mod-21 rules', 'Half vs double']
    for i, item in enumerate(items):
        ax.text(sb_x + 0.015, sb_y + sb_h - 0.075 - i * 0.038,
                f'- {item}', ha='left', va='center', fontsize=4.5,
                color='#4E342E')

    # Arrow from side box to LLM
    draw_arrow(ax, (sb_x + sb_w, sb_y + sb_h / 2 + 0.06),
               (bx - 0.01, y_llm + bh / 2),
               color='#E65100', linewidth=0.7,
               arrowstyle='->', mutation_scale=8)

    # Failure annotation
    ax.text(0.50, 0.19, '~0% success on complex tasks',
            ha='center', va='center', fontsize=7.5, fontweight='bold',
            color='white',
            bbox=dict(boxstyle='round,pad=0.35', facecolor=red_dark,
                      edgecolor=red_border, linewidth=1.0))

    ax.text(0.50, 0.10,
            'Model cannot reliably compose\n'
            'multi-step DNA origami operations',
            ha='center', va='center', fontsize=5.5, color='#666666',
            fontstyle='italic', linespacing=1.3)

    # Big X
    ax.text(0.50, 0.04, '\u2717', ha='center', va='center',
            fontsize=20, color=red_dark, fontweight='bold',
            fontfamily='DejaVu Sans')

    # =========================================================================
    # (b) Coding Agent Approach — RIGHT
    # =========================================================================
    ax = ax_b

    # Title
    ax.text(0.50, 0.97, 'Coding Agent Approach',
            ha='center', va='top', fontsize=8.5, fontweight='bold',
            color=good_border)

    bw = 0.58
    bh = 0.065
    bx = 0.21

    # User
    y_user = 0.85
    draw_rounded_box(ax, (bx, y_user), bw, bh, 'User',
                     facecolor='#F5F5F5', edgecolor='#666666',
                     fontsize=7, fontweight='bold')

    # Coding Agent
    y_agent = 0.74
    draw_rounded_box(ax, (bx, y_agent), bw, bh,
                     'Coding Agent  (Claude Code)',
                     facecolor=blue_light, edgecolor='#1565C0',
                     fontsize=6.5, fontweight='bold')

    # Read source + Write scripts side by side
    half_w = bw * 0.47
    gap_h = bw * 0.06
    left_x = bx
    right_x = bx + half_w + gap_h

    y_rw = 0.63
    draw_rounded_box(ax, (left_x, y_rw), half_w, bh,
                     'Reads source code',
                     facecolor=green_light, edgecolor=good_border,
                     fontsize=5.8)
    draw_rounded_box(ax, (right_x, y_rw), half_w, bh,
                     'Writes Python scripts',
                     facecolor=green_light, edgecolor=good_border,
                     fontsize=5.8)

    # cadnano API
    y_api = 0.52
    draw_rounded_box(ax, (bx, y_api), bw, bh,
                     'cadnano Python API',
                     facecolor=green_mid, edgecolor=good_border,
                     fontsize=6.5, fontweight='bold')

    # tacoxDNA
    y_taco = 0.41
    draw_rounded_box(ax, (bx, y_taco), bw, bh,
                     'tacoxDNA  (format conversion)',
                     facecolor=teal_light, edgecolor='#00695C',
                     fontsize=6.5)

    # oxDNA
    y_ox = 0.30
    draw_rounded_box(ax, (bx, y_ox), bw, bh,
                     'oxDNA  (molecular simulation)',
                     facecolor=teal_mid, edgecolor='#00695C',
                     fontsize=6.5, fontweight='bold')

    # Arrows — main flow
    cx = bx + bw / 2
    ag = 0.012
    draw_arrow(ax, (cx, y_user - ag), (cx, y_agent + bh + ag),
               color=good_arrow, linewidth=1.0)

    # Agent to two boxes
    draw_arrow(ax, (cx - 0.06, y_agent - ag),
               (left_x + half_w / 2, y_rw + bh + ag),
               color=good_arrow, linewidth=0.8)
    draw_arrow(ax, (cx + 0.06, y_agent - ag),
               (right_x + half_w / 2, y_rw + bh + ag),
               color=good_arrow, linewidth=0.8)

    # Two boxes merge to cadnano API
    draw_arrow(ax, (left_x + half_w / 2, y_rw - ag),
               (cx - 0.06, y_api + bh + ag),
               color=good_arrow, linewidth=0.8)
    draw_arrow(ax, (right_x + half_w / 2, y_rw - ag),
               (cx + 0.06, y_api + bh + ag),
               color=good_arrow, linewidth=0.8)

    # Straight down
    for y_top, y_bot in [(y_api, y_taco), (y_taco, y_ox)]:
        draw_arrow(ax, (cx, y_top - ag), (cx, y_bot + bh + ag),
                   color=good_arrow, linewidth=1.0)

    # Side annotation: what the agent does
    sb_x, sb_y, sb_w, sb_h = 0.02, 0.42, 0.17, 0.28
    draw_rounded_box(ax, (sb_x, sb_y), sb_w, sb_h,
                     '',
                     facecolor='#E8EAF6', edgecolor='#283593',
                     fontsize=5.5, linewidth=0.6)
    ax.text(sb_x + sb_w / 2, sb_y + sb_h - 0.015,
            'Agent reads\n& understands:',
            ha='center', va='top', fontsize=5, fontweight='bold',
            color='#1A237E')
    items = ['cadnano internals', 'Part/Strand API', 'Crossover rules',
             'JSON schema', 'oxDNA formats']
    for i, item in enumerate(items):
        ax.text(sb_x + 0.015, sb_y + sb_h - 0.075 - i * 0.038,
                f'- {item}', ha='left', va='center', fontsize=4.5,
                color='#1A237E')

    draw_arrow(ax, (sb_x + sb_w, sb_y + sb_h / 2 + 0.06),
               (bx - 0.01, y_agent + bh / 2),
               color='#283593', linewidth=0.7,
               arrowstyle='->', mutation_scale=8)

    # Success annotation
    ax.text(0.50, 0.19, 'End-to-end verified designs',
            ha='center', va='center', fontsize=7.5, fontweight='bold',
            color='white',
            bbox=dict(boxstyle='round,pad=0.35', facecolor='#43A047',
                      edgecolor=good_border, linewidth=1.0))

    ax.text(0.50, 0.10,
            'Agent writes correct code by\n'
            'reading the actual implementation',
            ha='center', va='center', fontsize=5.5, color='#666666',
            fontstyle='italic', linespacing=1.3)

    # Checkmark
    ax.text(0.50, 0.04, '\u2713', ha='center', va='center',
            fontsize=20, color='#2E7D32', fontweight='bold',
            fontfamily='DejaVu Sans')

    # =========================================================================
    # Final layout
    # =========================================================================
    fig.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.02,
                        wspace=0.08)

    out_png = 'results/paper_figures/fig1_architecture.png'
    out_pdf = 'results/paper_figures/fig1_architecture.pdf'
    fig.savefig(out_png, dpi=300, bbox_inches='tight', facecolor='white')
    fig.savefig(out_pdf, bbox_inches='tight', facecolor='white')
    print(f"Saved: {out_png}")
    print(f"Saved: {out_pdf}")
    plt.close(fig)


# =========================================================================
# CLI entry point
# =========================================================================
FIGURES = {
    'fig1': fig1,
}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in FIGURES:
        print(f"Usage: python {sys.argv[0]} <{'|'.join(FIGURES.keys())}>")
        sys.exit(1)
    FIGURES[sys.argv[1]]()
