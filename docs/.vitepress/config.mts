import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, type DefaultTheme } from 'vitepress'

// The site is built from the Markdown in docs/, the same files GitHub renders.
// Nothing here forks that content: two adaptations are made at build time, and
// both are deliberate rather than silenced.
//
// 1. Links. A relative link is resolved against the real source file. A target
//    inside docs/ becomes a site page; a target outside docs/ — a crate, a
//    benchmark artifact, ROADMAP.md — becomes a link to that file on GitHub,
//    but only after checking that it exists. A missing target fails the build.
// 2. Anchors. Headings are slugged the way GitHub slugs them, so the anchors the
//    documents already use resolve on the site as well as on GitHub.

const DOCS = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const REPO = path.resolve(DOCS, '..')
const GITHUB = 'https://github.com/Rexy-5097/cartograph'
const BRANCH = 'main'

const posix = (p: string) => p.split(path.sep).join('/')

/** A link to a repository path on GitHub. Fails the build if the path is absent. */
function repoLink(relativeToRepo: string): string {
  const target = path.join(REPO, relativeToRepo)
  if (!fs.existsSync(target)) {
    throw new Error(`site link to ${posix(relativeToRepo)}, which does not exist`)
  }
  const kind = fs.statSync(target).isDirectory() ? 'tree' : 'blob'
  return `${GITHUB}/${kind}/${BRANCH}/${posix(relativeToRepo)}`
}

/** A directory's site path: `''` is the site root. */
function sitePath(relativeDir: string): string {
  const dir = posix(relativeDir)
  return dir === '' || dir === '.' ? '/' : `/${dir}/`
}

/** Resolves one relative link written for GitHub into its site equivalent. */
function rewriteLink(href: string, source: string): string {
  if (/^[a-z][a-z0-9+.-]*:/i.test(href) || href.startsWith('#') || href.startsWith('/')) {
    return href
  }
  const cut = href.indexOf('#')
  const rawPath = cut === -1 ? href : href.slice(0, cut)
  const hash = cut === -1 ? '' : href.slice(cut)
  const target = path.resolve(path.dirname(source), decodeURIComponent(rawPath))
  const fromDocs = path.relative(DOCS, target)
  const insideDocs = !fromDocs.startsWith('..') && !path.isAbsolute(fromDocs)
  const isDir = fs.existsSync(target) && fs.statSync(target).isDirectory()

  if (insideDocs) {
    if (isDir && ['index.md', 'README.md'].some((f) => fs.existsSync(path.join(target, f)))) {
      return sitePath(fromDocs) + hash
    }
    if (target.endsWith('.md')) {
      // A README is its directory's index page. Any other page keeps its .md
      // link, which VitePress checks for existence and rewrites to .html.
      if (path.basename(target) === 'README.md') return sitePath(path.dirname(fromDocs)) + hash
      return `/${posix(fromDocs)}${hash}`
    }
    // A non-Markdown file inside docs/ is not a page; it is linked on GitHub.
  }
  if (!fs.existsSync(target)) {
    throw new Error(
      `${posix(path.relative(REPO, source))}: link "${href}" points at ` +
        `${posix(path.relative(REPO, target))}, which does not exist`,
    )
  }
  return repoLink(path.relative(REPO, target)) + hash
}

function repositoryLinks(md: any) {
  md.core.ruler.push('cartograph_repository_links', (state: any) => {
    const raw: string = state.env.realPath ?? state.env.path
    const source = path.isAbsolute(raw) ? raw : path.resolve(DOCS, raw)
    for (const block of state.tokens) {
      if (block.type !== 'inline' || !block.children) continue
      for (const token of block.children) {
        if (token.type !== 'link_open') continue
        const href = token.attrGet('href')
        if (href) token.attrSet('href', rewriteLink(href, source))
      }
    }
  })
}

/**
 * GitHub's heading slug: lower-case, drop everything but letters, marks,
 * numbers, connector punctuation, hyphens and spaces, then turn each space
 * into a hyphen. VitePress's default differs — it collapses separators and
 * prefixes a leading digit — which would break anchors such as
 * `#4-excluded-and-unresolved-figures` that the documents rely on.
 */
const githubSlug = (s: string) =>
  s
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{M}\p{N}\p{Pc}\- ]/gu, '')
    .replace(/ /g, '-')

