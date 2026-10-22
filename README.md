# Cartograph

**Compute the architecture. Prove the relationships.**

Cartograph is a local-first architectural intelligence engine. It derives a
symbol-level, cross-language graph of a software system from source code,
language semantics, HTTP boundaries, database schemas and Git history — and
shows the evidence behind every edge it draws.

> **Status: milestones M00–M16 accepted; M17, the public launch, in progress.**
> Version 0.1.0. One analysis core serves a CLI, a desktop application, an MCP
> server and a pull-request review workflow, with evidence on every edge.
> Nothing in this README describes behaviour the code does not have —
> see [What works today](#what-works-today).

---

## Try it

```bash
cargo install --git https://github.com/Rexy-5097/cartograph cartograph-cli
cartograph .
```

Then follow one relationship all the way down. This is real output, from
[Apache Airflow](https://github.com/apache/airflow) at commit `9b43d6a`:

```console
$ cartograph trace enqueueConnectionTest

enqueueConnectionTest  (function)  .../ui/openapi-gen/requests/services.gen.ts:834
  │
  ↓ HTTP-CALL   confidence 0.98   provenance route-matcher
  │   evidence   POST /api/v2/connections/enqueue-test matched POST /api/v2/connections/enqueue-test
  │              at .../routes/public/connections.py:383 (enqueue_connection_test);
  │              exact HTTP method; every path segment static and equal
  │
enqueue_connection_test  (function)  .../core_api/routes/public/connections.py:383
  │
  ↓ ORM-ACCESS   confidence 0.80   provenance orm-resolution
  │   evidence   ConnectionTestRequest(...) in enqueue_connection_test at .../connections.py:427
  │
ConnectionTestRequest  (class)  .../airflow/models/connection_test.py:82
  │
  ↓ QUERIES   confidence 0.80   provenance orm-resolution
  │   evidence   ConnectionTestRequest maps to table "connection_test_request"
  │
connection_test_request  (table)

This path crosses the HTTP boundary and reaches a database table.
```

A TypeScript function, an HTTP boundary, a Python handler, a SQLAlchemy model
and a database table. Four artefacts, three languages, no shared symbol table —
and every hop carries the evidence for itself.

*(Directory paths are shortened to `...` above, and the per-hop `observed`
line is omitted, so the block fits. Everything else is verbatim; run the
command to see the rest.)*

Add `--json` for the machine-readable graph.
[Installation and the full command reference](docs/releases/v0.1.0.md).

---

## The problem

Every tool in this category draws a file-level import graph and calls it
architecture. Ask one what a checkout button touches and it answers with the
files that import each other. That is a lexical fact; the question was a causal
one, and the gap between them is where production incidents live.

## What is different

Cartograph resolves relationships **across** the stack, not merely within a
language. A React component, an HTTP route, a Python handler and a database
table are four artefacts in three languages with no shared symbol table:

```
CheckoutButton.tsx  onSubmit() line 34
        │  HTTP POST /api/orders          0.94  template-eval
        ▼
POST /api/orders/{*}  (canonical)
        │  route match                    0.98  route-matcher
        ▼
orders.py  create_order() line 12
        │  ORM Order(...)                 0.97  orm-resolve
        ▼
orders — table
```

*Illustrative. The confidences above (0.94, 0.98, 0.97) belong to the synthetic
fixture in `crates/cartograph-testkit`, not to an analysed repository. Across the
seven-repository corpus M08 measured, the resolver emitted exactly seven values —
0.98, 0.90, 0.80, 0.784, 0.72, 0.65 and 0.64 — and every ORM-resolution edge
scored 0.80, as the Airflow trace above shows. See
[the M08 report](docs/benchmarks/m08-report.md).*

Doing this requires partial evaluation of dynamically constructed URLs,
normalisation across four route-declaration dialects, and ORM model
resolution — three compiler problems, none of which a GitHub API call can
answer.

### Never `A → B`

Cartograph stores the claim *and how it was known*:

```json
{
  "source": "web/src/CheckoutButton.tsx:34",
  "target": "api/orders.py:12 create_order",
  "kind": "http-call",
  "confidence": 0.94,
  "provenance": "route-matcher",
  "evidence": "POST /api/orders",
  "commit": "a3f9c21",
  "created_at": "2026-08-17T09:14:22Z"
}
```

*Also illustrative, from the same fixture. `commit` and `created_at` are not
fields of Cartograph's [JSON output](docs/architecture/json-schema.md) in any
schema version.*

Click any edge and you get its record. Competitors assert relationships;
Cartograph produces evidence for them.

### The governing principle

**Deterministic analysis first. Evidence second. Inference third. The model
last, and never in the graph.**

No language model constructs graph structure — ever. A model may explain a
subgraph after static analysis has produced it (M16). It may never propose an
edge. This is an immutable architectural principle, not a current limitation:
see [ADR-0007](docs/adr/ADR-0007-no-llm-graph-construction.md).

---

## What works today

M00 delivered the foundation, M01–M02 extraction, M03 canonicalisation, M04
the first semantic join, M05 dynamic URLs, M06 ORM resolution, M07 validation
against seven production repositories, M08 measurement of confidence and
recall, and M09 the CLI. M10–M16 built the remaining surfaces on the same core:

| Milestone | Capability |
|---|---|
| M10 | Incremental analysis — unchanged files are not reparsed and per-file ORM-access resolution is cached, with an incremental result equal to a clean one ([ADR-0014](docs/adr/ADR-0014-m10-scope-reconciliation.md)) |
| M11 | **MAP** — a desktop application (Tauri) that draws the architecture graph and shows the evidence behind any edge |
| M12 | **BLAST** — `cartograph blast`: what depends on an artefact, across language boundaries |
| M13 | **DIFF** — `cartograph diff`: what a change did to the architecture, one tree against another |
| M14 | A pull-request workflow that runs `cartograph diff --markdown` and posts the result as a comment. It is configured for this repository's own pull requests; no reusable `action.yml` is published |
| M15 | `cartograph-mcp` — an MCP server exposing `map`, `trace`, `blast` and `diff` over one repository identity granted when it is launched ([ADR-0020](docs/adr/ADR-0020-mcp-boundary-and-authorization.md)) |
| M16 | **ASK** in the desktop app — opt-in per repository, explaining already-derived evidence, with every claim required to cite that evidence verbatim ([ADR-0021](docs/adr/ADR-0021-ask-boundary-and-citation-contract.md)). No in-product way to provide an API key ships, so in practice ASK shows the evidence unexplained — the degraded path it is designed to fall back to |

| Crate | Role |
|---|---|
| `cartograph-core` | Domain model: nodes, edges, evidence, provenance and confidence |
| `cartograph-graph` | The architecture graph; `petgraph` sits underneath |
| `cartograph-parser` | tree-sitter TypeScript/TSX **and Python** extraction |
| `cartograph-resolver` | Cross-language resolution: canonical routes, HTTP boundaries, ORM models |
| `cartograph-pipeline` | Repository analysis composed once for every client |
| `cartograph-cli` | `cartograph .`, `trace`, `blast`, `diff`, `parse`, `normalize`, `match`, `version` |
| `cartograph-desktop` | Repository lifecycle and session model for the desktop application |
| `cartograph-mcp` | The MCP server |
| `cartograph-ask` | The ASK boundary: a question, derived evidence, and citations checked against it |
| `cartograph-testkit` | Test fixtures; not published, not a runtime dependency |

```console
$ cartograph match ./my-project
web/src/CheckoutButton.tsx:5  POST /api/orders
    ↓ MATCH (exact)   confidence 0.98   provenance route_matcher
      api/orders.py:6  POST /api/orders  → create_order
```

That is the chain the product exists to produce — and it is refused rather than
guessed when the evidence is thin: ambiguous candidates produce no edge, a
`${BASE}` prefix that cannot be determined statically stays `{unknown}`, and a
call to an absolute host is never joined to a local route.

`parse` reports **observed syntax** — symbols, imports, call sites, string and
template structure, HTTP-shaped calls, and (Python) route declarations — plus
structured diagnostics for files the grammar cannot fully parse. It walks
mixed `.ts`/`.tsx`/`.py` trees in one pass.

`normalize` canonicalises those observations — `/orders/:id`, `/orders/{id}`
and `/orders/<int:id>` all become the shape `/orders/{*}` — while keeping each
one's raw form and source position.

Neither command claims a resolved relationship. A route observation means "this
file declares a route that looks like this", not "this endpoint exists"; an
HTTP observation means "this file contains a call shaped like a request", not
"it reaches that handler". Canonicalisation makes the two sides *comparable*;
actually connecting them is the resolver's job, and that distinction is the
whole point of the architecture.

### Accuracy, measured

M08 labelled every edge Cartograph produced on seven pinned production
repositories — Superset, PostHog, Zulip, Onyx, Airflow, AutoGPT and the FastAPI
full-stack template — re-deriving each from source with instruments that share
no code with the analyser.

| Across all seven repositories | |
|---|---|
| Edges produced and labelled | 14,932 |
| False positives among 11,221 independently verified edges | **1** |
| Edges that could not be verified from source | **24.9%** (3,711) |
| Calibration error (ECE) | 0.18, toward **under**-confidence |

Recall was measured in **one repository, inside a stated scope**. It is not
recall across the corpus and must not be quoted as such:

| Airflow only | Scope | Recall |
|---|---|---|
| `HttpCall` | Operations its generated client declares that a route serves | 0.907 (117/129) |
| `OrmAccess` | Import-bound uses of models that declare a table | 0.744 (1401/1883) |
| End-to-end chain | Chains whose every hop is independently readable | 3 of 5 |

The 24.9% row is the important one: a quarter of the graph could not be checked,
and it is not a random quarter — it concentrates where the evidence is weakest.
Every figure above is therefore an upper bound. **Confidence values are
uncalibrated priors, not probabilities**, and must not be thresholded as if they
were.

Method and limitations: [the M08 report](docs/benchmarks/m08-report.md) and
[the confidence policy](docs/benchmarks/m08-confidence-policy.md). Every figure
above is read from the committed results in
[`benchmarks/m08/results/`](benchmarks/m08/results/).

---

## Product surfaces

Three surfaces, in build order, all delivered:

| Surface | Question | Milestone |
|---|---|---|
| **MAP** | What is this system? | M11 |
| **BLAST** | What breaks if I change this? | M12 |
| **DIFF** | What did this change do to the architecture? | M13 |

Each is downstream of the first finish line, one command against a real
repository, which M09 delivered as `cartograph .`.

Full plan: [ROADMAP.md](ROADMAP.md).

---

## Privacy

- No source code leaves the machine. Default and unconditional.
- AI is opt-in, per repository, off by default. Cartograph is fully useful with
  no API key and no network.
- Credentials live in the OS keychain, never in configuration files.
- Source contents, tokens and environment variable values are never logged.

See [SECURITY.md](SECURITY.md).

---

## Building

Requires Rust 1.97.1, pinned in `rust-toolchain.toml` and selected
automatically by `rustup`.

```bash
make check
```

That runs the same gates CI runs: formatting, clippy with warnings denied,
tests, and the AgentOS validator. Individual targets are listed by `make help`.

---

## Repository layout

```
crates/          The product. Ten Rust crates.
desktop/         The desktop application's Tauri shell and React window. No analysis lives here.
npm/             A launcher for the native binary. No analysis lives here.
benchmarks/      The M07 corpus and M08 calibration harness.
docs/            Architecture, resolver design, benchmarks, security, ADRs.
agentos/         Vendored AgentOS v1.0.0 — development governance, not product code.
.github/         CI and pull request governance.
```

`agentos/` orchestrates how this project is built (milestones, gates,
checkpoints). It is deliberately separate from the implementation and ships no
runtime code. See [AGENTOS.md](AGENTOS.md).

---

## Governance

| Document | Purpose |
|---|---|
| [PROJECT_RULES.md](PROJECT_RULES.md) | The 26 binding rules |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture |
| [ROADMAP.md](ROADMAP.md) | 17 milestones and their gates |
| [CHECKPOINTS.md](CHECKPOINTS.md) | Reproducible rollback points |
| [AGENTS.md](AGENTS.md) | Instructions for AI coding assistants |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |
| [docs/adr/](docs/adr/) | Architecture decision records |

---

## Licence

[Apache-2.0](LICENSE).

The vendored AgentOS framework under `agentos/` is MIT-licensed and retains its
own [LICENSE](agentos/LICENSE).
