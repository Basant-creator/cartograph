#!/usr/bin/env python3
"""Score Cartograph's output against ground truth, and say how it was scored.

Every label this produces is one of the six declared in supported-subset.json,
and the six are never collapsed: a safe refusal is not a miss, an unsupported
pattern is not a miss, and an ambiguous case is not a miss. Those three are
reported with their own counts so the recall denominator can be checked rather
than trusted.

Two kinds of check appear here.

  * Ground-truth checks compare produced relationships against the records in
    benchmarks/ground-truth/, which were authored from source before the first
    pass. These cover a sample.
  * Source checks re-read the corpus at its pinned commit and verify a
    produced relationship directly. These cover every edge, which is what
    makes a precision figure meaningful — a precision computed only over
    sampled edges would let unexamined false positives sit outside the ratio.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where the committed scoring inputs live, relative to ROOT. Whatever paths
# the command line names, these are what the files used must match.
GROUND_TRUTH_DIR = "benchmarks/ground-truth"
SUBSET_PATH = "benchmarks/supported-subset.json"
CORPUS_PATH = "benchmarks/corpus.json"

CLASS_DECL = re.compile(r"^\s*class\s+(\w+)\s*[\(:]")
TABLENAME = re.compile(r"""^\s*__tablename__\s*=\s*["']([^"']+)["']""")
DB_TABLE = re.compile(r"""^\s*db_table\s*=\s*["']([^"']+)["']""")
IMPORT_FROM = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+(.+)$")
IMPORT_PLAIN = re.compile(r"^\s*import\s+([\w.]+)")

# "Order(...) in create_order at api/orders.py:7"
ACCESS_EVIDENCE = re.compile(r"^(?P<expr>\S+)\(\.\.\.\) in (?P<handler>\S+) at (?P<file>.+):(?P<line>\d+)$")
# 'Order maps to table "orders"; __tablename__ = "orders"'
QUERIES_EVIDENCE = re.compile(r'^(?P<model>\S+) maps to table "(?P<table>[^"]+)"')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def run(*argv):
    """(returncode, stdout) of a command, run without a shell.

    The checks below used `os.popen` with a command string, which hands quoting
    to the platform's shell. On Windows that is cmd.exe: it does not strip the
    single quotes `{path!r}` produced, and it has no /dev/null, so git failed on
    every call, its error went to stderr, and empty stdout read as "no
    uncommitted changes" and as "no revision". An argument list needs no
    quoting, so a path with spaces or backslashes reaches git as written.
    """
    try:
        proc = subprocess.run(list(argv), capture_output=True, text=True, check=False)
    except OSError as exc:
        return None, str(exc)
    return proc.returncode, proc.stdout.strip()


def verify_scoring_inputs(ground_truth_dir, subset_path, corpus_path, root=ROOT):
    """Proves the files being scored with are the committed ones, or says why not.

    Ground truth is authored from source before the first pass and committed;
    scoring against anything else lets the answer key move after the answers
    are known. So every file the scorer loads is compared with the blob
    committed at `root`'s HEAD under its canonical path, whatever directory the
    command line pointed at, and the ground-truth directory must hold exactly
    the committed set of files - an added or a missing repository is a change
    to the answer key too.

    `git hash-object --path` hashes a file the way git would store it at that
    path, applying the repository's line-ending rules, so a checkout's line
    endings are not mistaken for an edit.

    Fails closed: if git cannot answer, the inputs are unverified, which is
    reported as a failure rather than as a pass.
    """
    problems = []
    code, commit = run("git", "-C", root, "rev-parse", "--verify", "HEAD")
    if code != 0 or not commit:
        return {"verified": False, "reference_commit": None,
                "problems": [f"cannot read the reference commit in {root}: git rev-parse failed"]}

    def committed_blob(repo_path):
        code, blob = run("git", "-C", root, "rev-parse", "--verify", "--quiet",
                         f"HEAD:{repo_path}")
        return blob if code == 0 and blob else None

    def compare(used, repo_path):
        expected = committed_blob(repo_path)
        if expected is None:
            problems.append(f"{repo_path} is not committed at HEAD")
            return
        if not os.path.isfile(used):
            problems.append(f"{repo_path}: {used} does not exist")
            return
        # Absolute, because `git -C` resolves a relative path against `root`
        # rather than against the directory the scorer was started from.
        code, actual = run("git", "-C", root, "hash-object", f"--path={repo_path}", "--",
                           os.path.abspath(used))
        if code != 0 or not actual:
            problems.append(f"{repo_path}: could not hash {used}")
        elif actual != expected:
            problems.append(f"{repo_path}: {used} differs from the committed file")

    compare(subset_path, SUBSET_PATH)
    compare(corpus_path, CORPUS_PATH)

    code, listing = run("git", "-C", root, "ls-tree", "--name-only", "HEAD",
                        f"{GROUND_TRUTH_DIR}/")
    committed = {os.path.basename(p) for p in listing.splitlines() if p.endswith(".json")} \
        if code == 0 else set()
    if code != 0 or not committed:
        problems.append(f"no ground truth is committed under {GROUND_TRUTH_DIR} at HEAD")
    used = {os.path.basename(p) for p in glob.glob(os.path.join(ground_truth_dir, "*.json"))}
    for name in sorted(used - committed):
        problems.append(f"{GROUND_TRUTH_DIR}/{name} is used but not committed")
    for name in sorted(committed - used):
        problems.append(f"{GROUND_TRUTH_DIR}/{name} is committed but missing from {ground_truth_dir}")
    for name in sorted(used & committed):
        compare(os.path.join(ground_truth_dir, name), f"{GROUND_TRUTH_DIR}/{name}")

    return {"verified": not problems, "reference_commit": commit, "problems": problems}


def revision_of(checkout):
    """The commit a checkout is at, or None when git cannot say."""
    code, head = run("git", "-C", checkout, "rev-parse", "HEAD")
    return head if code == 0 and head else None


class Source:
    """Read-only access to a pinned checkout. Never executes anything."""

    def __init__(self, root):
        self.root = root
        self._cache = {}

    def lines(self, rel):
        if rel not in self._cache:
            path = os.path.join(self.root, rel)
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    self._cache[rel] = handle.readlines()
            except OSError:
                self._cache[rel] = []
        return self._cache[rel]

    def line(self, rel, number):
        lines = self.lines(rel)
        return lines[number - 1].rstrip("\n") if 0 < number <= len(lines) else None

    def declared_table(self, rel, class_name):
        """The table a class declares in source, read directly.

        Returns (table_or_None, how). Used to check every Queries edge rather
        than only the sampled ones.
        """
        lines = self.lines(rel)
        start = None
        for index, line in enumerate(lines):
            match = CLASS_DECL.match(line)
            if match and match.group(1) == class_name and not line.startswith((" ", "\t")):
                start = index
                break
        if start is None:
            return None, "class not found in this file"
        for line in lines[start + 1 : start + 400]:
            if CLASS_DECL.match(line) and not line.startswith((" ", "\t")):
                break
            found = TABLENAME.match(line) or DB_TABLE.match(line)
            if found:
                return found.group(1), "declared in source"
        return None, "no literal table declared in this class"

    def binding_of(self, rel, name):
        """How a name is bound in a file: defined here, imported, or absent.

        This is the check that separates a real model access from a call to
        something that merely shares a model's name. Cartograph matches the
        receiver name against a project-wide map without consulting the file's
        imports, so `Table(...)` in a file that imported Table from sqlalchemy
        is indistinguishable to it from the project's own Table model.
        """
        for line in self.lines(rel):
            match = CLASS_DECL.match(line)
            if match and match.group(1) == name:
                return "defined-here", None
            if re.match(rf"^\s*(?:async\s+)?def\s+{re.escape(name)}\s*\(", line):
                return "defined-here", None
            if re.match(rf"^{re.escape(name)}\s*=", line):
                return "defined-here", None

        # Imports are matched over the joined text, not line by line. Reading
        # them a line at a time reported that Zulip's analytics module neither
        # defines nor imports FillState, when the file opens with
        #
        #     from analytics.models import (
        #         FillState,
        #         ...
        #     )
        #
        # — the commonest import shape in a large codebase, and one an
        # instrument that judges false positives cannot afford to miss.
        text = "".join(self.lines(rel))
        for found in re.finditer(
            r"^\s*from\s+([\w.]+)\s+import\s+(\(.*?\)|[^\n]*)",
            text, re.M | re.S,
        ):
            module, imported = found.group(1), found.group(2)
            if re.search(rf"(^|[\s(,]){re.escape(name)}\s*(,|\)|$|\s+as\s)", imported, re.M):
                return "imported", module
            if "*" in imported:
                return "star-import", module
        for found in re.finditer(r"^\s*import\s+([\w.]+)(?:\s+as\s+(\w+))?", text, re.M):
            module, alias = found.group(1), found.group(2)
            if (alias or module.split(".")[-1]) == name:
                return "imported", module
        return "absent", None


def module_of(rel):
    return rel[:-3].replace("/", ".") if rel.endswith(".py") else rel.replace("/", ".")


def nodes_by_id(graph):
    return {n["id"]: n for n in graph["nodes"]}


# ── Route declarations ───────────────────────────────────────────────

def score_routes(gt, normalize_report):
    """In-scope route records against the observations the analyser made."""
    produced = {}
    for route in normalize_report["canonical_routes"]:
        provenance = route["provenance"]
        if provenance["kind"] != "route-declaration":
            continue
        produced[(provenance["file"], provenance["span"]["start_line"])] = route

    labels = defaultdict(list)
    for record in gt["route_declarations"]:
        scope = record["classification"]
        key = (record["file"], record["line"])
        found = produced.get(key)

        if scope != "IN_SCOPE":
            label = "UNSUPPORTED" if scope == "UNSUPPORTED" else "EXCLUDED"
            if scope == "UNSUPPORTED" and found is not None:
                # Producing an out-of-scope relationship is not a win; it means
                # the scope declaration is wrong, and it is reported as such
                # rather than quietly counted as a success.
                label = "UNSUPPORTED_BUT_PRODUCED"
            labels[label].append(record["id"])
            continue

        if found is not None:
            labels["TRUE_POSITIVE"].append(record["id"])
        else:
            near = [
                offset
                for offset in (-2, -1, 1, 2)
                if (record["file"], record["line"] + offset) in produced
            ]
            labels["FALSE_NEGATIVE"].append(
                {
                    "id": record["id"],
                    "rule": record["rule"],
                    "receiver": record.get("receiver"),
                    "path": record.get("path_as_written"),
                    "predicted_gap": record.get("predicted_gap"),
                    "near_miss_offsets": near,
                }
            )
    return labels, len(produced)


# ── Queries edges (model to table) ───────────────────────────────────

def score_queries(gt, graph, source):
    """Every Queries edge is checked against source, not only sampled ones."""
    ids = nodes_by_id(graph)
    produced = []
    for edge in graph["edges"]:
        if edge["kind"] != "queries":
            continue
        model_node, table_node = ids[edge["source"]], ids[edge["target"]]
        produced.append(
            {
                "model": model_node["name"],
                "file": model_node.get("file"),
                "table": table_node["name"],
                "evidence": edge["evidence"],
                "line": edge["line"],
            }
        )

    confirmed, contradicted, unverifiable = [], [], []
    for item in produced:
        if not item["file"]:
            unverifiable.append(item)
            continue
        declared, how = source.declared_table(item["file"], item["model"])
        if declared is None:
            unverifiable.append({**item, "why": how})
        elif declared == item["table"]:
            confirmed.append(item)
        else:
            contradicted.append({**item, "source_says": declared})

    produced_index = {(p["model"], p["file"]): p for p in produced}
    labels = defaultdict(list)
    for record in gt["orm_declarations"]:
        scope = record["classification"]
        found = produced_index.get((record["model"], record["file"]))
        if scope == "IN_SCOPE":
            if found and found["table"] == record["table"]:
                labels["TRUE_POSITIVE"].append(record["id"])
            elif found:
                labels["FALSE_POSITIVE"].append(
                    {"id": record["id"], "expected": record["table"], "produced": found["table"]}
                )
            else:
                labels["FALSE_NEGATIVE"].append(
                    {
                        "id": record["id"],
                        "model": record["model"],
                        "expected_table": record["table"],
                        "table_source": record["table_source"],
                        "bases": record["bases"],
                        "flavour": record["flavour"],
                    }
                )
        elif scope == "SAFE_REFUSAL":
            if found:
                labels["FALSE_POSITIVE"].append(
                    {"id": record["id"], "expected": "no edge", "produced": found["table"],
                     "rule": record["rule"]}
                )
            else:
                labels["SAFE_REFUSAL"].append(record["id"])
        elif scope == "UNSUPPORTED":
            if found:
                labels["FALSE_POSITIVE"].append(
                    {"id": record["id"], "expected": "no edge (out of scope ORM)",
                     "produced": found["table"], "rule": record["rule"]}
                )
            else:
                labels["UNSUPPORTED"].append(record["id"])

    return {
        "produced": len(produced),
        "source_confirmed": len(confirmed),
        "source_contradicted": contradicted,
        "source_unverifiable": unverifiable[:20],
        "source_unverifiable_count": len(unverifiable),
        "ground_truth": {k: v for k, v in labels.items()},
    }


# ── OrmAccess edges (handler to model) ───────────────────────────────

def score_orm_access(graph, source, model_files):
    """Checks that the name at each access site is really the model.

    Cartograph resolves a model by name across the whole project. A file that
    calls `Table(...)` having imported Table from SQLAlchemy therefore looks
    identical to one calling the project's own Table model. Re-reading the
    access file's own bindings is what separates them.
    """
    ids = nodes_by_id(graph)
    confirmed, wrong_symbol, not_at_line, unverifiable = [], [], [], []

    for edge in graph["edges"]:
        if edge["kind"] != "orm-access":
            continue
        model = ids[edge["target"]]["name"]
        match = ACCESS_EVIDENCE.match(edge["evidence"])
        if not match:
            unverifiable.append({"evidence": edge["evidence"]})
            continue
        file, line = match.group("file"), int(match.group("line"))
        expression = match.group("expr")

        text = source.line(file, line)
        root_name = expression.split(".")[0]
        if text is None or root_name not in text:
            not_at_line.append(
                {"model": model, "file": file, "line": line, "expression": expression,
                 "source_line": (text or "")[:120]}
            )
            continue

        binding, origin = source.binding_of(file, root_name)
        declaring = model_files.get(model)
        if binding == "absent":
            wrong_symbol.append(
                {"model": model, "file": file, "line": line, "expression": expression,
                 "why": "the name is neither defined nor imported in this file",
                 "source_line": text.strip()[:120]}
            )
        elif binding == "imported" and declaring and origin:
            declaring_module = module_of(declaring)
            if not (declaring_module.endswith(origin) or origin.endswith(module_of(declaring).split(".")[-1])
                    or origin in declaring_module or declaring_module in origin):
                wrong_symbol.append(
                    {"model": model, "file": file, "line": line, "expression": expression,
                     "why": f"imported from {origin}, but the model is declared in {declaring}",
                     "source_line": text.strip()[:120]}
                )
            else:
                confirmed.append({"model": model, "file": file, "line": line})
        else:
            confirmed.append({"model": model, "file": file, "line": line})

    non_python = [row for row in confirmed + wrong_symbol + not_at_line
                  if not row["file"].endswith(".py")]
    return {
        "produced": sum(1 for e in graph["edges"] if e["kind"] == "orm-access"),
        "source_confirmed": len(confirmed),
        "wrong_symbol": wrong_symbol,
        "wrong_symbol_count": len(wrong_symbol),
        "not_at_cited_line": not_at_line,
        "unverifiable": len(unverifiable),
        # An OrmAccess whose site is a TypeScript file is a false positive by
        # construction: a Python ORM model cannot be used from TSX.
        "access_site_not_python": non_python,
        "access_site_not_python_count": len(non_python),
    }


# ── HttpCall edges and chains ────────────────────────────────────────

def score_http(graph, source):
    """Checks each HttpCall edge's two ends against source."""
    ids = nodes_by_id(graph)
    confirmed, endpoint_missing, unverifiable = [], [], []

    for edge in graph["edges"]:
        if edge["kind"] != "http-call":
            continue
        target = ids[edge["target"]]
        client_line = source.line(edge["file"], edge["line"])
        handler_line = None
        if target.get("file") and target.get("line"):
            handler_line = source.line(target["file"], target["line"])

        row = {
            "client": f"{edge['file']}:{edge['line']}",
            "target": target["name"],
            "target_at": f"{target.get('file')}:{target.get('line')}",
            "evidence": edge["evidence"],
            "confidence": edge["confidence"],
        }
        if client_line is None or handler_line is None:
            unverifiable.append(row)
        elif target["kind"] == "function":
            # The cited line is where the declaration starts. For a decorator
            # that is the `@` line, and the `def` it decorates can be many
            # lines below when the decorator spans several lines — Airflow
            # routinely writes twenty. Checking only the next line reported
            # 177 of Airflow's 199 endpoints as missing when every one of them
            # was present.
            window = "".join(
                source.lines(target["file"])[target["line"] - 1 : target["line"] + 40]
            )
            if re.search(rf"def\s+{re.escape(target['name'])}\s*\(", window):
                confirmed.append(row)
            else:
                endpoint_missing.append({**row, "source_line": handler_line.strip()[:120]})
        else:
            confirmed.append(row)

    return {
        "produced": sum(1 for e in graph["edges"] if e["kind"] == "http-call"),
        "endpoints_confirmed": len(confirmed),
        "endpoint_not_at_cited_location": endpoint_missing,
        "unverifiable": len(unverifiable),
        "sample": confirmed[:8],
    }


