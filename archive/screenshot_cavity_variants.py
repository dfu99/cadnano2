#!/usr/bin/env python
"""
Take cadnano2 UI screenshots of cavity variant designs.

Strategy: Load the original PI template (which decodes cleanly), then
resize strands to demonstrate different gap sizes. Take path view screenshot.

Max 1800px on longest edge.

Usage:
  conda activate cn24-agentic
  QT_QPA_PLATFORM=offscreen python tools/screenshot_cavity_variants.py
"""

import os
import sys
import io
import json

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, 'examples/2x12_rectangle_cavity.json')
VARIANT_DIR = os.path.join(PROJECT_ROOT, 'results', 'cavity_variants')
MAX_DIM = 1800


def render_pathview(dc):
    """Render the path view scene to a QImage."""
    from PyQt6.QtCore import QMarginsF, QRectF
    from PyQt6.QtGui import QImage, QPainter, QColor

    scene = dc.win.pathscene
    rect = scene.itemsBoundingRect()
    if rect.isEmpty():
        rect = QRectF(0, 0, 1600, 400)

    margin = 30
    rect = rect.marginsAdded(QMarginsF(margin, margin, margin, margin))

    scale = 2.0
    w = int(rect.width() * scale)
    h = int(rect.height() * scale)

    if w > MAX_DIM or h > MAX_DIM:
        ratio = min(MAX_DIM / w, MAX_DIM / h)
        scale *= ratio
        w = int(rect.width() * scale)
        h = int(rect.height() * scale)

    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(255, 255, 255))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(painter, source=rect)
    painter.end()
    return img


def main():
    from math import ceil
    sys.path.insert(0, PROJECT_ROOT)
    import cadnano2.cadnano as cadnano

    app = cadnano.initAppWithGui()

    # Import AFTER QApplication exists (decoder imports Qt widgets at module level)
    from cadnano2.model.io.decoder import decode

    dc = list(app.documentControllers)[0]

    NM_PER_BP = 0.34
    STEP = 21
    SCAFFOLD_TARGET = 8064

    # If called with args, do single variant
    if len(sys.argv) >= 3:
        gap_nm = int(sys.argv[1])
        png_name = sys.argv[2]
    elif len(sys.argv) >= 2:
        # Dispatch mode: run each variant as subprocess
        import subprocess
        for gnm, pn in [(20, 'screenshot_20nm.png'),
                        (30, 'screenshot_30nm.png'),
                        (40, 'screenshot_40nm.png')]:
            print(f"\n=== {gnm}nm gap ===", flush=True)
            result = subprocess.run(
                [sys.executable, __file__, str(gnm), pn],
                env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
                timeout=60, capture_output=True, text=True
            )
            print(result.stdout)
            if result.returncode != 0:
                print(f"  ERROR: {result.stderr[-300:]}")
        print("\nDone.", flush=True)
        return
    else:
        # Default: dispatch mode
        import subprocess
        for gnm, pn in [(20, 'screenshot_20nm.png'),
                        (30, 'screenshot_30nm.png'),
                        (40, 'screenshot_40nm.png')]:
            print(f"\n=== {gnm}nm gap ===", flush=True)
            result = subprocess.run(
                [sys.executable, __file__, str(gnm), pn],
                env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
                timeout=60, capture_output=True, text=True
            )
            print(result.stdout)
            if result.returncode != 0:
                print(f"  ERROR: {result.stderr[-300:]}")
        print("\nDone.", flush=True)
        return

    for gap_nm, png_name in [(gap_nm, png_name)]:
        print(f"\n--- {gap_nm}nm gap ---", flush=True)

        # Load fresh template each time
        dc.newDocument()
        doc = dc.document()
        with io.open(TEMPLATE_PATH, 'r', encoding='utf-8') as fd:
            decode(doc, fd.read())

        part = doc.selectedPart()
        vhs = list(part.getVirtualHelices())
        print(f"  Loaded template: {len(vhs)} helices", flush=True)

        # Compute target helix length
        gap_bp = int(gap_nm / NM_PER_BP)
        n_cavity = 8
        n_helices = 24
        target_L = (SCAFFOLD_TARGET / 0.95 + n_cavity * gap_bp) / n_helices
        new_len = int(ceil(target_L / STEP)) * STEP
        new_len = max(new_len, gap_bp + 140)

        old_len = 252  # template length
        delta = new_len - old_len

        if delta > 0:
            # Extend part size
            max_idx = part.maxBaseIdx()
            if new_len - 1 > max_idx:
                needed = int(ceil((new_len - 1 - max_idx) / STEP)) * STEP
                part.resizeVirtualHelices(0, needed, useUndoStack=False)

            # Resize each strand
            for vh in vhs:
                for ss in [vh.scaffoldStrandSet(), vh.stapleStrandSet()]:
                    for strand in list(ss):
                        lo, hi = strand.idxs()
                        if vh.isEvenParity():
                            new_hi = hi + delta
                        else:
                            new_lo = lo  # keep lo
                            new_hi = hi + delta
                        # Don't extend cavity strands into the gap
                        # (cavity helices have 2 strands, non-cavity have 1)
                        strand.resize((lo, min(hi + delta, new_len - 1)),
                                      useUndoStack=False)

            print(f"  Extended by {delta}bp to {new_len}bp", flush=True)

        # Count scaffold
        scaf_oligos = [o for o in part.oligos() if not o.isStaple()]
        total_bp = sum(o.length() for o in scaf_oligos)
        print(f"  Scaffold: {total_bp}bp", flush=True)

        # Take screenshot
        img = render_pathview(dc)
        out_path = os.path.join(VARIANT_DIR, png_name)
        os.makedirs(VARIANT_DIR, exist_ok=True)
        img.save(out_path)
        print(f"  Screenshot: {out_path} ({img.width()}x{img.height()}px)", flush=True)

    print("\nDone.", flush=True)


if __name__ == '__main__':
    main()
