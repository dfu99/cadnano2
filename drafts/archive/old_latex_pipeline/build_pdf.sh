#!/usr/bin/env bash
set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MD_FILE="$SCRIPT_DIR/paper_draft_dna32.md"
FIG_DIR="$SCRIPT_DIR/figures"
OUT_DIR="$SCRIPT_DIR/output"
TEX_FILE="$OUT_DIR/paper_draft_dna32.tex"
PDF_FILE="$OUT_DIR/paper_draft_dna32.pdf"

# ── Dependency check / install ─────────────────────────────────────
check_or_install() {
    local cmd="$1" pkg="$2"
    if ! command -v "$cmd" &>/dev/null; then
        echo "Installing $pkg via Homebrew..."
        brew install "$pkg"
    fi
}

if ! command -v brew &>/dev/null; then
    echo "Error: Homebrew is required. Install from https://brew.sh" >&2
    exit 1
fi

check_or_install pandoc pandoc

# TeX: check for pdflatex in common locations or install basictex
if ! command -v pdflatex &>/dev/null && ! /Library/TeX/texbin/pdflatex --version &>/dev/null 2>&1; then
    echo "Installing basictex via Homebrew (may require sudo for the installer)..."
    brew install --cask basictex
    eval "$(/usr/libexec/path_helper -s)"
fi

# Prefer /Library/TeX/texbin if it exists
if [ -d /Library/TeX/texbin ]; then
    export PATH="/Library/TeX/texbin:$PATH"
fi

# Install any missing TeX packages (one-time setup, requires sudo once)
STAMP_FILE="$SCRIPT_DIR/.tex_packages_installed"
if [ ! -f "$STAMP_FILE" ]; then
    echo "Installing required TeX packages (one-time setup)..."
    echo "This requires sudo once. Future runs will skip this step."
    sudo tlmgr update --self 2>/dev/null || true
    sudo tlmgr install booktabs caption float enumitem \
        titlesec collection-fontsrecommended 2>/dev/null || true
    touch "$STAMP_FILE"
    echo "Done. TeX packages installed."
fi

# ── Prepare output directory ───────────────────────────────────────
mkdir -p "$OUT_DIR"

# ── Build LaTeX from Markdown ──────────────────────────────────────
echo "Generating LaTeX..."

# We'll use pandoc for the core conversion, then post-process to insert figures
pandoc "$MD_FILE" \
    -f markdown \
    -t latex \
    --standalone \
    -V geometry:"margin=1in" \
    -V fontsize:11pt \
    -V documentclass:article \
    --pdf-engine=pdflatex \
    -o "$TEX_FILE"

# ── Post-process: insert figures, fix formatting ───────────────────

# Create a temp file for sed work
TMPF="$(mktemp)"

python3 - "$TEX_FILE" "$TMPF" << 'PYEOF'
import sys, re, os, shutil

tex_file = sys.argv[1]
tmp_file = sys.argv[2]
# Use relative path from output/ dir — avoids underscore issues in absolute paths
fig_dir  = "../figures"

with open(tex_file, 'r') as f:
    tex = f.read()

# --- Fix Unicode characters that pdflatex can't handle ---
unicode_map = {
    '\u2264': r'$\leq$',
    '\u2265': r'$\geq$',
    '\u2192': r'$\to$',
    '\u2013': '--',
    '\u2014': '---',
    '\u2018': '`',
    '\u2019': "'",
    '\u201c': '``',
    '\u201d': "''",
    '\u00d7': r'$\times$',
}
for char, replacement in unicode_map.items():
    tex = tex.replace(char, replacement)

# --- Preamble additions ---
preamble_extra = r"""
\usepackage{graphicx}
\usepackage{float}
"""
tex = tex.replace(r'\begin{document}',
                  preamble_extra + r'\begin{document}')

