<script setup lang="ts">
// A decorative halftone field: a disc of dots, sparse at the centre, dense in
// a ring, fading at the rim, with a slow ripple travelling outward. The pointer
// probes it — dots near the cursor fall away and a crosshair follows.
//
// `field` draws the whole disc in the middle of its box; `dome` centres the
// disc on the top edge, so only its lower half shows.
//
// Content can sit in the field: the dots part around any element in the same
// section marked `data-clear`. The first time the field is seen, it blooms
// outward from its centre.
//
// Purely presentational: aria-hidden, drawn only while on screen, and still
// (but still pointer-responsive) under prefers-reduced-motion or `paused`.

import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{ variant?: 'field' | 'dome'; dot?: string; cross?: string; paused?: boolean }>(),
  { variant: 'field', dot: '#b7b39c', cross: '#222222', paused: false },
)

// The disc's shape, as fractions of its radius unless stated.
const SHAPE = {
  ringStart: 0.1, // density starts rising here...
  ringFull: 0.62, // ...and is full here
  rimStart: 0.88, // the fade at the edge starts here...
  rimEnd: 1.02, // ...and reaches nothing here
  cutoff: 0.07, // dots fainter than this are not drawn
  crossFrom: 0.58, // denser than this, a dot is drawn as a cross
  dotSize: 0.42, // a full-density dot, as a fraction of the grid step
}
// The ripple: how many waves fit across the radius, how fast they travel
// (radians per millisecond), and how deep they modulate the density.
const RIPPLE = { waves: 18, speed: 0.0011, depth: 0.2 }
// The pointer clears dots fully within `inner` px and not at all beyond `outer`.
const PROBE = { inner: 24, outer: 130 }
const CROSSHAIR = 8 // half-length of the crosshair arms, px
// Around a [data-clear] element, dots fade back in over this many px.
const CLEAR_FALLOFF = 36
// The first-sight bloom: how long the disc takes to grow to full size, ms.
const BLOOM_MS = 1600

type Rect = { x: number; y: number; w: number; h: number }

const host = ref<HTMLDivElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)

let ctx: CanvasRenderingContext2D | null = null
let width = 0
let height = 0
let frame = 0
let visible = false
let reducedMotion = false
let clears: Rect[] = []
let bloomStart = -1
const pointer = { x: 0, y: 0, active: false }
const cleanups: Array<() => void> = []

const still = () => reducedMotion || props.paused

/** An element's layout box relative to `ancestor`, ignoring transforms. */
function layoutRect(el: HTMLElement, ancestor: HTMLElement): Rect | null {
  let x = 0
  let y = 0
  let n: HTMLElement | null = el
  while (n && n !== ancestor) {
    x += n.offsetLeft
    y += n.offsetTop
    n = n.offsetParent as HTMLElement | null
  }
  return n === ancestor ? { x, y, w: el.offsetWidth, h: el.offsetHeight } : null
}

/** Where the [data-clear] elements of this section sit, relative to the canvas. */
function measureClears() {
  const h = host.value
  const section = h?.offsetParent as HTMLElement | null
  if (!h || !section) return
  clears = [...section.querySelectorAll<HTMLElement>('[data-clear]')]
    .map((el) => layoutRect(el, section))
    .filter((r): r is Rect => r !== null)
    .map((r) => ({ ...r, x: r.x - h.offsetLeft, y: r.y - h.offsetTop }))
}

/** Distance from (x, y) to the nearest clear rect; 0 inside one. */
function clearDistance(x: number, y: number) {
  let best = Infinity
  for (const r of clears) {
    const dx = Math.max(r.x - x, 0, x - (r.x + r.w))
    const dy = Math.max(r.y - y, 0, y - (r.y + r.h))
    best = Math.min(best, Math.hypot(dx, dy))
  }
  return best
}

/** 0 before the field is first seen, easing to 1 as it blooms; 1 when still. */
function bloom(now: number) {
  if (still()) return 1
  if (bloomStart < 0) return 0
  const t = Math.min(1, (now - bloomStart) / BLOOM_MS)
  return 1 - Math.pow(1 - t, 3)
}

const smooth = (a: number, b: number, x: number) => {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)))
  return t * t * (3 - 2 * t)
}

function resize() {
  const c = canvas.value
  const h = host.value
  if (!c || !h) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  width = h.clientWidth
  height = h.clientHeight
  c.width = Math.round(width * dpr)
  c.height = Math.round(height * dpr)
  c.style.width = `${width}px`
  c.style.height = `${height}px`
  ctx = c.getContext('2d')
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0)
  measureClears()
}

