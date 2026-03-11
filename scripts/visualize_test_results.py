#!/usr/bin/env python
"""Generate visualization for pattern automation test results."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Load results
with open('results/test_pattern_automation_results.json') as f:
    data = json.load(f)

tests = data['tests']
names = list(tests.keys())
statuses = [1 if v == "PASS" else 0 for v in tests.values()]

fig, axes = plt.subplots(1, 2, figsize=(14, 5), gridspec_kw={'width_ratios': [3, 1]})

# Left: test results bar chart
colors = ['#2ecc71' if s == 1 else '#e74c3c' for s in statuses]
bars = axes[0].barh(range(len(names)), statuses, color=colors, height=0.6)
axes[0].set_yticks(range(len(names)))
axes[0].set_yticklabels([n.replace('_', ' ').title() for n in names], fontsize=10)
axes[0].set_xlim(0, 1.3)
axes[0].set_xticks([0, 1])
axes[0].set_xticklabels(['FAIL', 'PASS'])
axes[0].set_title('Pattern Automation Methods — Headless Test Results', fontsize=13, fontweight='bold')
for i, (bar, status) in enumerate(zip(bars, tests.values())):
    axes[0].text(bar.get_width() + 0.05, bar.get_y() + bar.get_height()/2,
                 status, va='center', fontsize=10,
                 color='#2ecc71' if status == 'PASS' else '#e74c3c',
                 fontweight='bold')
axes[0].invert_yaxis()
axes[0].spines['top'].set_visible(False)
axes[0].spines['right'].set_visible(False)

# Right: summary pie
passed = data['passed']
failed = data['failed']
if failed == 0:
    axes[1].pie([passed], labels=[f'{passed}/{passed}\nAll Pass'],
                colors=['#2ecc71'], startangle=90,
                textprops={'fontsize': 14, 'fontweight': 'bold'})
else:
    axes[1].pie([passed, failed], labels=[f'{passed} Pass', f'{failed} Fail'],
                colors=['#2ecc71', '#e74c3c'], startangle=90, autopct='%1.0f%%',
                textprops={'fontsize': 12})
axes[1].set_title('Summary', fontsize=13, fontweight='bold')

# Add method coverage annotation
method_list = [
    'resizeAllStrands', 'removeCrossoversForPair', 'removeAllCrossovers',
    'addInsertionPattern', 'removeInsertionPattern',
    'addInsertionPatternAll', 'listInsertions'
]
coverage_text = f"Methods tested: {len(method_list)}/7 pattern automation methods"
fig.text(0.5, 0.02, coverage_text, ha='center', fontsize=10, style='italic', color='gray')

plt.tight_layout(rect=[0, 0.05, 1, 1])
outpath = 'results/obj-004-test-pattern-automation-2026-03-10.png'
plt.savefig(outpath, dpi=150, bbox_inches='tight')
print(f"Saved to {outpath}")
