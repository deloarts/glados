<script setup lang="ts">
// The row-filter DatePicker repeated on every date-range column: range
// selection with a clear button. The caller owns the underlying `[from, to]`
// state (see useDateRangeFilter) and any side effect the update should
// trigger, this only wires the DatePicker's own events through.
type DateRangeValue = Date | Array<Date | null> | null | undefined

defineProps<{
  modelValue: DateRangeValue
  placeholder: string
}>()

defineEmits<{
  'update:modelValue': [value: DateRangeValue]
  'clear-click': []
}>()
</script>

<template>
  <DatePicker
    :model-value="modelValue"
    selection-mode="range"
    show-button-bar
    show-clear
    :placeholder="placeholder"
    size="small"
    fluid
    @update:model-value="$emit('update:modelValue', $event)"
    @clear-click="$emit('clear-click')"
  />
</template>
