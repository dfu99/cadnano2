#!/usr/bin/env python
"""Pipeline: load JSON → autoStaple → autoBreak → tacoxDNA → 3D plot."""
import os, sys, subprocess
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

def main():
    import io, importlib, importlib.util, numpy as np

    json_in = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(json_in)
    base = os.path.splitext(os.path.basename(json_in))[0]

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()

    # Load autobreak
    ab_pkg = os.path.join(project_root, 'cadnano2', 'plugins', 'autobreak')
    sg_spec = importlib.util.spec_from_file_location(
        'cadnano2.plugins.autobreak.staplegraph',
        os.path.join(ab_pkg, 'staplegraph.py'), submodule_search_locations=[])
    sg = importlib.util.module_from_spec(sg_spec)
    sys.modules['cadnano2.plugins.autobreak.staplegraph'] = sg
    sys.modules['staplegraph'] = sg
    sg_spec.loader.exec_module(sg)
    ab_spec = importlib.util.spec_from_file_location(
        'cadnano2.plugins.autobreak.autobreak',
        os.path.join(ab_pkg, 'autobreak.py'), submodule_search_locations=[])
    ab_mod = importlib.util.module_from_spec(ab_spec)
    sys.modules['cadnano2.plugins.autobreak.autobreak'] = ab_mod
    ab_spec.loader.exec_module(ab_mod)

    from cadnano2.model.io.decoder import decode
    from cadnano2.model.io.encoder import encode
    from cadnano2.model.parts.part import Part

    dc = list(app.documentControllers)[0]
    doc = dc.document()
    with io.open(json_in, 'r', encoding='utf-8') as fd:
        decode(doc, fd.read())

    part = doc.selectedPart()
    scaf = [o for o in part.oligos() if not o.isStaple()]
    print(f'{base}: {sum(o.length() for o in scaf)}bp, {len(scaf)} scaf oligo(s)')

    # AutoStaple + AutoBreak
    Part.autoStaple(part)
    settings = {'minStapleLen': 18, 'maxStapleLen': 50, 'tgtStapleLen': 32, 'minStapleLegLen': 3}
    for oligo in list(part.oligos()):
        if oligo.isStaple() and oligo.length() >= 18:
            try:
                ab_mod.nxBreakStaple(oligo, settings)
            except:
                pass
    stap_count = sum(1 for o in part.oligos() if o.isStaple())
    print(f'  Stapled: {stap_count} staples')

    # Save stapled
    json_stapled = os.path.join(out_dir, f'{base}_stapled.json')
    helixOrderList = dc.win.pathroot.getSelectedPartOrderedVHList()
    if helixOrderList:
        with open(json_stapled, 'w') as f:
            encode(doc, helixOrderList, f)

    # tacoxDNA
    tacox = os.path.join(project_root, '..', 'tacoxDNA', 'src', 'cadnano_oxDNA.py')
    old_cwd = os.getcwd()
    os.chdir(out_dir)
    result = subprocess.run(
        [sys.executable, os.path.join(old_cwd, tacox),
         os.path.basename(json_stapled), 'he'],
        capture_output=True, text=True, timeout=60)
    os.chdir(old_cwd)

    oxdna_file = json_stapled + '.oxdna'
    top_file = json_stapled + '.top'

    if not os.path.exists(top_file):
        # Check if files are in out_dir with just the basename
        alt_oxdna = os.path.join(out_dir, os.path.basename(json_stapled) + '.oxdna')
        alt_top = os.path.join(out_dir, os.path.basename(json_stapled) + '.top')
        if os.path.exists(alt_top):
            oxdna_file = alt_oxdna
            top_file = alt_top

    if not os.path.exists(top_file):
        print(f'  tacoxDNA failed: {result.stderr[-200:]}')
        return

    with open(top_file) as f:
        header = f.readline().strip().split()
        n_nuc, n_strands = int(header[0]), int(header[1])
    print(f'  tacoxDNA: {n_nuc} nt, {n_strands} strands')

    # 3D visualization
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    positions = []
    with open(oxdna_file) as f:
        f.readline(); f.readline(); f.readline()
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 3:
                positions.append([float(parts[0]), float(parts[1]), float(parts[2])])
    positions = np.array(positions)
    UNIT_NM = 0.8518

    centered = positions - positions.mean(axis=0)
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    order = eigvals.argsort()[::-1]
    eigvecs = eigvecs[:, order]
    proj = (centered @ eigvecs) * UNIT_NM

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    for ax, (i, j, title) in zip(axes, [(0, 1, 'Side'), (0, 2, 'Top'), (1, 2, 'Cross-Section')]):
        color = 'darkorange' if title == 'Cross-Section' else 'steelblue'
        ax.scatter(proj[:, i], proj[:, j], s=0.5, alpha=0.3, c=color)
        ax.set_xlabel(f'PC{i+1} (nm)')
        ax.set_ylabel(f'PC{j+1} (nm)')
        ax.set_title(title)
        ax.set_aspect('equal')

    dims = proj.max(axis=0) - proj.min(axis=0)
    fig.suptitle(f'{base} — tacoxDNA 3D\n{n_nuc} nt, {n_strands} strands, '
                 f'{dims[0]:.1f} x {dims[1]:.1f} x {dims[2]:.1f} nm',
                 fontsize=12, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 1, 0.9])
    out_png = os.path.join(out_dir, f'{base}_3d.png')
    plt.savefig(out_png, dpi=150, bbox_inches='tight')
    plt.close()
    print(f'  3D plot: {out_png}')

if __name__ == '__main__':
    main()
