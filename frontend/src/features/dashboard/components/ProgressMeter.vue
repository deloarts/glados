<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    label: string
    value: number
    max: number
    colorFrom?: string
    colorTo?: string
  }>(),
  { colorFrom: 'var(--p-primary-400)', colorTo: 'var(--p-primary-600)' },
)

const percent = computed(() => (props.max > 0 ? Math.min(100, (props.value / props.max) * 100) : 0))
</script>

<template>
  <div class="progress-meter">
    <div class="progress-meter-labels">
      <span class="progress-meter-label">{{ label }}</span>
      <span class="progress-meter-value">{{ value }}/{{ max }}</span>
    </div>
    <div class="progress-meter-track">
      <div
        class="progress-meter-fill"
        :style="{
          width: `${percent}%`,
          background: `linear-gradient(90deg, ${colorFrom}, ${colorTo})`,
        }"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.progress-meter {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.progress-meter-labels {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: var(--font-size-sm);
}

.progress-meter-label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-meter-value {
  flex-shrink: 0;
  color: var(--p-text-muted-color);
  margin-left: var(--space-2);
}

.progress-meter-track {
  height: 8px;
  border-radius: 999px;
  background: var(--p-surface-200);
  overflow: hidden;
}

.p-dark .progress-meter-track {
  background: var(--p-surface-700);
}

.progress-meter-fill {
  height: 100%;
  border-radius: 999px;
  transition: width 0.6s ease-out;
}
</style>
