<script setup lang="ts">
// The site's home page. Every statement on it is taken from the README and the
// documentation, and every figure is one the README already publishes from
// committed benchmark results, with the same scope and caveats. Nothing here
// describes behaviour the code does not have.

import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { withBase } from 'vitepress'
import HalftoneField from './HalftoneField.vue'

const REPO = 'https://github.com/Rexy-5097/cartograph'

/** A page on this site. Directory paths end in `/`; any other gets `.html`. */
const page = (path: string, hash = '') => withBase((path.endsWith('/') ? path : `${path}.html`) + hash)
/** A file in the repository, on GitHub. */
const repo = (path: string) => `${REPO}/blob/main/${path}`

const menu = [
  { text: 'Technical writeup', href: page('/writeup/technical-writeup') },
  { text: 'Resolver', href: page('/resolver/') },
  { text: 'Benchmarks', href: page('/benchmarks/') },
  { text: 'Architecture', href: page('/architecture/') },
  { text: 'Decisions', href: page('/adr/') },
  { text: 'Command line', href: page('/development/cli') },
  { text: 'Releases', href: page('/releases/') },
]

const surfaces = [
  {
    key: 'CLI',
    title: 'The command line',
    tag: 'cartograph . · trace · blast · diff',
    body: 'What a repository contains, how one relationship crosses the stack, what depends on an artefact, and what a change did to the architecture.',
    link: { text: 'Command-line reference', href: page('/development/cli') },
    tone: 'black',
  },
  {
    key: 'MAP',
    title: 'MAP — the desktop application',
    tag: 'Tauri · Sigma',
    body: 'Draws the architecture graph and shows the evidence behind any edge.',
    link: { text: 'The desktop boundary', href: page('/adr/ADR-0016-desktop-boundary') },
    tone: 'green',
  },
  {
    key: 'MCP',
    title: 'cartograph-mcp',
    tag: 'map · trace · blast · diff',
    body: 'An MCP server exposing the same graph over one repository identity, granted when it is launched.',
    link: { text: 'MCP boundary and authorization', href: page('/adr/ADR-0020-mcp-boundary-and-authorization') },
    tone: 'pink',
  },
  {
    key: 'PR review',
    title: 'Pull-request review',
    tag: 'cartograph diff --markdown',
    body: 'A workflow that posts what a change did to the architecture as a pull-request comment. It is configured for this repository’s own pull requests; no reusable action is published.',
    link: { text: 'cartograph diff', href: page('/development/cli', '#cartograph-diff-before-after') },
    tone: 'light',
  },
  {
    key: 'ASK',
    title: 'ASK — explanation over evidence',
    tag: 'Opt-in per repository',
    body: 'Explains already-derived evidence, and every claim must cite that evidence verbatim. No in-product way to supply an API key ships yet, so in practice it shows the evidence unexplained.',
    link: { text: 'The citation contract', href: page('/adr/ADR-0021-ask-boundary-and-citation-contract') },
    tone: 'khaki',
  },
]

const steps = [
  {
    title: 'Parse',
    body: 'tree-sitter reads TypeScript, TSX and Python: symbols, imports, calls, HTTP requests, route declarations, and ORM models with the tables they name. Only the source under the path it is given — not Git history, not a database.',
    href: page('/architecture/parser'),
  },
  {
    title: 'Resolve',
    body: 'Dynamically built URLs are partially evaluated, four route-declaration dialects are normalised to one shape, client calls are matched to the handlers that serve them, and models to their tables. Every stage is deterministic.',
    href: page('/resolver/'),
  },
  {
    title: 'Prove',
    body: 'Every edge carries its provenance, a confidence and the evidence for it. An ambiguous match produces no edge; a segment that cannot be determined statically stays {unknown}.',
    href: page('/graph/'),
  },
]

const principles = [
  {
    title: 'No model in the graph',
    body: 'No language model constructs graph structure — not as a fallback, not as a hint, not behind a flag. A model may explain a finished subgraph, and nothing else.',
    href: page('/adr/ADR-0007-no-llm-graph-construction'),
    link: 'ADR-0007',
    tone: 'green',
  },
  {
    title: 'Refuse rather than guess',
    body: 'Ambiguous candidates produce no edge, a prefix that cannot be determined statically stays {unknown}, and a call to an absolute host is never joined to a local route.',
    href: page('/resolver/matching'),
    link: 'Matching',
    tone: 'pink',
  },
  {
    title: 'Evidence is first-class',
    body: 'Cartograph stores the claim and how it was known. The domain model will not construct an edge without its provenance, confidence and evidence.',
    href: page('/adr/ADR-0004-evidence-first-class'),
    link: 'ADR-0004',
    tone: 'light',
  },
  {
    title: 'No unmeasured number',
    body: 'No accuracy or performance claim without a benchmark run on this codebase, and failures are published alongside successes.',
    href: page('/benchmarks/'),
    link: 'Benchmarks',
    tone: 'khaki',
  },
  {
    title: 'Local-first',
    body: 'No source code leaves the machine. AI is opt-in per repository and off by default; Cartograph is fully useful with no API key and no network.',
    href: page('/security/'),
    link: 'Security',
    tone: 'black',
  },
]

const corpus = ['Superset', 'PostHog', 'Zulip', 'Onyx', 'Airflow', 'AutoGPT', 'Full-stack FastAPI']

const install = `cargo install --git https://github.com/Rexy-5097/cartograph cartograph-cli
cartograph .`

const trace = `$ cartograph trace enqueueConnectionTest

enqueueConnectionTest  (function)  .../ui/openapi-gen/requests/services.gen.ts:834
  │
  ↓ HTTP-CALL   confidence 0.98   provenance route-matcher
  │   evidence   POST /api/v2/connections/enqueue-test matched POST /api/v2/connections/enqueue-test
  │              at .../routes/public/connections.py:383 (enqueue_connection_test);
  │              exact HTTP method; every path segment static and equal
  │
enqueue_connection_test  (function)  .../core_api/routes/public/connections.py:383
  │
  ↓ ORM-ACCESS   confidence 0.80   provenance orm-resolution
  │   evidence   ConnectionTestRequest(...) in enqueue_connection_test at .../connections.py:427
  │
ConnectionTestRequest  (class)  .../airflow/models/connection_test.py:82
  │
  ↓ QUERIES   confidence 0.80   provenance orm-resolution
  │   evidence   ConnectionTestRequest maps to table "connection_test_request"
  │
connection_test_request  (table)

This path crosses the HTTP boundary and reaches a database table.`

