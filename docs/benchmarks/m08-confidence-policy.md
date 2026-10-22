# Confidence policy (specification, not an implementation)

A semantic specification for later UI and API work, derived from the M08
measurements. **No production threshold changes on the strength of this
document.** Changing one is an architecture decision and needs its own ADR.

## What a confidence number currently means

It is an **uncalibrated prior selected by evidence class**, not a probability.
Seven values exist. Grouping edges by confidence and grouping them by evidence
are the same partition, which is why the policy below is written in terms of
evidence rather than numbers.

## Categories

| Category | Evidence | Measured basis |
|---|---|---|
| **HIGH** — safe to state plainly | Route matched on an exact method with every path segment static and equal (0.98); a name resolved to its declaration through an import (0.90) | 544 and 1,039 verified observations, no false positive in either |
| **MEDIUM** — state with visible uncertainty | Model-to-table and handler-to-model resolution (0.80) | 9,630 verified, one false positive |
| **LOW** — state as inference, never as fact | A route matched with an undeclared method, a wildcard suffix, or a client value the source does not fix (0.64–0.784) | **705 produced. 8 verified, all at 0.65 and all correct; the other 697 (0.64, 0.72, 0.784) are unverifiable.** Eight observations cannot support an estimate, so accuracy here is unmeasured |
| **REFUSED** — no edge | Ambiguity, unresolvable imports, dynamic prefixes, non-literal table names | 1,544 ambiguous decisions produced no edge |

## The rule this measurement suggests

**Do not raise confidence to match observed accuracy.** Observed accuracy is
~1.0 in every measured band, which would argue for pushing 0.80 toward 1.0.
That would be fitting to a filtered subset: a quarter of all edges could not be
verified, and the unverifiable ones are concentrated exactly where the evidence
is weakest. The measured gap is real, but the population it was measured on is
not the population the number is applied to.

**Do not lower the acceptance threshold below 0.8.** The threshold table shows
nothing to gain: every threshold from 0.0 to 0.8 keeps the same single false
positive and the same precision, 0.9999. Moving the threshold across 0.65–0.70
changes only the eight verified edges at 0.65; the edges at 0.64, 0.72 and
0.784 were never verifiable either way.

**Treat the LOW band as display-only.** It is 4.7% of edges, and its only
verified observations are the eight at 0.65 — too few to estimate accuracy
from. Until it has more, it should not feed anything automatic.

## What would change this

Measuring the low band needs labels for edges whose client value is not fixed
in source — which is, by construction, what makes them unverifiable to a static
reader. That is a genuine open problem, recorded rather than assumed away.

---

*Source: [`benchmarks/m08/results/calibration-all.json`](../../benchmarks/m08/results/calibration-all.json)
(`by_confidence_value` and `thresholds`), and for refused decisions the
per-repository `decisions.ambiguous` counts in
[`benchmarks/acceptance/m07-acceptance-measurements.json`](../../benchmarks/acceptance/m07-acceptance-measurements.json),
which total 1,544. Corrected in M17's traceability review: the LOW band
previously read "707 produced, zero verified", and the threshold rule said every
band kept the same true positives. Both disagreed with that file.*
