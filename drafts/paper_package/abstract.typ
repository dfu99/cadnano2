#set document(title: "Coding Agents as a Mechanism for Formalizing and Transferring Domain Knowledge in DNA Origami Design")
#set page(margin: (top: 1in, bottom: 1in, right: 1in, left: 1in), numbering: none)
#set text(font: "New Computer Modern", size: 11pt)
#set par(justify: true)
#show link: underline
#show figure.caption: set align(left)

#align(center)[
  #text(size: 14pt, weight: "bold")[Coding Agents as a Mechanism for Formalizing and Transferring Domain Knowledge in DNA Origami Design]

  #v(0.5em)
  Daniel Fu, Yonggang Ke

  #v(0.3em)
  #text(size: 10pt, style: "italic")[Emory University]
]

#v(1em)

== Abstract

Designing DNA origami requires coordinating a series of disjointed tools (caDNAno, tacoxDNA, oxDNA) and applying informal design rules that are rarely documented and must be re-learned by each new practitioner. Many of these workflows are now standardized in practice, but the knowledge connecting them remains fragmented across individual expertise, lab conventions, and ad hoc scripts.

We demonstrate that a coding agent, a large language model with direct access to source code, can formalize this knowledge. When prompted to design DNA origami through caDNAno, the agent fails at points where domain knowledge is required but absent from the codebase. Each failure exposes a rule that experienced designers apply implicitly. The human designer corrects the agent once, and the agent encodes each correction as verifier functions, parametric scripts, and documented failure catalogs, consolidating the disjointed pipeline into a single, reproducible workflow.

As a proof of concept, we developed a parametric pipeline for 2-layer rectangular origami with tunable cavities, resolving 10 failure modes spanning lattice geometry, scaffold routing, and cavity-specific crossover patterns. With these rules formalized, the agent produced parametric cavity variants at 20, 30, and 40 nm widths, executing the full pipeline from design through stapling, format conversion, and molecular dynamics simulation without user interaction. These artifacts are transferable text-file instructions that reduce the friction of adopting new tools and design methodologies, allowing subsequent users and agents to build on established design logic rather than rediscovering it.

#v(0.5em)

*Keywords:* DNA origami, coding agents, large language models, caDNAno, domain knowledge formalization, parametric design, oxDNA

#figure(
  image("figures/fig_abstract.png", width: 100%),
  caption: [(A) From failure to autonomous design. Left: early agent output (4-by-7 grid, fragmented routing). Center: user-provided template with correct cavity routing. Right: autonomous output (2-by-22 stapled design, 220+ staples). (B) Parametric cavity variants at 20, 30, and 40 nm widths produced autonomously, showing tacoxDNA initial structure (top) and oxDNA-relaxed structure (bottom).],
)
