# Changes Log

## 2026-03-27

1. Moved paper_package, paper_package 2, and zips from ../drafts into cadnano2-agentic for organization.
2. Replaced figures 2, 3, 4, 6, 7, 8 with new versions from paper_package 2.
3. Removed figure 4 (cross-section helix placement). Added matter-of-fact statement about tacoxDNA helix placement to Section 3.
4. Removed figure 9 (targeted_edits, duplicate of fig8 content).
5. Removed failure table figure (fig_failure_table.png).
6. Restored figure 8 (one_shot_edits) after accidental removal.
7. Replaced fig8 image with fig_targeted_edits_sequence.png (fixed formatting version).
8. Rewrote Section 2 (First Attempt): removed "What we learned" slop heading, restructured as statement/evidence/conclusion, added CodeAct citation (Wang et al. ICML 2024), elaborated on why tool-calling failed (primitives couldn't stay primitive, context couldn't be resolved from schemas, tool count ballooned, 0% multi-step success).
9. Removed quirky subtitle from Section 3 ("Worked, Then Didn't, Then Did").
10. Updated captions for all replaced figures to match paper_package 2 draft descriptions.
11. User manually edited fig2 and fig3 captions to remove "The ugly mess" and similar informal language.
12. Rewrote Section 3 bullet points: (1) discovery through source code reading (setConnection3p/5p example), (2) end-to-end pipeline construction across packages, (3) autonomous geometric verification via tacoxDNA. Rewrote Section 3 closing paragraph: 2x14 rectangle as initial demonstration, cavity as next challenge, overview of modification capabilities (precise crossover moves, cavity centering/shifting, structure shrinking, scaffold length tuning).
13. Restructured Section 4 into two phases: Phase 1 (scaffold routing and lattice geometry) covers honeycomb grid-to-layer mapping with explanation of hexagonal y-coordinate ambiguity, dense crossover routing with half/full crossover distinction, and scaffold/staple confusion. Phase 2 (cavity introduction and scaling) covers cavity orientation, file format corruption, cavity destruction, crossover misalignment, and cavity edge alignment. Added @fig2 and @fig3 references to Phase 1.
14. Entity chronology pass: removed premature cavity references from Phase 1 (template filename, @fig3 cavity caption), moved 2x14 rectangle validation to end of Phase 1 as first successful output, introduced cavity concept for the first time in Phase 2 opening, updated Section 5 error numbering to Phase 1/Phase 2 terminology, updated Section 6 extension list to start at 2x16 (since 2x14 already produced in Phase 1), rewrote Section 3 closing to defer specifics to later sections.
15. Full draft revision: replaced all narrative-illustrative and narraustrative writing with analytic/declarative style. Affected sections: Introduction (removed "tedious" editorializing), Section 2 (replaced "one primitive became three, then six" storytelling with declarative "combinatorial expansion of tool variants"), Section 4 intro (removed "This is where limitations became clear"), Section 5 title and body (renamed to "Error Retention and Cumulative Capability"), Section 7 (replaced "key insight" framing with declarative property list), "The Threshold We Crossed" retitled to "From Demonstration to Knowledge Transfer", Section 8 intro (replaced "strongest evidence" framing with evaluation framing), removed "Why this matters:" editorial aside.
