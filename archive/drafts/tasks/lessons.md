# Lessons

## Writing Style
- NEVER use emdashes (---). Use commas, semicolons, colons, or restructure the sentence.
- No quirky or clever section titles. Titles should be direct and descriptive.
- No "What we learned:" or similar AI-slop subheadings. Conclusions should be stated as objective scientific observations integrated into the paragraph.
- No informal language in captions ("The ugly mess", etc.). Captions are factual descriptions.
- Each section should follow statement, supporting evidence, conclusion structure.
- NEVER use narrative-illustrative or narraustrative vague writing. Always use analytic or declarative style. Examples of violations:
  - "one primitive became three, then six" (narrative storytelling)
  - "This is where the agent's limitations became clear" (narraustrative scene-setting)
  - "The strongest evidence came in the final session" (narrative framing)
  - "Early in this project, the agent produced 'cool demos'" (anecdotal)
  - "*Why this matters:*" (editorial aside)
  - "The threshold we crossed" (narrative milestone language)
  Instead, state what happened, what was measured, and what it demonstrates. Use declarative sentences with concrete subjects and verbs.
- NEVER use sentence fragment corrections like "*Correction:* the user did X." Explain the resolution in full prose, describing how the correction was delivered (descriptive prompt, few-shot examples, corrected design file) and what the agent retained from it.
- NEVER use low-information descriptors like "(failed)" or "(succeeded)" in captions or text. Always explain what happened (the specific outcome), then why it happened (the causal mechanism). E.g., not "embedded LLM (failed)" but "embedded LLM achieved 0% success on multi-step tasks because the model could not resolve contextual constraints from tool schemas."
- Figure captions with subfigures must reference the labels: "(a) description... (b) description..."

## Figure Management
- When the user says "remove figure X", confirm which figure by content, not just number. Figure numbers shift as figures are added/removed.
- When replacing figures, always update both the image path AND the caption.
- Check for dangling @fig references in body text after removing figures.

## Colon Usage
- Do not overuse colons. Excessive colons read as AI-generated. Use periods, conjunctions, or restructure the sentence instead. Only use colons where absolutely necessary (e.g., introducing a formal list title, or where no other punctuation works). When in doubt, use a period and start a new sentence.

## Figure Citations
- Every figure and subfigure must be explicitly cited in the body text. No figure should appear without a corresponding textual reference. This is standard academic paper writing practice.
- Subfigure labels use uppercase: (A), (B), (C) — not lowercase. Match the case used in the actual figure images.

## Task Execution
- Do not remove things the user wants to keep. When instructions are ambiguous, clarify before acting.
- The failure table figure was removed when user said "remove Figure 7" — user meant the failure table (which was the last figure), not fig7_final_stapled_product. Listen to content descriptions, not just numbers.
