// Checks the built site's links, after `vitepress build`.
//
// VitePress's own dead-link check confirms that a linked page exists. It does
// not check anchors, and it does not look at links that leave the site. This
// script reads the generated HTML and fails if any of these is broken:
//
//   - a link to a page inside the site, or to an anchor on that page;
//   - a link still pointing at a `.md` source file;
//   - a link to a file in this repository on GitHub whose path does not exist.
//
// Node's standard library only; no dependency is added for it.

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const DIST = path.join(HERE, 'dist')
const REPO = path.resolve(HERE, '..', '..')
const BASE = '/cartograph/'
const REPO_URL = /^https:\/\/github\.com\/Rexy-5097\/cartograph\/(?:blob|tree)\/main\/([^#?]*)/

if (!fs.existsSync(DIST)) {
  console.error(`no build output at ${path.relative(REPO, DIST)}; run \`npm run build\` first`)
  process.exit(1)
}

const pages = []
;(function walk(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) walk(full)
    else if (entry.name.endsWith('.html')) pages.push(full)
  }
})(DIST)

const decode = (s) =>
  s.replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>')

const idCache = new Map()
function idsOf(file) {
  if (!idCache.has(file)) {
    const html = fs.readFileSync(file, 'utf8')
    idCache.set(file, new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((m) => decodeURIComponent(decode(m[1])))))
  }
  return idCache.get(file)
}

/** The built file a site path refers to, or null. */
function fileFor(sitePath) {
  let rel = decodeURIComponent(sitePath.slice(BASE.length))
  const candidates = rel === '' || rel.endsWith('/') ? [rel + 'index.html'] : [rel, rel + '.html', rel + '/index.html']
  for (const c of candidates) {
    const full = path.join(DIST, c)
    if (fs.existsSync(full) && fs.statSync(full).isFile()) return full
  }
  return null
}

const problems = []
let internal = 0
let anchors = 0
let repository = 0

for (const page of pages) {
  const html = fs.readFileSync(page, 'utf8')
  const from = path.relative(DIST, page).split(path.sep).join('/')
  for (const m of html.matchAll(/<a\s[^>]*?href="([^"]*)"/g)) {
    const href = decode(m[1])

    const repo = href.match(REPO_URL)
    if (repo) {
      repository++
      const target = path.join(REPO, decodeURIComponent(repo[1]))
      if (!fs.existsSync(target)) problems.push(`${from}: GitHub link to missing path ${repo[1]}`)
      continue
    }
    if (/^[a-z][a-z0-9+.-]*:/i.test(href)) continue // any other external link

    const cut = href.indexOf('#')
    const pathPart = cut === -1 ? href : href.slice(0, cut)
    const fragment = cut === -1 ? '' : decodeURIComponent(href.slice(cut + 1))

    if (/\.md$/i.test(pathPart)) {
      problems.push(`${from}: link still points at Markdown source: ${href}`)
      continue
    }

    let target = page
    if (pathPart !== '') {
      if (!pathPart.startsWith(BASE)) {
        problems.push(`${from}: link outside the site base ${BASE}: ${href}`)
        continue
      }
      internal++
      target = fileFor(pathPart)
      if (!target) {
        problems.push(`${from}: link to a page that was not built: ${href}`)
        continue
      }
    }
    if (fragment !== '') {
      anchors++
      if (!idsOf(target).has(fragment)) {
        const to = path.relative(DIST, target).split(path.sep).join('/')
        problems.push(`${from}: anchor #${fragment} does not exist in ${to}`)
      }
    }
  }
}

console.log(
  `checked ${pages.length} pages: ${internal} internal links, ${anchors} anchors, ` +
    `${repository} links to repository files on GitHub`,
)
if (problems.length > 0) {
  for (const p of problems) console.error(`  BROKEN  ${p}`)
  console.error(`${problems.length} broken link(s)`)
  process.exit(1)
}
console.log('no broken links')
