<script setup lang="ts">
// Import from file: creates bought items from a spreadsheet. The file is
// read with the bought-item create profile (Settings, Data import); when a
// required column is not recognised the user maps the columns for this
// upload. The review lists every row with its status: ready rows are
// created, rows describing an existing item are left alone and show where
// the file differs, the rest stay in the draft to be fixed or removed.
import { computed, ref, watch } from 'vue'
import { useConfirm } from 'openvue/useconfirm'
import { useI18n } from 'vue-i18n'

import { useAppToast } from '@/core/composables/useAppToast'
import { useHostStore } from '@/core/host/stores/hostStore'
import { HelpDrawer } from '@/shared/help'
import { extractApiError } from '@/core/utils/errors'
import {
  SpreadsheetColumnNamesButton,
  SpreadsheetDropzone,
  SpreadsheetImportError,
  SpreadsheetMappingStep,
} from '@/shared/spreadsheet-import'
import BoughtItemsImportReviewTable from './BoughtItemsImportReviewTable.vue'
import { useBoughtItemsImportDraftStore } from '../stores/boughtItemsImportDraftStore'
import {
  BOUGHT_ITEM_IMPORT_FIELDS,
  importFieldsFor,
  isImportMappingComplete,
} from '../utils/boughtItemsImportFields'

import type { ColumnMapping, ImportFieldSpec } from '@/shared/spreadsheet-import'
import type { BoughtItemImportField } from '../utils/boughtItemsImportFields'

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  created: []
}>()

const { t } = useI18n()
const confirm = useConfirm()
const toast = useAppToast()
const store = useBoughtItemsImportDraftStore()
const hostStore = useHostStore()

// A draft started with the lookup falls back to the file alone once the
// Data Portal is switched off, so nothing of the portal shows or runs.
watch(
  () => hostStore.edpEnabled,
  (enabled) => {
    if (!enabled) store.lookup = false
  },
  { immediate: true },
)

const parsing = ref(false)
const explainVisible = ref(false)
const errorMessage = ref<string | null>(null)
const mapping = ref<ColumnMapping<BoughtItemImportField>>({ ...store.mapping })

const dialogStyle = computed(() =>
  store.step === 'review'
    ? { width: 'var(--dialog-width-full)', maxWidth: '1800px', height: '85vh' }
    : { width: 'var(--dialog-width-lg)' },
)

const mappingFields = computed(() => importFieldsFor(store.lookup))
const mappingComplete = computed(() => isImportMappingComplete(mapping.value, store.lookup))

function fieldLabel(field: ImportFieldSpec<BoughtItemImportField>): string {
  return t(`boughtItems.import.fields.${field.key}`)
}

function uploadErrorMessage(error: unknown): string {
  if (!(error instanceof SpreadsheetImportError)) return t('boughtItems.import.errors.parseFailed')
  switch (error.code) {
    case 'headerNotFound':
      return t('spreadsheetImport.errors.headerNotFound', {
        fields: error.missing
          .map((key) => BOUGHT_ITEM_IMPORT_FIELDS.find((f) => f.payloadKey === key))
          .filter((f) => !!f)
          .map(fieldLabel)
          .join(', '),
      })
    case 'tooManyRows':
      return t('spreadsheetImport.errors.tooManyRows', { count: error.count, limit: error.limit })
    case 'emptyFile':
      return t('spreadsheetImport.errors.emptyFile')
  }
}

async function onValidate(): Promise<void> {
  errorMessage.value = null
  try {
    await store.validate()
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('boughtItems.import.errors.unknown')
  }
}

async function onFile(file: File): Promise<void> {
  parsing.value = true
  errorMessage.value = null
  try {
    await store.loadFile(file)
    mapping.value = { ...store.mapping }
    if (store.step === 'review') await onValidate()
  } catch (e) {
    errorMessage.value = uploadErrorMessage(e)
  } finally {
    parsing.value = false
  }
}

async function onConfirmMapping(): Promise<void> {
  store.confirmMapping(mapping.value)
  await onValidate()
}