def score_chains(graph):
    """Walks the graph for file -> handler -> model -> table.

    A chain counts only when consecutive edges share a node id. Five correct
    edges that do not meet at the same handler are five edges, not a chain
    (PART 8).
    """
    ids = nodes_by_id(graph)
    out = defaultdict(list)
    for edge in graph["edges"]:
        out[edge["source"]].append(edge)

    chains, partial = [], defaultdict(int)
    for edge in graph["edges"]:
        if edge["kind"] != "http-call":
            continue
        handler = edge["target"]
        accesses = [e for e in out.get(handler, []) if e["kind"] == "orm-access"]
        if not accesses:
            partial["http_call_only"] += 1
            continue
        reached_table = False
        for access in accesses:
            queries = [e for e in out.get(access["target"], []) if e["kind"] == "queries"]
            for query in queries:
                reached_table = True
                chains.append(
                    {
                        "frontend": f"{ids[edge['source']]['name']}",
                        "handler": ids[handler]["name"],
                        "handler_node": handler,
                        "model": ids[access["target"]]["name"],
                        "table": ids[query["target"]]["name"],
                        "edges": [edge["id"], access["id"], query["id"]],
                        "confidences": [edge["confidence"], access["confidence"], query["confidence"]],
                    }
                )
        if not reached_table:
            partial["reached_model_not_table"] += 1

    return {
        "fully_verified": len(chains),
        "partial": dict(partial),
        "chains": chains[:25],
        "distinct_handlers_in_chains": len({c["handler_node"] for c in chains}),
    }


