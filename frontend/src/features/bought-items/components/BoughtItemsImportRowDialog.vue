<script setup lang="ts">
// Edits one row of the bought-item import draft, every field as the sheet
// carried it. The row is validated again with the whole draft afterwards.
import { reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { BOUGHT_ITEM_IMPORT_FIELDS } from '../utils/boughtItemsImportFields'

import type { BoughtItemImportRow } from '../types/boughtItemsImportTypes'

const props = defineProps<{
  row: BoughtItemImportRow | null
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  save: [row: BoughtItemImportRow]
}>()

const { t } = useI18n()

type TextKey = Exclude<keyof BoughtItemImportRow, 'row_index' | 'mass'>

const form = reactive<{ text: Record<string, string>; mass: number | null }>({
  text: {},
  mass: null,
})

const textFields = BOUGHT_ITEM_IMPORT_FIELDS.filter((f) => f.kind === 'text')

watch(
  () => [visible.value, props.row] as const,
  ([isVisible, row]) => {
    if (!isVisible || !row) return
    form.text = Object.fromEntries(
      textFields.map((f) => [f.payloadKey, (row[f.payloadKey as TextKey] as string | null) ?? '']),
    )
    form.mass = row.mass ?? null
  },
  { immediate: true },
)

function onSave(): void {
  if (!props.row) return
  const text = Object.fromEntries(
    Object.entries(form.text).map(([key, value]) => [key, value.trim() || null]),
  )
  emit('save', { ...props.row, ...text, mass: form.mass })
  visible.value = false
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('boughtItems.import.editRow')"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <div class="row-form">
      <div v-for="field in textFields" :key="field.key" class="field">
        <label :for="`bii-${field.key}`">{{ t(`boughtItems.import.fields.${field.key}`) }}</label>
        <InputText :id="`bii-${field.key}`" v-model="form.text[field.payloadKey]" fluid />
      </div>
      <div class="field">
        <label for="bii-mass">{{ t('boughtItems.import.fields.mass') }}</label>
        <InputNumber
          v-model="form.mass"
          input-id="bii-mass"
          :min="0"
          :use-grouping="false"
          suffix=" g"
          fluid
        />
      </div>
    </div>
    <template #footer>
      <Button :label="t('common.cancel')" severity="secondary" text @click="visible = false" />
      <Button :label="t('common.save')" data-testid="bought-item-import-row-save" @click="onSave" />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.row-form {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-4);
}
</style>