const root = ref<HTMLElement | null>(null)
const menuButton = ref<HTMLButtonElement | null>(null)
const menuOpen = ref(false)
const scrolled = ref(false)
const surface = ref(0)
const principle = ref(0)
/** The viewer paused the page's looping motion. */
const still = ref(false)

const cleanups: Array<() => void> = []

watch(menuOpen, async (open) => {
  document.documentElement.style.overflow = open ? 'hidden' : ''
  await nextTick()
  if (open) root.value?.querySelector<HTMLAnchorElement>('.cg-menu a')?.focus()
  else menuButton.value?.focus()
})

onMounted(() => {
  const el = root.value
  if (!el) return
  el.classList.add('cg-js')

  const onScroll = () => {
    scrolled.value = window.scrollY > 24
  }
  onScroll()
  window.addEventListener('scroll', onScroll, { passive: true })
  cleanups.push(() => window.removeEventListener('scroll', onScroll))

  const onKey = (e: KeyboardEvent) => {
    if (e.key === 'Escape' && menuOpen.value) menuOpen.value = false
  }
  window.addEventListener('keydown', onKey)
  cleanups.push(() => window.removeEventListener('keydown', onKey))

  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        entry.target.classList.add('is-in')
        io.unobserve(entry.target)
      }
    },
    { rootMargin: '0px 0px -8% 0px' },
  )
  el.querySelectorAll('[data-reveal]').forEach((node) => io.observe(node))
  cleanups.push(() => io.disconnect())
})

onBeforeUnmount(() => {
  document.documentElement.style.overflow = ''
  cleanups.forEach((fn) => fn())
})
</script>

