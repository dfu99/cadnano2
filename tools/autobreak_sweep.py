#!/usr/bin/env python
"""Autobreak parameter sweep on a cadnano design.

Generates screenshots and JSON for each parameter combination.
Uses a single QApplication instance, creating fresh documents via new file action.
"""
import os, sys, io, json
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, '.')

import importlib, importlib.util

# Pre-load autobreak modules
sg_path = os.path.join('.', 'cadnano2', 'plugins', 'autobreak', 'staplegraph.py')
sg_spec = importlib.util.spec_from_file_location(
    'cadnano2.plugins.autobreak.staplegraph', sg_path)
sg = importlib.util.module_from_spec(sg_spec)
sys.modules['cadnano2.plugins.autobreak.staplegraph'] = sg
sg_spec.loader.exec_module(sg)

ab_path = os.path.join('.', 'cadnano2', 'plugins', 'autobreak', 'autobreak.py')
ab_spec = importlib.util.spec_from_file_location(
    'cadnano2.plugins.autobreak.autobreak', ab_path)
ab_mod = importlib.util.module_from_spec(ab_spec)
sys.modules['cadnano2.plugins.autobreak.autobreak'] = ab_mod
ab_spec.loader.exec_module(ab_mod)

import cadnano2.cadnano as cadnano
from cadnano2.model.io.decoder import decode
from cadnano2.model.io.encoder import encode
from cadnano2.model.parts.part import Part
from PyQt6.QtCore import QMarginsF, QRectF
from PyQt6.QtGui import QImage, QPainter, QColor

app = cadnano.initAppWithGui()

INPUT_JSON = 'results/cavity_variants/cavity_30nm_2x12_8064bp.json'
OUT_DIR = 'results/autobreak_sweep'
os.makedirs(OUT_DIR, exist_ok=True)

with open(INPUT_JSON) as f:
    raw_json = f.read()

configs = [
    {'name': 'leg3_tgt28', 'minStapleLen': 18, 'maxStapleLen': 50,
     'tgtStapleLen': 28, 'minStapleLegLen': 3},
    {'name': 'leg3_tgt32', 'minStapleLen': 18, 'maxStapleLen': 50,
     'tgtStapleLen': 32, 'minStapleLegLen': 3},
    {'name': 'leg3_tgt42', 'minStapleLen': 18, 'maxStapleLen': 50,
     'tgtStapleLen': 42, 'minStapleLegLen': 3},
    {'name': 'leg5_tgt28', 'minStapleLen': 18, 'maxStapleLen': 50,
     'tgtStapleLen': 28, 'minStapleLegLen': 5},
    {'name': 'leg5_tgt32', 'minStapleLen': 18, 'maxStapleLen': 50,
     'tgtStapleLen': 32, 'minStapleLegLen': 5},
    {'name': 'leg5_tgt42', 'minStapleLen': 18, 'maxStapleLen': 50,
     'tgtStapleLen': 42, 'minStapleLegLen': 5},
]

results_data = []

for i, cfg in enumerate(configs):
    # Create fresh document
    dc = list(app.documentControllers)[0]
    if i > 0:
        dc.actionNewSlot()
        dc = list(app.documentControllers)[-1]
    doc = dc.document()
    decode(doc, raw_json)

    part = doc.selectedPart()

    # AutoStaple
    Part.autoStaple(part)
    stap_before = sum(1 for o in part.oligos() if o.isStaple())

    # AutoBreak
    settings = {k: cfg[k] for k in
                ['minStapleLen', 'maxStapleLen', 'tgtStapleLen', 'minStapleLegLen']}

    unsolvable = 0
    for oligo in list(part.oligos()):
        if oligo.isStaple() and oligo.length() >= settings['minStapleLen']:
            try:
                ab_mod.nxBreakStaple(oligo, settings)
            except Exception:
                unsolvable += 1

    stap_after = sum(1 for o in part.oligos() if o.isStaple())
    lengths = sorted([o.length() for o in part.oligos() if o.isStaple()])
    short_ct = sum(1 for l in lengths if l < 18)
    long_ct = sum(1 for l in lengths if l > 50)
    avg = sum(lengths) / len(lengths) if lengths else 0

    result = {
        'name': cfg['name'],
        'minStapleLegLen': cfg['minStapleLegLen'],
        'tgtStapleLen': cfg['tgtStapleLen'],
        'staples_before_break': stap_before,
        'staples_after_break': stap_after,
        'min_len': min(lengths) if lengths else 0,
        'max_len': max(lengths) if lengths else 0,
        'avg_len': round(avg, 1),
        'short_under_18': short_ct,
        'long_over_50': long_ct,
        'unsolvable': unsolvable,
    }
    results_data.append(result)

    label = f"leg{cfg['minStapleLegLen']}_tgt{cfg['tgtStapleLen']}"
    print(f"{label}: {stap_after} staples, "
          f"{min(lengths)}-{max(lengths)}bp, avg={avg:.0f}bp, "
          f"short={short_ct}, long={long_ct}, unsolvable={unsolvable}")

    # Screenshot
    scene = dc.win.pathscene
    rect = scene.itemsBoundingRect()
    if rect.isEmpty():
        rect = QRectF(0, 0, 1600, 400)
    margin = 30
    rect = rect.marginsAdded(QMarginsF(margin, margin, margin, margin))
    scale = 2.0
    w = int(rect.width() * scale)
    h = int(rect.height() * scale)
    if w > 1800 or h > 1800:
        ratio = min(1800 / w, 1800 / h)
        scale *= ratio
        w = int(rect.width() * scale)
        h = int(rect.height() * scale)
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(QColor(255, 255, 255))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(painter, source=rect)
    painter.end()
    img.save(os.path.join(OUT_DIR, f'screenshot_{cfg["name"]}.png'))

    # Save JSON
    helixOrderList = dc.win.pathroot.getSelectedPartOrderedVHList()
    if helixOrderList:
        with open(os.path.join(OUT_DIR, f'design_{cfg["name"]}.json'), 'w') as f:
            encode(doc, helixOrderList, f)

# Save summary
with open(os.path.join(OUT_DIR, 'sweep_results.json'), 'w') as f:
    json.dump(results_data, f, indent=2)

print(f"\nSweep complete. {len(results_data)} configs saved to {OUT_DIR}/")
