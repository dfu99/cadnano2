#!/usr/bin/env python
"""Verify a cadnano JSON design: loads in cadnano, checks oligo count, crossover integrity."""
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

def main():
    import io
    json_path = sys.argv[1]
    expected_oligos = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import cadnano2.cadnano as cadnano
    app = cadnano.initAppWithGui()
    from cadnano2.model.io.decoder import decode

    dc = list(app.documentControllers)[0]
    doc = dc.document()

    try:
        with io.open(json_path, 'r', encoding='utf-8') as fd:
            decode(doc, fd.read())
    except Exception as e:
        print(f'FAIL: decode error: {e}')
        sys.exit(1)

    part = doc.selectedPart()
    if part is None:
        print('FAIL: no part loaded')
        sys.exit(1)

    vhs = list(part.getVirtualHelices())
    scaf_oligos = [o for o in part.oligos() if not o.isStaple()]
    n_oligos = len(scaf_oligos)
    total_bp = sum(o.length() for o in scaf_oligos)

    # Check scaffold oligo count
    if n_oligos != expected_oligos:
        print(f'FAIL: {n_oligos} scaffold oligos (expected {expected_oligos})')
        sys.exit(1)

    # Check for broken crossovers: every crossover should be reciprocal
    broken = 0
    for vh in vhs:
        scaf_ss = vh.scaffoldStrandSet()
        for strand in scaf_ss:
            c3 = strand.connection3p()
            if c3:
                # Verify reciprocal: c3's 5' should point back to strand
                if c3.connection5p() != strand:
                    broken += 1
            c5 = strand.connection5p()
            if c5:
                if c5.connection3p() != strand:
                    broken += 1

    if broken > 0:
        print(f'FAIL: {broken} broken crossover connections')
        sys.exit(1)

    # Check for deformed full crossovers: a full crossover should have
    # two half-crossovers at adjacent indices
    deformed = 0
    for vh in vhs:
        scaf_ss = vh.scaffoldStrandSet()
        for strand in scaf_ss:
            c3 = strand.connection3p()
            if c3 and c3.strandSet().virtualHelix() != vh:
                # This is a crossover. Check if partner has adjacent crossover back
                partner_vh = c3.strandSet().virtualHelix()
                idx_here = strand.idx3Prime()
                # Find the adjacent crossover (should be at idx_here ± 1)
                found_adjacent = False
                for partner_strand in partner_vh.scaffoldStrandSet():
                    pc3 = partner_strand.connection3p()
                    if pc3 and pc3.strandSet().virtualHelix() == vh:
                        partner_idx = partner_strand.idx3Prime()
                        if abs(partner_idx - idx_here) <= 1:
                            found_adjacent = True
                            break
                    pc5 = partner_strand.connection5p()
                    if pc5 and pc5.strandSet().virtualHelix() == vh:
                        partner_idx = partner_strand.idx5Prime()
                        if abs(partner_idx - idx_here) <= 1:
                            found_adjacent = True
                            break
                if not found_adjacent:
                    deformed += 1

    if deformed > 0:
        print(f'FAIL: {deformed} deformed crossovers (missing adjacent pair)')
        sys.exit(1)

    print(f'PASS: {len(vhs)}h, {total_bp}bp, {n_oligos} oligo(s), 0 broken, 0 deformed')
    sys.exit(0)

if __name__ == '__main__':
    main()