def edge_attribute_audit(graph):
    """Every edge must carry confidence, provenance, evidence and a location."""
    problems = []
    for edge in graph["edges"]:
        missing = [
            field
            for field in ("confidence", "provenance", "evidence", "file", "line")
            if edge.get(field) in (None, "", 0)
        ]
        # A confidence of exactly 0 is meaningful, a line of 0 is not.
        missing = [m for m in missing if not (m == "confidence" and edge.get("confidence") == 0.0)]
        if missing:
            problems.append({"edge": edge["id"], "missing": missing})
        if edge["provenance"] == "model-inference":
            problems.append({"edge": edge["id"], "missing": ["RULE 007: model inference"]})
    return problems


def metrics(tp, fp, fn):
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision and recall and (precision + recall)
        else None
    )
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
        "precision_denominator": tp + fp,
        "recall_denominator": tp + fn,
    }


# ── Checks against gaming the benchmark ──────────────────────────────
#
# The ten attacks of the M07 benchmark plan, each as a check that runs on every
# evaluation. A check guards against one way the numbers could be flattered,
# and records one of four outcomes:
#
#   passed     it ran, and found none of the condition it guards against;
#   violation  it ran, and found that condition;
#   error      it could not complete, because something it needs could not be
#              read;
#   not_run    there was nothing for it to examine.
#
# Only `passed` is a pass. The scorer exits 1 unless all ten passed, and writes
# the result either way, so the evidence of a failed run can be read.
#
# Until this change every check recorded `detected: true` whatever it found, so
# that field said only that the check existed. Evaluations written before then
# keep it; `recorded_outcome` reads their evidence instead.

