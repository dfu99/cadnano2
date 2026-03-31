#!/usr/bin/env python
"""Single attempt: build tapered 2x12. Strategy chosen by CLI arg."""
import os, sys, io
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

TAPER = [246, 225, 204, 183, 162, 141]


def main():
    strategy = sys.argv[1] if len(sys.argv) > 1 else 'taper_only'

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)

    base_json = os.path.join(project_root, 'results', 'solid_rectangle', '2x12_simple_routing.json')
    out_json = os.path.join(project_root, 'results', 'stress_test', 'tapered_centered_2x12.json')
    out_png = os.path.join(project_root, 'results', 'stress_test', 'tapered_centered_2x12_both.png')

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

    rows = {}
    for vh in vhs:
        r = vh.coord()[0]
        if r not in rows: rows[r] = []
        rows[r].append(vh)
    for r in rows: rows[r].sort(key=lambda v: v.coord()[1])

    r12 = rows[12]
    r13 = rows[13]

    # Step 1: Always taper
    for pair_idx in range(6):
        new_hi = TAPER[pair_idx]
        for vh in [r12[11 - 2 * pair_idx], r12[10 - 2 * pair_idx]]:
            for strand in list(vh.scaffoldStrandSet()):
                lo, hi = strand.idxs()
                if hi > new_hi:
                    strand.resize((lo, new_hi), useUndoStack=False)
            for strand in list(vh.scaffoldStrandSet()):
                if strand.idxs()[0] > new_hi:
                    vh.scaffoldStrandSet().removeStrand(strand, useUndoStack=False)

        r13_hi = min(new_hi, 242)
        for vh in [r13[2 * pair_idx], r13[2 * pair_idx + 1]]:
            for strand in list(vh.scaffoldStrandSet()):
                lo, hi = strand.idxs()
                if hi > r13_hi:
                    strand.resize((lo, r13_hi), useUndoStack=False)
            for strand in list(vh.scaffoldStrandSet()):
                if strand.idxs()[0] > r13_hi:
                    vh.scaffoldStrandSet().removeStrand(strand, useUndoStack=False)

    scaf = [o for o in part.oligos() if not o.isStaple()]
    n = len(scaf)
    bp = sum(o.length() for o in scaf)
    print(f'After taper: {bp}bp, {n} oligo(s) [strategy={strategy}]', flush=True)

    if n != 1:
        print('FAIL: taper broke scaffold')
        sys.exit(1)

    # Save
    os.makedirs(os.path.dirname(out_json), exist_ok=True)
    helixOrderList = dc.win.pathroot.getSelectedPartOrderedVHList()
    if helixOrderList:
        with open(out_json, 'w') as f:
            encode(doc, helixOrderList, f)

    # Screenshot
    ss = dc.win.slicescene; sr = ss.itemsBoundingRect()
    if sr.isEmpty(): sr = QRectF(0, 0, 400, 400)
    sr = sr.marginsAdded(QMarginsF(20, 20, 20, 20))
    sc2 = 3.0; sw = int(sr.width()*sc2); sh = int(sr.height()*sc2)
    if sw > 600: sc2 *= 600/sw; sw = int(sr.width()*sc2); sh = int(sr.height()*sc2)
    si = QImage(sw, sh, QImage.Format.Format_ARGB32_Premultiplied)
    si.fill(QColor(255, 255, 255))
    p = QPainter(si); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    ss.render(p, source=sr); p.end(); si.save('/tmp/_s.png')

    ps = dc.win.pathscene; pr = ps.itemsBoundingRect()
    if pr.isEmpty(): pr = QRectF(0, 0, 1600, 400)
    pr = pr.marginsAdded(QMarginsF(30, 30, 30, 30))
    pc = 2.0; pw = int(pr.width()*pc); ph = int(pr.height()*pc)
    if pw > 1400: pc *= 1400/pw; pw = int(pr.width()*pc); ph = int(pr.height()*pc)
    pi2 = QImage(pw, ph, QImage.Format.Format_ARGB32_Premultiplied)
    pi2.fill(QColor(255, 255, 255))
    p2 = QPainter(pi2); p2.setRenderHint(QPainter.RenderHint.Antialiasing)
    ps.render(p2, source=pr); p2.end(); pi2.save('/tmp/_p.png')

    sp = Image.open('/tmp/_s.png').convert('RGB')
    pp = Image.open('/tmp/_p.png').convert('RGB')
    th = pp.size[1]; r = th / sp.size[1]
    sp = sp.resize((int(sp.size[0]*r), th), Image.LANCZOS)
    tw = sp.size[0]+20+pp.size[0]
    m = Image.new('RGB', (tw, th), (255, 255, 255))
    m.paste(sp, (0, 0)); m.paste(pp, (sp.size[0]+20, 0))
    m.save(out_png)
    print(f'Saved: {out_json}', flush=True)


if __name__ == '__main__':
    main()
