#!/usr/bin/env python3
"""Compare what two analyser runs produced, relationship by relationship.

Totals cannot say where two runs part company: 28 fewer client calls could be
one file or twenty-eight. This reads two `cartograph match --json` documents -
or one of them and the M08 dataset, which records every edge the accepted
engine produced on the corpus - and reports every difference, sorted, with the
first one in path order and a per-file count.

What is compared:

  * edges, as (kind, file:line, confidence, provenance), and between two `match`
    documents also the (kind, name, file) identity of each edge's source and
    target - the identity `cartograph diff` uses - so an edge from the same call
    site to a different handler is a difference;
  * edge numbering: whether each edge also has the same id on both sides;
  * client calls, as (file, line, route, status) from `matches`, so a call
    matched on one side and refused on the other is a difference - `match`
    documents only, because the M08 dataset records edges, not calls.

The M08 dataset records no edge endpoints, so against it an edge is compared by
kind, location, confidence and provenance, with its numbering: what the dataset
holds, and nothing it does not.

Edge ids are graph-local (ADR-0011): removing one edge renumbers every edge
after it, so ids are no part of an edge's identity when locating a divergence.
Identical numbering is still required for two runs to count as identical, which
is the right bar for the same code on two platforms.

Nothing meaningful is normalised away. `elapsed_ms` is never read. Confidence is
rounded to six decimals only when one side is the M08 dataset, because
`m08/label_edges.py` wrote it that way: 0.78400004 there reads 0.784.

Exit status 0 when the runs agree, 1 when they differ, 2 on bad input.
Standard library only, like the rest of benchmarks/.

    python3 benchmarks/compare_edges.py windows.json macos.json
    python3 benchmarks/compare_edges.py posthog.json \\
        --m08 benchmarks/m08/results/dataset.json --repository posthog
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

# Decimal places `m08/label_edges.py` rounds confidence to.
M08_CONFIDENCE_PLACES = 6


def edges_of_match(document, places=None, numbered=False, endpoints=False):
    """The edge multiset of a `match --json` document.

    `endpoints` adds the (kind, name, file) identity of the edge's source and
    target nodes; `numbered` adds the edge's graph-local id.
    """
    nodes = {}
    if endpoints:
        nodes = {n["id"]: (n["kind"], n["name"], n.get("file"))
                 for n in document["graph"]["nodes"]}
    out = Counter()
    for edge in document["graph"]["edges"]:
        confidence = edge["confidence"]
        if places is not None:
            confidence = round(confidence, places)
        key = (edge["kind"], f"{edge['file']}:{edge['line']}", confidence, edge["provenance"])
        if endpoints:
            key += (nodes[edge["source"]], nodes[edge["target"]])
        out[key + (edge["id"],) if numbered else key] += 1
    return out


def edges_of_m08(dataset, repository, numbered=False):
    """The edge multiset the M08 dataset records for one repository."""
    out = Counter()
    for record in dataset["records"]:
        if record["repository"] == repository:
            key = (record["kind"], record["at"], record["confidence"], record["provenance"])
            out[key + (record["edge"],) if numbered else key] += 1
    return out


def calls_of_match(document):
    """The client-call multiset of a `match --json` document."""
    return Counter((m["client_file"], m["client_line"], m["client_route"], m["status"])
                   for m in document["matches"])


def location(item):
    """(path, line) of an edge or call key, for ordering and per-file counts."""
    if isinstance(item[1], str) and ":" in item[1]:  # an edge: kind, "file:line", ...
        path, _, line = item[1].rpartition(":")
        return path, int(line) if line.isdigit() else 0
    return item[0], item[1]  # a call: file, line, route


def difference(left, right):
    """Everything only on one side, in path order, with per-file counts."""
    only_left = sorted((left - right).elements(), key=lambda k: (location(k), repr(k)))
    only_right = sorted((right - left).elements(), key=lambda k: (location(k), repr(k)))
    first = min(
        [("left", k) for k in only_left[:1]] + [("right", k) for k in only_right[:1]],
        key=lambda side_key: (location(side_key[1]), repr(side_key[1])),
        default=None,
    )
    per_file = Counter(location(k)[0] for k in only_left)
    per_file_right = Counter(location(k)[0] for k in only_right)
    files = sorted(set(per_file) | set(per_file_right))
    return {
        "left": sum(left.values()),
        "right": sum(right.values()),
        "only_left": [list(k) for k in only_left],
        "only_right": [list(k) for k in only_right],
        "first_divergence": None if first is None else {"side": first[0], "item": list(first[1])},
        "per_file": [{"file": f, "only_left": per_file[f], "only_right": per_file_right[f]}
                     for f in files],
    }


def compare(left, right=None, dataset=None, repository=None):
    """The comparison report for a `match` document against another or the dataset."""
    if dataset is not None:
        places = M08_CONFIDENCE_PLACES
        report = {"edges": difference(edges_of_match(left, places),
                                      edges_of_m08(dataset, repository))}
        numbering = (edges_of_match(left, places, numbered=True)
                     == edges_of_m08(dataset, repository, numbered=True))
    else:
        report = {"edges": difference(edges_of_match(left, endpoints=True),
                                      edges_of_match(right, endpoints=True)),
                  "client_calls": difference(calls_of_match(left), calls_of_match(right))}
        numbering = (edges_of_match(left, numbered=True, endpoints=True)
                     == edges_of_match(right, numbered=True, endpoints=True))
    same_content = all(not part["only_left"] and not part["only_right"]
                       for part in report.values())
    report["edge_numbering_identical"] = numbering
    report["identical"] = same_content and numbering
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("left", help="a `cartograph match --json` document")
    parser.add_argument("right", nargs="?", help="another `match --json` document")
    parser.add_argument("--m08", help="compare against this M08 dataset instead")
    parser.add_argument("--repository", help="the corpus name to take from --m08")
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    args = parser.parse_args(argv)
    if (args.right is None) == (args.m08 is None) or (args.m08 and not args.repository):
        parser.error("give either a second document, or --m08 with --repository")

    with open(args.left, encoding="utf-8") as handle:
        left = json.load(handle)
    if args.m08:
        with open(args.m08, encoding="utf-8") as handle:
            dataset = json.load(handle)
        if not any(r["repository"] == args.repository for r in dataset["records"]):
            print(f"the dataset records no edge for {args.repository}", file=sys.stderr)
            return 2
        report = compare(left, dataset=dataset, repository=args.repository)
    else:
        with open(args.right, encoding="utf-8") as handle:
            report = compare(left, json.load(handle))

    if args.json:
        json.dump(report, sys.stdout, indent=2)
        print()
    else:
        for name, part in report.items():
            if not isinstance(part, dict):
                continue
            print(f"{name}: {part['left']} left, {part['right']} right, "
                  f"{len(part['only_left'])} only left, {len(part['only_right'])} only right")
            if part["first_divergence"]:
                print(f"  first divergence ({part['first_divergence']['side']}): "
                      f"{part['first_divergence']['item']}")
            for row in part["per_file"]:
                print(f"    {row['only_left']:>5} {row['only_right']:>5}  {row['file']}")
        print(f"edge numbering identical: {report['edge_numbering_identical']}")
        print("identical" if report["identical"] else "DIFFERENT")
    return 0 if report["identical"] else 1


if __name__ == "__main__":
    sys.exit(main())
