<script setup lang="ts">
// The hero's background: Cartograph's own mark — three nodes, two edges —
// drawn monumentally, a shade above the ground. A few large forms rather than
// many small ones: it has weight without noise.
//
// It builds once (the edges draw, the nodes land), then is nearly still: one
// packet of evidence crosses an edge at a time, a faint orbit turns, and the
// mark leans a little toward the pointer. All of that lives under .cg-motion,
// so with motion paused or reduced it is simply the mark.
//
// Geometry, in the 1440 × 900 view box: the left node L (300, 470) r 120, and
// T (1150, 150) and B (1150, 760) r 86 — B sits clear of the hero's foot line.
// Each edge runs from L's rim to the other node's rim along their centre line:
// toward T the unit vector is (0.9359, −0.3523), toward B (0.9464, 0.3229).

import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = withDefaults(defineProps<{ paused?: boolean }>(), { paused: false })

// How far the mark leans toward the pointer, in view-box units.
const LEAN = { x: 18, y: 12 }

const svg = ref<SVGSVGElement | null>(null)
/** A portrait hero would crop the wide mark to its middle; fit it instead. */
const portrait = ref(false)
const cleanups: Array<() => void> = []

onMounted(() => {
  const el = svg.value
  const section = el?.parentElement
  if (!el || !section) return

  const ro = new ResizeObserver(() => (portrait.value = section.clientWidth < section.clientHeight))
  ro.observe(section)
  cleanups.push(() => ro.disconnect())

  if (!window.matchMedia('(pointer: fine)').matches) return
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)')

  const target = { x: 0, y: 0 }
  const current = { x: 0, y: 0 }
  let frame = 0

  const loop = () => {
    current.x += (target.x - current.x) * 0.06
    current.y += (target.y - current.y) * 0.06
    el.style.setProperty('--lx', current.x.toFixed(3))
    el.style.setProperty('--ly', current.y.toFixed(3))
    frame = Math.abs(target.x - current.x) + Math.abs(target.y - current.y) > 0.002 ? requestAnimationFrame(loop) : 0
  }
  const move = (e: PointerEvent) => {
    if (props.paused || reduced.matches) return
    const box = section.getBoundingClientRect()
    target.x = ((e.clientX - box.left) / box.width - 0.5) * 2
    target.y = ((e.clientY - box.top) / box.height - 0.5) * 2
    if (!frame) frame = requestAnimationFrame(loop)
  }
  const leave = () => {
    target.x = 0
    target.y = 0
    if (!frame) frame = requestAnimationFrame(loop)
  }
  section.addEventListener('pointermove', move)
  section.addEventListener('pointerleave', leave)
  cleanups.push(() => {
    cancelAnimationFrame(frame)
    section.removeEventListener('pointermove', move)
    section.removeEventListener('pointerleave', leave)
  })
})

onBeforeUnmount(() => cleanups.forEach((fn) => fn()))
</script>

<template>
  <svg
    ref="svg"
    class="hm"
    viewBox="0 0 1440 900"
    :preserveAspectRatio="portrait ? 'xMidYMid meet' : 'xMidYMid slice'"
    aria-hidden="true"
    :style="{ '--lean-x': `${LEAN.x}px`, '--lean-y': `${LEAN.y}px` }"
  >
    <g class="hm-lean">
      <path class="hm-edge" pathLength="1" d="M412.3 427.7 1069.5 180.3" />
      <path class="hm-edge" pathLength="1" d="M413.6 508.7 1068.6 732.2" style="--d: 0.15s" />
      <circle class="hm-orbit" cx="300" cy="470" r="170" />
      <circle class="hm-node" cx="300" cy="470" r="120" />
      <circle class="hm-node" cx="1150" cy="150" r="86" style="--d: 0.2s" />
      <circle class="hm-node" cx="1150" cy="760" r="86" style="--d: 0.3s" />
      <circle class="hm-packet hm-packet--t" cx="412.3" cy="427.7" r="7" />
      <circle class="hm-packet hm-packet--b" cx="413.6" cy="508.7" r="7" />
    </g>
  </svg>
</template>

<style scoped>
.hm {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.hm-lean {
  transform: translate(calc(var(--lx, 0) * var(--lean-x)), calc(var(--ly, 0) * var(--lean-y)));
}

/* Solid discs and heavy strokes, a step above the ground: weight that never
   competes with the type (the headline keeps 5.6:1 over a disc). */
.hm-edge,
.hm-node {
  stroke: #36313b;
  stroke-width: 22;
}

.hm-edge {
  fill: none;
}

.hm-node {
  fill: #29262c;
}

.hm-orbit {
  fill: none;
  stroke: rgba(205, 141, 189, 0.24);
  stroke-width: 1.5;
  stroke-dasharray: 2 12;
  transform-box: fill-box;
  transform-origin: center;
}

.hm-node {
  transform-box: fill-box;
  transform-origin: center;
}

/* Packets exist only while motion is on. */
.hm-packet {
  fill: #cd8dbd;
  opacity: 0;
}

/* Build: the edges draw from the left node, then the nodes land. */
.cg-motion .hm-edge {
  stroke-dasharray: 1;
  stroke-dashoffset: 1;
  animation: hm-draw 1.4s var(--cg-ease) calc(0.5s + var(--d, 0s)) both;
}

.cg-motion .hm-node {
  animation: hm-land 1.2s var(--cg-ease) calc(0.95s + var(--d, 0s)) both;
}

.cg-motion .hm-orbit {
  animation:
    hm-fade 1.2s ease 1.6s both,
    hm-spin 90s linear 1.6s infinite;
}

/* One packet at a time: each crosses its edge, rests, and the other goes. */
.cg-motion .hm-packet--t {
  animation: hm-cross-t 8s ease-in-out 2.6s infinite;
}

.cg-motion .hm-packet--b {
  animation: hm-cross-b 8s ease-in-out 6.6s infinite;
}

@keyframes hm-draw {
  from {
    stroke-dashoffset: 1;
  }
  to {
    stroke-dashoffset: 0;
  }
}

@keyframes hm-land {
  from {
    transform: scale(0.55);
    opacity: 0;
  }
}

@keyframes hm-fade {
  from {
    opacity: 0;
  }
}

@keyframes hm-spin {
  to {
    transform: rotate(360deg);
  }
}

/* From L's rim to the far node's rim: (657.2, −247.4) to T, (655, 223.5) to B. */
@keyframes hm-cross-t {
  0% {
    transform: translate(0, 0);
    opacity: 0;
  }
  6% {
    opacity: 1;
  }
  40% {
    transform: translate(657.2px, -247.4px);
    opacity: 1;
  }
  46%,
  100% {
    transform: translate(657.2px, -247.4px);
    opacity: 0;
  }
}

@keyframes hm-cross-b {
  0% {
    transform: translate(0, 0);
    opacity: 0;
  }
  6% {
    opacity: 1;
  }
  40% {
    transform: translate(655px, 223.5px);
    opacity: 1;
  }
  46%,
  100% {
    transform: translate(655px, 223.5px);
    opacity: 0;
  }
}
</style>
