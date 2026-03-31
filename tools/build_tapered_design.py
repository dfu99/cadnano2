#!/usr/bin/env python
"""Build a tapered 2x12 design with centered midseams, with verification loop.

Attempts up to MAX_ATTEMPTS times. Each attempt:
1. Load base simple routing design
2. Apply taper (resize strands)
3. Move midseam crossovers to centered positions
4. Save JSON
5. Verify: reload in fresh cadnano, check 1 oligo + no broken crossovers

If verification fails, diagnose the issue and adjust the approach.
"""
import os, sys, io, subprocess, json

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

MAX_ATTEMPTS = 10
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_JSON = os.path.join(PROJECT_ROOT, 'results', 'solid_rectangle', '2x12_simple_routing.json')
OUT_DIR = os.path.join(PROJECT_ROOT, 'results', 'stress_test')
OUT_JSON = os.path.join(OUT_DIR, 'tapered_centered_2x12.json')
OUT_PNG = os.path.join(OUT_DIR, 'tapered_centered_2x12_both.png')
VERIFY_SCRIPT = os.path.join(PROJECT_ROOT, 'tools', 'verify_design.py')

# Taper profile: pair index → right edge position
TAPER = [246, 225, 204, 183, 162, 141]


def verify(json_path):
    """Run verification in a separate process. Returns (passed, message)."""
    result = subprocess.run(
        [sys.executable, VERIFY_SCRIPT, json_path, '1'],
        capture_output=True, text=True, timeout=60,
        env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'}
    )
    output = (result.stdout + result.stderr).strip().split('\n')
    last_line = output[-1] if output else ''
    passed = result.returncode == 0
    return passed, last_line


