---
layout: home

hero:
  name: Cartograph
  text: Compute the architecture. Prove the relationships.
  tagline: A local-first engine that derives a cross-language architecture graph from source, and shows the evidence behind every edge it draws.
  actions:
    - theme: brand
      text: Read the technical writeup
      link: /writeup/technical-writeup
    - theme: alt
      text: Install and commands
      link: /releases/v0.1.0
    - theme: alt
      text: Source on GitHub
      link: https://github.com/Rexy-5097/cartograph

features:
  - title: Across the stack, not within a language
    details: A TypeScript call, the HTTP route it reaches, the Python handler behind it, the model that handler uses and the table the model maps to — joined by static analysis across languages that share no symbol table.
    link: /resolver/
    linkText: How the resolver works
  - title: Evidence on every edge
    details: Every relationship carries its provenance, a confidence and the evidence for it, and the domain model will not construct an edge without them.
    link: /graph/
    linkText: The domain graph
  - title: Refuses rather than guesses
    details: An unresolved URL segment stays unknown, an ambiguous match produces no edge, and no language model ever constructs graph structure.
    link: /adr/ADR-0007-no-llm-graph-construction
    linkText: ADR-0007
  - title: Measured, failures included
    details: Benchmark results are published with their scope, their denominators and their failures, and every figure the writeup uses is traced to a committed artifact.
    link: /benchmarks/
    linkText: What is measured
  - title: Local-first
    details: No source code leaves the machine. AI is opt-in per repository and off by default, and the product is fully useful with no API key and no network.
    link: /security/
    linkText: Security
---

## Status

Milestones M00–M16 are accepted; M17, the public launch, is in progress. The
current version is 0.1.0. What is and is not implemented is set out in the
[README](../README.md#what-works-today), and nothing on this site describes
behaviour the code does not have.

## Try it

```bash
cargo install --git https://github.com/Rexy-5097/cartograph cartograph-cli
cartograph .
```

Then follow one relationship across the stack with `cartograph trace <symbol>`.
The [v0.1.0 release notes](releases/v0.1.0.md) cover installation, and
[the command-line reference](development/cli.md) documents every command,
including `blast` and `diff`.

## What ships today

| Surface | What it answers |
|---|---|
| The CLI — `cartograph .`, `trace`, `blast`, `diff` | What a repository contains, how one relationship crosses the stack, what depends on an artefact, and what a change did to the architecture |
| MAP, the desktop application | The architecture graph, drawn, with the evidence behind any edge |
| `cartograph-mcp` | The same graph, queried by an MCP client over one repository granted at launch |
| A pull-request review workflow | `cartograph diff --markdown` posted as a comment — configured for this repository's own pull requests |
| ASK, in the desktop application | An explanation of already-derived evidence in which every claim must cite it verbatim — opt-in, and with no in-product way to supply a key yet, so in practice it shows the evidence unexplained |

TypeScript, TSX and Python only, within a declared supported subset; outside it
Cartograph refuses rather than guesses. The [resolver](resolver/README.md)
lists what is implemented and what is not.

## Where to start

- **[The technical writeup](writeup/technical-writeup.md)** — resolver design,
  benchmark results including failures, and calibration, with every figure
  traced to a committed artifact.
- **[Benchmarks](benchmarks/README.md)** — what was measured, what has been
  published, and why Gate 2 remains unevaluated.
- **[Architecture decisions](adr/README.md)** — the reasoning behind each
  boundary, recorded as it was made.
