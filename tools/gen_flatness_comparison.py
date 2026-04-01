#!/usr/bin/env python
"""Generate accepted vs rejected helix placement figures for 1-4 layer designs.

Uses existing tacoxDNA .oxdna files — no cadnano processing needed.
"""
import os, sys, numpy as np

STRESS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'results', 'stress_test')
UNIT_NM = 0.8518


def parse_oxdna(path):
    """Parse oxDNA .oxdna file → Nx3 array in nm."""
    positions = []
    with open(path) as f:
        f.readline(); f.readline(); f.readline()
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 3:
                positions.append([float(parts[0]), float(parts[1]), float(parts[2])])
    return np.array(positions) * UNIT_NM


def pca_cross_section(coords):
    """PCA-align, return (pc2, pc3) cross-section coords and bbox dims."""
    centered = coords - coords.mean(axis=0)
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = eigvals.argsort()[::-1]
    eigvecs = eigvecs[:, order]
    proj = centered @ eigvecs
    dims = proj.max(axis=0) - proj.min(axis=0)
    return proj[:, 1], proj[:, 2], dims


def oxdna_path(name):
    p = os.path.join(STRESS, f'{name}_stapled.json.oxdna')
    if os.path.exists(p):
        return p
    p2 = os.path.join(STRESS, f'{name}_stapled_stapled.json.oxdna')
    return p2 if os.path.exists(p2) else None