<template>
  <div ref="root" class="cg" :class="{ 'is-still': still }">
    <!-- Header -->
    <header class="cg-header" :class="{ 'is-solid': scrolled || menuOpen }">
      <a class="cg-logo" :href="withBase('/')" aria-label="Cartograph — home">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="5" cy="12" r="2.6" />
          <circle cx="19" cy="5" r="2.6" />
          <circle cx="19" cy="19" r="2.6" />
          <path d="M7.4 10.8 16.6 6.2M7.4 13.2l9.2 4.6" />
        </svg>
        <span>Cartograph</span>
      </a>
      <button
        ref="menuButton"
        class="cg-menu-button"
        type="button"
        :aria-expanded="menuOpen"
        aria-controls="cg-menu"
        @click="menuOpen = !menuOpen"
      >
        <span>{{ menuOpen ? 'Close' : 'Menu' }}</span>
        <i class="cg-plus" :class="{ 'is-open': menuOpen }" aria-hidden="true" />
      </button>
    </header>

    <Transition name="cg-menu">
      <nav v-show="menuOpen" id="cg-menu" class="cg-menu" aria-label="Site">
        <ol class="cg-menu-list">
          <li v-for="(item, i) in menu" :key="item.text">
            <a :href="item.href" @click="menuOpen = false">
              <small>{{ String(i + 1).padStart(2, '0') }}</small>
              {{ item.text }}
            </a>
          </li>
        </ol>
        <div class="cg-menu-aside">
          <div>
            <p class="cg-label">Source</p>
            <a class="cg-menu-small" :href="REPO">github.com/Rexy-5097/cartograph</a>
          </div>
          <div>
            <p class="cg-label">Install</p>
            <pre class="cg-menu-code"><code>{{ install }}</code></pre>
          </div>
          <div>
            <p class="cg-label">Status</p>
            <p class="cg-menu-small">v0.1.0 · M00–M16 accepted · M17 in progress</p>
          </div>
        </div>
      </nav>
    </Transition>

    <!-- While the menu is open, only the header and the menu take focus. -->
    <main :inert="menuOpen || undefined">
      <!-- Hero -->
      <section class="cg-hero">
        <h1 class="cg-hero-title">
          <span class="cg-hero-left">
            <span class="cg-line"><span style="--d: 0.05s">Compute the</span></span>
            <span class="cg-line"><span style="--d: 0.15s">architecture</span></span>
          </span>
          <span class="cg-hero-right">
            <span class="cg-line"><span style="--d: 0.3s">Prove the</span></span>
            <span class="cg-line"><span style="--d: 0.4s">relationships</span></span>
          </span>
        </h1>
        <div class="cg-hero-foot">
          <span>Local-first architectural intelligence</span>
          <span>TypeScript · TSX · Python</span>
          <span>v0.1.0 · M17 in progress</span>
        </div>
      </section>

      <!-- Statement -->
      <section class="cg-intro">
        <h2 class="cg-statement" data-reveal>
          A local-first engine that derives a cross-language architecture graph from source, and
          shows the evidence behind every edge it draws.
        </h2>
        <div class="cg-intro-side" data-reveal>
          <p>
            Cartograph reads a repository’s TypeScript, TSX and Python — symbols, imports, calls,
            HTTP requests, route declarations and ORM models — and joins them across languages that
            share no symbol table. One analysis core serves a CLI, a desktop application, an MCP
            server and a pull-request review workflow.
          </p>
          <a class="cg-button" :href="page('/writeup/technical-writeup')">
            <i aria-hidden="true">+</i>Read the writeup
          </a>
        </div>
        <div class="cg-badge" aria-hidden="true">
          <svg viewBox="0 0 120 120">
            <defs>
              <path id="cg-badge-ring" d="M60 60m-46 0a46 46 0 1 1 92 0a46 46 0 1 1-92 0" />
            </defs>
            <text>
              <textPath href="#cg-badge-ring">No model in the graph · Evidence on every edge ·</textPath>
            </text>
          </svg>
          <svg class="cg-badge-mark" viewBox="0 0 24 24">
            <circle cx="5" cy="12" r="2.6" />
            <circle cx="19" cy="5" r="2.6" />
            <circle cx="19" cy="19" r="2.6" />
            <path d="M7.4 10.8 16.6 6.2M7.4 13.2l9.2 4.6" />
          </svg>
        </div>
      </section>

      <!-- Manilla sheet: surfaces, approach, field -->
      <div class="cg-sheet">
        <section class="cg-section">
          <div class="cg-head" data-reveal>
            <div>
              <p class="cg-label">Surfaces</p>
              <h2 class="cg-h">One analysis core.<br />Five surfaces.</h2>
            </div>
            <a class="cg-button" :href="page('/releases/v0.1.0')">
              <i aria-hidden="true">+</i>Install and commands
            </a>
          </div>

          <div class="cg-acc" data-reveal>
            <article
              v-for="(s, i) in surfaces"
              :key="s.key"
              class="cg-acc-item"
              :class="[`tone-${s.tone}`, { 'is-open': surface === i }]"
            >
              <button
                class="cg-acc-strip"
                type="button"
                :aria-expanded="surface === i"
                :aria-controls="`cg-surface-${i}`"
                @click="surface = i"
              >
                <span class="cg-acc-strip-label">{{ s.key }}</span>
                <i aria-hidden="true">+</i>
              </button>
              <div :id="`cg-surface-${i}`" class="cg-acc-panel" :hidden="surface !== i">
                <div class="cg-acc-top">
                  <h3>{{ s.title }}</h3>
                  <span class="cg-index">{{ String(i + 1).padStart(2, '0') }}</span>
                </div>
                <div class="cg-acc-bottom">
                  <p class="cg-acc-tag">{{ s.tag }}</p>
                  <p>{{ s.body }}</p>
                  <a class="cg-button" :href="s.link.href"><i aria-hidden="true">+</i>{{ s.link.text }}</a>
                </div>
              </div>
            </article>
          </div>
        </section>

        <section class="cg-section">
          <div class="cg-head" data-reveal>
            <div>
              <p class="cg-label">How it works</p>
              <h2 class="cg-h">Source in. Evidence out.</h2>
            </div>
          </div>
          <div class="cg-steps" data-reveal>
            <a v-for="(s, i) in steps" :key="s.title" class="cg-step" :href="s.href">
              <div class="cg-step-top">
                <h3>{{ s.title }}</h3>
                <span class="cg-index">{{ String(i + 1).padStart(2, '0') }}</span>
              </div>
              <p>{{ s.body }}</p>
              <svg v-if="i === 0" class="cg-step-icon" viewBox="0 0 120 120" aria-hidden="true">
                <rect x="52" y="14" width="16" height="12" />
                <path d="M60 26v16M24 42h72M24 42v14M60 42v14M96 42v14" />
                <rect x="16" y="56" width="16" height="12" />
                <rect x="52" y="56" width="16" height="12" />
                <rect x="88" y="56" width="16" height="12" />
                <path d="M60 68v14M44 82h32M44 82v12M76 82v12" />
                <rect x="36" y="94" width="16" height="12" />
                <rect x="68" y="94" width="16" height="12" />
              </svg>
              <svg v-else-if="i === 1" class="cg-step-icon" viewBox="0 0 120 120" aria-hidden="true">
                <path d="M60 10v100" stroke-dasharray="3 5" />
                <circle cx="26" cy="60" r="14" />
                <circle cx="94" cy="60" r="14" />
                <path d="M38 52c10-22 34-22 44 0" />
                <path d="M76 46l6 6 3-8" />
                <path d="M20 60h12M88 54v12M82 60h12" />
              </svg>
              <svg v-else class="cg-step-icon" viewBox="0 0 120 120" aria-hidden="true">
                <path d="M14 30V14h16M90 14h16v16M106 90v16H90M30 106H14V90" />
                <rect x="32" y="32" width="56" height="56" />
                <path d="M32 32l56 56" stroke-dasharray="3 5" />
                <path d="M46 62l10 10 20-24" />
              </svg>
            </a>
          </div>
        </section>

        <section class="cg-field">
          <HalftoneField variant="field" dot="#aaa58c" cross="#222222" :paused="still" />
          <p class="cg-field-caption cg-label">
            Deterministic analysis first. Evidence second. Inference third. The model last, and
            never in the graph.
          </p>
        </section>
      </div>

      <!-- Proof -->
      <section class="cg-proof cg-section">
        <div class="cg-head" data-reveal>
          <div>
            <p class="cg-label">Real output</p>
            <h2 class="cg-h">One relationship,<br />all the way down.</h2>
          </div>
          <a class="cg-button" :href="page('/benchmarks/')">
            <i aria-hidden="true">+</i>All benchmarks
          </a>
        </div>

        <div class="cg-proof-stage">
          <figure class="cg-terminal" data-reveal>
            <div class="cg-terminal-bar" aria-hidden="true"><i /><i /><i /></div>
            <pre><code>{{ trace }}</code></pre>
            <figcaption>
              Apache Airflow at commit 9b43d6a. Directory paths are shortened to “...” and the
              per-hop observed line is omitted; everything else is verbatim.
            </figcaption>
          </figure>

          <div class="cg-feature tone-light" data-reveal>
            <span class="cg-tag">Apache Airflow · 9b43d6a</span>
            <h3>A TypeScript function to a database table, across three languages.</h3>
            <p>
              An HTTP boundary, a Python handler and a SQLAlchemy model, with no shared symbol table
              — and every hop carries the evidence for itself.
            </p>
            <a class="cg-button" :href="page('/resolver/')">
              <i aria-hidden="true">+</i>How the resolver works
            </a>
          </div>

          <div class="cg-feature-row">
            <a class="cg-feature cg-feature--small tone-khaki" :href="page('/benchmarks/m07-report')" data-reveal>
              <span class="cg-tag">Benchmarks</span>
              <h3>M07 — validation against seven production repositories</h3>
              <span class="cg-button"><i aria-hidden="true">+</i>Read more</span>
            </a>
            <a class="cg-feature cg-feature--small tone-pink" :href="page('/benchmarks/cross-platform-parity')" data-reveal>
              <span class="cg-tag">Benchmarks</span>
              <h3>Cross-platform parity</h3>
              <span class="cg-button"><i aria-hidden="true">+</i>Read more</span>
            </a>
          </div>
        </div>
      </section>

      <!-- Measured -->
      <section class="cg-measured cg-section">
        <div class="cg-head" data-reveal>
          <div>
            <p class="cg-label">Measured</p>
            <h2 class="cg-h">Failures included.</h2>
          </div>
          <a class="cg-button" :href="page('/benchmarks/m08-report')">
            <i aria-hidden="true">+</i>The M08 report
          </a>
        </div>

        <div class="cg-cards">
          <a class="cg-card tone-light" :href="page('/benchmarks/m08-report')" data-reveal>
            <span class="cg-card-rule" aria-hidden="true" />
            <span class="cg-tag cg-tag--plain">M08 · seven pinned repositories</span>
            <p class="cg-card-big">14,932 edges labelled. One false positive.</p>
            <p class="cg-card-small">
              One false positive among 11,221 independently verified edges. 24.9% (3,711) could not
              be verified from source, and they concentrate where evidence is weakest — so every
              figure is an upper bound.
            </p>
          </a>
          <a class="cg-card tone-green" :href="page('/benchmarks/m08-confidence-policy')" data-reveal>
            <svg class="cg-orbit" viewBox="0 0 320 320" aria-hidden="true">
              <circle cx="160" cy="160" r="150" />
              <circle cx="160" cy="160" r="112" stroke-dasharray="2 6" />
              <circle cx="160" cy="160" r="76" />
              <circle cx="160" cy="160" r="42" stroke-dasharray="2 6" />
              <circle class="cg-orbit-core" cx="160" cy="160" r="9" />
              <g class="cg-orbit-pill" transform="translate(206 44)">
                <rect x="0" y="0" width="86" height="24" rx="12" />
                <text x="43" y="16">SOURCE</text>
              </g>
              <g class="cg-orbit-pill" transform="translate(26 244)">
                <rect x="0" y="0" width="98" height="24" rx="12" />
                <text x="49" y="16">EVIDENCE</text>
              </g>
            </svg>
            <p class="cg-card-big cg-card-big--small">Confidence values are uncalibrated priors, not probabilities.</p>
            <p class="cg-card-small">
              Calibration error 0.18, toward under-confidence. They must not be thresholded as if
              they were probabilities.
            </p>
          </a>
        </div>

        <dl class="cg-stats" data-reveal>
          <div>
            <dt>0.907</dt>
            <dd>HttpCall recall · Airflow only · 117 of 129 operations its generated client declares that a route serves</dd>
          </div>
          <div>
            <dt>0.744</dt>
            <dd>OrmAccess recall · Airflow only · 1,401 of 1,883 import-bound uses of models that declare a table</dd>
          </div>
          <div>
            <dt>3 of 5</dt>
            <dd>End-to-end chains · Airflow only · chains whose every hop is independently readable</dd>
          </div>
        </dl>
        <p class="cg-footnote" data-reveal>
          Recall was measured in one repository, inside a stated scope. It is not recall across the
          corpus and must not be quoted as such.
        </p>
      </section>

      <!-- Principles -->
      <section class="cg-principles cg-section">
        <div class="cg-principles-lead" data-reveal>
          <p class="cg-label">Principles</p>
          <h2 class="cg-display">Unknown stays unknown.</h2>
          <div class="cg-principles-copy">
            <p>
              A plausible-looking guess is worse than a gap, because it is indistinguishable from a
              derived fact. Where the evidence is thin, Cartograph refuses. Contributions are
              welcome — real repositories that break the resolver most of all.
            </p>
            <a class="cg-button" :href="repo('CONTRIBUTING.md')">
              <i aria-hidden="true">+</i>Contributing
            </a>
          </div>
          <figure class="cg-install">
            <figcaption class="cg-label">Try it</figcaption>
            <pre><code>{{ install }}</code></pre>
          </figure>
        </div>

        <ol class="cg-values" data-reveal>
          <li
            v-for="(p, i) in principles"
            :key="p.title"
            class="cg-value"
            :class="[`tone-${p.tone}`, { 'is-open': principle === i }]"
            @mouseenter="principle = i"
          >
            <button type="button" :aria-expanded="principle === i" @click="principle = i" @focus="principle = i">
              <span class="cg-index">{{ String(i + 1).padStart(2, '0') }}</span>
              <span class="cg-value-title">{{ p.title }}</span>
            </button>
            <div class="cg-value-body" :inert="principle !== i || undefined">
              <div>
                <p>{{ p.body }}</p>
                <a :href="p.href">{{ p.link }} →</a>
              </div>
            </div>
          </li>
        </ol>
      </section>

      <!-- Corpus -->
      <section class="cg-corpus">
        <div class="cg-section cg-corpus-head cg-head" data-reveal>
          <div>
            <p class="cg-label">Corpus</p>
            <h2 class="cg-h">Measured on seven pinned<br />production repositories.</h2>
          </div>
          <!-- WCAG 2.2.2: anything that moves for more than five seconds can be paused. -->
          <button class="cg-button cg-toggle" type="button" :aria-pressed="still" @click="still = !still">
            <i aria-hidden="true">{{ still ? '▶' : '‖' }}</i>Pause motion
          </button>
        </div>
        <div class="cg-marquee">
          <ul aria-label="The seven repositories in the benchmark corpus">
            <li v-for="name in corpus" :key="name">{{ name }}</li>
          </ul>
          <ul aria-hidden="true">
            <li v-for="name in corpus" :key="name">{{ name }}</li>
          </ul>
        </div>
      </section>
    </main>

    <!-- Footer -->
    <footer class="cg-footer" :inert="menuOpen || undefined">
      <div class="cg-dome">
        <HalftoneField variant="dome" dot="#c9c6b8" cross="#eddfee" :paused="still" />
      </div>
      <div class="cg-footer-grid">
        <div>
          <p class="cg-label">Install</p>
          <pre class="cg-footer-code"><code>{{ install }}</code></pre>
        </div>
        <div>
          <p class="cg-label">Status</p>
          <p>Milestones M00–M16 accepted.<br />M17, the public launch, in progress.<br />Version 0.1.0.</p>
        </div>
        <div>
          <p class="cg-label">Documentation</p>
          <ul>
            <li><a :href="page('/writeup/technical-writeup')">Technical writeup</a></li>
            <li><a :href="page('/resolver/')">Resolver</a></li>
            <li><a :href="page('/benchmarks/')">Benchmarks</a></li>
            <li><a :href="page('/architecture/')">Architecture</a></li>
            <li><a :href="page('/adr/')">Decisions</a></li>
            <li><a :href="page('/security/')">Security</a></li>
          </ul>
        </div>
        <div>
          <p class="cg-label">Project</p>
          <ul>
            <li><a :href="REPO">GitHub</a></li>
            <li><a :href="repo('ROADMAP.md')">Roadmap</a></li>
            <li><a :href="repo('CHANGELOG.md')">Changelog</a></li>
            <li><a :href="repo('CONTRIBUTING.md')">Contributing</a></li>
            <li><a :href="repo('PROJECT_RULES.md')">Project rules</a></li>
          </ul>
        </div>
      </div>
      <div class="cg-footer-base">
        <span>© Cartograph contributors</span>
        <a :href="repo('LICENSE')">Apache-2.0 licence</a>
        <span>Built with VitePress</span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
