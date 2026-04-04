#set document(title: "Coding Agents as a Mechanism for Formalizing and Transferring Domain Knowledge in DNA Origami Design")
#set page(margin: (top: 0.75in, bottom: 0.75in, right: 0.75in, left: 0.75in), numbering: none)
#set text(font: "New Computer Modern", size: 10pt)
#set par(justify: true, leading: 0.55em)
#show link: underline
#show figure.caption: set align(left)

#align(center)[
  #text(size: 13pt, weight: "bold")[Coding Agents as a Mechanism for Formalizing and Transferring Domain Knowledge in DNA Origami Design]

  #v(0.4em)
  Daniel Fu, Yonggang Ke

  #v(0.2em)
  #text(size: 9pt, style: "italic")[Wallace H. Coulter Department of Biomedical Engineering, Emory University, Atlanta, GA]
]

#v(0.6em)

== Abstract

The DNA origami design ecosystem spans a growing number of specialized tools, each addressing a specific shape class or design subtask through its own interface. The knowledge governing when and how to use and compose these tools correctly remains fragmented across _ad hoc_ scripts, lab conventions, and individual expertise, and must be re-learned by each new practitioner for each new tool.

We demonstrate that a coding agent, a large language model with direct access to source code, can formalize this knowledge. When prompted to design DNA origami through caDNAno, the agent fails at points where domain knowledge is required but absent from the codebase. Each failure exposes a rule that experienced designers apply implicitly. The human designer corrects the agent once, and the agent encodes each correction as verifier functions, parametric scripts, and documented failure catalogs, consolidating the disjointed pipeline into a single, reproducible workflow.

As a proof of concept, we developed a parametric pipeline for 2-layer rectangular origami with tunable cavities using caDNAno, tacoxDNA, and oxDNA, resolving failure modes spanning lattice geometry, scaffold routing, and cavity-specific crossover patterns. With these rules formalized, the agent produced parametric cavity variants at 20, 30, and 40 nm widths, executing the full pipeline from design through stapling, format conversion, and molecular dynamics simulation without user interaction. These artifacts are transferable text-file instructions that reduce the friction of adopting new tools and design methodologies, allowing subsequent users and agents to build on established design logic rather than rediscovering it. The same approach can extend to other open-source design tools, potentially consolidating the fragmented ecosystem into a unified, agent-mediated pipeline across shape classes and design methodologies.

*Keywords:* DNA origami, coding agents, caDNAno, domain knowledge formalization, natural language design

#figure(
  image("figures/fig_abstract.png", width: 100%),
  caption: [(A) From failure to autonomous design. Left: early agent output (2-by-14 rectangle, 65 scaffold oligos, no routing logic). Center: user-provided template with correct cavity routing (1 scaffold oligo). Right: autonomous output (2-by-22 stapled design, 220+ staples). (B) Parametric cavity variants at 20, 30, and 40 nm widths produced autonomously, showing tacoxDNA initial structure (top) and oxDNA-relaxed structure (bottom).],
)
