# Cartograph — technical writeup

*Resolver design, benchmark results including failures, and calibration.*

Cartograph derives a cross-language architecture graph — a TypeScript call, the
HTTP route it reaches, the Python handler behind it, the model that handler
touches and the table that model maps to — from source alone, and records the
evidence for every relationship it draws. This document explains how that graph
is computed, what was measured about it, and what the measurements do not
establish.

**How this document is held to account.** Every number below is read from a
committed artifact under [`benchmarks/`](../../benchmarks/), from the source
that defines a design constant, or — for what a plan intended rather than what was
measured — from the document that set the target. The [appendix](#appendix-traceability)
maps each figure to its file and field. Where the project records a figure that
cannot be traced to a committed run, it is not used here; [§4](#4-excluded-and-unresolved-figures)
lists those exclusions and the reason for each. No target is presented as a
result, and nothing is estimated.

---

## The evidence this rests on

### One pinned corpus

Seven open-source full-stack repositories, each pinned to a commit in
[`benchmarks/corpus.json`][corpus] and analysed at its repository root, so the
scope could not be tuned against the results:

| Repository | Pinned commit | Files analysed |
|---|---|---:|
| `apache/superset` | `8222db334054` | 6,063 |
| `fastapi/full-stack-fastapi-template` | `162344da111e` | 156 |
| `onyx-dot-app/onyx` | `8ee706ebaa32` | 5,747 |
| `PostHog/posthog` | `2dd790a6e7c3` | 32,335 |
| `zulip/zulip` | `0ce8f6278cde` | 1,539 |
| `apache/airflow` | `9b43d6abc0fc` | 8,654 |
| `Significant-Gravitas/AutoGPT` | `601093ddfe23` | 3,731 |
| **Total** | | **58,225** |

The supported subset — what the resolver is meant to handle, and what it
refuses by design — was declared in
[`benchmarks/supported-subset.json`][subset] before the analyser ran against
any of these repositories: it arrived in commit `70e5ede`, an ancestor of the
first commit containing a result.

### Five runs, which are not interchangeable

Each run measured a different engine. They are reported separately throughout,
and a figure from one is never combined with a figure from another.

| Run | Engine commit | Source tree | Artifacts |
|---|---|---|---|
| M07 pass 1 | `3560874` | uncommitted changes | [measurements][p1m] |
| M07 pass 2 — **the baseline** | `3560874` | uncommitted changes | [evaluation][p2e] · [measurements][p2m] · [frozen baseline][base] |
| M07 remediation — pass 8 | `073eab7` | uncommitted changes | [evaluation][r8e] · [measurements][r8m] |
| M07 acceptance run — pass 9 | `7986348` | uncommitted changes | [evaluation][a9e] · [measurements][a9m] |
| M08 labelled dataset | `2514f77` | **clean** | [dataset][ds] and the results beside it |

Two consequences:

- **The four M07 runs were built from uncommitted source trees.** Each records
  its binary's SHA-256, so a run identifies the binary it measured, but not a
  commit that reproduces it.
- **Only the M08 results describe the accepted engine.** The dataset and the
  three calibration files are bound to `2514f77`, the `cartograph-m07`
  checkpoint, built from a clean tree. The
  acceptance run was recorded at `7986348`, the PR #10 merge, with uncommitted
  changes; the accepted commit came after two acceptance-audit pull requests,
  #12 and #13 ([CHECKPOINTS.md](../../CHECKPOINTS.md)). Its `HttpCall` count,
  1,736, sits between the remediation's 1,737 and the accepted engine's 1,735.

Re-running any of this needs the pinned repository checkouts, which are not part
of this repository; the corpus file names each one and its commit. The
committed artifacts carry `"status": "INTERNAL"`, the label their harness wrote
when they were produced; [docs/benchmarks/](../benchmarks/README.md#what-has-been-published)
explains what that label meant.

---

## 1. Resolver design

### The rule everything else follows

Deterministic analysis first, evidence second, inference third, and a language
model never in the graph ([ADR-0007](../adr/ADR-0007-no-llm-graph-construction.md)).
The domain model makes the evidence part of the type: an edge has one
constructor, and it requires provenance, a confidence, evidence and a source
location ([`edge.rs`][edge], RULES 004–006). The resolver never guesses a URL,
symbol, route, table or dependency (RULE 010), and a value it cannot determine
stays unknown rather than plausible (RULE 009).

The consequence for everything that follows: **when the evidence is not enough,
the resolver produces no edge.** Refusal is an output, and it is counted.

### The pipeline

```text
TypeScript ─► call sites, string and template structure ─► symbolic URL values ─┐
                                                                                ├─► canonical route ─► MATCH ─► HttpCall
Python ────► route declarations ─► served path (router prefixes) ───────────────┘
Python ────► model classes ─► table names ─► model uses (via imports) ─► OrmAccess, Queries
TypeScript ─► component ─► hook ─► client function (call following) ─► Call
```

Each stage is documented on its own page under [docs/resolver/](../resolver/).

### Canonical routes

Every route declaration and every client URL is reduced to one comparable shape,
per observation, without reference to any other observation
([canonical-routes.md](../resolver/canonical-routes.md)). Colon, curly and angle
parameter dialects, with or without a type converter such as `int`, all become
`{*}`; a path converter, which consumes several segments, becomes a wildcard:
`/orders/:id`, `/orders/{id}` and `/orders/<int:id>` share the shape
`/orders/{*}`.

The model keeps one distinction that a simpler normaliser would erase. A server
segment that *declares* a parameter and a client segment that *substitutes an
unknown value* are different facts — "this position accepts anything" against
"I am supplying something this analysis cannot see" — and they stay distinct
because the matcher needs both. A client URL never declares a parameter: a
client requesting the literal text `/orders/:id` is requesting that text.

### Matching

Matching is the first stage permitted to relate two observations, and the first
to create a semantic edge ([matching.md](../resolver/matching.md)).

**Candidates** are routes bucketed by segment count, with trailing-wildcard
routes held aside and consulted for every query. Method is deliberately not an
index key: an undeclared method is compatible with everything, so indexing on it
would silently drop valid candidates.

**Compatibility** is checked per position, client against server. Two static
segments must be equal. A static client segment bound into a declared parameter
is *parameter-bound*; an unknown client segment aligned with a parameter or a
static server segment is *variable-aligned*; a trailing server wildcard consumes
the rest. An undeclared method — on either side — is never read as `GET`.

**A candidate must share at least one static segment.** A route made entirely of
variable positions accepts a whole class of paths, so aligning with it says
nothing about a particular call. Such candidates are kept, visible, and never
accepted. The cost is a false negative on a genuinely parameterised root route;
the project prefers that to a false join.

**Ambiguity produces no edge.** Several equally plausible routes are an
unanswered question, and an edge is an answer:

| Classification | Meaning | Edge |
|---|---|---|
| `Exact` | one candidate; exact method; every position determined | yes |
| `Strong` | one candidate; compatible; something undetermined | yes |
| `Ambiguous` | several equally plausible candidates, or no discriminating evidence | **no** |
| `NoMatch` | no compatible route | no |
| `Unsupported` | the client is not comparable | no |

A client whose path cannot be canonicalised, whose prefix length is unknown, or
which addresses an absolute host is refused before matching.

### Confidence: a prior chosen by evidence class

A matched edge's confidence is **not** a probability. It is a prior chosen by the
kind of evidence that produced the match, defined in
[`cartograph-core`][conf] and selected in [`matching.rs`][match]:

| Path evidence | Exact method | Method undeclared on either side (× 0.8) |
|---|---:|---:|
| Every segment static and equal | 0.98 | 0.784 |
| Parameters bound to concrete client values | 0.90 | 0.72 |
| A client position undetermined | 0.80 | 0.64 |
| Matched only through a trailing wildcard | 0.65 | 0.52 |

Import resolution produces `Call` edges at 0.90, and ORM resolution produces
`OrmAccess` and `Queries` edges at 0.80. The ordering — more determined evidence
always outranks less — is enforced by test. Whether the *values* mean anything
is a calibration question, answered in [§3](#3-calibration).

### Dynamic URLs

Client URLs are often constructed rather than written out. A restricted abstract
interpretation evaluates a client URL expression into a symbolic value —
`Literal`, `Unknown`, `EnvVar`, `Unsupported` or a `Concat` of those — using
constants propagated across module scope ([dynamic-urls.md](../resolver/dynamic-urls.md)).
An environment variable is named and **never read**. An unresolved value renders
as `{unknown}`, and there is no way to flatten it into text.

### What the corpus forced the resolver to add

M07's validation against real repositories produced a negative result, and three
subsystems were added in answer to it:

- **Import resolution** ([imports.md](../resolver/imports.md)). A model name
  matched against a project-wide map cannot distinguish two classes that share a
  name — one corpus repository has a Pydantic `Document` and a SQLAlchemy
  `Document` in different modules. A use site is now resolved through its own
  import statement to a declaration, following re-exports for at most four hops
  (`MAX_REEXPORT_HOPS`, [`imports.rs`][imports-rs]).
- **Router prefix composition** ([routers.md](../resolver/routers.md)). A
  decorator states a fragment, not a served path: `@pools_router.post("")` under
  routers carrying `/pools` and `/api/v2` serves `POST /api/v2/pools`. Prefixes
  are composed through `include_router` chains, and an unknown prefix never
  becomes an empty one.
- **The client wrapper as a node** ([client-tracing.md](../resolver/client-tracing.md),
  [ADR-0012](../adr/ADR-0012-the-client-wrapper-is-a-node.md)). Only the
  innermost client function contains a URL, so an `HttpCall` edge is sourced at
  the function that issues the request, and the component and hooks above it
  connect through `Call` edges resolved by import. Call following stops after
  four hops (`MAX_CALL_HOPS`, [`client_trace.rs`][trace]); attaching a component
  directly to a handler was rejected, because no line of source states that
  relationship.

### ORM resolution

A class is a model only when the source says so: inheriting a recognised
SQLAlchemy or Django base is the evidence, and a name that looks like a model is
not ([orm.md](../resolver/orm.md)). Only module-scope classes count. A table name
comes from `__tablename__`, `db_table` or a shared declarative base; a table name
that is not a literal is refused rather than invented.

### What the resolver does not do

TypeScript, TSX and Python only. Class-based views and DRF routers, SQLModel,
`session.query(Model)` and `select(Model)`, deployment-time URL rewrites and
project-local prefix helpers are outside what it resolves — each is listed below
as an unsolved finding rather than hidden.

---

## 2. Benchmark results

### Method

The benchmark was built to resist its own author:

- **The scope was declared before measuring**, in
  [`supported-subset.json`][subset], so a miss could not be reclassified as out
  of scope afterwards.
- **Ground truth is independent of the analyser.** It is drafted from source by
  instruments that cannot import the analyser and never read its output.
- **Measuring and scoring are separate.** `run_benchmark.py` measures,
  `evaluate.py` scores, and the evaluator refuses results whose corpus, ground
  truth or supported subset do not match the digests recorded with them.
- **The benchmark attacks itself.** Every evaluation runs adversarial checks
  against the ways its numbers could be flattered, and records whether each was
  detected.

### M07: from a negative finding to the accepted engine

The same corpus, three engines. Each column is one run's
[evaluation](#five-runs-which-are-not-interchangeable).

| | Baseline — pass 2 | Remediation — pass 8 | Acceptance run — pass 9 |
|---|---:|---:|---:|
| Route extraction — true positives, false positives, false negatives | 101 · 0 · 0 | 101 · 0 · 0 | 101 · 0 · 0 |
| `Queries` — true positives, false positives, false negatives | 48 · 0 · 0 | 48 · 0 · 0 | 48 · 0 · 0 |
| `Queries` edges produced / confirmed against source | 290 / 290 | 290 / 290 | 290 / 290 |
| `OrmAccess` edges produced | 11,843 | 11,464 | 11,464 |
| … whose access-site name could not be tied to the model | 286 | 126 | 126 |
| `HttpCall` edges produced | 1,458 | 1,737 | 1,736 |
| Chains fully verified, request issuer to table | 6 | 11 | 11 |
| Decisions classified ambiguous — no edge | 1,886 | 1,544 | 1,544 |
| `must_not_produce` assertions violated | 0 of 13 | 0 of 13 | 0 of 13 |
| Adversarial checks detected | 10 of 10 | 10 of 10 | 10 of 10 |

Route extraction and model-to-table resolution held precision and recall at
1.000 on their in-scope ground truth in every run. The remediation is visible as
a subtraction: 379 `OrmAccess` edges were **removed** — every one the
remediation sampled was a symbol that merely shared a model's name — and the
unconfirmed remainder fell from 286 to 126.

**The chains, and what the artifacts do not record.** A chain here runs from the
function that issues a request — a client operation, a test, or a command-line
client — through a handler and a model to a table, every hop traversed through
shared graph nodes. The baseline's six began in a Python test file, an Airflow
command-line client and an Onyx integration test: none in a frontend. After
remediation the acceptance run verified eleven: ten in Airflow, one in Onyx.

M07's acceptance criterion went one step further — chains beginning in a
hand-written React component and reaching the client function through `Call`
edges, as in this path recorded by the remediation report
([m07-remediation.md](../benchmarks/m07-remediation.md)):

```text
ParseDagButton.tsx ─call─► useDagParsing ─call─► queries.ts ─call─► services.gen.ts
  ─http-call─► reparse_dag_file ─orm-access─► DagPriorityParsingRequest
  ─queries─► dag_priority_parsing_request
```

The committed evaluations record the chain from the client function onward,
not the `Call` edges above it; those were traversed on the raw analysis graphs,
which live with the corpus checkouts and are not committed. How many such
component-rooted chains exist is therefore **not traceable to a committed run**,
and this document does not state a count. See [§4](#4-excluded-and-unresolved-figures).

### M08: every edge the accepted engine produced, labelled

M08 labelled every edge produced by the accepted engine, re-deriving each from
source with instruments that share no code with the analyser
([dataset][ds]). An edge is *verified* when that reading decides it, and
*unverifiable* when it cannot — a name bound by a star import, a client URL the
source does not fix, a re-export the reader does not follow.

| Relationship | Produced | Verified | True | False | Unverifiable |
|---|---:|---:|---:|---:|---:|
| `Call` | 1,443 | 766 | 766 | 0 | 677 (46.9%) |
| `HttpCall` | 1,735 | 881 | 881 | 0 | 854 (49.2%) |
| `OrmAccess` | 11,464 | 9,284 | 9,283 | 1 | 2,180 (19.0%) |
| `Queries` | 290 | 290 | 290 | 0 | 0 |
| **All** | **14,932** | **11,221** | **11,220** | **1** | **3,711 (24.9%)** |

Observed accuracy over the verified edges is 0.9999, with a 95% interval of
0.9995 to 1.0 ([calibration-all][call]).

**The row that governs every other is the last column.** A quarter of the graph
could not be decided from source, and it is not a random quarter: an edge is
unverifiable for the same reasons it is weak. For the cross-language class,
`HttpCall`, it is almost half. Every accuracy figure above is measured on the
more tractable part of the corpus and is an upper bound on accuracy over all of
it.

The edges are unevenly spread — 7,872 in PostHog, 3,350 in Airflow, 1,469 in
Zulip, 1,076 in Onyx, 663 in Superset, 501 in AutoGPT, and **1** in the FastAPI
full-stack template ([dataset][ds], `counts.per_repository`).

### Recall: one repository, inside a stated scope

M07 left recall unmeasured, because counting what was missed needs an
independent list of what should have been found. M08 built that list for three
populations, all in Airflow ([recall-airflow][rec]):

| Class | Scope | Expected | Recovered | Recall |
|---|---|---:|---:|---:|
| `HttpCall` | operations declared by the generated client that a route serves | 129 | 117 | 0.907 |
| `OrmAccess` | import-bound constructor and manager uses of models that declare a table | 1,883 | 1,401 | 0.744 |
| End-to-end chain | chains whose client operation, route, handler and model are all independently readable | 5 | 3 | 3 of 5 |

**This is not recall across the corpus and must not be quoted as such.** The
generated client declares 177 operations, of which 48 have no route serving them
and are excluded. The chain denominator is five, too small to support a rate.
No other repository has a recall denominator.

Unlike the dataset, the recall file records no engine commit. Its 117 recovered
operations do match the dataset, which is bound to the accepted engine: the
dataset holds 117 `HttpCall` edges from that same generated client, all verified
true.

### Failures

Recorded as findings, not explained away.

1. **A quarter of the graph is unverifiable** — 24.9% overall and 49.2% of
   `HttpCall`. This bounds everything above.
2. **One false positive remains, deliberately.** An `OrmAccess` edge at 0.80 in a
   PostHog test file, where a local declaration shadows a real model
   ([dataset][ds], edge 4173). M08 measured it rather than patching it.
3. **The baseline's chains rested on an unsound step.** Every one depended on
   model names resolved without consulting imports, which the remediation found
   unsound and replaced; none began at a frontend. The 379 removed `OrmAccess`
   edges are the measurable part of that correction.
4. **Recall has misses with named causes.** Twelve generated-client operations
   were not recovered. Both missed chains, `patch_pool` and `get_pools`, route
   through `{pool_name:path}`, a path converter that consumes several segments,
   which a single-segment client does not align with. 482 import-bound model
   uses were not recovered.
5. **One repository produced a single edge.** The FastAPI full-stack template
   uses SQLModel, which is out of scope, and composes its routers through an
   attribute — `include_router(items.router)` — which router resolution does not
   follow.
6. **Still not solved**, as the remediation report lists them
   ([m07-remediation.md](../benchmarks/m07-remediation.md)): a frontend prefix
   added by a deployment-time rewrite (Onyx); a global prefix applied by a
   project-local helper (Onyx); Django chains broken between the URL-conf file
   and the view file; access sites bound through star or conditional imports;
   class-based views and DRF routers, which carry most of PostHog's and
   Superset's API; `session.query(Model)` and `select(Model)`; operations that
   Airflow's generated client declares twice under different service names,
   each pair collapsed into one node; and no corpus-wide recall denominator for
   any class.
7. **The benchmark this was meant to be was not built.** See below.

### CrossStack-Bench and Gate 2

The plan for M08 was CrossStack-Bench: 10–15 full-stack repositories, ~500
hand-labelled cross-language edges, precision, recall and F1, and a hard gate —
if F1 fell below 0.70, publish the benchmark standalone and reassess the research
direction rather than declare the resolver solved
([ROADMAP.md](../../ROADMAP.md), Gate 2).

**CrossStack-Bench was not built, and Gate 2 is unevaluated: it has neither
passed nor failed.** What M08 built instead was the per-edge labelling above. The
gate cannot be evaluated from it, because the population the gate is defined on
was never assembled: there is no ~500-edge cross-language corpus, cross-language
recall exists for one generated client in one repository, and almost half of
all `HttpCall` edges are unverifiable. An F1 can be computed for that one generated
client, where precision and recall were both measured; it describes a single
generated client, it is not the gate's measurement, and it is not reported here.
M08's own acceptance criterion asked for F1 to be published; M08 was accepted as
a measurement baseline, and its acceptance record does not mention F1
([benchmark index](../benchmarks/README.md#gate-2-was-not-evaluated-as-specified)).

### Performance — a record, not a claim

The only committed performance records are the four M07 runs' measurements. Each
is a single run, recorded on the same platform (`Darwin 25.5.0 arm64`) and built
from an uncommitted tree; passes 1 and 2 share a commit but not a binary. They
describe what those binaries did, not what Cartograph will do.

| Run | Wall time, all seven repositories | Peak RSS (PostHog) |
|---|---:|---:|
| M07 pass 1 | 51.7 s | 825 MB |
| M07 pass 2 — baseline | 68.4 s | 825 MB |
| M07 remediation — pass 8 | 75.8 s | 965 MB |
| M07 acceptance run — pass 9 | 75.6 s | 964 MB |

Memory grows with repository size because the whole analysis is held in memory
at once. No other performance figure in the project has a committed run behind
it; [§4](#4-excluded-and-unresolved-figures) lists them.

---

## 3. Calibration

### What a confidence number is

An **uncalibrated prior selected by evidence class**. Across the 14,932 edges of
the accepted engine there are exactly seven distinct values, and grouping edges
by value is the same partition as grouping them by evidence
([calibration-all][call]):

| Value | Produced by | Produced | Verified | True | False |
|---:|---|---:|---:|---:|---:|
| 0.98 | route match: every segment static and equal | 680 | 544 | 544 | 0 |
| 0.90 | import resolution (1,443); route match, parameters bound (294) | 1,737 | 1,039 | 1,039 | 0 |
| 0.80 | ORM resolution (11,754); route match, a position undetermined (56) | 11,810 | 9,630 | 9,629 | 1 |
| 0.784 | route match, static, method undeclared | 416 | 0 | 0 | 0 |
| 0.72 | route match, parameters bound, method undeclared | 63 | 0 | 0 | 0 |
| 0.65 | route match through a trailing wildcard | 8 | 8 | 8 | 0 |
| 0.64 | route match, a position undetermined, method undeclared | 218 | 0 | 0 | 0 |

The "produced by" column follows the selection in [`matching.rs`][match] and
agrees with the relationship classes recorded per value in the
[dataset][ds]. 11,810 edges — 79.1% — sit at exactly 0.80.

### Calibration error

Edges are split into development and holdout by a hash of each edge's identity,
not its label: SHA-256 of salt, repository, kind, location and edge id, modulo
4, with bucket 0 held out ([integrity][int]). That gives 11,153 development and
3,779 holdout edges, of which 8,391 and 2,830 are verified.

| | Development | Holdout |
|---|---:|---:|
| Verified edges | 8,391 | 2,830 |
| Expected calibration error | 0.1819 | 0.1825 |
| Maximum calibration error | 0.35 | 0.35 |

([development][cdev], [holdout][chold].) The two splits agree.

**The error is entirely under-confidence.** The three values with an adequate
sample — 0.98, 0.90 and 0.80 — are right on essentially every verified edge, so
each understates its own accuracy. **Over-confidence is unmeasured**, not
absent: the three values at 0.784, 0.72 and 0.64 — 697 edges — have no verified
observation at all, and 0.65 has eight, too few to estimate from. An ECE over seven discrete points
inherits those gaps; a ten-bin reliability diagram has six empty bins, and one
bin holds 79.1% of the corpus.

### Thresholds

Precision moves only when a threshold removes a whole evidence class
([calibration-all][call], `thresholds`):

| Thresholds recorded | Verified edges kept | Precision |
|---|---:|---:|
| 0.0, 0.6, 0.65 | 11,221 | 0.9999 |
| 0.7, 0.75, 0.784, 0.8 | 11,213 | 0.9999 |
| 0.85, 0.9 | 1,583 | 1.0 |
| 0.95, 0.98 | 544 | 1.0 |
| 0.99 | 0 | — |

The single false positive is at 0.80, so every threshold up to 0.80 keeps it,
and going above 0.80 removes it only by removing all 9,630 verified edges at
that value. Moving the threshold from 0.65 to 0.7 removes only the eight
verified edges at 0.65.

### What was planned, and what was done

The plan was a fitted calibration: a feature vector per candidate edge — path
match, method match, template arity, handler-name similarity, parameter overlap,
git co-change, directory proximity, OpenAPI confirmation — fitted by logistic
regression against the labelled set. **No model was fitted**, and no harness in
`benchmarks/` contains one. No production confidence or threshold changed.

What M08 established instead is narrower: the values
are discrete priors; they understate accuracy where accuracy can be measured;
and where the evidence is weakest, accuracy cannot be measured from source at
all. The [confidence policy](../benchmarks/m08-confidence-policy.md) draws the
practical rule: do not raise confidence to match observed accuracy, because that
fits a filtered subset; do not lower the threshold, because it gains nothing;
treat the lowest band as display-only; and never threshold a confidence as if
it were a probability.

---

## 4. Excluded and unresolved figures

These appear in project documents but are **not** used above, because no
committed run supports them. They are not withdrawn as false; they are withheld
because they cannot be traced.

| Figure as recorded | Where | Why it is excluded |
|---|---|---|
| Chains beginning in a hand-written component — "four" at acceptance; "six", of "24 complete chains", after remediation | [CHECKPOINTS.md](../../CHECKPOINTS.md), [m07-remediation.md](../benchmarks/m07-remediation.md), ledger | Traversed on the raw analysis graphs, which are not committed. The committed evaluations record eleven chains from the client function onward |
| "Five of the six" baseline chains false | [CHANGELOG.md](../../CHANGELOG.md), m07-remediation.md | No committed artifact records which baseline chains failed |
| "Twelve" `HttpCall` edges with a TypeScript client, at baseline | [client-tracing.md](../resolver/client-tracing.md) | No artifact field records it |
| "138 false edges from a single route" | [matching.md](../resolver/matching.md) | Observed during development; no committed run |
| v0.1.0 wall times and peak memory, including PostHog 64.42 s and 920 MB | [v0.1.0 release notes](../releases/v0.1.0.md) | From a single run of which no record was committed |
| "~100 s, peak RSS 860 MB" for M07, and "~4 minutes" of labelling | [m08-report.md](../benchmarks/m08-report.md) | Match no committed run |
| Airflow 267.6 s cold and 31.7 s warm | CHECKPOINTS.md (M15) | No committed run |
| Incremental-analysis speed-ups and timings | [incremental-engine.md](../development/incremental-engine.md) | Measured on one machine; outputs not committed |
| Renderer frame times | [m11-renderer.md](../benchmarks/m11-renderer.md) | One measurement on one machine; no committed artifact |
| Confidences 0.94 and 0.97 | [README.md](../../README.md) diagram, [docs/resolver/README.md](../resolver/README.md) | A synthetic test fixture's values; the resolver cannot produce them |

---

## Appendix: traceability

Every figure in this document, its source, and how it is obtained. Paths are
relative to [`benchmarks/`](../../benchmarks/) unless they name a source file.

### Corpus and runs

| Figure | Source | Field or calculation |
|---|---|---|
| Seven repositories, pinned commits | [corpus.json][corpus] | `repositories[].repository`, `.commit` |
| Files per repository; 58,225 total | [acceptance measurements][a9m] | `repositories[].measurements.files_analysed`; identical in every M07 run |
| Engine commits, clean or not | each run's measurements; [dataset][ds] | `toolchain.cartograph_commit`, `.cartograph_tree_clean`; `bound_to.cartograph_commit`, `.cartograph_tree_clean` |
| Machine | each run's measurements | `toolchain.os` |
| `HttpCall` 1,737 → 1,736 → 1,735 | [r8e]; [a9e]; [calibration-all][call] | `sum(repositories.*.http_call.produced)`; `by_relationship_class.http-call.produced` |
| Subset declared before results | git history | `70e5ede` is an ancestor of the first commit under `benchmarks/results/` |
| Which M08 results are bound | [dataset][ds]; [calibration files][call] | `bound_to.cartograph_commit` present in each; absent from [recall-airflow][rec] |

### M07 runs

| Figure | Source | Field or calculation |
|---|---|---|
| Route TP · FP · FN | [p2e] · [r8e] · [a9e] | `sum(repositories.*.routes.metrics.{tp,fp,fn})` |
| `Queries` TP · FP · FN | same | `sum(repositories.*.queries.metrics.{tp,fp,fn})` |
| `Queries` produced / confirmed | same | `sum(.queries.produced)`, `sum(.queries.source_confirmed)` |
| `OrmAccess` produced | same | `sum(.orm_access.produced)` |
| `OrmAccess` unconfirmed: 286 · 126 · 126 | same | `sum(.orm_access.wrong_symbol_count)` — the access-site name is not bound to the model in that file |
| 379 removed | [p2e], [r8e] | 11,843 − 11,464 |
| `HttpCall` produced | same | `sum(.http_call.produced)` |
| Chains: 6 · 11 · 11; ten Airflow, one Onyx | same | `sum(.chains.fully_verified)`; per repository; issuers from `.chains.chains[].frontend` |
| `must_not_produce`: 0 of 13 | same | `len` and `violated` over `.must_not_produce[]` |
| Adversarial checks: 10 of 10 | same | `adversarial_checks[].detected` |
| Ambiguous: 1,886 · 1,544 · 1,544 | [p2m] · [r8m] · [a9m] | `sum(repositories[].measurements.decisions.ambiguous)` |
| Wall time 51.7 · 68.4 · 75.8 · 75.6 s | [p1m] · [p2m] · [r8m] · [a9m] | `sum(repositories[].performance.wall_seconds)` |
| Peak RSS 825 · 825 · 965 · 964 MB | same | PostHog `performance.peak_rss_bytes` ÷ 10⁶ |

### M08

| Figure | Source | Field or calculation |
|---|---|---|
| 14,932 edges; 11,220 true, 1 false, 3,711 unverifiable | [dataset][ds] | `counts.edges`, `counts.per_label` |
| Per repository | [dataset][ds] | `counts.per_repository` |
| Per relationship class | [calibration-all][call] | `by_relationship_class.*` |
| Unverifiable shares 46.9% · 49.2% · 19.0% · 24.9% | [calibration-all][call] | `.unverifiable_share`: 677/1,443, 854/1,735, 2,180/11,464, 3,711/14,932 |
| 0.9999, interval 0.9995–1.0 | [calibration-all][call] | `overall.observed_accuracy`, `overall.ci95` |
| The false positive | [dataset][ds] | the record labelled `FALSE_POSITIVE` (edge 4173) |
| Recall: 117/129, 1,401/1,883, 3 of 5; 12 and 482 missed; 177 declared, 48 unserved | [recall-airflow][rec] | `*.recovered`, `.expected` or `.operations_a_route_serves`, `.missed`, `.operations_declared`, `.operations_no_route_serves` |
| Missed chains `patch_pool`, `get_pools` | [recall-airflow][rec] | `chain_recall.missed_examples[].handler` |
| 117 generated-client `HttpCall` edges in the dataset, all true | [dataset][ds] | records with `repository` airflow, `kind` http-call, `at` in `openapi-gen/requests/services.gen.ts` |
| Seven values; produced, verified, true, false per value | [calibration-all][call] | `by_confidence_value.*` |
| Per-value relationship classes (1,443; 294; 11,754; 56) | [dataset][ds] | records grouped by `confidence` and `kind` |
| 79.1% at 0.80 | [calibration-all][call] | 11,810 / 14,932 |
| 697 edges with no verified observation | [calibration-all][call] | 416 + 63 + 218 |
| Adequate sample: 0.98, 0.90, 0.80 only | [calibration-all][call] | `by_confidence_value.*.sample_adequate` |
| 9,630 verified at 0.80 | [calibration-all][call] | `by_confidence_value.0.8.verified`; equals 11,213 − 1,583 in `thresholds` |
| Split: 11,153 and 3,779; method | [dataset][ds]; [integrity][int] | `counts.per_split`; the holdout-split check's `method` |
| Verified per split: 8,391 and 2,830 | [development][cdev]; [holdout][chold] | `calibration_error.verified` |
| ECE 0.1819 · 0.1825; MCE 0.35 | [development][cdev]; [holdout][chold] | `calibration_error.ece`, `.mce` |
| Six of ten bins empty | [calibration-all][call] | `reliability_bins.*.produced == 0` |
| Thresholds | [calibration-all][call] | `thresholds[]` |

### Plan targets

| Figure | Source |
|---|---|
| CrossStack-Bench: 10–15 repositories, ~500 hand-labelled cross-language edges | [M08 definition](../../agentos/milestones/M08-benchmark-calibration.md) |
| Gate 2 threshold, F1 < 0.70 | [ROADMAP.md](../../ROADMAP.md), Gate 2; the M08 definition |

### Design constants

| Figure | Source |
|---|---|
| Priors 0.98, 0.90, 0.80, 0.65 | [`confidence.rs`][conf] — `ROUTE_METHOD_EXACT`, `STATIC_IMPORT`, `CONSTANT_PROPAGATION`, `PARTIAL_TEMPLATE_MATCH`; mapped in [`matching.rs`][match] `priors` |
| × 0.8, and 0.784, 0.72, 0.64, 0.52 | [`matching.rs`][match] — `UNDECLARED_METHOD_FACTOR`, applied in `confidence_for` |
| Four call hops | [`client_trace.rs`][trace] — `MAX_CALL_HOPS` |
| Four re-export hops | [`imports.rs`][imports-rs] — `MAX_REEXPORT_HOPS` |

[corpus]: ../../benchmarks/corpus.json
[subset]: ../../benchmarks/supported-subset.json
[p1m]: ../../benchmarks/results/m07-pass1-measurements.json
[p2e]: ../../benchmarks/results/m07-pass2-evaluation.json
[p2m]: ../../benchmarks/results/m07-pass2-measurements.json
[base]: ../../benchmarks/remediation/baseline.json
[r8e]: ../../benchmarks/remediation/final-evaluation.json
[r8m]: ../../benchmarks/remediation/final-measurements.json
[a9e]: ../../benchmarks/acceptance/m07-acceptance-evaluation.json
[a9m]: ../../benchmarks/acceptance/m07-acceptance-measurements.json
[ds]: ../../benchmarks/m08/results/dataset.json
[call]: ../../benchmarks/m08/results/calibration-all.json
[cdev]: ../../benchmarks/m08/results/calibration-development.json
[chold]: ../../benchmarks/m08/results/calibration-holdout.json
[rec]: ../../benchmarks/m08/results/recall-airflow.json
[int]: ../../benchmarks/m08/results/integrity.json
[conf]: ../../crates/cartograph-core/src/confidence.rs
[match]: ../../crates/cartograph-resolver/src/matching.rs
[trace]: ../../crates/cartograph-resolver/src/client_trace.rs
[imports-rs]: ../../crates/cartograph-resolver/src/imports.rs
[edge]: ../../crates/cartograph-core/src/edge.rs