/* ---------- Base ---------- */

.cg {
  --pad-section: clamp(4rem, 2.5rem + 3.5vw, 7rem);
  font-family: var(--cg-font);
  color: var(--cg-light-pink);
  background: var(--cg-black);
  overflow-x: clip;
  -webkit-font-smoothing: antialiased;
}

/* Zero specificity, so a tone class on a link still sets its colour. */
:where(.cg) a {
  color: inherit;
  text-decoration: none;
}

/* The ring takes the text colour, which every block already sets to 4.5:1
   against its own background; a fixed pink fails 3:1 on the light ones. */
.cg :focus-visible {
  outline: 2px solid currentColor;
  outline-offset: 3px;
}

.cg-section {
  padding: var(--pad-section) var(--cg-gutter);
}

.cg-label {
  margin: 0 0 0.75rem;
  font-family: var(--cg-font-mono);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  line-height: 1.3;
  text-transform: uppercase;
}

.cg-h {
  margin: 0;
  font-size: clamp(1.15rem, 0.85rem + 1.05vw, 1.75rem);
  font-weight: 500;
  line-height: 1.2;
  text-transform: uppercase;
}

.cg-index {
  font-family: var(--cg-font-mono);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.cg-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1.5rem;
  margin-bottom: clamp(2rem, 1.4rem + 1.8vw, 3.25rem);
}

