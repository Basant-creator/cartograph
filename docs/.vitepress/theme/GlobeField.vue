<script setup lang="ts">
// The hero's centrepiece: a globe of code glyphs, rotating. Its characters
// flicker and bright bands rain down its face — a nod to falling code — and
// it spins faster while the page scrolls. Around it a tilted orbit carries the
// benchmark figures (decorative copies: the Measured section states them with
// their scope). Edges run from the globe's rim to the elements marked
// `data-globe-edge` in the same section — the hero's taglines — with a packet
// travelling each one, so the globe sits as the hub of a small graph.
//
// One canvas, redrawn per frame only while the hero is on screen. Glyphs dim
// behind any `data-globe-edge` text so the headline keeps its contrast. Under
// prefers-reduced-motion or `paused`, a single still frame.

import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{ paused?: boolean }>(), { paused: false })

const GLYPHS = '01{}<>[]()/=+*#:;$&|~0123456789ABCDEF'
const PINK = '205, 141, 189'
const LIGHT = '237, 223, 238'
const TILT = 0.32 // the globe leans toward the viewer, radians about x
const SPIN = 0.00018 // resting rotation, radians per ms
const ORBIT = { rx: 1.62, ry: 0.36, tilt: -0.22, rate: 0.55 } // radii in globe radii; rate × spin
// The orbit's labels: figures the README publishes, with their scope.
const FIGURES = [
  '14,932 edges labelled',
  '1 false positive in 11,221',
  '24.9% unverifiable',
  '0.907 HttpCall recall · Airflow',
  '0.744 OrmAccess recall · Airflow',
  'Calibration error 0.18',
]
const LABEL_FONT = '600 10.5px "Geist Mono Variable", ui-monospace, monospace'
const LABEL_H = 22 // a label's pill height, px

type Pt = { x: number; y: number; z: number; ch: string }
type Rect = { l: number; t: number; r: number; b: number }

const host = ref<HTMLDivElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)

let ctx: CanvasRenderingContext2D | null = null
let width = 0
let height = 0
let points: Pt[] = []
let angle = 0.6
let orbitAngle = 0
let boost = 0
let last = 0
let frame = 0
let visible = false
let reducedMotion = false
let dpr = 1
// Each label, pill and text together, is drawn once into a small canvas of its
// own and placed whole. Drawn afresh every frame, the text snapped to whole
// device pixels while its pill moved smoothly, so the words shook in the pill.
const labelSprites = new Map<string, HTMLCanvasElement | null>()
const cleanups: Array<() => void> = []

const still = () => reducedMotion || props.paused
const glyph = () => GLYPHS[Math.floor(Math.random() * GLYPHS.length)]

/** Points spread evenly over a sphere (a Fibonacci lattice), each holding a glyph. */
function populate(count: number) {
  const golden = Math.PI * (3 - Math.sqrt(5))
  points = Array.from({ length: count }, (_, i) => {
    const y = 1 - (i / (count - 1)) * 2
    const r = Math.sqrt(1 - y * y)
    const t = i * golden
    return { x: Math.cos(t) * r, y, z: Math.sin(t) * r, ch: GLYPHS[i % GLYPHS.length] }
  })
}

function resize() {
  const c = canvas.value
  const h = host.value
  if (!c || !h) return
  dpr = Math.min(window.devicePixelRatio || 1, 2)
  width = h.clientWidth
  height = h.clientHeight
  c.width = Math.round(width * dpr)
  c.height = Math.round(height * dpr)
  ctx = c.getContext('2d')
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0)
  labelSprites.clear()
  populate(width < 640 ? 300 : 560)
}

