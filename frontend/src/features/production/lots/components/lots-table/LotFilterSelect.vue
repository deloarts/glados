<script setup lang="ts">
import { useI18n } from 'vue-i18n'

// The row-filter Select every plain-option column filter (status, priority,
// source status) uses, with the same clearable/small/fluid shape, just different
// options and option keys.
defineProps<{
  modelValue: unknown
  options: unknown[]
  optionLabel: string
  optionValue: string
  loading?: boolean
}>()

defineEmits<{
  'update:modelValue': [value: unknown]
}>()

const { t } = useI18n()

// The template root is a single element, so a disable comment in front
// of it would turn the root into a fragment and stop attribute fallthrough.
/* eslint-disable vuejs-accessibility/form-control-has-label -- the caller labels it, aria-labelledby falls through to the Select */
</script>

<template>
  <Select
    :model-value="modelValue"
    :options="options"
    :option-label="optionLabel"
    :option-value="optionValue"
    :loading="loading"
    show-clear
    :placeholder="t('production.lots.filters.any')"
    size="small"
    fluid
    @update:model-value="$emit('update:modelValue', $event)"
  />
</template>