PASSED = "passed"
VIOLATION = "violation"
ERROR = "error"
NOT_RUN = "not_run"


def _outcome(number, description, status, detail):
    return {"attack": number, "description": description, "status": status, "detail": detail}


def _found(problems):
    return VIOLATION if problems else PASSED


def check_scoring_inputs(integrity, ground_truth, subset_path):
    """1 — ground truth, scope or corpus edited after the fact.

    `main` refuses to score when this does not hold, so a run that reaches the
    check records the proof rather than discovering a failure.
    """
    return _outcome(
        1, "ground-truth or scope edited after measurement",
        PASSED if integrity["verified"] else VIOLATION,
        {"inputs_match_commit": integrity["verified"],
         "reference_commit": integrity["reference_commit"],
         "problems": integrity["problems"],
         "ground_truth_sha256": {n: sha256_file(p) for n, p in ground_truth["_paths"].items()},
         "supported_subset_sha256": sha256_file(subset_path),
         "note": "every ground-truth, scope and corpus file used was compared with the "
                 "blob committed at the reference commit before scoring began; a "
                 "difference, an extra file or a missing file stops the run"})


def check_raw_outputs(measurement, root=ROOT):
    """2 — analyser output edited between measuring and scoring.

    Both files the scorer reads are checked: the `match` output and the
    `normalize` output, from which route extraction is scored.
    """
    mismatched, checked = [], 0
    for row in measurement["repositories"]:
        if row["status"] != "OK":
            continue
        files = [(row["raw_path"], row["raw_sha256"])]
        if row.get("normalize", {}).get("raw_path"):
            files.append((row["normalize"]["raw_path"], row["normalize"].get("raw_sha256")))
        for relative, recorded in files:
            checked += 1
            path = os.path.join(root, relative)
            if not os.path.exists(path) or sha256_file(path) != recorded:
                mismatched.append({"repo": row["name"], "file": relative})
    return _outcome(
        2, "raw analyser output altered between measuring and scoring",
        NOT_RUN if checked == 0 else _found(mismatched),
        {"digest_mismatches": mismatched, "checked": checked})


