#!/usr/bin/env python
"""Screenshot a cadnano design with both slice and path views merged."""
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

def main():
    import io
    input_json = sys.argv[1]
    output_png = sys.argv[2]

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()

    from cadnano2.model.io.decoder import decode
    from cadnano2.model.parts.part import Part
    from PyQt6.QtCore import QMarginsF, QRectF
    from PyQt6.QtGui import QImage, QPainter, QColor
    from PIL import Image

    dc = list(app.documentControllers)[0]
    doc = dc.document()

    with io.open(input_json, 'r', encoding='utf-8') as fd:
        decode(doc, fd.read())

    part = doc.selectedPart()
    scaf = [o for o in part.oligos() if not o.isStaple()]
    stap = [o for o in part.oligos() if o.isStaple()]
    vhs = list(part.getVirtualHelices())
    print(f'{len(vhs)} helices, {sum(o.length() for o in scaf)}bp scaffold '
          f'in {len(scaf)} oligo(s), {len(stap)} staples')

    # Slice view
    ss = dc.win.slicescene
    sr = ss.itemsBoundingRect()
    if sr.isEmpty():
        sr = QRectF(0, 0, 400, 400)
    sr = sr.marginsAdded(QMarginsF(20, 20, 20, 20))
    sc = 3.0
    sw, sh = int(sr.width() * sc), int(sr.height() * sc)
    if sw > 600:
        sc *= 600 / sw
        sw = int(sr.width() * sc)
        sh = int(sr.height() * sc)
    si = QImage(sw, sh, QImage.Format.Format_ARGB32_Premultiplied)
    si.fill(QColor(255, 255, 255))
    p = QPainter(si)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    ss.render(p, source=sr)
    p.end()
    si.save('/tmp/_slice.png')

    # Path view
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
    pi2.save('/tmp/_path.png')

    # Merge side by side
    sp = Image.open('/tmp/_slice.png').convert('RGB')
    pp = Image.open('/tmp/_path.png').convert('RGB')
    th = pp.size[1]
    r = th / sp.size[1]
    sp = sp.resize((int(sp.size[0] * r), th), Image.LANCZOS)
    gap = 20
    tw = sp.size[0] + gap + pp.size[0]
    m = Image.new('RGB', (tw, th), (255, 255, 255))
    m.paste(sp, (0, 0))
    m.paste(pp, (sp.size[0] + gap, 0))

    os.makedirs(os.path.dirname(output_png) or '.', exist_ok=True)
    m.save(output_png)
    print(f'Saved: {output_png} ({tw}x{th}px)')

if __name__ == '__main__':
    main()