/** A label's pill and text, drawn once at the canvas's pixel density. */
function labelSprite(text: string): HTMLCanvasElement | null {
  if (labelSprites.has(text)) return labelSprites.get(text) ?? null
  let sprite: HTMLCanvasElement | null = document.createElement('canvas')
  const g = sprite.getContext('2d')
  if (g) {
    g.font = LABEL_FONT
    const w = Math.ceil(g.measureText(text).width) + 20
    // A pixel's margin on every side holds the outline. Resizing a canvas
    // resets its context, so everything is set after.
    sprite.width = Math.ceil((w + 2) * dpr)
    sprite.height = Math.ceil((LABEL_H + 2) * dpr)
    g.setTransform(dpr, 0, 0, dpr, dpr, dpr)
    g.fillStyle = 'rgba(34, 34, 34, 0.92)'
    g.strokeStyle = `rgba(${PINK}, 0.7)`
    g.lineWidth = 1
    g.beginPath()
    g.roundRect(0, 0, w, LABEL_H, LABEL_H / 2)
    g.fill()
    g.stroke()
    g.font = LABEL_FONT
    g.fillStyle = `rgb(${LIGHT})`
    g.textAlign = 'center'
    g.textBaseline = 'middle'
    g.fillText(text, w / 2, LABEL_H / 2 + 0.5)
  } else {
    sprite = null
  }
  labelSprites.set(text, sprite)
  return sprite
}

/** The tagline elements this globe links to, and their boxes relative to the canvas. */
function targets() {
  const h = host.value
  const section = h?.parentElement
  if (!h || !section) return [] as Array<{ box: Rect; el: HTMLElement }>
  const origin = h.getBoundingClientRect()
  return [...section.querySelectorAll<HTMLElement>('[data-globe-edge]')]
    .map((el) => {
      const r = el.getBoundingClientRect()
      return { el, box: { l: r.left - origin.left, t: r.top - origin.top, r: r.right - origin.left, b: r.bottom - origin.top } }
    })
    .filter((t) => t.box.r - t.box.l > 0)
}

