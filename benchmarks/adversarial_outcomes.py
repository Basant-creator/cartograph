#!/usr/bin/env python3
"""What each recorded adversarial check found, read from its evidence.

Evaluations written before the scorer recorded outcomes carry `detected: true`
on every check, whatever the check found, so that field cannot be counted. This
reads each check's evidence by the criterion `evaluate.py` now applies, and
reports how many of the ten passed. Read-only: it never rewrites a result.

    python3 benchmarks/adversarial_outcomes.py benchmarks/acceptance/m07-acceptance-evaluation.json

Exit status 0 when every file's ten checks all passed, 1 otherwise.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import evaluate as E  # noqa: E402


def outcomes(document):
    """[(attack, outcome)] for one evaluation, in attack order."""
    return sorted((c["attack"], E.recorded_outcome(c)) for c in document["adversarial_checks"])


def main(paths):
    if not paths:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        return 2
    every_file_passed = True
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            document = json.load(handle)
        found = outcomes(document)
        passed = sum(1 for _, outcome in found if outcome == E.PASSED)
        complete = [attack for attack, _ in found] == list(range(1, 11))
        every_file_passed &= passed == 10 and complete
        print(f"{path}: pass {document.get('pass')}: {passed} of {len(found)} passed")
        for attack, outcome in found:
            if outcome != E.PASSED:
                print(f"  {attack:>2}  {outcome}")
        if not complete:
            print("  the ten checks are not all recorded")
    return 0 if every_file_passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
