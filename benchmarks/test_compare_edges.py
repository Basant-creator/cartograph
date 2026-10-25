#!/usr/bin/env python3
"""Tests for compare_edges.py. Standard library `unittest`; run directly."""

from __future__ import annotations

import copy
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import compare_edges as C  # noqa: E402


def edge(i, kind, file, line, confidence=0.98, provenance="route-matcher"):
    return {"id": i, "kind": kind, "file": file, "line": line,
            "confidence": confidence, "provenance": provenance,
            "source": 0, "target": 1, "evidence": []}


def call(file, line, route, status="no-match"):
    return {"client_file": file, "client_line": line, "client_route": route,
            "status": status, "candidates": []}


def run_document():
    return {
        "root": "posthog",
        "elapsed_ms": 1000,
        "graph": {"edges": [
            edge(0, "http-call", "nodejs/src/common/api/router.ts", 43),
            edge(1, "http-call", "frontend/src/lib/api.ts", 12, confidence=0.78400004),
            edge(2, "orm-access", "posthog/api/action.py", 7, provenance="orm-resolution"),
        ]},
        "matches": [
            call("nodejs/src/cdp/cdp-api.ts", 101, "GET /public/hooks"),
            call("nodejs/src/common/api/router.ts", 43, "GET /_health", "exact"),
            call("frontend/src/lib/api.ts", 12, "GET /api/projects"),
        ],
    }


class Compare(unittest.TestCase):
    def test_identical_runs_agree(self):
        report = C.compare(run_document(), run_document())
        self.assertTrue(report["identical"])
        self.assertIsNone(report["edges"]["first_divergence"])

    def test_timing_is_not_compared(self):
        other = run_document()
        other["elapsed_ms"] = 999_999
        self.assertTrue(C.compare(run_document(), other)["identical"])

    def test_a_missing_client_call_is_the_first_divergence(self):
        # The shape of the PostHog question: a route registration read as a
        # request on one side and not on the other.
        after = run_document()
        after["matches"] = [m for m in after["matches"]
                            if m["client_file"] != "nodejs/src/cdp/cdp-api.ts"]
        report = C.compare(run_document(), after)

        self.assertFalse(report["identical"])
        calls = report["client_calls"]
        self.assertEqual(calls["only_left"], [["nodejs/src/cdp/cdp-api.ts", 101, "GET /public/hooks"]])
        self.assertEqual(calls["only_right"], [])
        self.assertEqual(calls["first_divergence"]["side"], "left")
        self.assertEqual(calls["per_file"],
                         [{"file": "nodejs/src/cdp/cdp-api.ts", "only_left": 1, "only_right": 0}])

    def test_divergences_are_reported_in_path_order(self):
        after = run_document()
        after["matches"] = [after["matches"][1]]  # drop cdp-api.ts and frontend api.ts
        first = C.compare(run_document(), after)["client_calls"]["first_divergence"]
        self.assertEqual(first["item"][0], "frontend/src/lib/api.ts")

    def test_a_changed_confidence_is_a_difference(self):
        after = run_document()
        after["graph"]["edges"][0]["confidence"] = 0.9
        report = C.compare(run_document(), after)
        self.assertFalse(report["identical"])
        self.assertEqual(len(report["edges"]["only_left"]), 1)
        self.assertEqual(len(report["edges"]["only_right"]), 1)

    def test_renumbering_is_not_a_divergence_but_is_not_identical(self):
        # Ids are graph-local: dropping one edge renumbers those after it.
        # That must not swamp the one real difference.
        after = run_document()
        after["graph"]["edges"].pop(0)
        for i, e in enumerate(after["graph"]["edges"]):
            e["id"] = i
        report = C.compare(run_document(), after)
        self.assertEqual(len(report["edges"]["only_left"]), 1)
        self.assertEqual(report["edges"]["only_right"], [])
        self.assertFalse(report["identical"])

    def test_same_edges_numbered_differently_are_not_identical(self):
        after = run_document()
        edges = after["graph"]["edges"]
        edges[0]["id"], edges[1]["id"] = edges[1]["id"], edges[0]["id"]
        report = C.compare(run_document(), after)
        self.assertEqual(report["edges"]["only_left"], [])
        self.assertFalse(report["edge_numbering_identical"])
        self.assertFalse(report["identical"])

    def test_a_changed_provenance_is_a_difference(self):
        after = run_document()
        after["graph"]["edges"][2]["provenance"] = "static-import-resolution"
        self.assertFalse(C.compare(run_document(), after)["identical"])


class AgainstM08(unittest.TestCase):
    def dataset(self, document):
        records = [{"repository": "posthog", "kind": e["kind"], "at": f"{e['file']}:{e['line']}",
                    "edge": e["id"], "confidence": round(e["confidence"], 6),
                    "provenance": e["provenance"]}
                   for e in document["graph"]["edges"]]
        records.append({"repository": "zulip", "kind": "call", "at": "x.py:1", "edge": 0,
                        "confidence": 0.9, "provenance": "static-import-resolution"})
        return {"records": records}

    def test_the_labellers_rounding_is_not_a_difference(self):
        document = run_document()
        report = C.compare(document, dataset=self.dataset(document), repository="posthog")
        self.assertTrue(report["identical"], report)

    def test_without_that_rounding_it_would_be_one(self):
        # The guard against normalising too much: compared exactly, 0.78400004
        # and 0.784 differ, and they should.
        document = run_document()
        dataset = self.dataset(document)
        exact = C.edges_of_match(document)
        self.assertNotEqual(exact, C.edges_of_m08(dataset, "posthog"))

    def test_a_missing_edge_is_found(self):
        document = run_document()
        dataset = self.dataset(document)
        shorter = copy.deepcopy(document)
        shorter["graph"]["edges"].pop(0)
        report = C.compare(shorter, dataset=dataset, repository="posthog")
        self.assertFalse(report["identical"])
        self.assertEqual(report["edges"]["only_right"][0][1], "nodejs/src/common/api/router.ts:43")

    def test_a_renumbered_edge_against_the_dataset_is_not_identical(self):
        document = run_document()
        dataset = self.dataset(document)
        dataset["records"][0]["edge"] = 99
        report = C.compare(document, dataset=dataset, repository="posthog")
        self.assertEqual(report["edges"]["only_left"], [])
        self.assertFalse(report["edge_numbering_identical"])
        self.assertFalse(report["identical"])


class CommandLine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cartograph compare ")
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def write(self, name, document):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle)
        return path

    def run_main(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            status = C.main(list(argv))
        return status, out.getvalue()

    def test_identical_documents_exit_0(self):
        a = self.write("a.json", run_document())
        b = self.write("b.json", run_document())
        status, out = self.run_main(a, b)
        self.assertEqual(status, 0)
        self.assertTrue(out.strip().endswith("identical"))

    def test_different_documents_exit_1(self):
        after = run_document()
        after["matches"].pop()
        status, out = self.run_main(self.write("a.json", run_document()),
                                    self.write("b.json", after))
        self.assertEqual(status, 1)
        self.assertIn("DIFFERENT", out)

    def test_an_unknown_repository_is_bad_input(self):
        dataset = self.write("d.json", {"records": []})
        status, _ = self.run_main(self.write("a.json", run_document()),
                                  "--m08", dataset, "--repository", "posthog")
        self.assertEqual(status, 2)


if __name__ == "__main__":
    unittest.main()