# --- Figure map ---
figures = {
    "Figure 1": ("fig1_architecture.png",
        "Architecture comparison: embedded tool-using LLM (failed) vs.\\ coding agent with source code access (succeeded)."),
    "Figure 2": ("fig2_pi_template.png",
        "The PI's template (\\texttt{2x12\\_rectangle\\_cavity.json}) showing correct scaffold routing with dense crossovers and cavity gap."),
    "Figure 3": ("fig3_cavity_design.png",
        "The 4-step scaling process: (a) scaffold only, (b) extended right side, (c) midseam moved, (d) cavity expanded and aligned between layers."),
    "Figure 4": ("fig4_parametric_sweep.png",
        "Scaffold routing visualization of the final scaled design (420 bp, 7,688 bp scaffold, 1 oligo)."),
    "Figure 5": (["fig5a_targeted_before.png", "fig5b_targeted_after.png"],
        "Targeted crossover edit. Left: before (scaffold-only). Right: after. H5--H6 moved from [64,65] to [43,44]; H33--H34 moved from [183,184] to [204,205]."),
    "Figure 6": ("fig6_oligo_journey.png",
        r"Scaffold oligo count journey: 65 $\to$ 54 $\to$ 10 $\to$ 8 $\to$ 4 $\to$ 1."),
    "Figure 7": ("fig7_verifier_comparison.png",
        "\\texttt{cadnano\\_verifier.py} output: before (3 failures, 8 oligos) vs.\\ after (all pass, 1 oligo)."),
    "Figure 8": ("fig8_cavities_oxdna.png",
        "All three parametric cavity variants (20/30/40 nm gap) after oxDNA production relaxation (20M MD steps)."),
    "Figure 9": ("fig9_targeted_edits.png",
        "One-shot targeted edits from natural language prompts on the 2$\\times$22 integrin cavity design."),
}

# Build figure LaTeX blocks
def make_figure(label, img, caption):
    tag = label.lower().replace(" ", "")
    if isinstance(img, list):
        # Side-by-side subfigures
        imgs = "\n".join([
            r"  \begin{minipage}{0.48\textwidth}\centering"
            + "\n"
            + r"    \includegraphics[width=\linewidth]{" + os.path.join(fig_dir, i) + "}"
            + "\n"
            + r"  \end{minipage}\hfill"
            for i in img
        ])
        return (
            r"\begin{figure}[H]" + "\n"
            + r"\centering" + "\n"
            + imgs + "\n"
            + r"\caption{" + caption + "}" + "\n"
            + r"\label{fig:" + tag + "}" + "\n"
            + r"\end{figure}"
        )
    else:
        return (
            r"\begin{figure}[H]" + "\n"
            + r"\centering" + "\n"
            + r"\includegraphics[width=0.9\textwidth]{" + os.path.join(fig_dir, img) + "}" + "\n"
            + r"\caption{" + caption + "}" + "\n"
            + r"\label{fig:" + tag + "}" + "\n"
            + r"\end{figure}"
        )

# Replace the Figures bullet list at the end with actual figures
# Find the figures section
figures_section = re.search(
    r'(\\(sub)?section\{Figures\}.*?)(?=\\(sub)?section|\\end\{document\})',
    tex, re.DOTALL)

if figures_section:
    fig_latex = "\n\\section{Figures}\n\n"
    for label, (img, cap) in figures.items():
        fig_latex += make_figure(label, img, cap) + "\n\n"
    tex = tex[:figures_section.start()] + fig_latex + tex[figures_section.end():]

# Also add the failure table figure if it exists
failure_table_path = os.path.join(fig_dir, "fig_failure_table.png")
# Check existence relative to the tex file's directory
tex_dir = os.path.dirname(os.path.abspath(tex_file))
if os.path.exists(os.path.join(tex_dir, failure_table_path)):
    ft_block = (
        r"\begin{figure}[H]" + "\n"
        + r"\centering" + "\n"
        + r"\includegraphics[width=0.9\textwidth]{" + failure_table_path + "}" + "\n"
        + r"\caption{Summary of failure modes, domain knowledge required, and resolution.}" + "\n"
        + r"\label{fig:failuretable}" + "\n"
        + r"\end{figure}" + "\n\n"
    )
    # Insert before \end{document}
    tex = tex.replace(r'\end{document}', ft_block + r'\end{document}')

with open(tex_file, 'w') as f:
    f.write(tex)

print("LaTeX post-processing complete.")
PYEOF

# ── Compile PDF ────────────────────────────────────────────────────
echo "Compiling PDF (pass 1/2)..."
(cd "$OUT_DIR" && pdflatex -interaction=nonstopmode \
    "$(basename "$TEX_FILE")" > /dev/null 2>&1) || true

echo "Compiling PDF (pass 2/2)..."
(cd "$OUT_DIR" && pdflatex -interaction=nonstopmode \
    "$(basename "$TEX_FILE")" > /dev/null 2>&1) || true

# ── Cleanup aux files ─────────────────────────────────────────────
rm -f "$OUT_DIR"/*.{aux,log,out,toc,fls,fdb_latexmk} 2>/dev/null || true

if [ -f "$PDF_FILE" ]; then
    echo ""
    echo "✓ PDF generated: $PDF_FILE"
    echo "  LaTeX source:  $TEX_FILE"
    open "$PDF_FILE" 2>/dev/null || true
else
    echo "Error: PDF compilation failed. Check $OUT_DIR for logs." >&2
    exit 1
fi
