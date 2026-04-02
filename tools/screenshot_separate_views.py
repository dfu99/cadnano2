#!/usr/bin/env python
"""
Screenshot a cadnano design as separate slice and path view PNGs.
Slice view is cropped to only active helices (no empty grid).

Usage:
    QT_QPA_PLATFORM=offscreen python tools/screenshot_separate_views.py input.json output_prefix
    # Produces: output_prefix_slice.png, output_prefix_path.png
"""
import os, sys, io
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

def main():
    input_json = sys.argv[1]
    output_prefix = sys.argv[2]

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()

    from cadnano2.model.io.decoder import decode
    from PyQt6.QtCore import QMarginsF, QRectF, QPointF
    from PyQt6.QtGui import QImage, QPainter, QColor

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

    # ---- Slice view: active helices only ----
    ss = dc.win.slicescene

    # Find the PartItem to access the virtual helix hash
    from cadnano2.views.sliceview.partitem import PartItem
    part_items = [item for item in ss.items() if isinstance(item, PartItem)]

    if part_items:
        pi = part_items[0]
        # Hide all empty helix items (gray circles) that don't have an active helix
        from cadnano2.views.sliceview.emptyhelixitem import EmptyHelixItem
        hidden_items = []
        for item in ss.items():
            if isinstance(item, EmptyHelixItem):
                if not item.childItems():  # no VirtualHelixItem child = empty
                    item.setVisible(False)
                    hidden_items.append(item)

        # Get bounding rect of only active virtual helix items
        active_items = list(pi._virtualHelixHash.values())
        if active_items:
            union_rect = None
            for vhi in active_items:
                item_rect = vhi.mapToScene(vhi.boundingRect()).boundingRect()
                if union_rect is None:
                    union_rect = item_rect
                else:
                    union_rect = union_rect.united(item_rect)
            sr = union_rect.marginsAdded(QMarginsF(5, 5, 5, 5))
        else:
            sr = ss.itemsBoundingRect()
    else:
        sr = ss.itemsBoundingRect()
        hidden_items = []

    if sr.isEmpty():
        sr = QRectF(0, 0, 400, 400)

    sc = 4.0
    sw, sh = int(sr.width() * sc), int(sr.height() * sc)
    # Cap at reasonable size
    if sw > 2000:
        sc *= 2000 / sw
        sw = int(sr.width() * sc)
        sh = int(sr.height() * sc)

    si = QImage(sw, sh, QImage.Format.Format_ARGB32_Premultiplied)
    si.fill(QColor(255, 255, 255))
    p = QPainter(si)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    ss.render(p, source=sr)
    p.end()

    slice_path = f'{output_prefix}_slice.png'
    si.save(slice_path)
    print(f'Slice view ({sw}x{sh}px): {slice_path}')

    # Restore hidden items
    for item in hidden_items:
        item.setVisible(True)

    # ---- Path view ----
    ps = dc.win.pathscene
    pr = ps.itemsBoundingRect()
    if pr.isEmpty():
        pr = QRectF(0, 0, 1600, 400)
    pr = pr.marginsAdded(QMarginsF(30, 30, 30, 30))

    pc = 3.0
    pw, ph = int(pr.width() * pc), int(pr.height() * pc)
    if pw > 4000:
        pc *= 4000 / pw
        pw = int(pr.width() * pc)
        ph = int(pr.height() * pc)

    pi2 = QImage(pw, ph, QImage.Format.Format_ARGB32_Premultiplied)
    pi2.fill(QColor(255, 255, 255))
    p2 = QPainter(pi2)
    p2.setRenderHint(QPainter.RenderHint.Antialiasing)
    ps.render(p2, source=pr)
    p2.end()

    path_path = f'{output_prefix}_path.png'
    pi2.save(path_path)
    print(f'Path view ({pw}x{ph}px): {path_path}')


if __name__ == '__main__':
    main()
