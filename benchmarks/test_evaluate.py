#!/usr/bin/env python3
"""Tests for the scorer's guarantee that it scores against the committed inputs.

Standard library `unittest`; no dependency is added for testing. Run directly
or through `make gates`, which invokes this file.

The check these tests pin used to pass without checking anything on Windows:
it ran `git -C {path!r} status ...` through `os.popen`, cmd.exe did not strip
the single quotes `repr` produced, git failed, and the empty output was
recorded as "the working tree matches the commit". Nothing failed a run either
way, so a scorer pointed at an edited answer key produced a normal-looking
result and exit status 0 on every platform.

Every test works on temporary copies extracted from the committed blobs, under
a directory whose name contains a space. The real ground truth is never
written to.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import evaluate as E  # noqa: E402

SCORER = os.path.join(HERE, "evaluate.py")


def committed(repo_path):
    """The bytes committed at HEAD for a repository path."""
    return subprocess.run(
        ["git", "-C", E.ROOT, "cat-file", "blob", f"HEAD:{repo_path}"],
        capture_output=True, check=True,
    ).stdout


def committed_ground_truth_names():
    listing = subprocess.run(
        ["git", "-C", E.ROOT, "ls-tree", "--name-only", "HEAD", f"{E.GROUND_TRUTH_DIR}/"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    return sorted(os.path.basename(p) for p in listing if p.endswith(".json"))


class CommittedCopies:
    """Copies of the committed scoring inputs in a throwaway directory."""

    def __init__(self, root):
        self.base = os.path.join(root, "scoring inputs copy")
        self.ground_truth = os.path.join(self.base, "ground truth")
        os.makedirs(self.ground_truth)
        for name in committed_ground_truth_names():
            self.write(os.path.join(self.ground_truth, name),
                       committed(f"{E.GROUND_TRUTH_DIR}/{name}"))
        self.subset = os.path.join(self.base, "supported-subset.json")
        self.write(self.subset, committed(E.SUBSET_PATH))
        self.corpus = os.path.join(self.base, "corpus.json")
        self.write(self.corpus, committed(E.CORPUS_PATH))

    @staticmethod
    def write(path, data):
        with open(path, "wb") as handle:
            handle.write(data)

    def verify(self, root=E.ROOT):
        return E.verify_scoring_inputs(self.ground_truth, self.subset, self.corpus, root=root)

    def edit_json(self, path, change):
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        change(document)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cartograph scorer ")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.copies = CommittedCopies(self.tmp)


class VerifyScoringInputs(TempDirTest):
    def test_committed_inputs_verify(self):
        result = self.copies.verify()
        self.assertTrue(result["verified"], result["problems"])
        self.assertEqual(result["problems"], [])
        self.assertRegex(result["reference_commit"], r"^[0-9a-f]{40}$")

    def test_an_edited_ground_truth_record_is_detected(self):
        target = os.path.join(self.copies.ground_truth, "airflow.json")

        def reclassify(document):
            record = document["route_declarations"][0]
            record["classification"] = (
                "UNSUPPORTED" if record["classification"] != "UNSUPPORTED" else "IN_SCOPE"
            )

        self.copies.edit_json(target, reclassify)
        result = self.copies.verify()
        self.assertFalse(result["verified"])
        self.assertTrue(
            any("airflow.json" in p and "differs" in p for p in result["problems"]),
            result["problems"],
        )

    def test_a_deleted_ground_truth_record_is_detected(self):
        # Deleting a record shrinks both sides of recall, so the denominator
        # check alone cannot see it.
        target = os.path.join(self.copies.ground_truth, "zulip.json")
        self.copies.edit_json(target, lambda d: d["route_declarations"].pop())
        self.assertFalse(self.copies.verify()["verified"])

    def test_a_one_byte_change_is_detected(self):
        target = os.path.join(self.copies.ground_truth, "onyx.json")
        with open(target, "ab") as handle:
            handle.write(b" ")
        self.assertFalse(self.copies.verify()["verified"])

    def test_an_added_ground_truth_file_is_detected(self):
        shutil.copy(os.path.join(self.copies.ground_truth, "airflow.json"),
                    os.path.join(self.copies.ground_truth, "extra.json"))
        result = self.copies.verify()
        self.assertFalse(result["verified"])
        self.assertTrue(any("extra.json is used but not committed" in p
                            for p in result["problems"]), result["problems"])

    def test_a_missing_ground_truth_file_is_detected(self):
        os.remove(os.path.join(self.copies.ground_truth, "superset.json"))
        result = self.copies.verify()
        self.assertFalse(result["verified"])
        self.assertTrue(any("superset.json is committed but missing" in p
                            for p in result["problems"]), result["problems"])

    def test_an_edited_scope_is_detected(self):
        self.copies.edit_json(self.copies.subset,
                              lambda d: d["out_of_scope"]["entries"].pop())
        result = self.copies.verify()
        self.assertFalse(result["verified"])
        self.assertTrue(any(E.SUBSET_PATH in p for p in result["problems"]),
                        result["problems"])

    def test_an_edited_corpus_is_detected(self):
        self.copies.edit_json(self.copies.corpus,
                              lambda d: d["repositories"][0].update(commit="0" * 40))
        self.assertFalse(self.copies.verify()["verified"])

    def test_crlf_line_endings_are_not_mistaken_for_an_edit(self):
        # A Windows checkout may hold CRLF. Git normalises it on the way in,
        # and so does the comparison, so this is not tampering.
        target = os.path.join(self.copies.ground_truth, "airflow.json")
        with open(target, "rb") as handle:
            data = handle.read()
        self.assertNotIn(b"\r\n", data)
        with open(target, "wb") as handle:
            handle.write(data.replace(b"\n", b"\r\n"))
        result = self.copies.verify()
        self.assertTrue(result["verified"], result["problems"])

    def test_outside_a_git_checkout_verification_fails_closed(self):
        not_a_checkout = os.path.join(self.tmp, "no git here")
        os.makedirs(not_a_checkout)
        result = self.copies.verify(root=not_a_checkout)
        self.assertFalse(result["verified"])
        self.assertIsNone(result["reference_commit"])


class RevisionOf(unittest.TestCase):
    def test_a_checkout_whose_path_has_spaces_is_read(self):
        tmp = tempfile.mkdtemp(prefix="cartograph scorer ")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        checkout = os.path.join(tmp, "pinned checkout")
        os.makedirs(checkout)

        def git(*args):
            subprocess.run(["git", "-C", checkout, *args], check=True, capture_output=True)

        git("init", "-q")
        with open(os.path.join(checkout, "f.txt"), "w", encoding="utf-8") as handle:
            handle.write("x\n")
        git("add", "f.txt")
        git("-c", "user.name=t", "-c", "user.email=t@example.invalid",
            "commit", "-q", "-m", "c")
        head = subprocess.run(["git", "-C", checkout, "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(E.revision_of(checkout), head)

    def test_a_directory_that_is_not_a_checkout_has_no_revision(self):
        tmp = tempfile.mkdtemp(prefix="cartograph scorer ")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.assertIsNone(E.revision_of(tmp))


class ScorerExitStatus(TempDirTest):
    """The command itself, as `make` and CI run it."""

    def score(self, ground_truth, measurement):
        out = os.path.join(self.tmp, "result dir", "evaluation.json")
        mirror = os.path.join(self.tmp, "empty mirror")
        os.makedirs(mirror, exist_ok=True)
        proc = subprocess.run(
            [sys.executable, SCORER,
             "--ground-truth", ground_truth,
             "--subset", self.copies.subset,
             "--corpus", self.copies.corpus,
             "--measurement", measurement,
             "--mirror", mirror,
             "--out", out],
            capture_output=True, text=True, check=False,
        )
        return proc, out

    def empty_measurement(self):
        path = os.path.join(self.tmp, "measurement.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"pass": 0, "corpus_sha256": "unused", "repositories": [],
                       "toolchain": {"rustc": "unused", "cartograph_commit": "unused"}},
                      handle)
        return path

    def test_a_tampered_ground_truth_stops_the_scorer_with_status_1(self):
        target = os.path.join(self.copies.ground_truth, "airflow.json")
        self.copies.edit_json(target, lambda d: d["route_declarations"].pop())

        proc, out = self.score(self.copies.ground_truth, self.empty_measurement())

        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("refusing to score", proc.stderr)
        self.assertIn("airflow.json", proc.stderr)
        self.assertFalse(os.path.exists(out), "no result may be written")

    def test_committed_ground_truth_is_scored_and_the_proof_recorded(self):
        proc, out = self.score(self.copies.ground_truth, self.empty_measurement())

        # Scored, because the inputs are the committed ones, and check 1 says so.
        with open(out, encoding="utf-8") as handle:
            result = json.load(handle)
        check = next(c for c in result["adversarial_checks"] if c["attack"] == 1)
        self.assertEqual(check["status"], E.PASSED)
        self.assertTrue(check["detail"]["inputs_match_commit"])
        self.assertEqual(check["detail"]["problems"], [])

        # But a measurement of nothing, with no checkouts, is not a passing run.
        # Before outcomes were recorded this exited 0, every check claiming
        # `detected: true`.
        self.assertEqual(proc.returncode, 1, proc.stderr)
        summary = result["adversarial_summary"]
        self.assertFalse(summary["all_passed"])
        self.assertEqual(summary[E.PASSED], [1, 3, 4])
        self.assertEqual(summary[E.VIOLATION], [7, 9])  # nothing scored; toolchain "unused"
        self.assertEqual(summary[E.ERROR], [10])        # no checkout to read
        self.assertEqual(summary[E.NOT_RUN], [2, 5, 6, 8])
        self.assertNotIn("detected", check)


if __name__ == "__main__":
    unittest.main()
