<script setup lang="ts" generic="K extends string">
// A small button on the upload step that opens a dialog listing the column
// names the import recognises for each field, so the user can name the
// sheet's header row before uploading. The names come from the import's
// profile (Settings, Data import) and are loaded each time the dialog opens.
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { extractApiError } from '@/core/utils/errors'
import { getDataImportProfile } from '../api/getDataImportProfile'

import type { DataImportProfile, DataImportType, ImportFieldSpec } from '../types/spreadsheetImport'

const props = defineProps<{
  importType: DataImportType
  fields: ImportFieldSpec<K>[]
  labelFor: (field: ImportFieldSpec<K>) => string
  isRequired?: (field: ImportFieldSpec<K>) => boolean
  /** The import's own rule for required columns, shown above the table. */
  hint?: string
}>()

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const visible = ref(false)
const loading = ref(false)
const errorMessage = ref<string | null>(null)
const profile = ref<DataImportProfile | null>(null)

const rows = computed(() =>
  props.fields.map((field) => ({
    key: field.key,
    label: props.labelFor(field),
    required: props.isRequired ? props.isRequired(field) : !!field.alwaysRequired,
    columnNames:
      profile.value?.fields.find((f) => f.key === field.payloadKey)?.column_names ?? [],
  })),
)

async function open(): Promise<void> {
  visible.value = true
  loading.value = true
  errorMessage.value = null
  try {
    profile.value = await getDataImportProfile(props.importType)
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('spreadsheetImport.columnNames.loadFailed')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <Button
    :label="t('spreadsheetImport.columnNames.open')"
    icon="mdi mdi-table-column"
    severity="secondary"
    size="small"
    text
    class="column-names-button"
    data-testid="spreadsheet-column-names"
    @click="open"
  />
  <Dialog
    v-model:visible="visible"
    modal
    :header="t('spreadsheetImport.columnNames.title')"
    :style="{ width: 'var(--dialog-width-md)' }"
  >
    <div class="column-names">
      <p class="hint">{{ t('spreadsheetImport.columnNames.intro') }}</p>
      <p v-if="hint" class="hint">{{ hint }}</p>
      <DataTable
        :value="rows"
        :loading="loading"
        data-key="key"
        size="small"
        :show-gridlines="isTableGridlinesEnabled"
        :striped-rows="isTableStripedEnabled"
      >
        <Column header="#" body-class="row-number" class="column-fit">
          <template #body="{ index }">{{ index + 1 }}</template>
        </Column>
        <Column :header="t('spreadsheetImport.columnNames.field')" class="column-fit">
          <template #body="{ data }">
            {{ data.label }}<span v-if="data.required"> *</span>
          </template>
        </Column>
        <Column :header="t('spreadsheetImport.columnNames.names')">
          <template #body="{ data }">
            <span v-if="data.columnNames.length">{{ data.columnNames.join(', ') }}</span>
            <span v-else class="hint">{{ t('spreadsheetImport.columnNames.none') }}</span>
          </template>
        </Column>
      </DataTable>
    </div>
    <template #footer>
      <Message v-if="errorMessage" severity="error" :closable="false">{{ errorMessage }}</Message>
      <Button
        :label="t('common.close')"
        severity="secondary"
        text
        @click="visible = false"
      />
    </template>
  </Dialog>
</template>

<style scoped lang="scss">
.column-names-button {
  align-self: flex-start;
}

.column-names {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.hint {
  margin: 0;
}
</style>
