<script setup lang="ts">
// The hero's background: a drifting graph. Nodes wander slowly, an edge is
// drawn between any two that come within reach, and small packets travel
// along edges — evidence moving through the graph. The pointer joins as a
// node of its own. It is decoration only: aria-hidden, faint enough that the
// headline keeps its contrast, drawn only while visible and `active`, and
// frozen into a single still frame under reduced motion or `paused`.

import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{ paused?: boolean; active?: boolean }>(), {
  paused: false,
  active: true,
})

const NODE = { perPixel: 1 / 16000, max: 90, speed: 0.12, radius: 1.6 }
const EDGE = { reach: 150, alpha: 0.22 } // reach in px; alpha at zero distance
const POINTER = { reach: 190, pull: 0.0006 }
const PACKETS = { count: 7, speed: 0.012 } // fraction of an edge per frame
const PINK = '205, 141, 189'

type Node = { x: number; y: number; vx: number; vy: number }
type Packet = { a: number; b: number; t: number }

const host = ref<HTMLDivElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)

let ctx: CanvasRenderingContext2D | null = null
let width = 0
let height = 0
let frame = 0
let visible = false
let reducedMotion = false
let nodes: Node[] = []
let packets: Packet[] = []
const pointer = { x: 0, y: 0, active: false }
const cleanups: Array<() => void> = []

const still = () => reducedMotion || props.paused

// A fixed seed, so the still frame is the same on every visit.
let seed = 7
const random = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646

function populate() {
  seed = 7
  const count = Math.min(NODE.max, Math.round(width * height * NODE.perPixel))
  nodes = Array.from({ length: count }, () => {
    const angle = random() * Math.PI * 2
    return { x: random() * width, y: random() * height, vx: Math.cos(angle) * NODE.speed, vy: Math.sin(angle) * NODE.speed }
  })
  packets = []
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
  ctx = c.getContext('2d')
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0)
  populate()
}

function step() {
  for (const n of nodes) {
    if (pointer.active) {
      const dx = pointer.x - n.x
      const dy = pointer.y - n.y
      if (Math.hypot(dx, dy) < POINTER.reach) {
        n.vx += dx * POINTER.pull
        n.vy += dy * POINTER.pull
      }
    }
    // Keep drift slow even after the pointer has pulled a node.
    const v = Math.hypot(n.vx, n.vy)
    if (v > NODE.speed * 3) {
      n.vx *= 0.96
      n.vy *= 0.96
    }
    n.x += n.vx
    n.y += n.vy
    if (n.x < 0 || n.x > width) n.vx *= -1
    if (n.y < 0 || n.y > height) n.vy *= -1
  }
  for (const p of packets) p.t += PACKETS.speed
  packets = packets.filter((p) => p.t < 1 && Math.hypot(nodes[p.a].x - nodes[p.b].x, nodes[p.a].y - nodes[p.b].y) < EDGE.reach)
}

function draw() {
  if (!ctx) return
  ctx.clearRect(0, 0, width, height)
  const edges: Array<[number, number]> = []

  ctx.lineWidth = 1
  for (let i = 0; i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      const d = Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y)
      if (d > EDGE.reach) continue
      edges.push([i, j])
      ctx.strokeStyle = `rgba(${PINK}, ${EDGE.alpha * (1 - d / EDGE.reach)})`
      ctx.beginPath()
      ctx.moveTo(nodes[i].x, nodes[i].y)
      ctx.lineTo(nodes[j].x, nodes[j].y)
      ctx.stroke()
    }
  }
  if (pointer.active) {
    for (const n of nodes) {
      const d = Math.hypot(n.x - pointer.x, n.y - pointer.y)
      if (d > POINTER.reach) continue
      ctx.strokeStyle = `rgba(${PINK}, ${0.4 * (1 - d / POINTER.reach)})`
      ctx.beginPath()
      ctx.moveTo(pointer.x, pointer.y)
      ctx.lineTo(n.x, n.y)
      ctx.stroke()
    }
  }

  ctx.fillStyle = `rgba(${PINK}, 0.55)`
  for (const n of nodes) {
    ctx.beginPath()
    ctx.arc(n.x, n.y, NODE.radius, 0, Math.PI * 2)
    ctx.fill()
  }

  if (!still()) {
    while (packets.length < PACKETS.count && edges.length) {
      const [a, b] = edges[Math.floor(Math.random() * edges.length)]
      packets.push(Math.random() < 0.5 ? { a, b, t: 0 } : { a: b, b: a, t: 0 })
    }
    ctx.fillStyle = 'rgba(237, 223, 238, 0.9)'
    for (const p of packets) {
      const x = nodes[p.a].x + (nodes[p.b].x - nodes[p.a].x) * p.t
      const y = nodes[p.a].y + (nodes[p.b].y - nodes[p.a].y) * p.t
      ctx.beginPath()
      ctx.arc(x, y, 1.8, 0, Math.PI * 2)
      ctx.fill()
    }
  }
}

function loop() {
  step()
  draw()
  frame = visible && props.active && !still() ? requestAnimationFrame(loop) : 0
}

/** Draw one still frame, or make sure the loop is running. */
function wake() {
  if (still() || !props.active || !visible) {
    cancelAnimationFrame(frame)
    frame = 0
    draw()
  } else if (!frame) {
    frame = requestAnimationFrame(loop)
  }
}

watch(() => [props.paused, props.active], wake)

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
    draw()
  })
  ro.observe(h)
  cleanups.push(() => ro.disconnect())

  const io = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting
    wake()
  })
  io.observe(h)
  cleanups.push(() => io.disconnect())

  // The canvas sits under the headline, so listen on its section.
  const section = h.parentElement ?? h
  const move = (e: PointerEvent) => {
    const box = h.getBoundingClientRect()
    pointer.x = e.clientX - box.left
    pointer.y = e.clientY - box.top
    pointer.active = true
    if (still()) draw()
  }
  const leave = () => {
    pointer.active = false
    if (still()) draw()
  }
  section.addEventListener('pointermove', move)
  section.addEventListener('pointerleave', leave)
  cleanups.push(() => {
    section.removeEventListener('pointermove', move)
    section.removeEventListener('pointerleave', leave)
  })

  draw()
})

onBeforeUnmount(() => {
  cancelAnimationFrame(frame)
  cleanups.forEach((fn) => fn())
})
</script>

<template>
  <div ref="host" class="cg-graph" aria-hidden="true">
    <canvas ref="canvas" />
  </div>
</template>

<style scoped>
.cg-graph {
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
