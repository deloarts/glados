<script setup lang="ts">
// One KPI stat tile: the value or an n/a reason, a definition tooltip and a
// delta versus the previous period. The caller supplies formatValue, so the
// tile stays unit-agnostic.
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

interface Props {
  label: string
  definition: string
  value: number | null
  formatValue: (value: number) => string
  /** Omit when there is nothing to compare against yet. */
  previousValue?: number | null
  /** Shown under the value/na state, e.g. a sample size note. */
  note?: string | null
  /** Shown instead of the value when it is null. */
  naReason?: string | null
  /** Whether a rising value is the good direction; false for e.g. scrap ratio or throughput time. */
  higherIsBetter?: boolean
  /** MDI icon class for the tile's own icon, e.g. "mdi mdi-calendar-check-outline". */
  icon?: string
}

const props = withDefaults(defineProps<Props>(), {
  previousValue: null,
  note: null,
  naReason: null,
  higherIsBetter: true,
  icon: undefined,
})

const isNa = computed(() => props.value === null)

const displayValue = computed(() => (props.value === null ? null : props.formatValue(props.value)))

interface Delta {
  text: string
  direction: 'up' | 'down' | 'flat'
  favorable: boolean | null
}

// Floating-point noise between two ratios reads as no change.
const FLAT_EPSILON = 1e-9

const delta = computed<Delta | null>(() => {
  if (props.value === null || props.previousValue === null || props.previousValue === undefined) {
    return null
  }
  const diff = props.value - props.previousValue
  if (Math.abs(diff) < FLAT_EPSILON) {
    return { text: props.formatValue(0), direction: 'flat', favorable: null }
  }
  const direction = diff > 0 ? 'up' : 'down'
  const favorable = props.higherIsBetter ? direction === 'up' : direction === 'down'
  const text = diff > 0 ? `+${props.formatValue(diff)}` : props.formatValue(diff)
  return { text, direction, favorable }
})

const deltaIcon = computed(() => {
  switch (delta.value?.direction) {
    case 'up':
      return 'mdi mdi-arrow-up-bold'
    case 'down':
      return 'mdi mdi-arrow-down-bold'
    default:
      return 'mdi mdi-minus'
  }
})
</script>

<template>
  <div class="kpi-tile" :class="{ 'kpi-tile--na': isNa }">
    <div class="kpi-tile-header">
      <span class="kpi-tile-label">
        <i v-if="icon" :class="icon" class="kpi-tile-icon" aria-hidden="true" />
        <span class="kpi-tile-label-text">{{ label }}</span>
      </span>
      <i
        class="mdi mdi-information-outline kpi-tile-info"
        aria-hidden="true"
        v-tooltip.top="definition"
      />
    </div>

    <div v-if="isNa" class="kpi-tile-na">
      <span class="kpi-tile-na-value">{{ t('productionKpi.tiles.naValue') }}</span>
      <span v-if="naReason" class="kpi-tile-na-reason">{{ naReason }}</span>
    </div>
    <template v-else>
      <div class="kpi-tile-value">{{ displayValue }}</div>
      <div class="kpi-tile-footer">
        <span v-if="note" class="kpi-tile-note">{{ note }}</span>
        <span
          v-if="delta"
          class="kpi-tile-delta"
          :class="{
            'kpi-tile-delta--favorable': delta.favorable === true,
            'kpi-tile-delta--unfavorable': delta.favorable === false,
          }"
          v-tooltip.top="t('productionKpi.tiles.deltaTooltip')"
        >
          <i :class="deltaIcon" aria-hidden="true" />
          {{ delta.text }}
        </span>
      </div>
    </template>
  </div>
</template>

<style scoped lang="scss">
.kpi-tile {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--p-content-border-radius);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  min-width: 0;
}

.kpi-tile--na {
  background: color-mix(in srgb, var(--p-content-background) 60%, transparent);
}

.kpi-tile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}

.kpi-tile-label {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  min-width: 0;
  // Only the label text truncates, so the icon glyph is never cropped.
  overflow: visible;
}

.kpi-tile-icon {
  flex-shrink: 0;
  line-height: 1;
}

.kpi-tile-label-text {
  min-width: 0;
  line-height: 1.3;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.kpi-tile-info {
  color: var(--p-text-muted-color);
  cursor: help;
  flex-shrink: 0;
  line-height: 1;
}

.kpi-tile-value {
  font-size: var(--font-size-2xl);
  font-weight: 600;
  font-family: var(--font-head);
  line-height: 1.15;
}

.kpi-tile-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  min-height: 1.2rem;
}

.kpi-tile-note {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kpi-tile-delta {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--p-text-muted-color);
  cursor: help;
  flex-shrink: 0;
}

.kpi-tile-delta--favorable {
  color: var(--p-green-600);
}

.kpi-tile-delta--unfavorable {
  color: var(--p-red-500);
}

.kpi-tile-na {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.kpi-tile-na-value {
  font-size: var(--font-size-2xl);
  font-weight: 600;
  font-family: var(--font-head);
  color: var(--p-text-muted-color);
}

.kpi-tile-na-reason {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}
</style>
