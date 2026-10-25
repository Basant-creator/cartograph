# Cross-platform parity: the corpus on Windows and macOS

**Finding.** At the accepted M07 engine, `cartograph-m07` (`2514f77`), the
analyser produces the same relationships on Windows as the M08 dataset records
from macOS, edge for edge, in all seven corpus repositories. An apparent
PostHog difference of 28 client calls and one `HttpCall` edge was not a
platform difference. It came from comparing against the M07 acceptance run,
which was measured on a tree one pull request older than the accepted commit.

This page records how that was established, and what it does not establish.

## The question

A Windows benchmark run in October 2026 compared its PostHog figures with
[`benchmarks/acceptance/m07-acceptance-measurements.json`](../../benchmarks/acceptance/m07-acceptance-measurements.json)
and found them lower:

| | Acceptance run (macOS) | Windows |
|---|---:|---:|
| Client calls | 18,671 | 18,643 |
| `HttpCall` edges | 911 | 910 |

The other six repositories matched exactly. Line endings, symlinks and file-name
case were checked first and explained nothing.

## What the acceptance run measured

That file records `cartograph_commit` `7986348`, the PR #10 merge, with
`cartograph_tree_clean: false`. The accepted commit came after two
acceptance-audit pull requests, #12 and #13, both of which change what the
TypeScript extractor counts as a request. The
[technical writeup](../writeup/technical-writeup.md) already notes this, and
that only the M08 results describe the accepted engine.

Each of those commits was built on Windows and run on PostHog at its pinned
commit. Each reproduces a recorded macOS measurement exactly:

| Commit, built on Windows | Client calls | `HttpCall` | `Call` | All edges | Reproduces |
|---|---:|---:|---:|---:|---|
| `7986348` | 18,675 | 912 | 226 | 7,876 | [`remediation/final-measurements.json`](../../benchmarks/remediation/final-measurements.json), pass 8 |
| `7a3e8a5`, after #12 | 18,671 | 911 | 227 | 7,876 | [`acceptance/m07-acceptance-measurements.json`](../../benchmarks/acceptance/m07-acceptance-measurements.json), pass 9 |
| `2514f77`, after #13: the accepted tag | 18,643 | 910 | 224 | 7,872 | [`m08/results/dataset.json`](../../benchmarks/m08/results/dataset.json) |

So the acceptance run's uncommitted change was, in effect, #12. The figures
match on five measures each, which identifies the tree's behaviour on PostHog
but not every byte of it.

## What #13 removed

Comparing `7a3e8a5` with `2514f77` on PostHog, both on Windows, gives 28 client
calls and four edges present only before, and nothing present only after:

| Client calls removed | File |
|---:|---|
| 22 | `nodejs/src/cdp/cdp-api.ts` |
| 2 | `nodejs/src/common/api/router.ts` |
| 1 each | `nodejs/src/common/utils/commands.ts`, `.../ml-mirror-image-scrub-sidecar/src/server.ts`, `nodejs/src/session-replay/recording-api/recording-api.ts`, `services/mcp/src/hono/public-routes.ts` |

All 28 are route registrations in PostHog's Node and Hono services —
`router.post(...)`, `app.get(...)` — and each passes an argument that is a
call, such as `asyncHandler(this.postCommand())`, `buildGetHealth(services)` or
`express.raw(...)`. #13 recognises a call argument as a handler, so these stopped
being read as requests. One of them,
`router.ts:43`, registers `GET /_health` and had been matched to a Python health
endpoint in `services/stripe-mock`: the removed `HttpCall` edge is that false
match. The other three removed edges are `Call` edges.

## Windows against macOS, edge by edge

The M08 dataset lists every edge the accepted engine produced on the corpus on
macOS, with its kind, location, id, confidence and provenance. The same commit
on Windows was compared with it using
[`benchmarks/compare_edges.py`](../../benchmarks/compare_edges.py):

| Repository | Edges | Identical, including numbering |
|---|---:|---|
| Superset | 663 | yes |
| full-stack-fastapi | 1 | yes |
| Onyx | 1,076 | yes |
| PostHog | 7,872 | yes |
| Zulip | 1,469 | yes |
| Airflow | 3,350 | yes |
| AutoGPT | 501 | yes |

That is 14,932 of 14,932. The only representational difference is that the
labeller wrote confidence rounded to six decimals, so the engine's `0.78400004`
is recorded as `0.784`; the comparison applies the same rounding to the Windows
side and to nothing else.

## What this does not establish

- **macOS was not re-run.** The macOS side is the committed M08 dataset and the
  committed measurements. The comparison is between a Windows run today and
  macOS results recorded at M07 and M08.
- **Client calls were compared across platforms only in total.** The M08
  dataset records edges, not calls, and no per-call macOS record is committed.
- **One Windows machine**, `x86_64-pc-windows-msvc`. Linux was not compared, and
  neither were timing or memory.
- **The M07-era binaries needed a larger stack on Windows.** Before #74 the
  extractor walk overflowed Windows' 1 MiB main thread on PostHog, so those
  three commits were run as copies whose only change is an 8 MiB stack
  reservation in the executable header. #74 shows, on all seven repositories,
  that the stack size does not change what is extracted.

## Reproducing it

The pinned checkouts live outside this repository, at the commits in
[`benchmarks/corpus.json`](../../benchmarks/corpus.json). On any platform:

```bash
git worktree add ../cartograph-m07 cartograph-m07
cargo build --release -p cartograph-cli --manifest-path ../cartograph-m07/Cargo.toml
../cartograph-m07/target/release/cartograph match --json <checkouts>/posthog > posthog.json
python3 benchmarks/compare_edges.py posthog.json \
    --m08 benchmarks/m08/results/dataset.json --repository posthog
```

Exit status 0 means the run agrees with the M08 dataset edge for edge, numbering
included; 1 means it does not, and the report lists every difference in path
order with the first one first. Two `match --json` documents can be compared
directly, client calls included:

```bash
python3 benchmarks/compare_edges.py before.json after.json
```

On Windows, before #74, the M07-era binary aborts on PostHog unless its stack
reservation is raised, for example with MSVC's
`editbin /STACK:8388608 cartograph.exe`.
