#!/usr/bin/env python
"""Debug op 9 staple crossovers."""
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cadnano2.cadnano as cadnano
app = cadnano.initAppWithGui()

# Use the same setup functions as gen_appendix_operations
from tools.gen_appendix_operations import setup_with_dense_xovers

dc, methods = setup_with_dense_xovers(app)

# List scaffold crossovers
scaf_xo = methods.listCrossovers(strand_type='scaffold')
print(f'Scaffold crossovers count: {scaf_xo.split("total")[0].split("(")[-1].strip()}')

# Test 1: default staple
r2 = methods.addCrossoversForPair(0, 1, 'staple')
print(f'Staple (default): {r2}')
stap_xo = methods.listCrossovers(strand_type='staple')
# Count and show staple positions
import re, ast
match = re.search(r'\[.*\]', str(stap_xo), re.DOTALL)
if match:
    xovers = ast.literal_eval(match.group())
    print(f'Staple count: {len(xovers)}')
    # Show rightmost few
    rightmost = sorted(xovers, key=lambda x: x.get('idx1', 0), reverse=True)[:3]
    for x in rightmost:
        print(f'  idx1={x["idx1"]} on H{x["helix1"]}')
else:
    print(f'No staple crossovers parsed')
