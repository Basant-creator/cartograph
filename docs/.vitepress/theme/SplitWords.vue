<script setup lang="ts">
// A heading whose words rise into place, one after another, when it enters
// the viewport — or, with `fill`, brighten in reading order as it is
// scrolled. Words are split here, at render time, so the server output and
// the hydrated page agree; the words stay separated by real spaces, so the
// text reads and copies as ordinary text.

import { computed } from 'vue'

const props = withDefaults(defineProps<{ lines: string[]; tag?: string; fill?: boolean }>(), {
  tag: 'h2',
  fill: false,
})

const words = computed(() => {
  let n = 0
  return props.lines.map((line) => line.split(/\s+/).filter(Boolean).map((text) => ({ text, i: n++ })))
})
const count = computed(() => words.value.reduce((sum, line) => sum + line.length, 0))
</script>

<template>
  <component
    :is="tag"
    class="cg-split"
    :class="{ 'cg-split--fill': fill }"
    :style="{ '--n': count }"
    :data-split="fill ? undefined : ''"
    :data-scroll="fill ? 'enter' : undefined"
  >
    <template v-for="(line, l) in words" :key="l">
      <br v-if="l > 0" />
      <template v-for="(w, k) in line" :key="w.i">
        <span class="cg-word"><span class="cg-word-in" :style="{ '--w': w.i }">{{ w.text }}</span></span>{{ k < line.length - 1 ? ' ' : '' }}
      </template>
    </template>
  </component>
</template>