const adrs: DefaultTheme.SidebarItem[] = fs
  .readdirSync(path.join(DOCS, 'adr'))
  .filter((f) => /^ADR-\d{4}.*\.md$/.test(f))
  .sort()
  .map((f) => {
    const heading = fs
      .readFileSync(path.join(DOCS, 'adr', f), 'utf8')
      .split('\n')
      .find((l) => l.startsWith('# '))
    return { text: (heading ?? f).replace(/^# /, '').replace(/`/g, ''), link: `/adr/${f}` }
  })

export default defineConfig({
  title: 'Cartograph',
  description:
    'Compute the architecture. Prove the relationships. A local-first, cross-language architecture graph with the evidence behind every edge.',
  base: '/cartograph/',
  lang: 'en-GB',

  // docs/README.md is the index GitHub shows for this directory; on the site
  // the home page and the sidebar take its place, and links to it resolve to
  // the home page. Every other README is its directory's index page.
  srcExclude: ['README.md'],
  rewrites: { ':dir/README.md': ':dir/index.md' },

  markdown: {
    anchor: { slugify: githubSlug },
    config: (md) => {
      md.use(repositoryLinks)
    },
  },

  themeConfig: {
    nav: [
      { text: 'Writeup', link: '/writeup/technical-writeup' },
      { text: 'Resolver', link: '/resolver/' },
      { text: 'Benchmarks', link: '/benchmarks/' },
      { text: 'Decisions', link: '/adr/' },
      { text: 'Releases', link: '/releases/' },
    ],

    sidebar: [
      {
        text: 'Getting started',
        items: [
          { text: 'Overview', link: '/' },
          { text: 'Install and commands (v0.1.0)', link: '/releases/v0.1.0' },
          { text: 'Command-line reference', link: '/development/cli' },
        ],
      },
      {
        text: 'Technical writeup',
        items: [{ text: 'Resolver design, benchmarks, calibration', link: '/writeup/technical-writeup' }],
      },
      {
        text: 'Architecture',
        collapsed: false,
        items: [
          { text: 'Architecture detail', link: '/architecture/' },
          { text: 'Parser', link: '/architecture/parser' },
          { text: 'The --json output contract', link: '/architecture/json-schema' },
          { text: 'The domain graph', link: '/graph/' },
          { text: 'ARCHITECTURE.md', link: repoLink('ARCHITECTURE.md') },
        ],
      },
      {
        text: 'Resolver',
        collapsed: false,
        items: [
          { text: 'Overview', link: '/resolver/' },
          { text: 'Canonical routes', link: '/resolver/canonical-routes' },
          { text: 'Dynamic URLs', link: '/resolver/dynamic-urls' },
          { text: 'Matching', link: '/resolver/matching' },
          { text: 'Router prefixes', link: '/resolver/routers' },
          { text: 'Imports', link: '/resolver/imports' },
          { text: 'ORM resolution', link: '/resolver/orm' },
          { text: 'Client wrapper tracing', link: '/resolver/client-tracing' },
        ],
      },
      {
        text: 'Benchmarks and limitations',
        collapsed: false,
        items: [
          { text: 'What is measured and published', link: '/benchmarks/' },
          { text: 'M07 — real-repository validation', link: '/benchmarks/m07-report' },
          { text: 'M07 — remediation', link: '/benchmarks/m07-remediation' },
          { text: 'M08 — calibration and measurement', link: '/benchmarks/m08-report' },
          { text: 'M08 — confidence policy', link: '/benchmarks/m08-confidence-policy' },
          { text: 'M11 — renderer', link: '/benchmarks/m11-renderer' },
          { text: 'Cross-platform parity', link: '/benchmarks/cross-platform-parity' },
        ],
      },
      {
        text: 'Security',
        items: [
          { text: 'Security documentation', link: '/security/' },
          { text: 'SECURITY.md', link: repoLink('SECURITY.md') },
        ],
      },
      {
        text: 'Development',
        collapsed: true,
        items: [
          { text: 'Development', link: '/development/' },
          { text: 'Continuous verification', link: '/development/continuous-verification' },
          { text: 'Incremental analysis engine', link: '/development/incremental-engine' },
          { text: 'External storage', link: '/development/external-storage' },
        ],
      },
      {
        text: 'Architecture decisions',
        collapsed: true,
        items: [{ text: 'Index', link: '/adr/' }, ...adrs],
      },
      {
        text: 'Releases',
        collapsed: true,
        items: [
          { text: 'Releases', link: '/releases/' },
          { text: 'v0.1.0', link: '/releases/v0.1.0' },
        ],
      },
      {
        text: 'Project',
        collapsed: true,
        items: [
          { text: 'Roadmap', link: repoLink('ROADMAP.md') },
          { text: 'Checkpoints', link: repoLink('CHECKPOINTS.md') },
          { text: 'Project rules', link: repoLink('PROJECT_RULES.md') },
          { text: 'Changelog', link: repoLink('CHANGELOG.md') },
          { text: 'Contributing', link: repoLink('CONTRIBUTING.md') },
        ],
      },
    ],

    socialLinks: [{ icon: 'github', link: GITHUB }],
    search: { provider: 'local' },
    outline: { level: [2, 3] },
    footer: {
      message: 'Released under the Apache-2.0 licence.',
    },
  },
})
