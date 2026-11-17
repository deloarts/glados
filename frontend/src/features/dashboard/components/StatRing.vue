<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    value: number
    max: number
    colorVar: string
    trackColorVar: string
    size?: number
    strokeWidth?: number
  }>(),
  { size: 44, strokeWidth: 5 },
)

const radius = computed(() => (props.size - props.strokeWidth) / 2)
const circumference = computed(() => 2 * Math.PI * radius.value)
const ratio = computed(() => (props.max > 0 ? Math.min(1, props.value / props.max) : 0))
const dashOffset = computed(() => circumference.value * (1 - ratio.value))
const center = computed(() => props.size / 2)
</script>

<template>
  <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`" class="stat-ring" role="img">
    <circle
      :cx="center"
      :cy="center"
      :r="radius"
      fill="none"
      :stroke="trackColorVar"
      :stroke-width="strokeWidth"
    />
    <circle
      :cx="center"
      :cy="center"
      :r="radius"
      fill="none"
      :stroke="colorVar"
      :stroke-width="strokeWidth"
      stroke-linecap="round"
      :stroke-dasharray="circumference"
      :stroke-dashoffset="dashOffset"
      class="stat-ring-fill"
      :transform="`rotate(-90 ${center} ${center})`"
    />
  </svg>
</template>

<style scoped lang="scss">
.stat-ring-fill {
  transition: stroke-dashoffset 0.6s ease-out;
}
</style>
