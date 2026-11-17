<script setup lang="ts">
/**
 * The row filter of a numeric column, built like UserDateFilter: one small
 * field sums up the range that is set and opens a panel with the minimum
 * and maximum inputs. A narrow column then keeps one readable field instead
 * of two cramped ones. It binds the same `[min, max]` value as
 * NumberRangeRowFilter, so the table's filter values stay as they are.
 */
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { localeTag } from '@/core/utils/dates'

import NumberRangeRowFilter from './NumberRangeRowFilter.vue'

import type { NumberRangeFilterValue } from '@/shared/utils/rowFilterModes'

const props = withDefaults(
  defineProps<{
    modelValue: NumberRangeFilterValue
    /** Names the column in the accessible labels. */
    column: string
    /** How many decimals the inputs accept; 0 keeps them integer-only. */
    fractionDigits?: number
    /** Shown after the numbers of the summary, such as "min". */
    unit?: string
    /** Shown while nothing is set, the table's usual "any" text. */
    placeholder?: string
  }>(),
  { fractionDigits: 0, unit: undefined, placeholder: undefined },
)

const emit = defineEmits<{
  'update:modelValue': [value: [number | null, number | null] | null]
}>()

const { t } = useI18n()

const popover = ref<{ toggle: (event: Event) => void } | null>(null)

function format(value: number): string {
  const number = new Intl.NumberFormat(localeTag(), {
    maximumFractionDigits: props.fractionDigits,
    useGrouping: false,
  }).format(value)
  return props.unit ? `${number} ${props.unit}` : number
}

const summary = computed(() => {
  const min = props.modelValue?.[0] ?? null
  const max = props.modelValue?.[1] ?? null
  if (min !== null && max !== null) {
    return min === max
      ? format(min)
      : t('common.rangeFilter.between', { min: format(min), max: format(max) })
  }
  if (min !== null) return t('common.rangeFilter.atLeast', { min: format(min) })
  if (max !== null) return t('common.rangeFilter.atMost', { max: format(max) })
  return ''
})

function toggle(event: Event): void {
  popover.value?.toggle(event)
}

function clear(): void {
  emit('update:modelValue', null)
}
</script>

<template>
  <div class="number-range-filter">
    <IconField>
      <InputText
        :model-value="summary"
        readonly
        :placeholder="props.placeholder ?? t('common.userDateFilter.any')"
        :title="summary || undefined"
        :aria-label="t('common.filterBy', { column })"
        aria-haspopup="dialog"
        size="small"
        fluid
        class="number-range-filter-field"
        data-testid="number-range-filter-field"
        @click="toggle"
        @keydown.enter.prevent="toggle"
        @keydown.space.prevent="toggle"
      />
      <InputIcon
        v-if="summary"
        class="mdi mdi-close number-range-filter-clear"
        role="button"
        tabindex="0"
        :aria-label="t('common.clear')"
        data-testid="number-range-filter-clear"
        @click.stop="clear"
        @keydown.enter.prevent="clear"
      />
    </IconField>

    <Popover ref="popover">
      <div class="number-range-filter-panel" data-testid="number-range-filter-panel">
        <span class="number-range-filter-label">{{ column }}</span>
        <NumberRangeRowFilter
          :model-value="modelValue"
          :column="column"
          :fraction-digits="fractionDigits"
          @update:model-value="emit('update:modelValue', $event)"
        />
        <small v-if="unit" class="hint">{{ t('common.rangeFilter.unit', { unit }) }}</small>
      </div>
    </Popover>
  </div>
</template>

<style scoped lang="scss">
.number-range-filter {
  min-width: 0;
}

.number-range-filter-field {
  cursor: pointer;
  text-overflow: ellipsis;
}

.number-range-filter-clear {
  cursor: pointer;
}

.number-range-filter-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  width: 16rem;
}

.number-range-filter-label {
  font-size: var(--font-size-sm);
}
</style>
