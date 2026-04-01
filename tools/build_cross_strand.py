#!/usr/bin/env python
"""Build a cross/plus shape by trimming a flat 2×12 rectangle.

The cross is created by moving edge crossovers INWARD on both sides
of the outer helix pairs, keeping center pairs at full length.

Cross shape in path view:
  H0:     ====        (short — outer arm)
  H1:     ====
  ...
  H4: ============    (full — center bar)
  H5: ============
  ...
  H8:     ====        (short — outer arm)
  ...

Usage:
  python tools/build_cross_strand.py [arm_pairs] [arm_bp]

  arm_pairs: number of pairs per arm (default: 2, i.e., 4 helices per arm)
  arm_bp: length of short arm helices in bp (default: 90)
"""
import os, sys, io
os.environ['QT_QPA_PLATFORM'] = 'offscreen'


def main():
    arm_pairs = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    arm_bp = int(sys.argv[2]) if len(sys.argv) > 2 else 90

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)

    base_json = os.path.join(project_root, 'results', 'solid_rectangle',
                             '2x12_simple_routing.json')
    out_json = os.path.join(project_root, 'results', 'stress_test',
                            f'cross_strand_{arm_pairs}arm_{arm_bp}bp.json')
    out_png = os.path.join(project_root, 'results', 'stress_test',
                           f'cross_strand_{arm_pairs}arm_{arm_bp}bp_both.png')

    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()
    from cadnano2.model.io.decoder import decode
    from cadnano2.model.io.encoder import encode
    from PyQt6.QtCore import QMarginsF, QRectF
    from PyQt6.QtGui import QImage, QPainter, QColor
    from PIL import Image

    dc = list(app.documentControllers)[0]
    doc = dc.document()

    with io.open(base_json, 'r', encoding='utf-8') as fd:
        decode(doc, fd.read())

    part = doc.selectedPart()
    vhs = list(part.getVirtualHelices())
    vh_by_num = {vh.number(): vh for vh in vhs}

    # Sort helices by row, then column
    rows = {}
    for vh in vhs:
        r = vh.coord()[0]
        if r not in rows:
            rows[r] = []
        rows[r].append(vh)
    for r in rows:
        rows[r].sort(key=lambda v: v.coord()[1])

    r12 = rows[12]  # sorted by col: col 9..20
    r13 = rows[13]

    n_pairs = len(r12) // 2  # 6 pairs per row
    bar_start = arm_pairs
    bar_end = n_pairs - arm_pairs

    print(f"Cross: {arm_pairs} arm pairs ({arm_pairs*2}h), "
          f"{bar_end - bar_start} bar pairs ({(bar_end - bar_start)*2}h), "
          f"arm length={arm_bp}bp")

    # Calculate trim positions (centered)
    # Row 12: full range [5..246], center ≈ 125
    # Row 13: full range [2..242], center ≈ 122
    r12_center = (5 + 246) // 2   # 125
    r13_center = (2 + 242) // 2   # 122
    half_arm = arm_bp // 2

    r12_new_lo = r12_center - half_arm
    r12_new_hi = r12_center + half_arm
    r13_new_lo = r13_center - half_arm
    r13_new_hi = r13_center + half_arm

    print(f"  Row 12: trim to [{r12_new_lo}..{r12_new_hi}] "
          f"(center pairs stay [5..246])")
    print(f"  Row 13: trim to [{r13_new_lo}..{r13_new_hi}] "
          f"(center pairs stay [2..242])")

    # Trim arm pairs in row 12
    # r12 is sorted by col: [col9, col10, ..., col20]
    # Routing order: H0=col20(rightmost), H11=col9(leftmost)
    # Pair 0 = (H0,H1) = (r12[11], r12[10]) = (col20, col19) → rightmost
    # Pair 5 = (H10,H11) = (r12[1], r12[0]) = (col10, col9) → leftmost
    for pair_idx in range(n_pairs):
        is_arm = pair_idx < arm_pairs or pair_idx >= (n_pairs - arm_pairs)
        if not is_arm:
            continue

        # Row 12: trim right-side pairs (high pair_idx → rightmost cols)
        vh_a = r12[11 - 2 * pair_idx]
        vh_b = r12[10 - 2 * pair_idx]
        for vh in [vh_a, vh_b]:
            for strand in list(vh.scaffoldStrandSet()):
                lo, hi = strand.idxs()
                new_lo = max(lo, r12_new_lo)
                new_hi = min(hi, r12_new_hi)
                if new_lo > lo or new_hi < hi:
                    strand.resize((new_lo, new_hi), useUndoStack=False)
            # Remove any strands entirely outside the new range
            for strand in list(vh.scaffoldStrandSet()):
                lo, hi = strand.idxs()
                if hi < r12_new_lo or lo > r12_new_hi:
                    vh.scaffoldStrandSet().removeStrand(strand,
                                                        useUndoStack=False)

    # Trim arm pairs in row 13
    # r13 sorted by col: [col9, col10, ..., col20]
    # H12=col9(leftmost), H23=col20(rightmost)
    # Pair 0 = (H12,H13) = (r13[0], r13[1]) = (col9, col10) → leftmost
    # Pair 5 = (H22,H23) = (r13[10], r13[11]) = (col19, col20) → rightmost
    for pair_idx in range(n_pairs):
        is_arm = pair_idx < arm_pairs or pair_idx >= (n_pairs - arm_pairs)
        if not is_arm:
            continue

        vh_a = r13[2 * pair_idx]
        vh_b = r13[2 * pair_idx + 1]
        for vh in [vh_a, vh_b]:
            for strand in list(vh.scaffoldStrandSet()):
                lo, hi = strand.idxs()
                new_lo = max(lo, r13_new_lo)
                new_hi = min(hi, r13_new_hi)
                if new_lo > lo or new_hi < hi:
                    strand.resize((new_lo, new_hi), useUndoStack=False)
            for strand in list(vh.scaffoldStrandSet()):
                lo, hi = strand.idxs()
                if hi < r13_new_lo or lo > r13_new_hi:
                    vh.scaffoldStrandSet().removeStrand(strand,
                                                        useUndoStack=False)

    # Verify
    scaf = [o for o in part.oligos() if not o.isStaple()]
    n = len(scaf)
    bp = sum(o.length() for o in scaf)
    print(f"\nResult: {bp}bp scaffold in {n} oligo(s)")

    if n != 1:
        print(f"WARNING: Expected 1 oligo, got {n}")

    # Save JSON
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    helixOrderList = dc.win.pathroot.getSelectedPartOrderedVHList()
    if helixOrderList:
        with open(out_json, 'w') as f:
            encode(doc, helixOrderList, f)

    # Screenshot (slice + path merged)
    ss = dc.win.slicescene
    sr = ss.itemsBoundingRect()
    if sr.isEmpty():
        sr = QRectF(0, 0, 400, 400)
    sr = sr.marginsAdded(QMarginsF(20, 20, 20, 20))
    sc2 = 3.0
    sw, sh = int(sr.width() * sc2), int(sr.height() * sc2)
    if sw > 600:
        sc2 *= 600 / sw
        sw = int(sr.width() * sc2)
        sh = int(sr.height() * sc2)
    si = QImage(sw, sh, QImage.Format.Format_ARGB32_Premultiplied)
    si.fill(QColor(255, 255, 255))
    p = QPainter(si)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    ss.render(p, source=sr)
    p.end()
    si.save('/tmp/_s.png')

    ps = dc.win.pathscene
    pr = ps.itemsBoundingRect()
    if pr.isEmpty():
        pr = QRectF(0, 0, 1600, 400)
    pr = pr.marginsAdded(QMarginsF(30, 30, 30, 30))
    pc = 2.0
    pw, ph = int(pr.width() * pc), int(pr.height() * pc)
    if pw > 1400:
        pc *= 1400 / pw
        pw = int(pr.width() * pc)
        ph = int(pr.height() * pc)
    pi2 = QImage(pw, ph, QImage.Format.Format_ARGB32_Premultiplied)
    pi2.fill(QColor(255, 255, 255))
    p2 = QPainter(pi2)
    p2.setRenderHint(QPainter.RenderHint.Antialiasing)
    ps.render(p2, source=pr)
    p2.end()
    pi2.save('/tmp/_p.png')

    sp = Image.open('/tmp/_s.png').convert('RGB')
    pp = Image.open('/tmp/_p.png').convert('RGB')
    th = pp.size[1]
    r = th / sp.size[1]
    sp = sp.resize((int(sp.size[0] * r), th), Image.LANCZOS)
    tw = sp.size[0] + 20 + pp.size[0]
    m = Image.new('RGB', (tw, th), (255, 255, 255))
    m.paste(sp, (0, 0))
    m.paste(pp, (sp.size[0] + 20, 0))
    m.save(out_png)
    print(f"Saved: {out_json}")
    print(f"Screenshot: {out_png}")


if __name__ == '__main__':
    main()
