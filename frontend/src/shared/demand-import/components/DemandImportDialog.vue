<script
  setup
  lang="ts"
  generic="K extends string, TRow extends DemandImportRow, TItem, R extends ImportRowValidation<TItem>"
>
import { computed, reactive, ref } from 'vue'
import { useConfirm } from 'openvue/useconfirm'
import { useAppToast } from '@/core/composables/useAppToast'
import { useI18n } from 'vue-i18n'

import DemandImportReviewTable from './DemandImportReviewTable.vue'
import { extractApiError } from '@/core/utils/errors'
import { HelpDrawer } from '@/shared/help'
import {
  SpreadsheetColumnNamesButton,
  SpreadsheetDropzone,
  SpreadsheetImportError,
  SpreadsheetMappingStep,
} from '@/shared/spreadsheet-import'

import type { DemandImportDraftStore } from '../stores/createDemandImportDraftStore'
import type { DemandImportAdapter, DemandImportRow, ImportRowValidation } from '../types/demandImport'

const props = defineProps<{
  adapter: DemandImportAdapter<K, TRow, TItem, R>
  store: DemandImportDraftStore<K, TRow, TItem, R>
}>()

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  created: []
}>()

const { t } = useI18n()
const confirm = useConfirm()
const appToast = useAppToast()

const parsing = ref(false)
const explainVisible = ref(false)
const errorMessage = ref<string | null>(null)
// `as Record<K, string | null>`: reactive()'s return type runs its value
// type through UnwrapNestedRefs, which, like ref()'s UnwrapRef, can't be
// proven equal to the input type while K is still an open generic parameter
// at this call site (same issue documented on the refs in
// createDemandImportDraftStore.ts). Nothing here is ever a nested Ref, so
// the cast is exactly what reactive() already does at runtime.
const mappingForm: Record<K, string | null> = reactive(
  Object.fromEntries(props.adapter.fields.map((f) => [f.key, null])) as Record<K, string | null>,
) as Record<K, string | null>

// Only the review (table) step needs the full-size dialog, keep it compact
// while the user is still uploading/mapping columns.
const dialogStyle = computed(() =>
  props.store.step === 'review'
    ? { width: 'var(--dialog-width-full)', maxWidth: '1800px', height: '85vh' }
    : { width: 'var(--dialog-width-lg)' },
)

function onMappingUpdate(mapping: Partial<Record<K, string | null>>): void {
  Object.assign(mappingForm, mapping)
}

function currentMapping(): Partial<Record<K, string | null>> {
  return { ...mappingForm }
}

// A field's label in this import, looked up by the payload key a
// SpreadsheetImportError names it by.
function fieldLabel(payloadKey: string): string {
  const field = props.adapter.fields.find((f) => f.payloadKey === payloadKey)
  return field ? mappingFieldLabel(field) : payloadKey
}

function uploadErrorMessage(error: unknown): string {
  if (!(error instanceof SpreadsheetImportError)) {
    return t(`${props.adapter.i18nPrefix}.errors.parseFailed`)
  }
  switch (error.code) {
    case 'headerNotFound':
      return t('spreadsheetImport.errors.headerNotFound', {
        fields: error.missing.map(fieldLabel).join(', '),
      })
    case 'tooManyRows':
      return t('spreadsheetImport.errors.tooManyRows', {
        count: error.count,
        limit: error.limit,
      })
    case 'emptyFile':
      return t('spreadsheetImport.errors.emptyFile')
  }
}

function mappingFieldLabel(field: { key: K }): string {
  return t(`${props.adapter.i18nPrefix}.mapColumns.fieldLabel.${field.key}`)
}

async function processFile(file: File): Promise<void> {
  parsing.value = true
  errorMessage.value = null
  try {
    await props.store.loadFile(file)
    Object.assign(mappingForm, props.store.columnMapping)
    // Auto-mapping found every required column, so the review step opens;
    // validate right away so the user doesn't have to click Validate.
    if (props.store.step === 'review') {
      await onValidate()
    }
  } catch (e) {
    errorMessage.value = uploadErrorMessage(e)
  } finally {
    parsing.value = false
  }
}

async function onConfirmMapping(): Promise<void> {
  props.store.confirmMapping(currentMapping())
  await onValidate()
}