/* The "+ LABEL" button. */
.cg-button {
  display: inline-flex;
  align-items: center;
  gap: 0.75rem;
  font-family: var(--cg-font-mono);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  white-space: nowrap;
  cursor: pointer;
}

.cg-button i {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: 1px solid currentColor;
  border-radius: 0.3em;
  font-style: normal;
  font-size: 15px;
  font-weight: 400;
  transition:
    background-color 0.3s var(--cg-ease),
    color 0.3s var(--cg-ease),
    transform 0.3s var(--cg-ease);
}

.cg-button:hover i,
a:hover > .cg-button i {
  background: var(--cg-pink);
  border-color: var(--cg-pink);
  color: var(--cg-black);
  transform: rotate(90deg);
}

/* ---------- Header and menu ---------- */

.cg-header {
  position: fixed;
  inset: 0 0 auto;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 72px;
  padding: 0 var(--cg-gutter);
  transition:
    background-color 0.4s var(--cg-ease),
    height 0.4s var(--cg-ease);
}

.cg-header.is-solid {
  height: 60px;
  background: var(--cg-black);
}

.cg-logo {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  color: var(--cg-pink) !important;
  font-size: 1.2rem;
  font-weight: 600;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.cg-logo svg {
  width: 22px;
  height: 22px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.6;
}

.cg-menu-button {
  display: inline-flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.5rem 0;
  color: var(--cg-light-pink);
  font-family: var(--cg-font);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.cg-plus {
  position: relative;
  width: 16px;
  height: 16px;
  transition: transform 0.5s var(--cg-ease);
}

.cg-plus::before,
.cg-plus::after {
  content: '';
  position: absolute;
  inset: 50% 0 auto;
  height: 1.5px;
  margin-top: -0.75px;
  background: var(--cg-pink);
}

.cg-plus::after {
  transform: rotate(90deg);
}

.cg-plus.is-open {
  transform: rotate(135deg);
}

.cg-menu {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  align-items: end;
  gap: 3rem;
  padding: 110px var(--cg-gutter) var(--cg-gutter);
  overflow-y: auto;
  background: var(--cg-black);
  clip-path: inset(0 0 0 0);
  transition: clip-path 0.7s var(--cg-ease);
}

.cg-menu-enter-from,
.cg-menu-leave-to {
  clip-path: inset(0 0 100% 0);
}

.cg-menu-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.cg-menu-list a {
  display: flex;
  align-items: baseline;
  gap: 1rem;
  padding: 0.2rem 0;
  color: var(--cg-pink);
  font-size: clamp(2rem, 1.1rem + 3.2vw, 4.25rem);
  font-weight: 500;
  line-height: 1.05;
  text-transform: uppercase;
  transition:
    color 0.3s var(--cg-ease),
    transform 0.4s var(--cg-ease);
}

.cg-menu-list a:hover {
  color: var(--cg-light-pink);
  transform: translateX(0.5rem);
}

.cg-menu-list small {
  min-width: 2ch;
  font-family: var(--cg-font-mono);
  font-size: 11px;
  font-weight: 600;
  color: var(--cg-light-pink);
}

.cg-menu-aside {
  display: grid;
  gap: 2rem;
  padding-bottom: 0.5rem;
}

.cg-menu-small {
  margin: 0;
  font-family: var(--cg-font-mono);
  font-size: 12px;
  line-height: 1.6;
}

.cg-menu-aside a:hover {
  color: var(--cg-pink);
}

.cg-menu-code,
.cg-footer-code {
  margin: 0;
  font-family: var(--cg-font-mono);
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

/* ---------- Hero ---------- */

.cg-hero {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: 100svh;
  padding: 120px var(--cg-gutter) var(--cg-gutter);
}

.cg-hero-title {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 2rem 3rem;
  margin: 0;
  color: var(--cg-pink);
  font-size: clamp(2.4rem, 0.8rem + 4.5vw, 5.4rem);
  font-weight: 500;
  line-height: 1;
  letter-spacing: -0.01em;
  text-transform: uppercase;
}

.cg-hero-left,
.cg-hero-right {
  display: flex;
  flex-direction: column;
}

.cg-hero-right {
  align-items: flex-end;
  text-align: right;
}

.cg-line {
  display: block;
  overflow: hidden;
  padding-bottom: 0.04em;
}

.cg-line > span {
  display: block;
  animation: cg-rise 1.1s var(--cg-ease) both;
  animation-delay: var(--d, 0s);
}

@keyframes cg-rise {
  from {
    transform: translateY(105%);
  }
  to {
    transform: translateY(0);
  }
}

.cg-hero-foot {
  position: absolute;
  inset: auto var(--cg-gutter) var(--cg-gutter);
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  font-family: var(--cg-font-mono);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: rgba(237, 223, 238, 0.6);
  animation: cg-fade 1.2s 0.7s var(--cg-ease) both;
}

@keyframes cg-fade {
  from {
    opacity: 0;
  }
}

/* ---------- Statement ---------- */

.cg-intro {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr);
  align-items: end;
  gap: 3rem 4rem;
  padding: var(--pad-section) var(--cg-gutter) calc(var(--pad-section) * 1.6);
}

.cg-statement {
  margin: 0;
  font-size: clamp(1.4rem, 0.95rem + 1.45vw, 2.2rem);
  font-weight: 500;
  line-height: 1.2;
  text-transform: uppercase;
}

.cg-intro-side {
  max-width: 34rem;
}

.cg-intro-side p {
  margin: 0 0 2rem;
  font-size: 15px;
  line-height: 1.55;
  color: rgba(237, 223, 238, 0.86);
}

.cg-badge {
  position: absolute;
  right: var(--cg-gutter);
  bottom: calc(var(--pad-section) * 0.35);
  width: 128px;
  height: 128px;
  color: var(--cg-light-pink);
}

.cg-badge > svg:first-child {
  width: 100%;
  height: 100%;
  animation: cg-spin 26s linear infinite;
}

.cg-badge text {
  fill: currentColor;
  font-family: var(--cg-font-mono);
  font-size: 8.4px;
  font-weight: 600;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.cg-badge-mark {
  position: absolute;
  inset: 50% auto auto 50%;
  width: 34px;
  height: 34px;
  transform: translate(-50%, -50%);
  fill: none;
  stroke: var(--cg-pink);
  stroke-width: 1.5;
}

@keyframes cg-spin {
  to {
    transform: rotate(360deg);
  }
}

/* ---------- Manilla sheet ---------- */

.cg-sheet {
  position: relative;
  z-index: 1;
  color: var(--cg-black);
  background: var(--cg-manilla);
  border-radius: 1.25rem 1.25rem 0 0;
}

/* Accordion of surfaces. */
.cg-acc {
  display: flex;
  height: clamp(460px, 64vh, 640px);
}

.cg-acc-item {
  position: relative;
  flex: 0 0 64px;
  overflow: hidden;
  transition: flex-basis 0.8s var(--cg-ease), flex-grow 0.8s var(--cg-ease);
}

.cg-acc-item.is-open {
  flex: 1 1 0;
}

.cg-acc-strip {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;
  padding: 1.1rem 0 1.4rem;
  color: inherit;
  cursor: pointer;
}

.cg-acc-strip i {
  order: -1;
  font-style: normal;
  font-size: 18px;
  line-height: 1;
}

.cg-acc-strip-label {
  writing-mode: vertical-rl;
  transform: rotate(180deg);
  font-family: var(--cg-font-mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

/* Hidden, not transparent: a transparent button would stay a tab stop. */
.is-open > .cg-acc-strip {
  visibility: hidden;
}

.cg-acc-panel {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-width: min(560px, 80vw);
  padding: clamp(1.25rem, 0.9rem + 1.2vw, 2rem);
  animation: cg-fade 0.6s 0.25s var(--cg-ease) both;
}

.cg-acc-panel[hidden] {
  display: none;
}

.cg-acc-top {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
}

.cg-acc-top h3 {
  margin: 0;
  max-width: 18ch;
  font-family: var(--cg-font-mono);
  font-size: clamp(1rem, 0.8rem + 0.7vw, 1.35rem);
  font-weight: 600;
  line-height: 1.25;
  text-transform: uppercase;
}

.cg-acc-bottom {
  max-width: 44ch;
}

.cg-acc-bottom p {
  margin: 0 0 1.25rem;
  font-family: var(--cg-font-mono);
  font-size: 12.5px;
  line-height: 1.6;
}

.cg-acc-bottom .cg-acc-tag {
  margin-bottom: 0.75rem;
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

/* Tones shared by every coloured block. */
.tone-black {
  background: var(--cg-black);
  color: var(--cg-light-pink);
}
.tone-green {
  background: var(--cg-green);
  color: var(--cg-light-pink);
}
.tone-pink {
  background: var(--cg-pink);
  color: var(--cg-black);
}
.tone-light {
  background: var(--cg-light-pink);
  color: var(--cg-black);
}
.tone-khaki {
  background: var(--cg-khaki);
  color: var(--cg-black);
}

/* Steps. */
.cg-steps {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border: 1px solid rgba(34, 34, 34, 0.18);
}

.cg-step {
  display: flex;
  flex-direction: column;
  min-height: 430px;
  padding: clamp(1.25rem, 0.9rem + 1.2vw, 2rem);
  transition: background-color 0.4s var(--cg-ease);
}

.cg-step + .cg-step {
  border-left: 1px solid rgba(34, 34, 34, 0.18);
}

.cg-step:hover {
  background: rgba(255, 255, 255, 0.35);
}

.cg-step-top {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.cg-step h3 {
  margin: 0;
  font-size: clamp(1.05rem, 0.9rem + 0.5vw, 1.35rem);
  font-weight: 500;
  text-transform: uppercase;
}

.cg-step p {
  max-width: 40ch;
  margin: 0;
  font-family: var(--cg-font-mono);
  font-size: 12.5px;
  line-height: 1.65;
}

.cg-step-icon {
  align-self: flex-end;
  width: clamp(96px, 7vw + 40px, 132px);
  margin-top: auto;
  padding-top: 2rem;
  fill: none;
  stroke: var(--cg-black);
  stroke-width: 1.1;
  transition: transform 0.6s var(--cg-ease);
}

.cg-step:hover .cg-step-icon {
  transform: translateY(-6px);
}

/* Halftone field. */
.cg-field {
  position: relative;
  height: clamp(440px, 82vh, 860px);
  border-top: 1px solid rgba(34, 34, 34, 0.12);
}

.cg-field-caption {
  position: absolute;
  inset: auto var(--cg-gutter) 1.5rem;
  margin: 0;
  text-align: center;
  color: rgba(34, 34, 34, 0.66);
  pointer-events: none;
}

/* ---------- Proof (white) ---------- */

.cg-proof,
.cg-measured {
  color: var(--cg-black);
  background: var(--cg-white);
}

.cg-proof-stage {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  grid-template-rows: auto clamp(5rem, 9vw, 9rem) auto auto;
}

.cg-terminal {
  grid-column: 1 / -1;
  grid-row: 1 / 3;
  margin: 0;
  padding: clamp(1.25rem, 0.6rem + 2.4vw, 3rem);
  padding-bottom: clamp(6rem, 11vw, 11rem);
  color: var(--cg-light-pink);
  background: var(--cg-black);
  overflow-x: auto;
}

.cg-terminal-bar {
  display: flex;
  gap: 6px;
  margin-bottom: 1.75rem;
}

.cg-terminal-bar i {
  width: 9px;
  height: 9px;
  border: 1px solid rgba(237, 223, 238, 0.4);
  border-radius: 50%;
}

.cg-terminal pre {
  margin: 0;
  font-family: var(--cg-font-mono);
  font-size: clamp(10.5px, 0.45rem + 0.42vw, 13.5px);
  line-height: 1.65;
  white-space: pre;
}

.cg-terminal figcaption {
  max-width: 60ch;
  margin-top: 1.75rem;
  font-family: var(--cg-font-mono);
  font-size: 11px;
  line-height: 1.6;
  color: rgba(237, 223, 238, 0.55);
}

.cg-feature {
  grid-column: 7 / -1;
  grid-row: 2 / 4;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1rem;
  padding: clamp(1.25rem, 0.8rem + 1.5vw, 2.25rem);
}

.cg-feature h3 {
  margin: 0;
  font-size: clamp(1.15rem, 0.85rem + 1vw, 1.75rem);
  font-weight: 500;
  line-height: 1.2;
  text-transform: uppercase;
}

.cg-feature p {
  margin: 0 0 0.5rem;
  max-width: 48ch;
  font-size: 14.5px;
  line-height: 1.55;
}

.cg-feature-row {
  grid-column: 7 / -1;
  grid-row: 4;
  display: grid;
  grid-template-columns: 1fr 1fr;
}

.cg-feature--small {
  grid-column: auto;
  grid-row: auto;
  min-height: 220px;
  justify-content: space-between;
}

.cg-feature--small h3 {
  font-size: clamp(0.95rem, 0.8rem + 0.45vw, 1.2rem);
}

.cg-tag {
  display: inline-block;
  padding: 0.35rem 0.6rem;
  font-family: var(--cg-font-mono);
  font-size: 9.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  background: var(--cg-white);
  color: var(--cg-black);
  border-radius: 0.3em;
}

.cg-tag--plain {
  padding: 0;
  background: none;
}

/* ---------- Measured ---------- */

.cg-measured {
  padding-top: 0;
}

.cg-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: clamp(1rem, 0.5rem + 1.5vw, 2rem);
}

.cg-card {
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 1.25rem;
  min-height: clamp(420px, 38vw, 560px);
  padding: clamp(1.25rem, 0.8rem + 1.5vw, 2.25rem);
  overflow: hidden;
}

.cg-card .cg-tag--plain {
  position: absolute;
  top: clamp(1.25rem, 0.8rem + 1.5vw, 2.25rem);
  left: clamp(1.25rem, 0.8rem + 1.5vw, 2.25rem);
}

.cg-card-rule {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(currentColor, currentColor) 70% 0 / 1px 100% no-repeat,
    linear-gradient(90deg, currentColor, currentColor) 0 22% / 100% 1px no-repeat;
  opacity: 0.25;
}

.cg-card-big {
  position: relative;
  margin: 0;
  max-width: 14ch;
  font-size: clamp(2rem, 1rem + 3.4vw, 4.25rem);
  font-weight: 500;
  line-height: 1;
  text-transform: uppercase;
}

.cg-card-big--small {
  max-width: 20ch;
  font-size: clamp(1.25rem, 0.9rem + 1.2vw, 2rem);
  line-height: 1.15;
}

.cg-card-small {
  position: relative;
  max-width: 52ch;
  margin: 0;
  font-family: var(--cg-font-mono);
  font-size: 12px;
  line-height: 1.6;
}

.cg-orbit {
  position: absolute;
  top: 8%;
  left: 50%;
  width: min(62%, 340px);
  transform: translateX(-50%);
  fill: none;
  stroke: rgba(237, 223, 238, 0.5);
  stroke-width: 1;
  animation: cg-spin 80s linear infinite;
}

.cg-orbit-core {
  fill: var(--cg-pink);
  stroke: none;
}

.cg-orbit-pill rect {
  fill: var(--cg-green);
  stroke: var(--cg-pink);
}

.cg-orbit-pill text {
  fill: var(--cg-light-pink);
  stroke: none;
  font-family: var(--cg-font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-anchor: middle;
}

.cg-card:hover .cg-card-big {
  color: var(--cg-pink-deep);
}

.cg-card.tone-green:hover .cg-card-big {
  color: var(--cg-pink);
}

.cg-stats {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: clamp(1rem, 0.5rem + 1.5vw, 2rem);
  margin: clamp(2.5rem, 2rem + 2vw, 4rem) 0 0;
}

.cg-stats div {
  padding-top: 1.25rem;
  border-top: 1px solid rgba(34, 34, 34, 0.2);
}

.cg-stats dt {
  font-size: clamp(2rem, 1.2rem + 2.4vw, 3.5rem);
  font-weight: 500;
  line-height: 1;
}

.cg-stats dd {
  margin: 0.9rem 0 0;
  max-width: 40ch;
  font-family: var(--cg-font-mono);
  font-size: 11.5px;
  line-height: 1.6;
  color: rgba(34, 34, 34, 0.72);
}

.cg-footnote {
  margin: 2rem 0 0;
  font-family: var(--cg-font-mono);
  font-size: 11px;
  line-height: 1.6;
  color: rgba(34, 34, 34, 0.72);
}

/* ---------- Principles ---------- */

.cg-principles {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: clamp(2rem, 1rem + 3vw, 4.5rem);
  color: var(--cg-black);
  background: var(--cg-manilla);
}

.cg-display {
  margin: 0 0 2rem;
  font-size: clamp(2.6rem, 1rem + 5vw, 5.6rem);
  font-weight: 500;
  line-height: 0.98;
  letter-spacing: -0.01em;
  text-transform: uppercase;
}

.cg-principles-copy {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1.5rem;
  max-width: 38rem;
}

.cg-principles-copy p {
  margin: 0;
  font-size: 15px;
  line-height: 1.55;
}

.cg-install {
  margin: clamp(2rem, 1.5rem + 2vw, 3.5rem) 0 0;
  padding: clamp(1.25rem, 0.9rem + 1vw, 1.75rem);
  color: var(--cg-light-pink);
  background: var(--cg-black);
}

.cg-install pre {
  margin: 0;
  font-family: var(--cg-font-mono);
  font-size: 12.5px;
  line-height: 1.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.cg-values {
  display: flex;
  flex-direction: column;
  margin: 0;
  padding: 0;
  list-style: none;
}

.cg-value button {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.4rem;
  width: 100%;
  padding: 1rem clamp(1rem, 0.8rem + 0.8vw, 1.5rem);
  color: inherit;
  text-align: left;
  cursor: pointer;
}

.cg-value-title {
  font-family: var(--cg-font-mono);
  font-size: clamp(0.85rem, 0.75rem + 0.35vw, 1.05rem);
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.cg-value-body {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.7s var(--cg-ease);
}

.cg-value-body > div {
  overflow: hidden;
  padding: 0 clamp(1rem, 0.8rem + 0.8vw, 1.5rem);
}

.cg-value.is-open .cg-value-body {
  grid-template-rows: 1fr;
}

.cg-value-body p {
  max-width: 46ch;
  margin: clamp(3rem, 2rem + 5vw, 8rem) 0 1rem;
  font-family: var(--cg-font-mono);
  font-size: 12.5px;
  line-height: 1.65;
}

.cg-value-body a {
  display: inline-block;
  margin-bottom: 1.5rem;
  font-family: var(--cg-font-mono);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  border-bottom: 1px solid currentColor;
}

/* ---------- Corpus (green) ---------- */

.cg-corpus {
  color: var(--cg-light-pink);
  background: var(--cg-green);
  border-radius: 1.25rem 1.25rem 0 0;
  margin-top: -1.25rem;
  position: relative;
}

.cg-corpus-head {
  padding-bottom: clamp(2rem, 1.5rem + 2vw, 3.5rem);
}

.cg-marquee {
  display: flex;
  overflow: hidden;
  border-block: 1px solid rgba(237, 223, 238, 0.12);
}

.cg-marquee ul {
  display: flex;
  flex: none;
  gap: clamp(3rem, 2rem + 4vw, 7rem);
  margin: 0;
  padding: 2.25rem clamp(1.5rem, 1rem + 2vw, 3.5rem);
  list-style: none;
  animation: cg-marquee 42s linear infinite;
}

.cg-marquee li {
  flex: none;
  color: #c9c6b8;
  font-size: clamp(1.1rem, 0.9rem + 0.8vw, 1.6rem);
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  white-space: nowrap;
}

@keyframes cg-marquee {
  to {
    transform: translateX(-100%);
  }
}

.cg-marquee:hover ul,
.cg.is-still .cg-marquee ul,
.cg.is-still .cg-badge > svg:first-child,
.cg.is-still .cg-orbit {
  animation-play-state: paused;
}

.cg-toggle[aria-pressed='true'] i {
  background: var(--cg-light-pink);
  border-color: var(--cg-light-pink);
  color: var(--cg-green);
}

.cg-toggle:hover i {
  transform: none;
}

/* ---------- Footer ---------- */

.cg-footer {
  color: var(--cg-light-pink);
  background: var(--cg-green);
}

.cg-dome {
  height: clamp(240px, 36vw, 540px);
}

.cg-footer-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr 1fr;
  gap: 2.5rem;
  padding: clamp(3rem, 2rem + 3vw, 5rem) var(--cg-gutter) 3rem;
}

.cg-footer-grid p:not(.cg-label) {
  margin: 0;
  font-size: 14px;
  line-height: 1.6;
}

.cg-footer-grid .cg-label {
  color: var(--cg-pink);
}

.cg-footer-grid ul {
  margin: 0;
  padding: 0;
  list-style: none;
}

.cg-footer-grid li a {
  display: inline-block;
  padding: 0.15rem 0;
  font-size: 14px;
  font-weight: 500;
  text-transform: uppercase;
  transition: color 0.3s var(--cg-ease);
}

.cg-footer-grid li a:hover,
.cg-footer-base a:hover {
  color: var(--cg-pink);
}

.cg-footer-base {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 1.5rem var(--cg-gutter);
  border-top: 1px solid rgba(237, 223, 238, 0.12);
  font-family: var(--cg-font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

/* ---------- Scroll reveal (only once JS has run) ---------- */

.cg-js [data-reveal] {
  opacity: 0;
  transform: translateY(28px);
  transition:
    opacity 1s var(--cg-ease),
    transform 1s var(--cg-ease);
}

.cg-js [data-reveal].is-in,
.cg-js [data-reveal]:focus-within {
  opacity: 1;
  transform: none;
}

/* ---------- Narrow screens ---------- */

@media (max-width: 960px) {
  .cg-intro,
  .cg-principles,
  .cg-cards {
    grid-template-columns: 1fr;
  }

  .cg-badge {
    position: relative;
    inset: auto;
    width: 104px;
    height: 104px;
  }

  .cg-steps,
  .cg-stats {
    grid-template-columns: 1fr;
  }

  .cg-step {
    min-height: 0;
  }

  .cg-step + .cg-step {
    border-left: 0;
    border-top: 1px solid rgba(34, 34, 34, 0.18);
  }

  .cg-step-icon {
    width: 88px;
  }

  .cg-proof-stage {
    grid-template-rows: auto auto auto;
  }

  .cg-terminal {
    grid-row: 1;
    padding-bottom: clamp(1.25rem, 0.6rem + 2.4vw, 3rem);
  }

  .cg-feature,
  .cg-feature-row {
    grid-column: 1 / -1;
  }

  .cg-feature {
    grid-row: 2;
  }

  .cg-feature-row {
    grid-row: 3;
  }

  .cg-footer-grid {
    grid-template-columns: 1fr 1fr;
  }

  .cg-menu {
    grid-template-columns: 1fr;
    align-content: start;
  }

  /* Side by side, the open panel needs 560px beside four 64px strips; below
     this width it would be clipped, so the surfaces stack instead. */
  .cg-acc {
    flex-direction: column;
    height: auto;
  }

  .cg-acc-item,
  .cg-acc-item.is-open {
    flex: none;
  }

  .cg-acc-strip {
    position: relative;
    flex-direction: row;
    width: 100%;
    padding: 1rem 1.1rem;
  }

  .cg-acc-strip i {
    order: 1;
  }

  .cg-acc-strip-label {
    writing-mode: horizontal-tb;
    transform: none;
  }

  .is-open > .cg-acc-strip {
    display: none;
  }

  .cg-acc-panel {
    position: relative;
    min-width: 0;
    min-height: 360px;
    gap: 3rem;
  }
}

@media (max-width: 760px) {
  .cg-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .cg-hero-title {
    flex-direction: column;
    justify-content: center;
  }

  .cg-hero-foot span:nth-child(2) {
    display: none;
  }

  .cg-feature-row {
    grid-template-columns: 1fr;
  }

  .cg-footer-grid {
    grid-template-columns: 1fr;
  }

  .cg-footer-base {
    flex-direction: column;
  }
}

@media (prefers-reduced-motion: reduce) {
  .cg *,
  .cg *::before,
  .cg *::after {
    animation: none !important;
    transition: none !important;
  }

  .cg-js [data-reveal] {
    opacity: 1;
    transform: none;
  }
}
</style>