function draw(time: number) {
  if (!ctx) return
  ctx.clearRect(0, 0, width, height)

  const step = width < 640 ? 9 : 11
  const dome = props.variant === 'dome'
  const cx = width / 2
  const cy = dome ? 0 : height / 2
  // A dome may fill its box's height; a field keeps its disc a little inside.
  const full = dome ? Math.min(width * 0.42, height * 0.98) : Math.min(width, height * 1.25) * 0.47
  const grown = bloom(performance.now())
  if (grown <= 0) return
  const radius = full * grown
  const moving = !still()

  ctx.fillStyle = props.dot
  ctx.strokeStyle = props.dot
  ctx.lineWidth = 1
  ctx.beginPath()

  for (let y = step / 2; y < height; y += step) {
    for (let x = step / 2; x < width; x += step) {
      const r = Math.hypot(x - cx, y - cy) / radius
      if (r > SHAPE.rimEnd) continue
      let v = smooth(SHAPE.ringStart, SHAPE.ringFull, r) * (1 - smooth(SHAPE.rimStart, SHAPE.rimEnd, r))
      if (moving) v *= 1 - RIPPLE.depth + RIPPLE.depth * Math.sin(r * RIPPLE.waves - time * RIPPLE.speed)
      if (pointer.active) v *= smooth(PROBE.inner, PROBE.outer, Math.hypot(x - pointer.x, y - pointer.y))
      if (clears.length) v *= smooth(0, CLEAR_FALLOFF, clearDistance(x, y))
      if (v < SHAPE.cutoff) continue
      const s = v * step * SHAPE.dotSize
      if (v > SHAPE.crossFrom) {
        ctx.moveTo(x - s / 2, y - s / 2)
        ctx.lineTo(x + s / 2, y + s / 2)
        ctx.moveTo(x + s / 2, y - s / 2)
        ctx.lineTo(x - s / 2, y + s / 2)
      } else {
        ctx.fillRect(x - s / 2, y - s / 2, s, s)
      }
    }
  }
  ctx.stroke()

  // Crosshair: on the pointer while it is over the field, else at the centre;
  // never over content sitting in a clearing.
  const hx = pointer.active ? pointer.x : cx
  const hy = pointer.active ? pointer.y : dome ? Math.min(height * 0.42, full * 0.42) : cy
  if (clears.length && clearDistance(hx, hy) < CROSSHAIR) return
  ctx.strokeStyle = props.cross
  ctx.lineWidth = 1.5
  ctx.beginPath()
  ctx.moveTo(hx - CROSSHAIR, hy)
  ctx.lineTo(hx + CROSSHAIR, hy)
  ctx.moveTo(hx, hy - CROSSHAIR)
  ctx.lineTo(hx, hy + CROSSHAIR)
  ctx.stroke()
}

function loop(time: number) {
  draw(time)
  frame = visible && !still() ? requestAnimationFrame(loop) : 0
}

/** The field has come into view: start its bloom, once. */
function seen() {
  if (bloomStart < 0) bloomStart = performance.now()
}

/** Redraw once if still; otherwise make sure the animation loop is running. */
function wake() {
  if (still()) {
    cancelAnimationFrame(frame)
    frame = 0
    draw(0)
  } else if (!frame && visible) {
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

  const io = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting
    if (visible) seen()
    wake()
  })
  io.observe(h)
  cleanups.push(() => io.disconnect())

  // Content in a clearing can change size (fonts load, text wraps); remeasure.
  const section = h.offsetParent as HTMLElement | null
  const clearing = new ResizeObserver(() => {
    measureClears()
    if (still()) draw(0)
  })
  section?.querySelectorAll('[data-clear]').forEach((el) => clearing.observe(el))
  cleanups.push(() => clearing.disconnect())

  const move = (e: PointerEvent) => {
    const box = h.getBoundingClientRect()
    pointer.x = e.clientX - box.left
    pointer.y = e.clientY - box.top
    pointer.active = true
    if (still()) draw(0)
  }
  const leave = () => {
    pointer.active = false
    if (still()) draw(0)
  }
  h.addEventListener('pointermove', move)
  h.addEventListener('pointerleave', leave)
  cleanups.push(() => {
    h.removeEventListener('pointermove', move)
    h.removeEventListener('pointerleave', leave)
  })

  draw(0)
})

onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  cleanups.forEach((fn) => fn())
})
</script>

<template>
  <div ref="host" class="cg-halftone" aria-hidden="true">
    <canvas ref="canvas" />
  </div>
</template>

<style scoped>
.cg-halftone {
  position: relative;
  width: 100%;
  height: 100%;
  touch-action: pan-y;
}

canvas {
  position: absolute;
  inset: 0;
  display: block;
}
</style>
