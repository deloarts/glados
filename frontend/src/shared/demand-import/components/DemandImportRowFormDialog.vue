<script
  setup
  lang="ts"
  generic="K extends string, TRow extends DemandImportRow, TItem, R extends ImportRowValidation<TItem>"
>
import { computed, reactive, useId, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { dateToParam } from '@/core/utils/dates'

import type { DemandImportAdapter, DemandImportRow, ImportRowValidation } from '../types/demandImport'

const props = defineProps<{
  adapter: DemandImportAdapter<K, TRow, TItem, R>
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  added: [row: TRow]
}>()

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()

type FieldValue = string | number | Date | null

function emptyForm(): Record<K, FieldValue> {
  const form = {} as Record<K, FieldValue>
  for (const field of props.adapter.fields) {
    form[field.key] = field.kind === 'text' ? '' : null
  }
  return form
}

// `as Record<K, FieldValue>`: reactive()'s return type runs its value type
// through UnwrapNestedRefs, which can't be proven equal to the input type
// while K is still an open generic parameter at this call site (same issue
// documented on the refs in createDemandImportDraftStore.ts).
const form: Record<K, FieldValue> = reactive(emptyForm()) as Record<K, FieldValue>

watch(visible, (isVisible) => {
  if (isVisible) Object.assign(form, emptyForm())
})

// Mirrors what buildRowsFromMapping's coercion does for a mapped Excel
// cell. A manually-typed row goes through the same text-trim/date-param
// shaping so buildRow() never has to know whether a value came from a file
// or this form.
function coerceFieldValue(kind: 'text' | 'number' | 'date', value: FieldValue): unknown {
  if (kind === 'date') return dateToParam(value as Date | null)
  if (kind === 'number') return value
  const text = typeof value === 'string' ? value.trim() : value
  return text ? text : null
}

// Read/write `form` through these rather than `form[field.key]` directly in
// the template: Vue's template type-checker runs every top-level setup
// binding through its own ref/reactive-unwrapping type (DistributeRef),
// which can't resolve a generic-keyed Record and reports every dynamic-key
// access as an error. A plain function call sidesteps it.
function fieldValue(key: K): FieldValue {
  return form[key]
}

function setFieldValue(key: K, value: FieldValue): void {
  form[key] = value
}

// Typed per-kind wrappers rather than an inline `fieldValue(...) as X | Y`
// cast in the template: eslint-vue's expression parser reads a bare `|`
// there as the deprecated Vue 2 filter-pipe syntax (`expr | filterName`),
// not a TS union type, and flags it (vue/no-deprecated-filter).
function textFieldValue(key: K): string {
  return (fieldValue(key) as string | null) ?? ''
}

function numberFieldValue(key: K): number | null {
  return fieldValue(key) as number | null
}

function dateFieldValue(key: K): Date | null {
  return fieldValue(key) as Date | null
}

function setDateFieldValue(key: K, value: unknown): void {
  setFieldValue(key, (value as Date | null | undefined) ?? null)
}

const candidateRow = computed<TRow>(() => {
  const values = {} as Record<K, unknown>
  for (const field of props.adapter.fields) {
    values[field.key] = coerceFieldValue(field.kind, form[field.key])
  }
  return props.adapter.buildRow(values)
})

const isValid = computed(() => props.adapter.isRowComplete(candidateRow.value))

function onSubmit(): void {
  if (!isValid.value) return
  emit('added', candidateRow.value)
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t(`${adapter.i18nPrefix}.addRow.title`)"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <div class="row-form">
      <div class="field-grid">
        <div v-for="field in adapter.fields" :key="field.key" class="field">
          <label
            :for="`${uid}-field-${field.key}`"
            >{{ t(`${adapter.i18nPrefix}.addRow.${field.key}`) }}
            <span v-if="field.alwaysRequired">*</span></label
          >
          <InputText
            v-if="field.kind === 'text'"
            :id="`${uid}-field-${field.key}`"
            :model-value="textFieldValue(field.key)"
            fluid
            @update:model-value="(value) => setFieldValue(field.key, value ?? '')"
          />
          <InputNumber
            v-else-if="field.kind === 'number'"
            :model-value="numberFieldValue(field.key)"
            :min="0.001"
            :max-fraction-digits="3"
            fluid
            @update:model-value="(value) => setFieldValue(field.key, value)"
          />
          <DatePicker
            v-else
            :model-value="dateFieldValue(field.key)"
            show-icon
            date-format="yy-mm-dd"
            fluid
            @update:model-value="(value) => setDateFieldValue(field.key, value)"
          />
        </div>
      </div>
    </div>

    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" outlined @click="visible = false" />
      <Button :label="t(`${adapter.i18nPrefix}.addRow.add`)" :disabled="!isValid" @click="onSubmit" />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.row-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
}
</style>