# ── Design catalog ────────────────────────────────────────────────
PANELS = [
    # (n_layers, status, oxdna_name, label)
    (1, 'accepted', '6hb',              '1×6 Linear Chain\n6 helices, 1 row'),
    (1, 'rejected', 'l_shape_true_8h',  'L-Shape\n8 helices, 2+ rows'),

    (2, 'accepted', 'rect_2x8',         '2×8 Rectangle\n16 helices, 2 rows'),
    (2, 'rejected', 'hex_ring_8h',      'Hexagonal Ring\n8 helices, circular'),

    (3, 'accepted', 'rect_3x6',         '3×6 Rectangle\n18 helices, 3 rows'),
    (3, 'rejected', 'cross_20h',        'Cross Pattern\n20 helices, 4 rows'),

    (4, 'accepted', 'block_4x4',        '4×4 Block\n16 helices, 4 rows'),
    (4, 'rejected', 't_shape_20h',      'T-Shape\n20 helices, 4 rows'),
]


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    # ── Load all cross-sections ──────────────────────────────────
    loaded = {}
    for n_layers, status, name, label in PANELS:
        path = oxdna_path(name)
        if not path:
            print(f'  MISSING: {name}')
            continue
        coords = parse_oxdna(path)
        pc2, pc3, dims = pca_cross_section(coords)
        loaded[(n_layers, status)] = {
            'pc2': pc2, 'pc3': pc3, 'dims': dims, 'label': label,
            'width': pc2.max() - pc2.min(),
            'height': pc3.max() - pc3.min(),
        }
        print(f'{name}: {dims[0]:.1f}×{dims[1]:.1f}×{dims[2]:.1f} nm, '
              f'cross-section {pc2.max()-pc2.min():.1f}×{pc3.max()-pc3.min():.1f} nm')

    # ── Big comparison figure (4 rows × 2 cols) ─────────────────
    fig, axes = plt.subplots(4, 2, figsize=(12, 18))

    for row_idx, n_layers in enumerate([1, 2, 3, 4]):
        for col_idx, status in enumerate(['accepted', 'rejected']):
            ax = axes[row_idx, col_idx]
            key = (n_layers, status)

            if key not in loaded:
                ax.axis('off')
                continue

            d = loaded[key]
            is_ok = status == 'accepted'

            # Colors
            dot_c = '#1976D2' if is_ok else '#C62828'
            box_c = '#2E7D32' if is_ok else '#C62828'
            bg_tint = '#E8F5E9' if is_ok else '#FFEBEE'

            # Light background tint
            ax.set_facecolor(bg_tint)

            # Plot nucleotide positions
            ax.scatter(d['pc2'], d['pc3'], s=1.2, alpha=0.25, c=dot_c,
                       edgecolors='none', rasterized=True)

            # Bounding box
            x0, x1 = d['pc2'].min(), d['pc2'].max()
            y0, y1 = d['pc3'].min(), d['pc3'].max()
            w, h = x1 - x0, y1 - y0
            rect = plt.Rectangle((x0, y0), w, h, linewidth=2.5,
                                 edgecolor=box_c, facecolor='none',
                                 linestyle='--', zorder=5)
            ax.add_patch(rect)

            # Dimension labels
            ax.annotate(f'{w:.1f} nm', xy=(x0 + w / 2, y1),
                        xytext=(0, 10), textcoords='offset points',
                        ha='center', va='bottom', fontsize=10,
                        color=box_c, fontweight='bold')
            ax.annotate(f'{h:.1f} nm', xy=(x1, y0 + h / 2),
                        xytext=(10, 0), textcoords='offset points',
                        ha='left', va='center', fontsize=10,
                        color=box_c, fontweight='bold', rotation=90)

            # Aspect ratio for non-flat shapes
            aspect = h / w if w > 0 else 0
            if not is_ok:
                ax.text(0.98, 0.02,
                        f'Aspect: {aspect:.2f}\n(want ≈ 0)',
                        transform=ax.transAxes, ha='right', va='bottom',
                        fontsize=9, color=box_c, fontstyle='italic',
                        bbox=dict(facecolor='white', alpha=0.8,
                                  edgecolor='none', pad=2))

            # Status badge
            if is_ok:
                badge_text = '✓ FLAT'
                badge_color = '#2E7D32'
            else:
                badge_text = '✗ NOT FLAT'
                badge_color = '#C62828'

            ax.text(0.02, 0.98, badge_text, transform=ax.transAxes,
                    ha='left', va='top', fontsize=13, fontweight='bold',
                    color='white',
                    bbox=dict(boxstyle='round,pad=0.4', facecolor=badge_color,
                              alpha=0.95, edgecolor='none'))

            # Design label
            ax.set_title(d['label'], fontsize=11, fontweight='bold', pad=10)
            ax.set_xlabel('PC2 (nm)', fontsize=9)
            ax.set_ylabel('PC3 (nm)', fontsize=9)
            ax.set_aspect('equal')
            ax.tick_params(labelsize=8)

            # Pad axis limits
            pad = max(w, h) * 0.15
            ax.set_xlim(x0 - pad, x1 + pad)
            ax.set_ylim(y0 - pad, y1 + pad)

        # Row label on left margin
        axes[row_idx, 0].annotate(
            f'{n_layers}-Layer', xy=(-0.28, 0.5),
            xycoords='axes fraction', fontsize=16, fontweight='bold',
            ha='center', va='center', rotation=90,
            color='#333',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#E0E0E0',
                      edgecolor='#999', linewidth=1.5))

    # Column headers
    axes[0, 0].annotate('ACCEPTED', xy=(0.5, 1.25),
                         xycoords='axes fraction', fontsize=14,
                         fontweight='bold', ha='center', color='#2E7D32')
    axes[0, 1].annotate('REJECTED', xy=(0.5, 1.25),
                         xycoords='axes fraction', fontsize=14,
                         fontweight='bold', ha='center', color='#C62828')

    fig.suptitle('Helix Placement Verification: Cross-Section Bounding Box\n'
                 'tacoxDNA 3D coordinates — PCA-aligned cross-sections',
                 fontsize=16, fontweight='bold', y=0.995)

    plt.tight_layout(rect=[0.06, 0, 1, 0.96], h_pad=3.0, w_pad=2.0)
    out = os.path.join(STRESS, 'flatness_accepted_rejected.png')
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor='white',
                edgecolor='none')
    plt.close()
    print(f'\nSaved: {out}')

    # ── Per-layer individual figures ─────────────────────────────
    for n_layers in [1, 2, 3, 4]:
        keys = [(n_layers, 'accepted'), (n_layers, 'rejected')]
        keys = [k for k in keys if k in loaded]
        if not keys:
            continue

        fig, axes_row = plt.subplots(1, len(keys), figsize=(7 * len(keys), 6))
        if len(keys) == 1:
            axes_row = [axes_row]

        for idx, key in enumerate(keys):
            ax = axes_row[idx]
            d = loaded[key]
            n_l, status = key
            is_ok = status == 'accepted'

            dot_c = '#1976D2' if is_ok else '#C62828'
            box_c = '#2E7D32' if is_ok else '#C62828'
            bg = '#E8F5E9' if is_ok else '#FFEBEE'
            ax.set_facecolor(bg)

            ax.scatter(d['pc2'], d['pc3'], s=2.5, alpha=0.3, c=dot_c,
                       edgecolors='none', rasterized=True)

            x0, x1 = d['pc2'].min(), d['pc2'].max()
            y0, y1 = d['pc3'].min(), d['pc3'].max()
            w, h = x1 - x0, y1 - y0
            rect = plt.Rectangle((x0, y0), w, h, linewidth=3,
                                 edgecolor=box_c, facecolor='none',
                                 linestyle='--', zorder=5)
            ax.add_patch(rect)

            badge = '✓ FLAT' if is_ok else '✗ NOT FLAT'
            ax.text(0.03, 0.97, badge, transform=ax.transAxes,
                    ha='left', va='top', fontsize=15, fontweight='bold',
                    color='white',
                    bbox=dict(boxstyle='round,pad=0.4',
                              facecolor=box_c, alpha=0.95, edgecolor='none'))

            ax.annotate(f'{w:.1f} nm', xy=(x0 + w/2, y1),
                        xytext=(0, 12), textcoords='offset points',
                        ha='center', fontsize=12, color=box_c,
                        fontweight='bold')
            ax.annotate(f'{h:.1f} nm', xy=(x1, y0 + h/2),
                        xytext=(12, 0), textcoords='offset points',
                        ha='left', va='center', fontsize=12,
                        color=box_c, fontweight='bold', rotation=90)

            ax.set_title(d['label'], fontsize=13, fontweight='bold', pad=12)
            ax.set_xlabel('PC2 (nm)', fontsize=11)
            ax.set_ylabel('PC3 (nm)', fontsize=11)
            ax.set_aspect('equal')
            pad = max(w, h) * 0.18
            ax.set_xlim(x0 - pad, x1 + pad)
            ax.set_ylim(y0 - pad, y1 + pad)

        fig.suptitle(f'{n_layers}-Layer Helix Placement: Cross-Section Verification',
                     fontsize=15, fontweight='bold')
        plt.tight_layout(rect=[0, 0, 1, 0.93], w_pad=3.0)
        per = os.path.join(STRESS, f'flatness_{n_layers}layer.png')
        plt.savefig(per, dpi=150, bbox_inches='tight', facecolor='white',
                    edgecolor='none')
        plt.close()
        print(f'Saved: {per}')


if __name__ == '__main__':
    main()
