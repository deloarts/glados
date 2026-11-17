<script setup lang="ts">
import { useI18n } from 'vue-i18n'

// The row-filter DatePicker every date-range column filter (Ordered,
// Expected Delivery, Delivery, Created) uses: same range/clearable/small/
// fluid shape, just a different bound range and setter.
defineProps<{
  modelValue: [Date, Date | null] | null
}>()

defineEmits<{
  'update:modelValue': [value: Date | Array<Date | null> | null | undefined]
  clear: []
}>()

const { t } = useI18n()
</script>

<template>
  <DatePicker
    :model-value="modelValue"
    selection-mode="range"
    show-button-bar
    show-clear
    :placeholder="t('orders.filters.filterBy')"
    size="small"
    fluid
    @update:model-value="$emit('update:modelValue', $event)"
    @clear-click="$emit('clear')"
  />
</template>