def check_refusal_records(ground_truth):
    """3 — out-of-scope and refused cases left out of the ground truth."""
    missing = [name for name, gt in ground_truth["repos"].items()
               if not any(r["classification"] in ("UNSUPPORTED", "SAFE_REFUSAL")
                          for r in gt["route_declarations"] + gt["orm_declarations"])]
    return _outcome(
        3, "unsupported and refused cases omitted from ground truth",
        NOT_RUN if not ground_truth["repos"] else _found(missing),
        {"repositories_with_none": missing,
         "note": "a repository whose ground truth contains no out-of-scope and no "
                 "refusal record would be reporting only the cases that work"})


def check_declared_rules(subset, ground_truth):
    """4 — a miss reclassified as out of scope under a rule nobody declared."""
    valid = {e["id"] for e in subset["out_of_scope"]["entries"]} | {"OUT-9", "OUT-10"}
    valid_refusal = {e["id"] for e in subset["safe_refusal"]["entries"]}
    bad, examined = [], 0
    for name, gt in ground_truth["repos"].items():
        for record in gt["route_declarations"] + gt["orm_declarations"]:
            if record["classification"] == "UNSUPPORTED":
                examined += 1
                if record["rule"] not in valid:
                    bad.append({"repo": name, "id": record["id"], "rule": record["rule"]})
            if record["classification"] == "SAFE_REFUSAL":
                examined += 1
                if record["rule"] not in valid_refusal:
                    bad.append({"repo": name, "id": record["id"], "rule": record["rule"]})
    return _outcome(
        4, "a miss reclassified as out of scope without a declared rule",
        NOT_RUN if examined == 0 else _found(bad),
        {"records_citing_an_undeclared_rule": bad, "examined": examined})


