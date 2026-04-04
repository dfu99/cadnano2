#!/usr/bin/env python3
"""
Figure 4: Parametric DNA Origami Redesign — Cavity Width Sweep

Demonstrates that changing a single parameter (cavity width) automatically
recomputes the entire design (staples, polyT extensions, insertions, verification).
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# ---------- Style ----------
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 9,
    'axes.labelsize': 10,
    'axes.titlesize': 10,
    'xtick.labelsize': 8.5,
    'ytick.labelsize': 8.5,
    'legend.fontsize': 8.5,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'axes.linewidth': 0.8,
    'xtick.major.width': 0.6,
    'ytick.major.width': 0.6,
})

# Colors
C_DESIGN1 = '#4878CF'   # steel blue
C_DESIGN2 = '#E8783A'   # burnt orange
C_HELIX = '#3B6BA5'     # helix lines
C_CAVITY_BORDER = '#C0392B'  # red dashed cavity box
C_TRIGGER = '#C0392B'   # red trigger box
C_CASCADE = '#2471A3'   # blue cascade boxes
C_BG_LIGHT = '#F7F9FC'

fig = plt.figure(figsize=(7.5, 8.0))

# Layout: (a) top half, (b) bottom-left, (c) bottom-right
gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.1],
                      hspace=0.32, wspace=0.30,
                      left=0.06, right=0.97, top=0.96, bottom=0.04)

# ================================================================
# Panel (a): Side-by-side schematics
# ================================================================
ax_a = fig.add_subplot(gs[0, :])
ax_a.set_xlim(0, 10)
ax_a.set_ylim(0, 5.0)
ax_a.set_aspect('equal')
ax_a.axis('off')
ax_a.text(-0.02, 1.02, '(a)', transform=ax_a.transAxes,
          fontsize=12, fontweight='bold', va='top')

def draw_cavity_schematic(ax, cx, cy, n_helices, cavity_w_display,
                          total_w_display, label, sublabel, color_border):
    """Draw a simplified helix layout with a cavity cutout."""
    helix_spacing = 0.30
    total_h = (n_helices - 1) * helix_spacing
    y_top = cy + total_h / 2

    # Draw helices (blue horizontal lines)
    for i in range(n_helices):
        y = y_top - i * helix_spacing
        # Left segment
        left_end = cx - total_w_display / 2
        cavity_left = cx - cavity_w_display / 2
        cavity_right = cx + cavity_w_display / 2
        right_end = cx + total_w_display / 2

        # Top and bottom helices span full width (outside cavity region)
        if i < 2 or i >= n_helices - 2:
            ax.plot([left_end, right_end], [y, y],
                    color=C_HELIX, lw=1.8, solid_capstyle='round')
        else:
            # Middle helices: break for cavity
            ax.plot([left_end, cavity_left - 0.05], [y, y],
                    color=C_HELIX, lw=1.8, solid_capstyle='round')
            ax.plot([cavity_right + 0.05, right_end], [y, y],
                    color=C_HELIX, lw=1.8, solid_capstyle='round')

    # Cavity rectangle (red dashed)
    cav_y_top = y_top - 1.5 * helix_spacing
    cav_y_bot = y_top - (n_helices - 2.5) * helix_spacing
    cav_rect = mpatches.FancyBboxPatch(
        (cx - cavity_w_display / 2, cav_y_bot),
        cavity_w_display, cav_y_top - cav_y_bot,
        boxstyle="round,pad=0.03",
        linewidth=1.4, edgecolor=color_border, facecolor='#FADBD8',
        linestyle='--', alpha=0.6)
    ax.add_patch(cav_rect)

    # Cavity label inside
    ax.text(cx, (cav_y_top + cav_y_bot) / 2, 'cavity',
            ha='center', va='center', fontsize=7, color='#922B21',
            fontstyle='italic')

    # Width dimension arrow below
    arrow_y = cy - total_h / 2 - 0.35
    ax.annotate('', xy=(cx + cavity_w_display / 2, arrow_y),
                xytext=(cx - cavity_w_display / 2, arrow_y),
                arrowprops=dict(arrowstyle='<->', color='#555555', lw=1.0))
    ax.text(cx, arrow_y - 0.16, label, ha='center', va='top',
            fontsize=8, fontweight='bold', color='#333333')

    # Title above
    ax.text(cx, cy + total_h / 2 + 0.35, sublabel, ha='center', va='bottom',
            fontsize=9.5, fontweight='bold', color='#222222')


# Design 1 (left)
draw_cavity_schematic(ax_a, cx=2.8, cy=2.5, n_helices=8,
                      cavity_w_display=1.6, total_w_display=3.2,
                      label='126 bp (~43 nm)', sublabel='Design 1: Original Cavity',
                      color_border=C_CAVITY_BORDER)

# Design 2 (right) — wider cavity, wider total
draw_cavity_schematic(ax_a, cx=7.2, cy=2.5, n_helices=8,
                      cavity_w_display=2.3, total_w_display=3.8,
                      label='147 bp (~50 nm)', sublabel='Design 2: Widened Cavity (+5 nm)',
                      color_border=C_DESIGN2)

# Arrow between designs
ax_a.annotate('', xy=(5.25, 2.5), xytext=(4.65, 2.5),
              arrowprops=dict(arrowstyle='->', color='#888888',
                              lw=1.8, connectionstyle='arc3,rad=0'))
ax_a.text(4.95, 2.72, '+5 nm', ha='center', va='bottom',
          fontsize=9, fontweight='bold', color=C_TRIGGER)

# ================================================================
# Panel (b): Grouped bar chart
# ================================================================
ax_b = fig.add_subplot(gs[1, 0])
ax_b.text(-0.10, 1.05, '(b)', transform=ax_b.transAxes,
          fontsize=12, fontweight='bold', va='top')

metrics = ['Staple\ncount', 'PolyT\nextensions', 'Cavity\nwidth (nm)']
vals_d1 = [107, 212, 43]
vals_d2 = [122, 242, 50]

x = np.arange(len(metrics))
width = 0.32

bars1 = ax_b.bar(x - width/2, vals_d1, width, color=C_DESIGN1,
                 edgecolor='white', linewidth=0.5, label='Design 1 (43 nm)', zorder=3)
bars2 = ax_b.bar(x + width/2, vals_d2, width, color=C_DESIGN2,
                 edgecolor='white', linewidth=0.5, label='Design 2 (50 nm)', zorder=3)

# Value labels on bars
for bar_group in [bars1, bars2]:
    for bar in bar_group:
        h = bar.get_height()
        ax_b.text(bar.get_x() + bar.get_width() / 2, h + 3,
                  f'{int(h)}', ha='center', va='bottom', fontsize=8, fontweight='bold')

ax_b.set_xticks(x)
ax_b.set_xticklabels(metrics)
ax_b.set_ylabel('Count / Value')
ax_b.set_ylim(0, 285)
ax_b.legend(frameon=True, fancybox=False, edgecolor='#CCCCCC', loc='upper left')
ax_b.spines['top'].set_visible(False)
ax_b.spines['right'].set_visible(False)
ax_b.yaxis.grid(True, alpha=0.3, lw=0.5)
ax_b.set_axisbelow(True)
ax_b.set_title('Design Metrics Comparison', fontsize=10, pad=8)

# Delta annotations — show percent change above Design 2 bars
deltas_pct = ['+14%', '+14%', '+16%']
for i, pct in enumerate(deltas_pct):
    mid_x = x[i] + width/2
    top_y = vals_d2[i]
    ax_b.text(mid_x, top_y + 16, pct, ha='center', va='bottom',
              fontsize=7.5, color=C_DESIGN2, fontweight='bold')

# ================================================================
# Panel (c): Cascade flow diagram
# ================================================================
ax_c = fig.add_subplot(gs[1, 1])
ax_c.set_xlim(0, 10)
ax_c.set_ylim(0, 10)
ax_c.axis('off')
ax_c.text(-0.04, 1.05, '(c)', transform=ax_c.transAxes,
          fontsize=12, fontweight='bold', va='top')

def draw_flow_box(ax, cx, cy, text, color, text_color='white',
                  width=3.8, height=0.9, fontsize=8):
    box = FancyBboxPatch(
        (cx - width/2, cy - height/2), width, height,
        boxstyle="round,pad=0.15",
        facecolor=color, edgecolor='#555555', linewidth=0.8,
        zorder=5)
    ax.add_patch(box)
    ax.text(cx, cy, text, ha='center', va='center',
            fontsize=fontsize, color=text_color, fontweight='bold',
            zorder=6, wrap=False)
    return cy

def draw_flow_arrow(ax, y_from, y_to, cx=5.0):
    ax.annotate('', xy=(cx, y_to + 0.45), xytext=(cx, y_from - 0.45),
                arrowprops=dict(arrowstyle='->', color='#666666',
                                lw=1.5, connectionstyle='arc3,rad=0'),
                zorder=4)

steps = [
    ("Change cavity_width\n126 \u2192 147 bp (+5 nm)", C_TRIGGER, 'white'),
    ("Staples recomputed\n107 \u2192 122 staples", C_CASCADE, 'white'),
    ("PolyT brushes re-applied\n212 \u2192 242 extensions", C_CASCADE, 'white'),
    ("Insertions recalculated\nacross all helices", C_CASCADE, 'white'),
    ("oxDNA verification\nrelaxation + analysis", '#27AE60', 'white'),
]

y_positions = [8.8, 7.2, 5.6, 4.0, 2.4]

for i, (text, color, tc) in enumerate(steps):
    draw_flow_box(ax_c, 5.0, y_positions[i], text, color, tc,
                  width=4.2, height=1.1, fontsize=8)
    if i > 0:
        draw_flow_arrow(ax_c, y_positions[i-1], y_positions[i])

# Small label at top
ax_c.text(5.0, 9.7, 'Cascade of Automatic Recomputation',
          ha='center', va='bottom', fontsize=9.5, fontweight='bold',
          color='#333333')

# "single parameter change" label with arrow pointing to trigger
ax_c.annotate('single parameter\nchange', xy=(2.8, 8.8),
              xytext=(0.5, 9.5),
              fontsize=7, ha='center', va='center', color=C_TRIGGER,
              fontstyle='italic',
              arrowprops=dict(arrowstyle='->', color=C_TRIGGER, lw=1.0))

# "automatic" brace-like label on cascade side
ax_c.annotate('fully\nautomatic', xy=(7.3, 5.6),
              xytext=(9.2, 5.6),
              fontsize=7.5, ha='center', va='center', color=C_CASCADE,
              fontweight='bold',
              arrowprops=dict(arrowstyle='->', color=C_CASCADE, lw=1.0))

# ---------- Save ----------
out_base = '/home/dan/Documents/code/cadnano2/results/paper_figures/fig4_parametric_sweep'
fig.savefig(out_base + '.png', dpi=300, bbox_inches='tight', facecolor='white')
fig.savefig(out_base + '.pdf', bbox_inches='tight', facecolor='white')
print(f"Saved: {out_base}.png")
print(f"Saved: {out_base}.pdf")
plt.close()
