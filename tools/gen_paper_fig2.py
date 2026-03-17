"""Generate Figure 2 for the paper: Proof of concept — rectangular DNA origami with m13mp18.

Panels:
  (a) Initial 3D structure face view (XZ) from oxDNA coordinates — shows rectangular shape
  (b) Energy convergence (minimization + MD relaxation)
  (c) Relaxation comparison: initial vs relaxed face view (XZ)

The rectangular origami is elongated in X (~44 nm) and Z (~96 nm), thin in Y (~2 nm).
XZ projection shows the rectangular face.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path

DATA_DIR = Path("results/rectangular_origami")
OUT_DIR = Path("results/paper_figures")

# Publication style
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans"],
    "font.size": 8,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "axes.linewidth": 0.8,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
})

NM_PER_SU = 0.8518  # oxDNA simulation units to nm


def load_conf(conf_path):
    """Load oxDNA configuration file, return positions in nm."""
    lines = conf_path.read_text().strip().split("\n")
    data_lines = lines[3:]
    positions = []
    for line in data_lines:
        vals = line.split()
        x, y, z = float(vals[0]), float(vals[1]), float(vals[2])
        positions.append((x, y, z))
    positions = np.array(positions) * NM_PER_SU
    return positions


def load_topology(top_path):
    """Load topology file, return strand IDs per nucleotide."""
    lines = top_path.read_text().strip().split("\n")
    strand_ids = []
    for line in lines[1:]:
        vals = line.split()
        strand_ids.append(int(vals[0]))
    return np.array(strand_ids)


def load_energy(dat_path):
    """Load energy .dat file. Columns: time, potential, kinetic, total."""
    return np.loadtxt(dat_path)


def plot_structure_xz(ax, positions, strand_ids, title=None, point_scale=1.0):
    """Plot face view (XZ) of the structure, colored by strand.

    X = horizontal (helix cross-section direction), Z = vertical (helix axis).
    """
    scaffold_mask = strand_ids == 1
    staple_mask = ~scaffold_mask

    # Staples with varied colors
    staple_strand_ids = strand_ids[staple_mask]
    unique_staples = np.unique(staple_strand_ids)
    cmap = plt.cm.tab20
    colors = {s: cmap((i % 20) / 20) for i, s in enumerate(unique_staples)}

    for s in unique_staples:
        mask = strand_ids == s
        ax.scatter(positions[mask, 2], positions[mask, 0],
                   s=0.15 * point_scale, alpha=0.4, c=[colors[s]],
                   linewidths=0, rasterized=True)

    # Scaffold on top
    ax.scatter(positions[scaffold_mask, 2], positions[scaffold_mask, 0],
               s=0.25 * point_scale, alpha=0.5, c="royalblue",
               linewidths=0, rasterized=True, label="Scaffold")

    ax.set_xlabel("Z (nm)")
    ax.set_ylabel("X (nm)")
    ax.set_aspect("equal")
    if title:
        ax.set_title(title, fontsize=8, fontweight="bold")
    ax.tick_params(direction="in")


def main():
    # Load data
    start_pos = load_conf(DATA_DIR / "start.conf")
    relaxed_pos = load_conf(DATA_DIR / "relaxed.conf")
    strand_ids = load_topology(DATA_DIR / "topology.top")
    energy_min = load_energy(DATA_DIR / "energy_min.dat")
    energy_relax = load_energy(DATA_DIR / "energy_relax.dat")

    # --- Create composite figure ---
    # Panel (a) spans full width top, (b) and (c) share bottom row
    fig = plt.figure(figsize=(7.0, 7.0))

    gs = gridspec.GridSpec(2, 2, figure=fig,
                           height_ratios=[0.55, 1.0],
                           width_ratios=[1.0, 1.0],
                           hspace=0.45, wspace=0.35)

    # --- Panel (a): Initial structure face view (XZ) ---
    ax_a = fig.add_subplot(gs[0, :])
    plot_structure_xz(ax_a, start_pos, strand_ids,
                      title="Initial structure (tacoxDNA)", point_scale=1.5)

    dx = start_pos[:, 0].max() - start_pos[:, 0].min()
    dy = start_pos[:, 1].max() - start_pos[:, 1].min()
    dz = start_pos[:, 2].max() - start_pos[:, 2].min()
    ax_a.annotate(f"{dx:.0f} x {dy:.0f} x {dz:.0f} nm\n"
                  f"24 helices, 14498 nt, 121 strands",
                  xy=(0.02, 0.95), xycoords="axes fraction",
                  fontsize=6, va="top",
                  bbox=dict(boxstyle="round,pad=0.3", fc="wheat", alpha=0.8))

    # --- Panel (b): Energy convergence ---
    ax_b = fig.add_subplot(gs[1, 0])

    t_min = energy_min[:, 0]
    e_min = energy_min[:, 1]
    ax_b.plot(t_min, e_min, color="steelblue", linewidth=0.8, label="Minimization")

    t_relax = energy_relax[:, 0]
    e_relax = energy_relax[:, 1]
    t_offset = t_min[-1] + (t_relax[1] - t_relax[0]) if len(t_relax) > 1 else t_min[-1]
    t_relax_shifted = t_relax + t_offset

    ax_b.plot(t_relax_shifted, e_relax, color="coral", linewidth=0.8, label="MD relaxation")
    ax_b.axvline(t_offset, color="gray", linewidth=0.5, linestyle="--", alpha=0.6)

    ax_b.set_xlabel("Simulation time (steps)")
    ax_b.set_ylabel("Potential energy (sim. units)")
    ax_b.legend(frameon=False, loc="upper right")
    ax_b.set_title("Energy convergence", fontsize=8, fontweight="bold")
    ax_b.tick_params(direction="in")

    ax_b.annotate(f"Final: {e_min[-1]:.2f}",
                  xy=(t_min[-1], e_min[-1]), xycoords="data",
                  xytext=(0.35, 0.55), textcoords="axes fraction",
                  fontsize=6, color="steelblue",
                  arrowprops=dict(arrowstyle="->", color="steelblue", lw=0.5))
    ax_b.annotate(f"Final: {e_relax[-1]:.2f}",
                  xy=(t_relax_shifted[-1], e_relax[-1]), xycoords="data",
                  xytext=(0.75, 0.35), textcoords="axes fraction",
                  fontsize=6, color="coral",
                  arrowprops=dict(arrowstyle="->", color="coral", lw=0.5))

    # --- Panel (c): Relaxation comparison (initial vs relaxed, XZ face view) ---
    ax_c = fig.add_subplot(gs[1, 1])

    # Initial in light gray
    ax_c.scatter(start_pos[:, 2], start_pos[:, 0],
                 s=0.15, alpha=0.25, c="silver", linewidths=0, rasterized=True,
                 label="Initial")

    # Relaxed colored
    scaffold_mask = strand_ids == 1
    staple_mask = ~scaffold_mask
    ax_c.scatter(relaxed_pos[staple_mask, 2], relaxed_pos[staple_mask, 0],
                 s=0.15, alpha=0.35, c="tomato", linewidths=0, rasterized=True,
                 label="Relaxed (staples)")
    ax_c.scatter(relaxed_pos[scaffold_mask, 2], relaxed_pos[scaffold_mask, 0],
                 s=0.25, alpha=0.45, c="royalblue", linewidths=0, rasterized=True,
                 label="Relaxed (scaffold)")

    dx_r = relaxed_pos[:, 0].max() - relaxed_pos[:, 0].min()
    dy_r = relaxed_pos[:, 1].max() - relaxed_pos[:, 1].min()
    dz_r = relaxed_pos[:, 2].max() - relaxed_pos[:, 2].min()
    ax_c.annotate(f"Relaxed: {dx_r:.0f} x {dy_r:.0f} x {dz_r:.0f} nm",
                  xy=(0.02, 0.95), xycoords="axes fraction",
                  fontsize=6, va="top",
                  bbox=dict(boxstyle="round,pad=0.2", fc="wheat", alpha=0.8))

    ax_c.set_xlabel("Z (nm)")
    ax_c.set_ylabel("X (nm)")
    ax_c.set_aspect("equal")
    ax_c.set_title("Relaxation comparison", fontsize=8, fontweight="bold")
    ax_c.legend(frameon=False, loc="lower right", fontsize=6, markerscale=8)
    ax_c.tick_params(direction="in")

    # --- Subfigure labels ---
    for label, ax in [("a", ax_a), ("b", ax_b), ("c", ax_c)]:
        ax.text(-0.06, 1.08, f"({label})", transform=ax.transAxes,
                fontsize=11, fontweight="bold", va="top", ha="left")

    # Save
    fig.savefig(OUT_DIR / "fig2_proof_of_concept.png", bbox_inches="tight", dpi=300)
    fig.savefig(OUT_DIR / "fig2_proof_of_concept.pdf", bbox_inches="tight")
    print(f"Saved to {OUT_DIR / 'fig2_proof_of_concept.png'}")
    print(f"Saved to {OUT_DIR / 'fig2_proof_of_concept.pdf'}")
    plt.close()


if __name__ == "__main__":
    main()
