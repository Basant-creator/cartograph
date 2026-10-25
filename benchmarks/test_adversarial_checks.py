#!/usr/bin/env python3
"""Each adversarial check must find what it guards against, and say so.

Standard library `unittest`; no dependency is added for testing. Run directly
or through `make gates`, which invokes this file.

Until these outcomes existed, every check recorded `detected: true` whatever it
found, so "10 of 10" counted checks rather than results. Every check here gets
a fixture it must pass and one it must flag. The fixtures are small dictionaries
and temporary files; the committed evaluations are read, never written.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import adversarial_outcomes as A  # noqa: E402
import evaluate as E  # noqa: E402


def record(rid, classification, rule=None):
    return {"id": rid, "classification": classification, "rule": rule}


def ground_truth(**repos):
    return {"repos": {name: {"route_declarations": routes, "orm_declarations": []}
                      for name, routes in repos.items()},
            "_paths": {}}


def scored(recall_denominator=1, produced=3, confirmed=2, contradicted=0, unverifiable=1):
    return {"status": "OK",
            "routes": {"metrics": {"recall_denominator": recall_denominator}},
            "queries": {"produced": produced, "source_confirmed": confirmed,
                        "source_contradicted": [None] * contradicted,
                        "source_unverifiable_count": unverifiable}}


def measured(name, files=10, routes=1, calls=1, status="OK"):
    return {"name": name, "status": status,
            "measurements": {"files_analysed": files, "backend_routes": routes,
                             "client_calls": calls}}


SUBSET = {"out_of_scope": {"entries": [{"id": "OUT-1"}]},
          "safe_refusal": {"entries": [{"id": "REF-1"}]}}
CORPUS = {"repositories": [{"name": "a", "commit": "1" * 40}, {"name": "b", "commit": "2" * 40}],
          "coverage_requirements": {"django": ["b"]}}


class ScoringInputs(unittest.TestCase):
    def test_verified_inputs_pass_and_unverified_ones_are_a_violation(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        subset = os.path.join(tmp, "subset.json")
        open(subset, "w").close()
        gt = {"repos": {}, "_paths": {}}
        ok = {"verified": True, "reference_commit": "c", "problems": []}
        bad = {"verified": False, "reference_commit": "c", "problems": ["x differs"]}
        self.assertEqual(E.check_scoring_inputs(ok, gt, subset)["status"], E.PASSED)
        self.assertEqual(E.check_scoring_inputs(bad, gt, subset)["status"], E.VIOLATION)


class RawOutputs(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="cartograph checks ")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def file(self, name, text):
        path = os.path.join(self.root, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        return name, hashlib.sha256(text.encode()).hexdigest()

    def measurement(self):
        raw, raw_sha = self.file("a.json", "{}")
        norm, norm_sha = self.file("a.normalize.json", "[]")
        return {"repositories": [{"name": "a", "status": "OK", "raw_path": raw,
                                  "raw_sha256": raw_sha,
                                  "normalize": {"raw_path": norm, "raw_sha256": norm_sha}}]}

    def test_unaltered_outputs_pass(self):
        check = E.check_raw_outputs(self.measurement(), root=self.root)
        self.assertEqual(check["status"], E.PASSED)
        self.assertEqual(check["detail"]["checked"], 2)

    def test_an_altered_match_output_is_a_violation(self):
        m = self.measurement()
        self.file("a.json", '{"edited": true}')
        self.assertEqual(E.check_raw_outputs(m, root=self.root)["status"], E.VIOLATION)

    def test_an_altered_normalize_output_is_a_violation(self):
        # Route extraction is scored from the normalize output, which the
        # check used not to look at.
        m = self.measurement()
        self.file("a.normalize.json", '["edited"]')
        check = E.check_raw_outputs(m, root=self.root)
        self.assertEqual(check["status"], E.VIOLATION)
        self.assertEqual(check["detail"]["digest_mismatches"],
                         [{"repo": "a", "file": "a.normalize.json"}])

    def test_a_deleted_output_is_a_violation(self):
        m = self.measurement()
        os.remove(os.path.join(self.root, "a.json"))
        self.assertEqual(E.check_raw_outputs(m, root=self.root)["status"], E.VIOLATION)

    def test_with_nothing_measured_it_does_not_run(self):
        m = {"repositories": [{"name": "a", "status": "MISSING"}]}
        self.assertEqual(E.check_raw_outputs(m, root=self.root)["status"], E.NOT_RUN)


class RefusalRecords(unittest.TestCase):
    def test_ground_truth_with_refusals_passes(self):
        gt = ground_truth(a=[record("r1", "IN_SCOPE"), record("r2", "UNSUPPORTED", "OUT-1")])
        self.assertEqual(E.check_refusal_records(gt)["status"], E.PASSED)

    def test_a_repository_with_only_successes_is_a_violation(self):
        gt = ground_truth(a=[record("r1", "UNSUPPORTED", "OUT-1")], b=[record("r2", "IN_SCOPE")])
        check = E.check_refusal_records(gt)
        self.assertEqual(check["status"], E.VIOLATION)
        self.assertEqual(check["detail"]["repositories_with_none"], ["b"])

    def test_with_no_ground_truth_it_does_not_run(self):
        self.assertEqual(E.check_refusal_records(ground_truth())["status"], E.NOT_RUN)


class DeclaredRules(unittest.TestCase):
    def test_declared_rules_pass(self):
        gt = ground_truth(a=[record("r1", "UNSUPPORTED", "OUT-1"), record("r2", "SAFE_REFUSAL", "REF-1")])
        self.assertEqual(E.check_declared_rules(SUBSET, gt)["status"], E.PASSED)

    def test_an_undeclared_out_of_scope_rule_is_a_violation(self):
        gt = ground_truth(a=[record("r1", "UNSUPPORTED", "OUT-99")])
        self.assertEqual(E.check_declared_rules(SUBSET, gt)["status"], E.VIOLATION)

    def test_a_refusal_citing_an_out_of_scope_rule_is_a_violation(self):
        gt = ground_truth(a=[record("r1", "SAFE_REFUSAL", "OUT-1")])
        self.assertEqual(E.check_declared_rules(SUBSET, gt)["status"], E.VIOLATION)

    def test_with_nothing_out_of_scope_it_does_not_run(self):
        gt = ground_truth(a=[record("r1", "IN_SCOPE")])
        self.assertEqual(E.check_declared_rules(SUBSET, gt)["status"], E.NOT_RUN)


class Denominators(unittest.TestCase):
    def test_a_denominator_equal_to_the_in_scope_count_passes(self):
        gt = ground_truth(a=[record("r1", "IN_SCOPE"), record("r2", "UNSUPPORTED", "OUT-1")])
        self.assertEqual(E.check_denominators(gt, {"a": scored(1)})["status"], E.PASSED)

    def test_a_shrunk_denominator_is_a_violation(self):
        gt = ground_truth(a=[record("r1", "IN_SCOPE"), record("r2", "IN_SCOPE")])
        check = E.check_denominators(gt, {"a": scored(1)})
        self.assertEqual(check["status"], E.VIOLATION)
        self.assertEqual(check["detail"]["drift"][0]["in_scope_records"], 2)

    def test_an_unscored_repository_is_not_examined_and_does_not_crash(self):
        # It used to raise KeyError on any repository that was not scored.
        gt = ground_truth(a=[record("r1", "IN_SCOPE")], b=[record("r2", "IN_SCOPE")])
        results = {"a": scored(1), "b": {"status": "MISSING"}}
        self.assertEqual(E.check_denominators(gt, results)["status"], E.PASSED)
        self.assertEqual(E.check_denominators(gt, {"b": {"status": "MISSING"}})["status"],
                         E.NOT_RUN)


class QueriesAccounted(unittest.TestCase):
    def test_every_edge_in_a_bucket_passes(self):
        self.assertEqual(E.check_queries_accounted({"a": scored()})["status"], E.PASSED)

    def test_an_edge_in_no_bucket_is_a_violation(self):
        results = {"a": scored(produced=4, confirmed=2, unverifiable=1)}
        self.assertEqual(E.check_queries_accounted(results)["status"], E.VIOLATION)

    def test_with_nothing_scored_it_does_not_run(self):
        self.assertEqual(E.check_queries_accounted({"a": {"status": "MISSING"}})["status"],
                         E.NOT_RUN)


class CorpusCoverage(unittest.TestCase):
    def test_every_entry_scored_passes(self):
        results = {"a": scored(), "b": scored()}
        self.assertEqual(E.check_corpus_coverage(CORPUS, results)["status"], E.PASSED)

    def test_a_dropped_repository_is_a_violation(self):
        check = E.check_corpus_coverage(CORPUS, {"a": scored()})
        self.assertEqual(check["status"], E.VIOLATION)
        self.assertEqual(check["detail"]["coverage_entries_unscored"], ["b"])

    def test_with_no_corpus_it_does_not_run(self):
        # An empty corpus has nothing to cover; that is not a pass.
        empty = {"repositories": [], "coverage_requirements": {}}
        self.assertEqual(E.check_corpus_coverage(empty, {})["status"], E.NOT_RUN)

    def test_a_repository_listed_but_not_scored_is_a_violation(self):
        # It used to count: a MISSING entry in the results read as scored.
        results = {"a": scored(), "b": {"status": "MISSING"}}
        check = E.check_corpus_coverage(CORPUS, results)
        self.assertEqual(check["status"], E.VIOLATION)
        self.assertEqual(check["detail"]["missing_from_results"], ["b"])


class EmptyRuns(unittest.TestCase):
    def test_repositories_with_observations_pass(self):
        m = {"repositories": [measured("a"), measured("b", routes=0, calls=3)]}
        self.assertEqual(E.check_empty_runs(m)["status"], E.PASSED)

    def test_a_repository_that_produced_nothing_is_a_violation(self):
        for empty in (measured("b", files=0), measured("b", routes=0, calls=0)):
            m = {"repositories": [measured("a"), empty]}
            self.assertEqual(E.check_empty_runs(m)["status"], E.VIOLATION)

    def test_with_nothing_measured_it_does_not_run(self):
        m = {"repositories": [measured("a", status="ANALYSIS_FAILED")]}
        self.assertEqual(E.check_empty_runs(m)["status"], E.NOT_RUN)


class Toolchain(unittest.TestCase):
    m = {"toolchain": {"rustc": "rustc 1.97.1", "cartograph_commit": "c"}}

    def test_the_recorded_toolchain_passes(self):
        self.assertEqual(E.check_toolchain(self.m, "rustc 1.97.1")["status"], E.PASSED)

    def test_a_different_toolchain_is_a_violation(self):
        self.assertEqual(E.check_toolchain(self.m, "rustc 1.98.0")["status"], E.VIOLATION)

    def test_an_unreadable_toolchain_is_an_error(self):
        self.assertEqual(E.check_toolchain(self.m, None)["status"], E.ERROR)


class Revisions(unittest.TestCase):
    def setUp(self):
        self.revisions = {}
        self.real = E.revision_of
        E.revision_of = lambda path: self.revisions.get(os.path.basename(path))
        self.addCleanup(setattr, E, "revision_of", self.real)

    def test_pinned_revisions_pass(self):
        self.revisions = {"a": "1" * 40, "b": "2" * 40}
        self.assertEqual(E.check_revisions(CORPUS, "mirror")["status"], E.PASSED)

    def test_a_different_revision_is_a_violation(self):
        self.revisions = {"a": "1" * 40, "b": "3" * 40}
        check = E.check_revisions(CORPUS, "mirror")
        self.assertEqual(check["status"], E.VIOLATION)
        self.assertEqual(check["detail"]["mismatched"][0]["repo"], "b")

    def test_with_no_corpus_it_does_not_run(self):
        empty = {"repositories": [], "coverage_requirements": {}}
        self.assertEqual(E.check_revisions(empty, "mirror")["status"], E.NOT_RUN)

    def test_an_unreadable_checkout_is_an_error_not_a_mismatch(self):
        # On Windows the old shell command made every checkout unreadable and
        # recorded each as a mismatch against revision "".
        self.revisions = {"a": "1" * 40}
        check = E.check_revisions(CORPUS, "mirror")
        self.assertEqual(check["status"], E.ERROR)
        self.assertEqual(check["detail"]["unreadable"], ["b"])
        self.assertEqual(check["detail"]["mismatched"], [])


class Summary(unittest.TestCase):
    def test_only_ten_passes_is_a_pass(self):
        ten = [{"attack": n, "status": E.PASSED} for n in range(1, 11)]
        self.assertTrue(E.summarize(ten)["all_passed"])
        for status in (E.VIOLATION, E.ERROR, E.NOT_RUN):
            nine = ten[:-1] + [{"attack": 10, "status": status}]
            summary = E.summarize(nine)
            self.assertFalse(summary["all_passed"])
            self.assertEqual(summary[status], [10])
        self.assertFalse(E.summarize(ten[:-1])["all_passed"], "nine checks are not ten")


class RecordedOutcomes(unittest.TestCase):
    """Evaluations written before outcomes existed, read by their evidence."""

    def test_the_always_true_detected_field_is_not_believed(self):
        check = {"attack": 5, "detected": True,
                 "detail": {"drift": [{"repo": "a", "in_scope_records": 2,
                                       "recall_denominator": 1}]}}
        self.assertEqual(E.recorded_outcome(check), E.VIOLATION)

    def test_evidence_that_cannot_be_read_is_an_error(self):
        self.assertEqual(E.recorded_outcome({"attack": 5, "detected": True, "detail": {}}),
                         E.ERROR)

    def test_a_recorded_status_is_taken_as_recorded(self):
        self.assertEqual(E.recorded_outcome({"attack": 5, "status": E.NOT_RUN}), E.NOT_RUN)

    def committed(self, path):
        with open(os.path.join(E.ROOT, path), encoding="utf-8") as handle:
            return dict(A.outcomes(json.load(handle)))

    def test_the_committed_baseline_passes_record_check_1_as_violated(self):
        # Passes 1 and 2 were scored against ground truth that was not yet
        # committed: the corrected instrument output m07-report.md lists. Their
        # check 1 recorded that, and nothing else failed.
        for path in ("benchmarks/results/m07-pass1-evaluation.json",
                     "benchmarks/results/m07-pass2-evaluation.json"):
            outcomes = self.committed(path)
            self.assertEqual(outcomes[1], E.VIOLATION, path)
            self.assertEqual([n for n, o in outcomes.items() if o != E.PASSED], [1], path)

    def test_the_committed_remediation_and_acceptance_runs_pass_all_ten(self):
        for path in ("benchmarks/remediation/final-evaluation.json",
                     "benchmarks/acceptance/m07-acceptance-evaluation.json"):
            outcomes = self.committed(path)
            self.assertEqual(sorted(outcomes), list(range(1, 11)), path)
            self.assertTrue(all(o == E.PASSED for o in outcomes.values()), path)


if __name__ == "__main__":
    unittest.main()
