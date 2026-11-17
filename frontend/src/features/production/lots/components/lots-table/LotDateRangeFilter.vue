<script setup lang="ts">
import { useI18n } from 'vue-i18n'

// The row-filter DatePicker every date-range column filter uses, in the
// same range/clearable/small/fluid shape. The DatePicker's loose payload
// (a bare Date, a partial array, or nothing at all on clear) is normalized
// here to the `[from, to]` tuple or null that the callers' writable range
// computeds (see useDateRangeFilter) hand back, so a plain v-model on one
// of those round-trips with a single type.
type LotDateRange = [Date, Date | null] | null

defineProps<{
  modelValue: LotDateRange
}>()

const emit = defineEmits<{
  'update:modelValue': [value: LotDateRange]
}>()

const { t } = useI18n()

function onUpdate(value: Date | Array<Date | null> | null | undefined): void {
  const [from, to] = Array.isArray(value) ? value : [value ?? null, null]
  emit('update:modelValue', from ? [from, to ?? null] : null)
}
</script>

<template>
  <DatePicker
    :model-value="modelValue"
    selection-mode="range"
    show-button-bar
    show-clear
    :placeholder="t('production.lots.filters.filterBy')"
    size="small"
    fluid
    @update:model-value="onUpdate"
  />
</template>