def _scored(results):
    """Repositories that were actually scored, not merely listed."""
    return {name: repo for name, repo in results.items() if repo.get("status") == "OK"}


def check_denominators(ground_truth, results):
    """5 — the recall denominator quietly changed."""
    drift = []
    scored = _scored(results)
    for name, repo in scored.items():
        declared = sum(1 for r in ground_truth["repos"][name]["route_declarations"]
                       if r["classification"] == "IN_SCOPE")
        denominator = repo["routes"]["metrics"]["recall_denominator"]
        if declared != denominator:
            drift.append({"repo": name, "in_scope_records": declared,
                          "recall_denominator": denominator})
    return _outcome(
        5, "recall denominator not equal to the in-scope record count",
        NOT_RUN if not scored else _found(drift), {"drift": drift})


def check_queries_accounted(results):
    """6 — a false positive hidden in an unexamined bucket."""
    unaccounted = []
    scored = _scored(results)
    for name, repo in scored.items():
        q = repo["queries"]
        total = q["source_confirmed"] + len(q["source_contradicted"]) + q["source_unverifiable_count"]
        if total != q["produced"]:
            unaccounted.append({"repo": name, "produced": q["produced"], "accounted": total})
    return _outcome(
        6, "produced edges not fully accounted for",
        NOT_RUN if not scored else _found(unaccounted),
        {"unaccounted": unaccounted,
         "note": "every Queries edge must land in confirmed, contradicted or "
                 "unverifiable; unverifiable is reported, never discarded"})


def check_corpus_coverage(corpus, results):
    """7 — a difficult repository dropped from the corpus or left unscored.

    A repository counts as scored only if it was: one listed in the results
    with a status of MISSING or ANALYSIS_FAILED was not.
    """
    declared_names = {r["name"] for r in corpus["repositories"]}
    scored_names = set(_scored(results))
    required = {n for names in corpus["coverage_requirements"].values() for n in names}
    missing = sorted(declared_names - scored_names)
    unscored = sorted(required - scored_names)
    return _outcome(
        7, "a corpus entry removed or left unscored",
        NOT_RUN if not declared_names else _found(missing + unscored),
        {"declared": sorted(declared_names), "scored": sorted(scored_names),
         "missing_from_results": missing, "coverage_entries_unscored": unscored})


