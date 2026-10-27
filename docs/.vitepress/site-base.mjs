// Where the site is served from, shared by the build and the link check.
//
// GitHub Pages serves the site under the repository's name, /cartograph/, and
// that is the default. A host that serves it at the root of a domain builds
// with CARTOGRAPH_SITE_BASE=/ ; the link check, run in the same environment,
// then expects the same base.

export const SITE_BASE = process.env.CARTOGRAPH_SITE_BASE || '/cartograph/'

if (!/^\/(?:[A-Za-z0-9._-]+\/)*$/.test(SITE_BASE)) {
  throw new Error(
    `CARTOGRAPH_SITE_BASE must start and end with "/", as "/" and "/cartograph/" do; got "${SITE_BASE}"`,
  )
}