async function onCommit(): Promise<void> {
  errorMessage.value = null
  try {
    const count = await store.commit()
    toast.success(t('boughtItems.import.title'), t('boughtItems.import.created', { count }))
    emit('created')
    if (store.rows.length === 0) {
      visible.value = false
    } else {
      await onValidate()
    }
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t('boughtItems.import.errors.unknown')
  }
}

function onDiscard(): void {
  confirm.require({
    group: 'bought-item-import',
    message: t('boughtItems.import.discardConfirm'),
    header: t('boughtItems.import.discard'),
    icon: 'mdi mdi-alert',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('boughtItems.import.discard'), severity: 'danger' },
    accept: () => {
      store.discardDraft()
      mapping.value = {}
      errorMessage.value = null
    },
  })
}
</script>

<template>
  <ConfirmDialog group="bought-item-import" />
  <Dialog
    v-model:visible="visible"
    modal
    :style="dialogStyle"
    :content-style="{ display: 'flex', flexDirection: 'column', overflow: 'hidden', gap: '0.75rem' }"
  >
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ t('boughtItems.import.title') }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t('boughtItems.import.explain')"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t('boughtItems.import.explain')"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <div v-if="store.step === 'upload'" class="upload-step">
      <p class="hint">{{ t('boughtItems.import.intro') }}</p>
      <div v-if="hostStore.edpEnabled" class="lookup-option">
        <Checkbox
          v-model="store.lookup"
          binary
          input-id="bought-item-import-lookup"
          data-testid="bought-item-import-lookup"
        />
        <label for="bought-item-import-lookup">
          {{ t('boughtItems.import.lookup') }}
          <span class="hint">{{ t('boughtItems.import.lookupHint') }}</span>
        </label>
      </div>
      <SpreadsheetDropzone
        :label="t('boughtItems.import.upload')"
        :hint="t('boughtItems.import.dropHint')"
        :loading="parsing"
        @file="onFile"
      />
      <SpreadsheetColumnNamesButton
        import-type="bought_item_create"
        :fields="mappingFields"
        :label-for="fieldLabel"
        :hint="store.lookup ? t('boughtItems.import.mapColumnsLookupHint') : undefined"
      />
    </div>

    <div v-else-if="store.step === 'mapColumns'" class="map-step">
      <p>{{ t('boughtItems.import.mapColumns') }}</p>
      <p v-if="store.lookup" class="hint">{{ t('boughtItems.import.mapColumnsLookupHint') }}</p>
      <SpreadsheetMappingStep
        v-model:mapping="mapping"
        :fields="mappingFields"
        :headers="store.headers"
        :label-for="fieldLabel"
      />
      <Button
        :label="t('common.continue')"
        :disabled="!mappingComplete"
        data-testid="bought-item-import-confirm-mapping"
        @click="onConfirmMapping"
      />
    </div>

    <BoughtItemsImportReviewTable v-else />

    <Message v-if="errorMessage" severity="error" :closable="false">{{ errorMessage }}</Message>

    <template #footer>
      <Button
        v-if="store.hasDraft"
        :label="t('boughtItems.import.discard')"
        severity="danger"
        outlined
        @click="onDiscard"
      />
      <template v-if="store.step === 'review'">
        <Button
          :label="t('boughtItems.import.validate')"
          severity="secondary"
          :loading="store.isValidating"
          data-testid="bought-item-import-validate"
          @click="onValidate"
        />
        <Button
          :label="t('boughtItems.import.create', { count: store.readyCount })"
          :disabled="store.readyCount === 0"
          :loading="store.isCommitting"
          data-testid="bought-item-import-commit"
          @click="onCommit"
        />
      </template>
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="catalogue/bought-item-import" />
</template>

<style scoped lang="scss">
.dialog-header {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  min-width: 0;
}

.dialog-explain-button :deep(.mdi) {
  font-size: var(--font-size-sm);
}

.upload-step,
.map-step {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  flex: 1 1 0%;
  min-height: 0;
}

.lookup-option {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);

  label {
    display: flex;
    flex-direction: column;
  }
}

.hint {
  margin: 0;
}
</style>