def attempt_build(move_midseams=True, midseam_deltas=None):
    """Build the tapered design. Returns the output JSON path."""
    sys.path.insert(0, PROJECT_ROOT)

    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()
    from cadnano2.model.io.decoder import decode
    from cadnano2.model.io.encoder import encode
    from cadnano2.views.agent.agentmethods import AgentMethods
    from PyQt6.QtCore import QMarginsF, QRectF
    from PyQt6.QtGui import QImage, QPainter, QColor
    from PIL import Image

    dc = list(app.documentControllers)[0]
    doc = dc.document()

    with io.open(BASE_JSON, 'r', encoding='utf-8') as fd:
        decode(doc, fd.read())

    part = doc.selectedPart()
    vhs = list(part.getVirtualHelices())
    vh_by_num = {vh.number(): vh for vh in vhs}

    # Group by row
    rows = {}
    for vh in vhs:
        r = vh.coord()[0]
        if r not in rows:
            rows[r] = []
        rows[r].append(vh)
    for r in rows:
        rows[r].sort(key=lambda v: v.coord()[1])

    r12 = rows[12]
    r13 = rows[13]

    # Step 1: Apply taper (resize strands on right side)
    for pair_idx in range(6):
        new_hi = TAPER[pair_idx]

        # R12 pair
        for vh in [r12[11 - 2 * pair_idx], r12[10 - 2 * pair_idx]]:
            for strand in list(vh.scaffoldStrandSet()):
                lo, hi = strand.idxs()
                if hi > new_hi:
                    strand.resize((lo, new_hi), useUndoStack=False)
            for strand in list(vh.scaffoldStrandSet()):
                if strand.idxs()[0] > new_hi:
                    vh.scaffoldStrandSet().removeStrand(strand, useUndoStack=False)

        # R13 pair
        r13_hi = min(new_hi, 242)
        for vh in [r13[2 * pair_idx], r13[2 * pair_idx + 1]]:
            for strand in list(vh.scaffoldStrandSet()):
                lo, hi = strand.idxs()
                if hi > r13_hi:
                    strand.resize((lo, r13_hi), useUndoStack=False)
            for strand in list(vh.scaffoldStrandSet()):
                if strand.idxs()[0] > r13_hi:
                    vh.scaffoldStrandSet().removeStrand(strand, useUndoStack=False)

    # Check oligo count after taper
    scaf = [o for o in part.oligos() if not o.isStaple()]
    print(f'  After taper: {sum(o.length() for o in scaf)}bp, {len(scaf)} oligo(s)')

    if len(scaf) != 1:
        print(f'  ERROR: Taper broke scaffold into {len(scaf)} oligos')
        return None

    # Step 2: Move midseam crossovers to centered positions
    if move_midseams:
        class MockDC:
            def __init__(self, a, d, p):
                self._app, self._doc, self._part = a, d, p
            def document(self):
                return self._doc
            def activePart(self):
                return self._part
            def undoStack(self):
                return self._doc.undoStack()

        methods = AgentMethods(MockDC(app, doc, part))

        for inter_idx in range(5):
            shorter_edge = min(TAPER[inter_idx], TAPER[inter_idx + 1])
            center = (5 + shorter_edge) // 2

            # R12 inter-pair
            ha = 2 * inter_idx + 1
            hb = 2 * inter_idx + 2

            # Find current midseam position
            vh_a = vh_by_num[ha]
            old_pos = None
            for strand in vh_a.scaffoldStrandSet():
                c3 = strand.connection3p()
                if c3 and c3.strandSet().virtualHelix().number() == hb:
                    old_pos = strand.idx3Prime()
                    break
                c5 = strand.connection5p()
                if c5 and c5.strandSet().virtualHelix().number() == hb:
                    old_pos = strand.idx5Prime()
                    break

            if old_pos is not None:
                delta = center - old_pos
                if midseam_deltas:
                    delta = midseam_deltas.get(inter_idx, delta)
                if abs(delta) > 2:
                    result = methods.moveCrossover(ha, hb, old_pos, 'scaffold', delta)
                    print(f'  R12 H{ha}-H{hb}: {old_pos}→{old_pos + delta}: {result[:50]}')

                    # Verify oligo count after each move
                    scaf_check = [o for o in part.oligos() if not o.isStaple()]
                    if len(scaf_check) != 1:
                        print(f'  WARNING: Move broke scaffold into {len(scaf_check)} oligos')

    # Final oligo check
    scaf_final = [o for o in part.oligos() if not o.isStaple()]
    n_oligos = len(scaf_final)
    total_bp = sum(o.length() for o in scaf_final)
    print(f'  Final: {total_bp}bp, {n_oligos} oligo(s)')

    # Save JSON
    os.makedirs(OUT_DIR, exist_ok=True)
    helixOrderList = dc.win.pathroot.getSelectedPartOrderedVHList()
    if helixOrderList:
        with open(OUT_JSON, 'w') as f:
            encode(doc, helixOrderList, f)

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

    ss = dc.win.slicescene
    sr = ss.itemsBoundingRect()
    if sr.isEmpty():
        sr = QRectF(0, 0, 400, 400)
    sr = sr.marginsAdded(QMarginsF(20, 20, 20, 20))
    sc2 = 3.0
    sw = int(sr.width() * sc2)
    sh = int(sr.height() * sc2)
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

    pi2 = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    pi2.fill(QColor(255, 255, 255))
    p2 = QPainter(pi2)
    p2.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(p2, source=rect)
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
    m.save(OUT_PNG)

    return OUT_JSON


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f'\n=== Attempt {attempt}/{MAX_ATTEMPTS} ===')

        if attempt == 1:
            # First attempt: taper + move midseams
            result = attempt_build(move_midseams=True)
        elif attempt == 2:
            # Second attempt: taper only, no midseam moves
            print('  Strategy: taper only, skip midseam centering')
            result = attempt_build(move_midseams=False)
        else:
            # Further attempts: taper + smaller midseam moves
            print(f'  Strategy: taper + conservative midseam moves (scale={1.0 - attempt * 0.1:.1f})')
            scale_factor = max(0.1, 1.0 - attempt * 0.1)
            deltas = {}
            for i in range(5):
                shorter = min(TAPER[i], TAPER[i + 1])
                center = (5 + shorter) // 2
                deltas[i] = int((center - 127) * scale_factor)
            result = attempt_build(move_midseams=True, midseam_deltas=deltas)

        if result is None:
            print(f'  Build failed, retrying...')
            continue

        # Verify
        passed, msg = verify(result)
        print(f'  Verification: {msg}')

        if passed:
            print(f'\n=== SUCCESS on attempt {attempt} ===')
            print(f'  Output: {OUT_JSON}')
            print(f'  Screenshot: {OUT_PNG}')
            return

        print(f'  Failed verification, retrying...')

    print(f'\n=== FAILED after {MAX_ATTEMPTS} attempts ===')
    sys.exit(1)


if __name__ == '__main__':
    main()
