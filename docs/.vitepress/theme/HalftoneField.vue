<script setup lang="ts">
// A decorative halftone field: a disc of dots, sparse at the centre, dense in
// a ring, fading at the rim, with a slow ripple travelling outward. The pointer
// probes it — dots near the cursor fall away and a crosshair follows.
//
// `field` draws the whole disc in the middle of its box; `dome` centres the
// disc on the top edge, so only its lower half shows.
//
// Purely presentational: aria-hidden, drawn only while on screen, and still
// (but still pointer-responsive) under prefers-reduced-motion.

import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{ variant?: 'field' | 'dome'; dot?: string; cross?: string }>(),
  { variant: 'field', dot: '#b7b39c', cross: '#222222' },
)

const host = ref<HTMLDivElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)

let ctx: CanvasRenderingContext2D | null = null
let width = 0
let height = 0
let frame = 0
let visible = false
let still = false
const pointer = { x: 0, y: 0, active: false }
const cleanups: Array<() => void> = []

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
}

function draw(time: number) {
  if (!ctx) return
  ctx.clearRect(0, 0, width, height)

  const step = width < 640 ? 9 : 11
  const dome = props.variant === 'dome'
  const cx = width / 2
  const cy = dome ? 0 : height / 2
  const radius = dome ? Math.min(width * 0.42, height * 0.98) : Math.min(width, height * 1.25) * 0.47

  ctx.fillStyle = props.dot
  ctx.strokeStyle = props.dot
  ctx.lineWidth = 1
  ctx.beginPath()

  for (let y = step / 2; y < height; y += step) {
    for (let x = step / 2; x < width; x += step) {
      const r = Math.hypot(x - cx, y - cy) / radius
      if (r > 1.02) continue
      let v = smooth(0.1, 0.62, r) * (1 - smooth(0.88, 1.02, r))
      if (!still) v *= 0.8 + 0.2 * Math.sin(r * 18 - time * 0.0011)
      if (pointer.active) v *= smooth(24, 130, Math.hypot(x - pointer.x, y - pointer.y))
      if (v < 0.07) continue
      const s = v * step * 0.42
      if (v > 0.58) {
        // Dense band: small crosses.
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

  // Crosshair: on the pointer while it is over the field, else at the centre.
  const hx = pointer.active ? pointer.x : cx
  const hy = pointer.active ? pointer.y : dome ? Math.min(height * 0.42, radius * 0.42) : cy
  ctx.strokeStyle = props.cross
  ctx.lineWidth = 1.5
  ctx.beginPath()
  ctx.moveTo(hx - 8, hy)
  ctx.lineTo(hx + 8, hy)
  ctx.moveTo(hx, hy - 8)
  ctx.lineTo(hx, hy + 8)
  ctx.stroke()
}

function loop(time: number) {
  draw(time)
  frame = visible && !still ? requestAnimationFrame(loop) : 0
}

function wake() {
  if (still) draw(0)
  else if (!frame && visible) frame = requestAnimationFrame(loop)
}

onMounted(() => {
  const h = host.value
  if (!h) return
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)')
  still = motion.matches
  const onMotion = () => {
    still = motion.matches
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
    wake()
  })
  io.observe(h)
  cleanups.push(() => io.disconnect())

  const move = (e: PointerEvent) => {
    const box = h.getBoundingClientRect()
    pointer.x = e.clientX - box.left
    pointer.y = e.clientY - box.top
    pointer.active = true
    if (still) draw(0)
  }
  const leave = () => {
    pointer.active = false
    if (still) draw(0)
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
