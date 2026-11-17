<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { NumberRangeFilterValue } from '@/shared/utils/rowFilterModes'

// The row filter for a numeric column: two small InputNumbers holding one
// `[min, max]` value. A table that filters in the browser binds it to the
// NUMBER_RANGE match mode; a server-filtered table binds it to its two store
// bounds through useNumberRangeFilter. Clearing both inputs emits null. Each
// bound clamps to the other so the pair can never be inverted, which a
// server would reject.
const props = withDefaults(
  defineProps<{
    modelValue: NumberRangeFilterValue
    // How many decimals the inputs accept; 0 keeps them integer-only.
    fractionDigits?: number
    // Names the column in the inputs' accessible labels.
    column: string
    // Unit hint shown as a tooltip, since the placeholders already carry
    // the min and max labels.
    unit?: string
  }>(),
  { fractionDigits: 0, unit: undefined },
)

const emit = defineEmits<{
  'update:modelValue': [value: [number | null, number | null] | null]
}>()

const { t } = useI18n()

function update(index: 0 | 1, value: number | null | undefined): void {
  const next: [number | null, number | null] = [props.modelValue?.[0] ?? null, props.modelValue?.[1] ?? null]
  next[index] = value ?? null
  emit('update:modelValue', next[0] === null && next[1] === null ? null : next)
}
</script>

<template>
  <div class="number-range" v-tooltip.top="unit">
    <InputNumber
      input-class="number-range-field"
      :model-value="modelValue?.[0] ?? null"
      :min="0"
      :max="modelValue?.[1] ?? undefined"
      :max-fraction-digits="fractionDigits"
      :use-grouping="false"
      :placeholder="t('common.rangeFilter.min')"
      :aria-label="t('common.rangeFilter.minOf', { column })"
      size="small"
      fluid
      class="number-range-input"
      @update:model-value="update(0, $event)"
    />
    <InputNumber
      input-class="number-range-field"
      :model-value="modelValue?.[1] ?? null"
      :min="modelValue?.[0] ?? 0"
      :max-fraction-digits="fractionDigits"
      :use-grouping="false"
      :placeholder="t('common.rangeFilter.max')"
      :aria-label="t('common.rangeFilter.maxOf', { column })"
      size="small"
      fluid
      class="number-range-input"
      @update:model-value="update(1, $event)"
    />
  </div>
</template>

<style scoped lang="scss">
.number-range {
  display: flex;
  gap: var(--space-1);
  min-width: 0;
}

.number-range-input {
  flex: 1 1 0;
  min-width: 0;
}

:deep(.number-range-field) {
  min-width: 0;
}
</style>