async function onValidate(): Promise<void> {
  errorMessage.value = null
  try {
    await props.store.validate()
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t(`${props.adapter.i18nPrefix}.errors.unknown`)
  }
}

async function onCommit(): Promise<void> {
  errorMessage.value = null
  try {
    const result = await props.store.commit()
    appToast.success(
      t(`${props.adapter.i18nPrefix}.create`),
      t(`${props.adapter.i18nPrefix}.createSuccess`, {
        count: result.created_demand_ids.length,
      }),
    )
    visible.value = false
    emit('created')
  } catch (e) {
    errorMessage.value = extractApiError(e) ?? t(`${props.adapter.i18nPrefix}.errors.unknown`)
  }
}

function onDiscard(): void {
  confirm.require({
    message: t(`${props.adapter.i18nPrefix}.discardDraftConfirm`),
    header: t(`${props.adapter.i18nPrefix}.discardDraft`),
    icon: 'mdi mdi-alert',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t(`${props.adapter.i18nPrefix}.discardDraft`), severity: 'danger' },
    accept: () => {
      props.store.discardDraft()
      visible.value = false
    },
  })
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :style="dialogStyle"
    :content-style="{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }"
  >
    <template #header>
      <div class="dialog-header">
        <span class="p-dialog-title">{{ t(`${adapter.i18nPrefix}.title`) }}</span>
        <Button
          type="button"
          class="dialog-explain-button"
          icon="mdi mdi-help"
          :aria-label="t(`${adapter.i18nPrefix}.explain`)"
          severity="secondary"
          rounded
          text
          v-tooltip.bottom="t(`${adapter.i18nPrefix}.explain`)"
          @click="explainVisible = true"
        />
      </div>
    </template>
    <div v-if="store.step === 'upload'" class="upload-step">
      <SpreadsheetDropzone
        :label="t(`${adapter.i18nPrefix}.upload.label`)"
        :hint="t(`${adapter.i18nPrefix}.upload.dropHint`)"
        :loading="parsing"
        @file="processFile"
      />
      <SpreadsheetColumnNamesButton
        :import-type="adapter.importType"
        :fields="adapter.fields"
        :label-for="mappingFieldLabel"
        :hint="t(`${adapter.i18nPrefix}.mapColumns.keyRuleHint`)"
      />
    </div>

    <div v-else-if="store.step === 'mapColumns'" class="map-columns-step">
      <p>{{ t(`${adapter.i18nPrefix}.mapColumns.title`) }}</p>
      <p class="key-rule-hint">{{ t(`${adapter.i18nPrefix}.mapColumns.keyRuleHint`) }}</p>
      <SpreadsheetMappingStep
        :fields="adapter.fields"
        :headers="store.headers"
        :mapping="currentMapping()"
        :label-for="mappingFieldLabel"
        @update:mapping="onMappingUpdate"
      />
      <Button
        :label="t('common.continue')"
        :disabled="!adapter.isMappingComplete(currentMapping())"
        @click="onConfirmMapping"
      />
    </div>

    <div v-else class="review-step">
      <DemandImportReviewTable :adapter="adapter" :store="store" />
    </div>

    <Message v-if="errorMessage" severity="error" :closable="false">{{ errorMessage }}</Message>

    <template #footer>
      <Button
        v-if="store.hasDraft"
        :label="t(`${adapter.i18nPrefix}.discardDraft`)"
        severity="danger"
        outlined
        @click="onDiscard"
      />
      <template v-if="store.step === 'review'">
        <Button
          :label="t(`${adapter.i18nPrefix}.validate`)"
          severity="secondary"
          :loading="store.isValidating"
          @click="onValidate"
        />
        <Button
          :label="t(`${adapter.i18nPrefix}.create`)"
          :disabled="!store.allRowsValid"
          :loading="store.isCommitting"
          @click="onCommit"
        />
      </template>
    </template>
  </Dialog>

  <HelpDrawer v-model:visible="explainVisible" slug="procurement/demand-import" />
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

.upload-step {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  flex: 1 1 0%;
  min-height: 0;
}

.map-columns-step {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.key-rule-hint {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  margin: 0;
}

.review-step {
  display: flex;
  flex-direction: column;
  flex: 1 1 0%;
  min-height: 0;
}
</style>
