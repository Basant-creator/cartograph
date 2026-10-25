# Real-repository benchmark

The M07 harness. Standard library only, matching the project's gate scripts —
benchmarking added no dependency.

| File | Role |
|---|---|
| `corpus.json` | Seven repositories at exact commits, with the scope and known limitations of each |
| `supported-subset.json` | What counts as in scope, out of scope, a required refusal, and a predicted implementation gap. Committed **before** the first measurement |
| `enumerate_source.py` | Finds route declarations and client calls by regex over text. Describes the frameworks, not the analyser, and over-approximates on purpose |
| `enumerate_models.py` | Finds ORM model declarations, including flavours Cartograph does not support |
| `draft_ground_truth.py` | Drafts ground-truth records from the two enumerators and the declared scope rules |
| `merge_orm_ground_truth.py` | Adds ORM records and `must_not_produce` assertions |
| `ground-truth/` | The records, one file per repository, reviewed against source |
| `run_benchmark.py` | Runs the analyser and records what it produced. Judges nothing |
| `evaluate.py` | Scores output against ground truth and against source. Measures nothing |
| `results/` | Measurements and evaluations for both passes |

## The separation that matters

`run_benchmark.py` measures and `evaluate.py` scores. Neither can reach into
the other: editing the evaluator cannot change what was observed, and editing
the runner cannot change how it is judged.

Ground truth is drafted by a tool that receives a filesystem path and nothing
else. It cannot import the analyser and never reads its output, so the labels
cannot drift toward the results they will be used to judge.

## Running it

Mirrors live outside this repository — no corpus source is committed. Each
must sit at the exact commit in `corpus.json`; the runner verifies this and
refuses otherwise.

```
python3 benchmarks/run_benchmark.py --mirror <corpus-dir> --raw <raw-dir> \
    --pass-number 2 --out benchmarks/results/m07-pass2-measurements.json
python3 benchmarks/evaluate.py \
    --measurement benchmarks/results/m07-pass2-measurements.json \
    --mirror <corpus-dir> --out benchmarks/results/m07-pass2-evaluation.json
```

Regenerating ground truth requires re-running `evaluate.py`: QG-009 binds each
result set to the digest of the ground truth it was scored against, so an
edited record fails the gate until the evaluation is redone.

`evaluate.py` scores only against committed inputs. Before reading anything it
compares every ground-truth file it loads, the supported subset and the corpus
with the blobs committed at `HEAD` — whatever directories `--ground-truth`,
`--subset` and `--corpus` name — and checks that the ground-truth directory
holds exactly the committed set of files. A difference, an extra file or a
missing one stops it with exit status 1 and no result written, and so does a
tree in which git cannot answer. Edited ground truth is therefore committed
before it is scored. `benchmarks/test_evaluate.py` tests both outcomes on
temporary copies.

## Reading the numbers

They are INTERNAL. `docs/benchmarks/m07-report.md` says what was measured, what
was measured only for precision, and what was not measured at all. The last
category is the one to read first.
