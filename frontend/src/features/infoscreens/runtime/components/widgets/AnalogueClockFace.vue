<script setup lang="ts">
import { computed } from 'vue'

// A round clock face drawn in SVG on a 100 by 100 grid, so it scales with
// the slot. Hands in the primary colour, ticks muted. Without seconds the
// minute hand moves in whole minutes, so the face only changes once a
// minute even though the widget ticks every second.
const props = defineProps<{ hours: number; minutes: number; seconds: number; showSeconds: boolean }>()

const TICKS = Array.from({ length: 60 }, (_, index) => ({
  index,
  major: index % 5 === 0,
  angle: index * 6,
}))

const hourAngle = computed(() => ((props.hours % 12) + props.minutes / 60) * 30)
const minuteAngle = computed(
  () => (props.minutes + (props.showSeconds ? props.seconds / 60 : 0)) * 6,
)
const secondAngle = computed(() => props.seconds * 6)
</script>

<template>
  <svg class="analogue-clock" viewBox="0 0 100 100" role="img" data-testid="clock-analogue">
    <circle class="analogue-clock-face" cx="50" cy="50" r="48" />
    <line
      v-for="tick in TICKS"
      :key="tick.index"
      class="analogue-clock-tick"
      :class="{ 'analogue-clock-tick--major': tick.major }"
      x1="50"
      :y1="tick.major ? 6 : 4.5"
      x2="50"
      y2="2.5"
      :transform="`rotate(${tick.angle} 50 50)`"
    />
    <line
      class="analogue-clock-hand analogue-clock-hand--hour"
      x1="50"
      y1="50"
      x2="50"
      y2="25"
      :transform="`rotate(${hourAngle} 50 50)`"
      data-testid="clock-hand-hour"
    />
    <line
      class="analogue-clock-hand analogue-clock-hand--minute"
      x1="50"
      y1="50"
      x2="50"
      y2="12"
      :transform="`rotate(${minuteAngle} 50 50)`"
      data-testid="clock-hand-minute"
    />
    <line
      v-if="showSeconds"
      class="analogue-clock-hand analogue-clock-hand--second"
      x1="50"
      y1="58"
      x2="50"
      y2="8"
      :transform="`rotate(${secondAngle} 50 50)`"
      data-testid="clock-hand-second"
    />
    <circle class="analogue-clock-pin" cx="50" cy="50" r="2.2" />
  </svg>
</template>

<style scoped lang="scss">
.analogue-clock {
  flex: 0 1 auto;
  width: auto;
  height: clamp(5rem, 62cqmin, 40rem);
  max-width: 100%;
  aspect-ratio: 1;
}

.analogue-clock-face {
  fill: none;
  stroke: var(--p-content-border-color);
  stroke-width: 1;
}

.analogue-clock-tick {
  stroke: var(--p-text-muted-color);
  stroke-width: 0.6;
  stroke-linecap: round;
}

.analogue-clock-tick--major {
  stroke-width: 1.4;
}

.analogue-clock-hand {
  stroke: var(--p-primary-color);
  stroke-linecap: round;
}

.analogue-clock-hand--hour {
  stroke-width: 4;
}

.analogue-clock-hand--minute {
  stroke-width: 2.6;
}

.analogue-clock-hand--second {
  stroke-width: 0.9;
}

.analogue-clock-pin {
  fill: var(--p-primary-color);
}
</style>