def check_empty_runs(measurement):
    """8 — a repository that produced nothing scoring as if it succeeded."""
    ok = [row for row in measurement["repositories"] if row["status"] == "OK"]
    empty = [row["name"] for row in ok
             if row["measurements"]["files_analysed"] == 0
             or row["measurements"]["backend_routes"] + row["measurements"]["client_calls"] == 0]
    return _outcome(
        8, "a repository that produced nothing scoring as if it succeeded",
        NOT_RUN if not ok else _found(empty),
        {"repositories_with_no_observations": empty})


def check_toolchain(measurement, live):
    """9 — benchmark metadata that does not describe the run.

    The toolchain the measurement recorded must be the one scoring sees, so
    scoring happens where measuring did. `live` is `rustc --version` now, or
    None when it could not be read.
    """
    recorded = measurement["toolchain"]["rustc"]
    if live is None:
        status = ERROR
    else:
        status = PASSED if live == recorded else VIOLATION
    return _outcome(
        9, "benchmark metadata that does not describe the run", status,
        {"rustc_recorded": recorded, "rustc_now": live, "agree": live == recorded,
         "cartograph_commit": measurement["toolchain"]["cartograph_commit"]})


def check_revisions(corpus, mirror):
    """10 — scored against a revision other than the pinned one."""
    wrong, unreadable = [], []
    for entry in corpus["repositories"]:
        head = revision_of(os.path.join(mirror, entry["name"]))
        if head is None:
            unreadable.append(entry["name"])
        elif head != entry["commit"]:
            wrong.append({"repo": entry["name"], "expected": entry["commit"], "actual": head})
    if not corpus["repositories"]:
        status = NOT_RUN
    else:
        status = VIOLATION if wrong else ERROR if unreadable else PASSED
    return _outcome(
        10, "evaluation run against a revision other than the pinned one", status,
        {"mismatched": wrong, "unreadable": unreadable})


def adversarial_checks(corpus, subset, subset_path, ground_truth, measurement, mirror, results,
                       integrity):
    """All ten checks, in order."""
    code, rustc = run("rustc", "--version")
    return [
        check_scoring_inputs(integrity, ground_truth, subset_path),
        check_raw_outputs(measurement),
        check_refusal_records(ground_truth),
        check_declared_rules(subset, ground_truth),
        check_denominators(ground_truth, results),
        check_queries_accounted(results),
        check_corpus_coverage(corpus, results),
        check_empty_runs(measurement),
        check_toolchain(measurement, rustc if code == 0 and rustc else None),
        check_revisions(corpus, mirror),
    ]


def summarize(checks):
    """{outcome: [attack numbers]} for every outcome, plus whether all passed."""
    summary = {status: [c["attack"] for c in checks if c["status"] == status]
               for status in (PASSED, VIOLATION, ERROR, NOT_RUN)}
    summary["all_passed"] = len(summary[PASSED]) == len(checks) == 10
    return summary


# How an evaluation written before outcomes were recorded is read: each check's
# own evidence, by the criterion that check now applies. The `detected` field
# those files carry was always true and is not consulted.
_RECORDED_CRITERIA = {
    1: lambda d: d.get("inputs_match_commit", d.get("working_tree_matches_commit")) is True,
    2: lambda d: d["digest_mismatches"] == [],
    3: lambda d: d["repositories_with_none"] == [],
    4: lambda d: d["records_citing_an_undeclared_rule"] == [],
    5: lambda d: d["drift"] == [],
    6: lambda d: d["unaccounted"] == [],
    7: lambda d: d["missing_from_results"] == [] and d["coverage_entries_unscored"] == [],
    8: lambda d: d["repositories_with_no_observations"] == [],
    9: lambda d: d["agree"] is True,
    10: lambda d: d["mismatched"] == [],
}


