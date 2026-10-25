# Gate 2: what a valid evaluation requires

**Status: unevaluated.** CrossStack-Bench Gate 2 has neither passed nor failed.
This page records why it still cannot be evaluated, what is missing, and what
would have to be decided and built first. It does not change the gate, and it
proposes no threshold, population or result.

## What the gate is

[ROADMAP.md](../../ROADMAP.md), Gate 2: *"M08 cross-stack F1 below 0.70 …
Publish CrossStack-Bench as a standalone contribution, publish the failures,
and stop."* The [M08 definition](../../agentos/milestones/M08-benchmark-calibration.md)
gives the population: *"CrossStack-Bench (10–15 real repos, ~500 hand-labelled
cross-language edges, scoring harness)"*, and the condition: *"if F1 < 0.70,
publish the benchmark standalone and reassess."*

The gate therefore needs three things: a population of about 500 hand-labelled
cross-language edges across 10 to 15 repositories, a precision and a recall
over that population, and the F1 that combines them.

## What exists, measured

| The gate requires | What the repository has | Source |
|---|---|---|
| 10–15 real repositories | **7**, the M07 corpus | [`corpus.json`](../../benchmarks/corpus.json) |
| ~500 **hand-labelled** cross-language edges | 1,735 `http-call` edges labelled **mechanically**, by an instrument that re-derives each edge from source: 881 true positives, 0 false positives, **854 unverifiable (49.2%)** | [`m08/results/dataset.json`](../../benchmarks/m08/results/dataset.json), produced by [`m08/label_edges.py`](../../benchmarks/m08/label_edges.py) |
| Precision over the population | an upper bound only: half the `http-call` edges could not be decided from source, and Superset's 15 and Zulip's 11 are all unverifiable | same |
| Recall over the population | **one scope**: Airflow's generated client, 117 of 129 (0.907). The other six repositories have no `HttpCall` recall denominator | [`m08/results/recall-airflow.json`](../../benchmarks/m08/results/recall-airflow.json), [m08-report.md](m08-report.md#recall--the-gaps-m07-left-open) |
| A cross-stack F1 | none | — |

An F1 can be computed for Airflow's generated client, the one scope where both
precision and recall were measured. That measures a single generated client in
a single repository. It is not the gate's measurement and must not be reported
as one.

## Why it cannot be evaluated from what exists

1. **The population was never assembled.** There are seven repositories, not
   10–15, and no hand-labelled edge set of any size.
2. **There is no recall outside one scope.** F1 needs recall, and recall needs a
   denominator: every true cross-language relationship in the population,
   including the ones Cartograph does not produce. Outside Airflow's generated
   client no such denominator exists.
3. **The protocol is not written down.** The gate names a population and a
   metric but not how to build or score them. Each of the decisions below
   changes the F1, so making any of them after seeing results would decide
   the gate's outcome.
4. **Labels must be independent of the analyser.** The benchmark's own rule
   ([benchmarks/README.md](../../benchmarks/README.md)) is that ground truth
   comes from an instrument that *"cannot import the analyser and never reads
   its output"*. "Hand-labelled" adds a person reading source. Labels written by
   anyone, or anything, that has worked on the analyser and read its output do
   not meet that bar. That includes an AI assistant that has done exactly that
   work, so none were produced in preparing this page.

## Decisions an evaluation needs first

These belong to the project owner, and must be recorded, committed, before any
labelling or measurement:

| Decision | Why it changes the result |
|---|---|
| **Which relationships count as cross-stack.** `HttpCall` alone, `HttpCall` plus the `Call` edges into a client wrapper, or end-to-end chains from issuer to table | Each has a different population and a different miss rate. M08 measured `HttpCall` recall at 0.907 and chain recall at 3 of 5 in the same repository |
| **The unit and the average.** Per edge or per chain; pooled across repositories, or per repository and then averaged | A pooled F1 is dominated by the largest repository. PostHog alone holds 910 of the corpus's 1,735 `HttpCall` edges |
| **How an unverifiable label scores.** Excluded, counted against precision, or resolved by a second labeller | 49.2% of the existing `http-call` labels are unverifiable, so this choice alone can move precision by tens of points |
| **The additional repositories.** Three to eight more, chosen by criteria stated before measuring, and pinned to commits | The M07 corpus was chosen partly for patterns known to be out of scope ([m07-report.md](m07-report.md)) |
| **Sample or census, and how many labellers.** About 500 edges sampled how, and labelled once or twice with an adjudication rule | A single labeller's error rate is unmeasured |
| **How the recall denominator is built.** Every client call site enumerated from source, with its true target found by reading the code, whether or not Cartograph produced an edge for it | Without it there is no recall and so no F1 |
| **Which engine is scored.** The accepted M07 engine, or the engine at the commit the evaluation runs | The engine's code has changed since M08, so the result belongs to a commit, and the protocol has to name it |
| **How the threshold is read.** A point estimate against 0.70, or an interval | At 500 edges, a proportion of 0.70 has a 95% Wilson interval of about 0.66 to 0.74, which straddles the threshold |

## What can be reused

The machinery exists. What does not exist is a population built under a
protocol:

- [`benchmarks/corpus.json`](../../benchmarks/corpus.json) pins repositories to
  commits. A larger corpus extends it, or sits beside it.
- [`enumerate_source.py`](../../benchmarks/enumerate_source.py) and
  [`enumerate_models.py`](../../benchmarks/enumerate_models.py) enumerate route
  declarations, client calls and models from source without the analyser. They
  are the starting point for a recall denominator, which is the missing half.
- [`draft_ground_truth.py`](../../benchmarks/draft_ground_truth.py) drafts
  records for review, and the ground-truth schema already distinguishes in
  scope, out of scope, safe refusal and ambiguous.
- [`run_benchmark.py`](../../benchmarks/run_benchmark.py) measures, and
  [`evaluate.py`](../../benchmarks/evaluate.py) scores against committed ground
  truth only and records adversarial checks.
- [`m08/recall.py`](../../benchmarks/m08/recall.py) shows how a recall
  denominator was built inside one scope.

No F1 computation exists in the scorer today. Adding one is part of the
evaluation, after the decisions above are made, not before.

## Next steps, in order

1. The owner decides, and commits, each row of the table above. That file is
   the protocol.
2. The additional repositories are chosen by the recorded criteria and pinned.
3. Recall denominators are built from source, independently of the analyser,
   and committed before any measurement.
4. The edges are labelled under the recorded procedure, by labellers who have
   not seen the analyser's output, and committed.
5. The engine named in the protocol is measured with `run_benchmark.py`.
6. The scorer gains the protocol's F1, and `evaluate.py` scores the run against
   the committed labels, failures included.
7. The gate is read against 0.70 as the protocol says, and the result is
   published whichever way it falls. Below 0.70, the roadmap's instruction
   applies: publish the benchmark standalone, and stop.

Until step 7 has been done, Gate 2 is **unevaluated**.
