<script setup lang="ts">
import { computed } from 'vue'

// A binary-coded-decimal clock: one column per digit of hours, minutes and,
// when shown, seconds. A column has as many dots as its digit can need (two
// for the tens of hours, three for the tens of minutes and seconds, four
// otherwise), the lowest value at the bottom, lit dots in the primary colour.
// The digit itself stands small below its column.
const props = defineProps<{ hours: number; minutes: number; seconds: number; showSeconds: boolean }>()

interface DigitColumn {
  key: string
  digit: number
  dots: { value: number; lit: boolean }[]
}

function column(key: string, digit: number, bits: number): DigitColumn {
  const dots = Array.from({ length: bits }, (_, index) => {
    const value = 2 ** (bits - 1 - index)
    return { value, lit: (digit & value) !== 0 }
  })
  return { key, digit, dots }
}

function pair(key: string, value: number, tensBits: number): DigitColumn[] {
  return [column(`${key}-tens`, Math.floor(value / 10), tensBits), column(`${key}-ones`, value % 10, 4)]
}

const groups = computed(() => {
  const result = [
    { key: 'hours', columns: pair('hours', props.hours, 2) },
    { key: 'minutes', columns: pair('minutes', props.minutes, 3) },
  ]
  if (props.showSeconds) result.push({ key: 'seconds', columns: pair('seconds', props.seconds, 3) })
  return result
})
</script>

<template>
  <div class="binary-clock" role="img" data-testid="clock-binary">
    <div v-for="group in groups" :key="group.key" class="binary-clock-group">
      <div
        v-for="digitColumn in group.columns"
        :key="digitColumn.key"
        class="binary-clock-column"
        :data-digit="digitColumn.digit"
        data-testid="binary-digit"
      >
        <span
          v-for="dot in digitColumn.dots"
          :key="dot.value"
          class="binary-clock-dot"
          :class="{ 'binary-clock-dot--lit': dot.lit }"
          data-testid="binary-dot"
        />
        <span class="binary-clock-label">{{ digitColumn.digit }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.binary-clock {
  --binary-dot: clamp(0.7rem, 9cqmin, 6rem);
  display: flex;
  align-items: flex-end;
  gap: calc(var(--binary-dot) * 0.9);
}

.binary-clock-group {
  display: flex;
  align-items: flex-end;
  gap: calc(var(--binary-dot) * 0.35);
}

.binary-clock-column {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: calc(var(--binary-dot) * 0.3);
}

.binary-clock-dot {
  width: var(--binary-dot);
  height: var(--binary-dot);
  border-radius: 50%;
  background: var(--p-content-border-color);
}

.binary-clock-dot--lit {
  background: var(--p-primary-color);
}

.binary-clock-label {
  font-size: calc(var(--binary-dot) * 0.55);
  line-height: 1;
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
}
</style>
