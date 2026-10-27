# Development

- [external-storage.md](external-storage.md) — working from the external SSD,
  cargo target-dir, exFAT caveats
- Root [Makefile](../../Makefile) — `make help`
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — workflow, branch/commit conventions
- [AGENTS.md](../../AGENTS.md) — AI assistant working agreement

Machine profile this project is tuned for: MacBook Air M4, 16 GB RAM, 256 GB
internal SSD, 1 TB external SSD. No Docker, no local LLMs; rust-analyzer alone
claims 3–6 GB and the chassis is fanless — keep heavyweight processes few.

## The documentation site

The Markdown in `docs/` is also published as a VitePress site. It is an npm
package of its own, in `docs/`, with VitePress pinned exactly and the lockfile
committed; it shares nothing with `desktop/` or `npm/`. From `docs/`:

```bash
npm ci                # install exactly what the lockfile records
npm run dev           # serve with live reload
npm run build         # build into docs/.vitepress/dist/
npm run check-links   # after a build: check every link and anchor
npm run preview       # serve the build as it will be deployed
```

The site's configuration is in [`.vitepress/config.mts`](../.vitepress/config.mts).
A relative link to a file outside `docs/` becomes a link to that file on GitHub,
and the build fails if the file does not exist. The
[docs workflow](../../.github/workflows/docs.yml) builds and link-checks the site
on every pull request, and publishes it to GitHub Pages from `main`.

GitHub Pages serves the site under `/cartograph/`, and the build assumes that
path unless told otherwise. A host that serves it at the root of a domain
builds with `CARTOGRAPH_SITE_BASE=/`, and runs the link check with the same
setting; [`.vitepress/site-base.mjs`](../.vitepress/site-base.mjs) reads it for
both.

The theme is in [`.vitepress/theme/`](../.vitepress/theme/).
[`style.css`](../.vitepress/theme/style.css) re-skins VitePress's default theme
for every page. The home page is a component,
[`Landing.vue`](../.vitepress/theme/Landing.vue); `docs/index.md` only mounts
it, so the home page's wording is edited there. It holds to the same rule as
the rest of the site: every statement comes from the README or these
documents, and it publishes no figure the README does not. Fonts are bundled
from npm, so the site makes no third-party request. Any colour pair the theme
adds must reach WCAG 2.1 AA contrast: 4.5:1 for text, and 3:1 for focus rings
and other non-text marks.

The home page's motion is in [`motion.ts`](../.vitepress/theme/motion.ts) and in
CSS scoped under `.cg-motion`. The page sets that class only after it has
mounted, and only while motion is allowed. Anything new that moves must:

- start from a state that exists only under that class, so the page is already
  in place without JavaScript;
- animate transform or opacity, never layout;
- stop under `prefers-reduced-motion` and the header's "Pause motion" control.

Links on the site read as names, never as bare addresses.
