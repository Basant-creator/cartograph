// The site theme: VitePress's default theme for the documentation pages,
// re-skinned by style.css, plus the landing page the home route renders.
//
// Geist and Geist Mono are bundled from npm rather than fetched from a font
// CDN, so a visit to the site makes no third-party request (ADR-0005). The
// default theme is imported without its own font, Inter, which nothing uses.

import DefaultTheme from 'vitepress/theme-without-fonts'
import type { Theme } from 'vitepress'
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import './style.css'
import Landing from './Landing.vue'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('Landing', Landing)
  },
} satisfies Theme
