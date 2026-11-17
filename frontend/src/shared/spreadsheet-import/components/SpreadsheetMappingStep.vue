<script setup lang="ts" generic="K extends string">
// The manual column mapping of one upload: a header picker per field. The
// caller owns the mapping and decides when it is complete enough to go on.
import type { ColumnMapping, ImportFieldSpec } from '../types/spreadsheetImport'

const props = defineProps<{
  fields: ImportFieldSpec<K>[]
  headers: string[]
  mapping: ColumnMapping<K>
  labelFor: (field: ImportFieldSpec<K>) => string
  isRequired?: (field: ImportFieldSpec<K>) => boolean
}>()

const emit = defineEmits<{
  'update:mapping': [mapping: ColumnMapping<K>]
}>()

// A function call rather than `mapping[field.key]` in the template, since
// Vue's template type-checker cannot resolve a generic-keyed record.
function valueOf(key: K): string | null {
  return props.mapping[key] ?? null
}

function setValue(key: K, value: unknown): void {
  emit('update:mapping', { ...props.mapping, [key]: (value as string | null | undefined) ?? null })
}

function required(field: ImportFieldSpec<K>): boolean {
  return props.isRequired ? props.isRequired(field) : !!field.alwaysRequired
}
</script>

<template>
  <div class="mapping-grid">
    <div v-for="field in fields" :key="field.key" class="field">
      <label :id="`spreadsheet-map-${field.key}-label`" :for="`spreadsheet-map-${field.key}`"
        >{{ labelFor(field) }} <span v-if="required(field)">*</span></label
      >
      <Select
        :input-id="`spreadsheet-map-${field.key}`"
        :aria-labelledby="`spreadsheet-map-${field.key}-label`"
        :model-value="valueOf(field.key)"
        :options="headers"
        show-clear
        fluid
        @update:model-value="(value) => setValue(field.key, value)"
      />
    </div>
  </div>
</template>

<style scoped lang="scss">
.mapping-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
}
</style>
