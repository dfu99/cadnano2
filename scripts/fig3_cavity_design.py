#!/usr/bin/env python3
"""Generate Figure 3: Cavity design capability for AI-assisted parametric DNA origami paper."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.image as mpimg
from matplotlib.gridspec import GridSpec
import numpy as np
from PIL import Image

# ── Style ──
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'font.size': 9,
    'axes.labelsize': 10,
    'axes.titlesize': 11,
    'figure.dpi': 300,
})

# ── Load and crop panel (a) ──
img_a = Image.open('/home/dan/Documents/code/cadnano2/results/origami_cavity_126bp_8h/figures/cavity_schematic.png')
# Auto-crop whitespace
img_a_arr = np.array(img_a)
# Find non-white rows/cols (threshold at 250 to catch near-white)
if img_a_arr.ndim == 3:
    non_white = np.any(img_a_arr[:, :, :3] < 245, axis=2)
else:
    non_white = img_a_arr < 245
rows = np.where(non_white.any(axis=1))[0]
cols = np.where(non_white.any(axis=0))[0]
pad = 15
r0, r1 = max(0, rows[0] - pad), min(img_a_arr.shape[0], rows[-1] + pad)
c0, c1 = max(0, cols[0] - pad), min(img_a_arr.shape[1], cols[-1] + pad)
img_a_cropped = img_a_arr[r0:r1, c0:c1]


# ── Build figure ──
fig = plt.figure(figsize=(7.5, 10.5))  # full page width

# Layout: panel a on top (wide), panel b middle, panel c bottom
gs = GridSpec(3, 1, figure=fig, height_ratios=[1.0, 1.0, 0.50],
              hspace=0.22, left=0.06, right=0.94, top=0.97, bottom=0.02)

# ── Panel (a): Cavity schematic ──
ax_a = fig.add_subplot(gs[0])
ax_a.imshow(img_a_cropped)
ax_a.axis('off')
ax_a.text(-0.02, 1.05, '(a)', transform=ax_a.transAxes, fontsize=13,
          fontweight='bold', va='top', ha='right')
ax_a.set_title('Scaffold routing with cavity region', fontsize=10, pad=4)

# ── Panel (b): Staple-removal schematic ──
ax_b = fig.add_subplot(gs[1])
ax_b.set_xlim(-10, 310)
ax_b.set_ylim(-27.5, 2)
ax_b.set_aspect('auto')

n_helices = 26
bp_length = 294
cav_h_start, cav_h_end = 9, 16  # inclusive
cav_bp_start, cav_bp_end = 84, 210

# Draw helices
for h in range(n_helices):
    y = -h
    in_cavity = cav_h_start <= h <= cav_h_end
    # Full helix line (scaffold present everywhere)
    ax_b.plot([0, bp_length], [y, y], color='#2166ac', lw=2.5, solid_capstyle='round', zorder=2)

    if in_cavity:
        # Overlay cavity region in lighter color to show "no staples"
        ax_b.plot([cav_bp_start, cav_bp_end], [y, y], color='#92c5de', lw=2.5,
                  solid_capstyle='round', zorder=3, linestyle='-')

    # Helix label
    ax_b.text(-6, y, f'H{h}', fontsize=5.5, va='center', ha='right', color='#333333')

# Draw cavity boundary box
cav_rect = mpatches.FancyBboxPatch(
    (cav_bp_start - 2, -(cav_h_end) - 0.5),
    (cav_bp_end - cav_bp_start + 4),
    (cav_h_end - cav_h_start + 1),
    boxstyle="round,pad=1.5",
    linewidth=2.0, edgecolor='#d32f2f', facecolor='#ffebee',
    linestyle='--', alpha=0.7, zorder=1
)
ax_b.add_patch(cav_rect)

# Cavity label
cx = (cav_bp_start + cav_bp_end) / 2
cy = -(cav_h_start + cav_h_end) / 2
ax_b.text(cx, cy - 0.2, 'Cavity region\n(staples removed)', fontsize=9,
          ha='center', va='center', color='#d32f2f', fontweight='bold',
          bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='none', alpha=0.85))

# Dimension annotations
# Horizontal dimension line for cavity width
dim_y = -(cav_h_end) - 2.5
ax_b.annotate('', xy=(cav_bp_end, dim_y), xytext=(cav_bp_start, dim_y),
              arrowprops=dict(arrowstyle='<->', color='#666', lw=1.2))
ax_b.text(cx, dim_y - 0.6, '126 bp (~43 nm)', fontsize=7, ha='center', va='top', color='#444')

# Vertical dimension line for cavity height
dim_x = cav_bp_end + 15
ax_b.annotate('', xy=(dim_x, -cav_h_start), xytext=(dim_x, -cav_h_end),
              arrowprops=dict(arrowstyle='<->', color='#666', lw=1.2))
ax_b.text(dim_x + 5, cy, '8 helices\n(~21 nm)', fontsize=7, ha='left', va='center', color='#444')

# Full rectangle dimension
dim_y2 = 1.5
ax_b.annotate('', xy=(bp_length, dim_y2), xytext=(0, dim_y2),
              arrowprops=dict(arrowstyle='<->', color='#999', lw=1.0))
ax_b.text(bp_length / 2, dim_y2 + 0.4, '294 bp (~100 nm)', fontsize=7, ha='center', va='bottom', color='#666')

# Legend
from matplotlib.lines import Line2D
legend_elements = [
    Line2D([0], [0], color='#2166ac', lw=2.5, label='Scaffold + staples'),
    Line2D([0], [0], color='#92c5de', lw=2.5, label='Scaffold only (no staples)'),
    mpatches.Patch(facecolor='#ffebee', edgecolor='#d32f2f', linestyle='--', lw=1.5, label='Cavity boundary'),
]
ax_b.legend(handles=legend_elements, loc='lower right', fontsize=7, framealpha=0.9,
            edgecolor='#ccc', borderpad=0.6)

ax_b.set_xlabel('Base pair position', fontsize=9)
ax_b.set_ylabel('Helix', fontsize=9)
ax_b.spines['top'].set_visible(False)
ax_b.spines['right'].set_visible(False)
ax_b.spines['left'].set_visible(False)
ax_b.tick_params(left=False, labelleft=False)
ax_b.tick_params(axis='x', labelsize=7)
ax_b.text(-0.02, 1.05, '(b)', transform=ax_b.transAxes, fontsize=13,
          fontweight='bold', va='top', ha='right')
ax_b.set_title('Staple-removal approach for cavity formation', fontsize=10, pad=4)

# ── Panel (c): Comparison table ──
ax_c = fig.add_subplot(gs[2])
ax_c.axis('off')

col_labels = ['', 'Solid Rectangle', 'With Cavity']
row_labels = ['Scaffold', 'Helices', 'Cavity', 'Staples', 'PolyT extensions']
table_data = [
    ['Scaffold',       'p8064 (8064 nt)',      'p8064 (8064 nt)'],
    ['Helices',        '26 \u00d7 294 bp',             '26 \u00d7 294 bp'],
    ['Cavity',         'None',                 '126 bp \u00d7 8 helices\n(~43 \u00d7 21 nm)'],
    ['Staples',        '113',                  '107 (6 removed)'],
    ['PolyT ext.',     '224',                  '212'],
]

table = ax_c.table(
    cellText=table_data,
    colLabels=col_labels,
    cellLoc='center',
    loc='center',
    colWidths=[0.22, 0.32, 0.36],
)

# Style the table
table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1.0, 1.6)

# Header row
for j in range(3):
    cell = table[0, j]
    cell.set_facecolor('#37474f')
    cell.set_text_props(color='white', fontweight='bold', fontsize=9)
    cell.set_edgecolor('#263238')

# Row label column
for i in range(1, len(table_data) + 1):
    cell = table[i, 0]
    cell.set_facecolor('#eceff1')
    cell.set_text_props(fontweight='bold', fontsize=8.5)
    cell.set_edgecolor('#b0bec5')

# Data cells
for i in range(1, len(table_data) + 1):
    for j in range(1, 3):
        cell = table[i, j]
        cell.set_facecolor('white')
        cell.set_edgecolor('#b0bec5')
        cell.set_text_props(fontsize=8.5)

# Highlight differences in cavity column
for i in [3, 4, 5]:  # Cavity, Staples, PolyT rows
    cell = table[i, 2]
    cell.set_facecolor('#fff3e0')

ax_c.text(-0.02, 1.0, '(c)', transform=ax_c.transAxes, fontsize=13,
          fontweight='bold', va='top', ha='right')
ax_c.set_title('Design parameter comparison', fontsize=10, pad=8)

# ── Save ──
out_base = '/home/dan/Documents/code/cadnano2/results/paper_figures/fig3_cavity_design'
fig.savefig(out_base + '.png', dpi=300, bbox_inches='tight', facecolor='white')
fig.savefig(out_base + '.pdf', bbox_inches='tight', facecolor='white')
print(f"Saved: {out_base}.png and .pdf")
plt.close()