function draw(time: number) {
  if (!ctx) return
  const g = ctx
  g.clearRect(0, 0, width, height)

  const moving = !still()
  const dt = last ? Math.min(64, time - last) : 16
  last = time
  if (moving) {
    angle += SPIN * dt * (1 + boost)
    orbitAngle += SPIN * ORBIT.rate * dt * (1 + boost)
    boost *= 0.94
  }

  const portrait = width < height
  const R = portrait ? width * 0.3 : Math.min(width * 0.135, height * 0.25)
  const cx = width / 2
  const cy = height / 2
  const links = targets()
  const boxes = links.map((l) => l.box)
  const behindText = (x: number, y: number) => boxes.some((b) => x > b.l - 12 && x < b.r + 12 && y > b.t - 8 && y < b.b + 8)

  // The orbit, as an ellipse; its far half is drawn before the globe.
  const cosT = Math.cos(ORBIT.tilt)
  const sinT = Math.sin(ORBIT.tilt)
  const onOrbit = (th: number) => {
    const ex = Math.cos(th) * R * ORBIT.rx
    const ey = Math.sin(th) * R * ORBIT.ry
    return { x: cx + ex * cosT - ey * sinT, y: cy + ex * sinT + ey * cosT, front: Math.sin(th) > 0 }
  }
  const orbitArc = (from: number, to: number, alpha: number) => {
    g.save()
    g.translate(cx, cy)
    g.rotate(ORBIT.tilt)
    g.beginPath()
    g.ellipse(0, 0, R * ORBIT.rx, R * ORBIT.ry, 0, from, to)
    g.setLineDash([2, 7])
    g.strokeStyle = `rgba(${PINK}, ${alpha})`
    g.lineWidth = 1.2
    g.stroke()
    g.restore()
  }
  // A narrow screen carries four figures, not six, so they do not crowd.
  const figures = width < 640 ? FIGURES.filter((_, k) => k !== 2 && k !== 5) : FIGURES
  const labels = figures.map((text, k) => ({ text, ...onOrbit(orbitAngle + (k * Math.PI * 2) / figures.length) }))
  const drawLabel = (l: { text: string; x: number; y: number; front: boolean }) => {
    const sprite = labelSprite(l.text.toUpperCase())
    if (!sprite) return
    const w = sprite.width / dpr
    const h = sprite.height / dpr
    // Kept inside the canvas: at the orbit's ends a label slides inward.
    const x = Math.max(w / 2 + 7, Math.min(width - w / 2 - 7, l.x))
    // Placed on whole device pixels, so the label is copied, not resampled.
    const left = Math.round((x - w / 2) * dpr) / dpr
    const top = Math.round((l.y - h / 2) * dpr) / dpr
    g.globalAlpha = l.front ? 1 : 0.32
    g.drawImage(sprite, left, top, w, h)
    g.globalAlpha = 1
  }
  orbitArc(Math.PI, Math.PI * 2, 0.22)
  labels.filter((l) => !l.front).forEach(drawLabel)

  // A faint wireframe gives the glyphs a definite sphere: the rim, and the
  // equator and two latitudes, which rotation about y leaves where they are.
  g.setLineDash([])
  g.lineWidth = 1
  g.strokeStyle = `rgba(${PINK}, 0.3)`
  g.beginPath()
  g.arc(cx, cy, R, 0, Math.PI * 2)
  g.stroke()
  for (const lat of [-Math.PI / 6, 0, Math.PI / 6]) {
    g.strokeStyle = `rgba(${PINK}, ${lat === 0 ? 0.22 : 0.14})`
    g.beginPath()
    g.ellipse(cx, cy - R * Math.sin(lat) * Math.cos(TILT), R * Math.cos(lat), R * Math.cos(lat) * Math.sin(TILT), 0, 0, Math.PI * 2)
    g.stroke()
  }

  // The globe: rotate each point about y, lean it about x, project.
  const ca = Math.cos(angle)
  const sa = Math.sin(angle)
  const cb = Math.cos(TILT)
  const sb = Math.sin(TILT)
  const band = (((time * 0.00022) % 2.8) - 1.4) // a bright band falling down the face
  g.textAlign = 'center'
  g.textBaseline = 'middle'
  // Grouped by font and colour (opacity quantised to 5% steps), so each group
  // sets its font and fill once instead of once per glyph.
  const groups = new Map<string, { font: string; style: string; glyphs: Array<{ ch: string; x: number; y: number }> }>()
  for (const p of points) {
    const x1 = p.x * ca + p.z * sa
    const z1 = -p.x * sa + p.z * ca
    const y2 = p.y * cb - z1 * sb
    const z2 = p.y * sb + z1 * cb
    const sx = cx + x1 * R
    const sy = cy + y2 * R
    const near = (z2 + 1) / 2 // 0 at the back, 1 facing us
    const rain = z2 > 0 ? Math.exp(-((y2 - band) ** 2) / 0.012) : 0
    if (moving && Math.random() < 0.006 + rain * 0.08) p.ch = glyph()
    let alpha = 0.1 + 0.62 * near ** 1.6 + rain * 0.7
    if (z2 < 0) alpha *= 0.55
    if (behindText(sx, sy)) alpha *= 0.22
    if (alpha < 0.04) continue
    const bright = rain > 0.45
    const size = Math.round(8 + 6 * near)
    const a = Math.round(Math.min(1, alpha) * 20) / 20
    const key = `${bright ? 1 : 0}|${size}|${a}`
    let group = groups.get(key)
    if (!group) {
      group = {
        font: `${bright ? 600 : 500} ${size}px "Geist Mono Variable", ui-monospace, monospace`,
        style: `rgba(${bright ? LIGHT : PINK}, ${a})`,
        glyphs: [],
      }
      groups.set(key, group)
    }
    group.glyphs.push({ ch: p.ch, x: sx, y: sy })
  }
  for (const { font, style, glyphs } of groups.values()) {
    g.font = font
    g.fillStyle = style
    for (const q of glyphs) g.fillText(q.ch, q.x, q.y)
  }

  // Edges from the globe's rim to each tagline, with a packet travelling out.
  links.forEach(({ box }, k) => {
    // Meet a block beside the globe at its inner edge; one below it, just above.
    const below = box.t > cy + R * 1.2
    const ax = box.r < cx ? box.r + 14 : box.l > cx ? box.l - 14 : (box.l + box.r) / 2
    const ay = below ? box.t - 10 : box.b < cy ? box.b - (box.b - box.t) * 0.3 : box.t + (box.b - box.t) * 0.5
    const dx = ax - cx
    const dy = ay - cy
    const len = Math.hypot(dx, dy) || 1
    const sx = cx + (dx / len) * R * 1.04
    const sy = cy + (dy / len) * R * 1.04
    const bend = 0.18 * (k % 2 ? 1 : -1)
    const qx = (sx + ax) / 2 - (dy / len) * len * bend
    const qy = (sy + ay) / 2 + (dx / len) * len * bend
    g.setLineDash([])
    g.strokeStyle = `rgba(${PINK}, 0.5)`
    g.lineWidth = 1.2
    g.beginPath()
    g.moveTo(sx, sy)
    g.quadraticCurveTo(qx, qy, ax, ay)
    g.stroke()
    g.fillStyle = `rgb(${PINK})`
    for (const [x, y, r] of [[sx, sy, 2.5], [ax, ay, 3.5]]) {
      g.beginPath()
      g.arc(x, y, r, 0, Math.PI * 2)
      g.fill()
    }
    if (moving) {
      const t = (time * 0.00032 + k * 0.29) % 1.6
      if (t < 1) {
        const u = 1 - t
        const px = u * u * sx + 2 * u * t * qx + t * t * ax
        const py = u * u * sy + 2 * u * t * qy + t * t * ay
        g.fillStyle = `rgb(${LIGHT})`
        g.beginPath()
        g.arc(px, py, 2.6, 0, Math.PI * 2)
        g.fill()
      }
    }
  })

  // The orbit's near half, and its labels, cross in front of the globe.
  orbitArc(0, Math.PI, 0.5)
  labels.filter((l) => l.front).forEach(drawLabel)
}

