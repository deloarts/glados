<script setup lang="ts">
/**
 * An SVG text label with the standard's symbols set as subscripts, for the
 * sketches. Subscripts are shifted with dy rather than baseline-shift, which
 * not every browser supports on tspan. Position and anchor come in as
 * attributes on the text element.
 */
import { computed } from 'vue'

import { splitSubscripts } from '../utils/safetyDistance/format'

const props = defineProps<{ text: string }>()

const SHIFT = 3

const parts = computed(() =>
  splitSubscripts(props.text).map((part, index, all) => ({
    ...part,
    dy: part.sub ? SHIFT : index > 0 && all[index - 1]?.sub ? -SHIFT : undefined,
  })),
)
</script>

<template>
  <text><tspan v-for="(part, index) in parts" :key="index" :dy="part.dy" :font-size="part.sub ? '75%' : undefined">{{ part.text }}</tspan></text>
</template>
