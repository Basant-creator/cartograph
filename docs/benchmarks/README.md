# Benchmarks

This page defines the standard a number has to meet before it is published,
and records what has been published so far.

## What has been published

Everything in this repository is publicly readable, so "internal" here has
never meant hidden. It marks figures whose methodology was first-generation:
recorded in project documents — this page, [CHANGELOG.md](../../CHANGELOG.md),
the milestone reports and the ledger — but not offered as headline claims.

| Figures | In project documents | As headline claims |
|---|---|---|
| M07 accuracy — route and query precision and recall, chain counts | since M07 (`2c8500e`) | never |
| M08 accuracy — false positives, ECE, unverifiable share, scoped recall | since M08 (`37288f8`) | since v0.1.0 (`0d567da`), in [README.md](../../README.md) and the [v0.1.0 release notes](../releases/v0.1.0.md) |

The v0.1.0 release notes also give per-repository file counts, wall times and
peak memory. The file counts match every committed M07 run; the wall times and
memory come from a run of which no record was committed, as a correction note
there explains.

Until M17 this section read "Nothing is published … none of them may be quoted
outside the project". That was not accurate even when written: the same commit,
`2c8500e`, recorded M07 figures on this page and in the changelog. The committed
artifacts under `benchmarks/` still carry `"status": "INTERNAL"`, the label
their harness wrote when they were produced. They are bound by digest to their
inputs, so they are not rewritten.

## Publishing standard

A number appears in public material only if it was produced by a benchmark run
on this codebase, with the harness and inputs available. Failures are published
alongside successes. "87.2% precision, 81.4% recall across ten repositories,
ECE 0.04" is the *shape* of claim this project makes — with real values or not
at all.

## Performance targets (targets, not results)

| Scenario | v1 | Later |
|---|---|---|
| 10k files, initial analysis | < 60 s | < 10 s warm |
| Normal file change, incremental | < 250 ms | < 100 ms |
| Rendering | 10k nodes @ 60 FPS | 50k / 100k / 200k benchmarked |

Criterion harness exists from M00 (`cargo bench`, graph construction +
traversal) so M10 has a baseline; its numbers are internal until methodology is
documented.

## What M07 measured

Seven pinned repositories, 58,225 files, ground truth authored from source by
an instrument with no access to analyser output, two full passes, and eleven
attacks on the benchmark's own machinery. Route extraction and model-to-table
resolution reached precision 1.000 and recall 1.000 on their in-scope ground
truth. The baseline verified six chains end to end, none beginning at a frontend
file; five of those six were later shown to be false
([m07-remediation.md](m07-remediation.md)). After remediation M07 was accepted
with four genuine frontend-originating chains, all in Airflow
([CHECKPOINTS.md](../../CHECKPOINTS.md)). M07 left `HttpCall`, `OrmAccess` and
chain recall unmeasured; M08 measured each inside a stated scope in Airflow
([m08-report.md](m08-report.md)).

Harness: `benchmarks/run_benchmark.py` measures, `benchmarks/evaluate.py`
scores, and the two never share a judgement — a change to one cannot alter what
the other recorded.

On Windows, the accepted engine produces the same 14,932 edges as the M08
dataset records from macOS, in all seven repositories
([cross-platform-parity.md](cross-platform-parity.md)).

## CrossStack-Bench (planned at M08, not built)

The M08 plan was 10–15 real full-stack repositories, ~500 manually labelled
cross-language edges, a scoring harness, a public leaderboard and published
failure cases, scored by precision, recall, F1, expected calibration error and
reliability diagrams, alongside golden fixtures (small synthetic repos with
expected graphs) in CI.

What M08 built instead was a per-edge labelling of the seven-repository M07
corpus: 14,932 edges re-derived from source, with recall measured inside stated
scopes in Airflow ([m08-report.md](m08-report.md)). The ~500-edge cross-language
corpus, the leaderboard and an F1 were not produced.

### Gate 2 was not evaluated as specified

The plan set a hard gate: if F1 < 0.70 at M08, publish the benchmark standalone
and reassess the research direction rather than declare the resolver solved
([ROADMAP.md](../../ROADMAP.md), Gate 2). M08's own acceptance criterion
required precision, recall and F1 to be published with failures
([M08 definition](../../agentos/milestones/M08-benchmark-calibration.md)). M08
was accepted on 2026-08-22 as a measurement baseline; its acceptance record
lists what was delivered and does not mention CrossStack-Bench or F1.

The gate cannot be evaluated from what exists, because the population it is
defined on was never assembled:

- **No CrossStack-Bench corpus.** The ~500 hand-labelled cross-language edges
  across 10–15 repositories do not exist.
- **No cross-language recall beyond one client.** `HttpCall` recall was measured
  only for Airflow's generated client; the other six repositories have no recall
  denominator.
- **Half the cross-language edges are unverifiable.** 854 of the 1,735
  `http-call` edges M08 labelled (49.2%) could not be decided from source, so
  precision for that class is an upper bound.

An F1 can be computed for the one scope where precision and recall were both
measured, Airflow's generated client. That is a diagnostic of a single
generated client, not the gate's measurement, and it is not a substitute for
one. **Gate 2 is unevaluated: it has neither passed nor failed.**

## Calibration (planned at M08, not fitted)

The plan was a feature vector per candidate edge — exact path match, method
match, template arity, handler-name similarity, parameter overlap, git
co-change, directory proximity, OpenAPI confirmation — fitted by logistic
regression against the labelled set, so that an edge marked 0.8 is correct 80%
of the time.

No model was fitted, and no harness in `benchmarks/` contains one. M08 instead
measured the calibration of the confidences the resolver already emits. They
are seven discrete values selected by evidence class, not probabilities. ECE is
0.1819 on the development split and 0.1825 on the holdout, MCE 0.35, all in the
direction of under-confidence. Overconfidence is unmeasured, because the lowest
bands have almost no verified observations. No production confidence or
threshold changed. See [m08-report.md](m08-report.md) and
[m08-confidence-policy.md](m08-confidence-policy.md).