function loop(time: number) {
  draw(time)
  frame = visible && !still() ? requestAnimationFrame(loop) : 0
}

/** Draw one still frame, or make sure the loop is running. */
function wake() {
  if (still() || !visible) {
    cancelAnimationFrame(frame)
    frame = 0
    last = 0
    draw(performance.now())
  } else if (!frame) {
    last = 0
    frame = requestAnimationFrame(loop)
  }
}

watch(() => props.paused, wake)

onMounted(() => {
  const h = host.value
  if (!h) return
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
  reducedMotion = motion.matches
  const onMotion = () => {
    reducedMotion = motion.matches
    wake()
  }
  motion.addEventListener('change', onMotion)
  cleanups.push(() => motion.removeEventListener('change', onMotion))

  resize()
  const ro = new ResizeObserver(() => {
    resize()
    draw(performance.now())
  })
  ro.observe(h)
  cleanups.push(() => ro.disconnect())

  // On screen and not yet scrolled past (the sticky hero stays "visible"
  // while the content above it covers it).
  let inView = false
  const update = () => {
    const next = inView && window.scrollY < window.innerHeight * 1.3
    if (next !== visible) {
      visible = next
      wake()
    }
  }
  const io = new IntersectionObserver(([entry]) => {
    inView = entry.isIntersecting
    update()
  })
  io.observe(h)
  cleanups.push(() => io.disconnect())

  // Scrolling spins the globe faster; the boost decays once scrolling stops.
  let lastY = window.scrollY
  const onScroll = () => {
    const y = window.scrollY
    if (!still()) boost = Math.min(9, boost + Math.abs(y - lastY) * 0.05)
    lastY = y
    update()
  }
  window.addEventListener('scroll', onScroll, { passive: true })
  cleanups.push(() => window.removeEventListener('scroll', onScroll))

  // Redraw once the mono face has loaded, so the glyphs are the right shape
  // (and the labels are drawn in it).
  document.fonts?.ready.then(() => {
    labelSprites.clear()
    draw(performance.now())
  })
  draw(performance.now())
})

onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  cleanups.forEach((fn) => fn())
})
</script>

<template>
  <div ref="host" class="cg-globe" aria-hidden="true">
    <canvas ref="canvas" />
  </div>
</template>

<style scoped>
.cg-globe {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

canvas {
  display: block;
  width: 100%;
  height: 100%;
}
</style>