def recorded_outcome(check):
    """The outcome a recorded check supports: its own, or one read from its evidence."""
    if "status" in check:
        return check["status"]
    criterion = _RECORDED_CRITERIA.get(check["attack"])
    if criterion is None:
        return ERROR
    try:
        return PASSED if criterion(check["detail"]) else VIOLATION
    except (KeyError, TypeError):
        return ERROR


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=os.path.join(ROOT, "benchmarks/corpus.json"))
    parser.add_argument("--subset", default=os.path.join(ROOT, "benchmarks/supported-subset.json"))
    parser.add_argument("--ground-truth", default=os.path.join(ROOT, "benchmarks/ground-truth"))
    parser.add_argument("--measurement", required=True)
    parser.add_argument("--mirror", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    # Before anything is read or scored: a result computed against an altered
    # answer key is not a result, so none is written.
    integrity = verify_scoring_inputs(args.ground_truth, args.subset, args.corpus)
    if not integrity["verified"]:
        print("refusing to score: the scoring inputs do not match the committed ones",
              file=sys.stderr)
        for problem in integrity["problems"]:
            print(f"  {problem}", file=sys.stderr)
        return 1

    corpus = json.load(open(args.corpus, encoding="utf-8"))
    subset = json.load(open(args.subset, encoding="utf-8"))
    measurement = json.load(open(args.measurement, encoding="utf-8"))

    ground_truth = {"repos": {}, "_paths": {}}
    for path in sorted(glob.glob(os.path.join(args.ground_truth, "*.json"))):
        document = json.load(open(path, encoding="utf-8"))
        ground_truth["repos"][document["repository"]] = document
        ground_truth["_paths"][document["repository"]] = path

    results = {}
    for row in measurement["repositories"]:
        if row["status"] != "OK":
            results[row["name"]] = {"status": row["status"]}
            continue
        name = row["name"]
        gt = ground_truth["repos"][name]
        report = json.load(open(os.path.join(ROOT, row["raw_path"]), encoding="utf-8"))
        normalize = json.load(
            open(os.path.join(ROOT, row["normalize"]["raw_path"]), encoding="utf-8")
        )
        graph = report["graph"]
        source = Source(os.path.join(args.mirror, name))

        model_files = {
            n["name"]: n.get("file")
            for n in graph["nodes"]
            if n["kind"] == "class"
        }

        route_labels, produced_routes = score_routes(gt, normalize)
        queries = score_queries(gt, graph, source)
        access = score_orm_access(graph, source, model_files)
        http = score_http(graph, source)
        chains = score_chains(graph)

        q_gt = queries["ground_truth"]
        results[name] = {
            "status": "OK",
            "commit": row["commit"],
            "routes": {
                "produced_observations": produced_routes,
                "labels": {k: len(v) for k, v in route_labels.items()},
                "false_negatives": route_labels.get("FALSE_NEGATIVE", []),
                "metrics": metrics(
                    len(route_labels.get("TRUE_POSITIVE", [])),
                    0,
                    len(route_labels.get("FALSE_NEGATIVE", [])),
                ),
            },
            "queries": {
                **{k: v for k, v in queries.items() if k != "ground_truth"},
                "labels": {k: len(v) for k, v in q_gt.items()},
                "false_negatives": q_gt.get("FALSE_NEGATIVE", []),
                "false_positives": q_gt.get("FALSE_POSITIVE", []),
                "metrics": metrics(
                    len(q_gt.get("TRUE_POSITIVE", [])),
                    len(q_gt.get("FALSE_POSITIVE", [])) + len(queries["source_contradicted"]),
                    len(q_gt.get("FALSE_NEGATIVE", [])),
                ),
            },
            "orm_access": access,
            "http_call": http,
            "chains": chains,
            "edge_attribute_problems": edge_attribute_audit(graph),
            "must_not_produce": [
                {
                    **assertion,
                    "violated": any(
                        n["kind"] == "class" and n["name"] == assertion["model"]
                        and any(e["kind"] == "queries" and e["source"] == n["id"]
                                for e in graph["edges"])
                        for n in graph["nodes"]
                    ),
                }
                for assertion in gt["must_not_produce"]
            ],
        }

    checks = adversarial_checks(
        corpus, subset, args.subset, ground_truth, measurement, args.mirror, results, integrity
    )
    summary = summarize(checks)

    document = {
        # /2: each adversarial check records its outcome in `status`, and the
        # always-true `detected` field of /1 is gone.
        "schema": "cartograph.benchmark-result/2",
        "milestone": "M07",
        "status": "INTERNAL — methodology is not yet stable; these numbers are not for publication",
        "pass": measurement["pass"],
        "toolchain": measurement["toolchain"],
        "corpus_sha256": measurement["corpus_sha256"],
        "supported_subset_sha256": sha256_file(args.subset),
        "ground_truth_sha256": {n: sha256_file(p) for n, p in ground_truth["_paths"].items()},
        "denominators": subset["denominators"],
        "repositories": results,
        "adversarial_checks": checks,
        "adversarial_summary": summary,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(document, open(args.out, "w", encoding="utf-8"), indent=2, sort_keys=True)
    print(f"wrote {args.out}", file=sys.stderr)

    # The result is written either way, so a failed run's evidence can be read;
    # it is only a pass if every check ran and found nothing.
    if not summary["all_passed"]:
        print(f"adversarial checks did not all pass: {len(summary[PASSED])} passed; "
              f"violation {summary[VIOLATION]}, error {summary[ERROR]}, "
              f"not run {summary[NOT_RUN]}", file=sys.stderr)
        return 1
    print(f"adversarial checks: {len(summary[PASSED])} of 10 passed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
