<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useDebounceFn } from '@vueuse/core'

import { getPrinters } from '@/features/printers'
import { getFieldSources } from '../api/getFieldSources'
import { previewPrintTemplate, previewPrintTemplateImageUrl } from '../api/previewPrintTemplate'
import { downloadPrintTemplate } from '../api/downloadPrintTemplate'
import { usePrintTemplatesStore } from '../stores/printTemplatesStore'
import { PRINT_TEMPLATE_KINDS } from '../utils/printTemplateKinds'
import { extractApiError } from '@/core/utils/errors'
import { API_MAX_PAGE_SIZE } from '@/core/constants/table'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { useSubmitAction } from '@/shared/composables/useSubmitAction'
import { useTemplateFileTransfer } from '@/shared/composables/useTemplateFileTransfer'
import { parseTemplateFile, templateFileKindOf } from '@/shared/utils/templateFile'
import { printTemplateSettingsContent, printTemplateSettingsPatch } from '../utils/printTemplateFile'
import { useArchivableOptions } from '@/shared/composables/useArchivableOptions'
import ArchivedOptionTag from '@/shared/components/archivable/ArchivedOptionTag.vue'
import ArchivedSelectionWarning from '@/shared/components/archivable/ArchivedSelectionWarning.vue'

import type { PrinterResponse } from '@/features/printers'
import type { PrintTemplateKind } from '../utils/printTemplateKinds'
import type { FieldSourceResponse, PrintTemplateResponse } from '../types/printTemplateResponse'
import { HelpButton } from '@/shared/help'

interface Props {
  kind: PrintTemplateKind
  template?: PrintTemplateResponse | null
}

const props = defineProps<Props>()
const emit = defineEmits<{ saved: [template: PrintTemplateResponse] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const { toastOnError } = useErrorToast()
const store = usePrintTemplatesStore()

const config = computed(() => PRINT_TEMPLATE_KINDS[props.kind])
const p = computed(() => config.value.i18nPrefix)
const id = (name: string): string => `${config.value.idPrefix}-${name}`

// ── Printer options, filtered to the classifier's required kind ────────

const printers = ref<PrinterResponse[]>([])
const loadingPrinters = ref(false)

// Archived printers stay selectable, sorted last.
const { sortedOptions: printerOptions, isArchived: isPrinterArchived } =
  useArchivableOptions(printers)
const selectedPrinter = computed<PrinterResponse | null>(
  () => printerOptions.value.find((printer) => printer.id === form.printerId) ?? null,
)

async function loadPrinters(): Promise<void> {
  loadingPrinters.value = true
  try {
    const result = await getPrinters({
      limit: API_MAX_PAGE_SIZE,
      kind: config.value.printerKind,
      include_archived: true,
    })
    printers.value = result.items
  } finally {
    loadingPrinters.value = false
  }
}

const paperOptions = computed(() => [
  { label: t(`${p.value}.editor.fields.paperA4`), value: 'a4' },
  { label: t(`${p.value}.editor.fields.paperA4Aligned`), value: 'a4_aligned' },
  { label: t(`${p.value}.editor.fields.paperA5`), value: 'a5' },
])

// ── Form state ──────────────────────────────────────────────────────────

interface FormState {
  trigger: PrintTemplateResponse['trigger']
  source: string
  fieldMap: Record<string, string>
  printerId: number | null
  autoPrint: boolean
  copiesRule: string
  copiesFixed: number
  maxCopies: number
  /** Only sent for kinds with a paper size. */
  paper: string
  /** Not editable here; carried so a template file can set them. */
  designDpi: number | null
  labelWidthMm: number | null
  labelHeightMm: number | null
  enabled: boolean
  note: string
}

function createEmptyForm(): FormState {
  return {
    trigger: null,
    source: '',
    fieldMap: {},
    printerId: null,
    autoPrint: false,
    copiesRule: 'fixed',
    copiesFixed: 1,
    maxCopies: 50,
    paper: 'a4',
    designDpi: null,
    labelWidthMm: null,
    labelHeightMm: null,
    enabled: true,
    note: '',
  }
}

function formFromTemplate(tpl: PrintTemplateResponse): FormState {
  return {
    trigger: tpl.trigger,
    source: tpl.source ?? '',
    fieldMap: { ...tpl.field_map },
    printerId: tpl.printer_id,
    autoPrint: tpl.auto_print,
    copiesRule: tpl.copies_rule,
    copiesFixed: tpl.copies_fixed,
    maxCopies: tpl.max_copies,
    paper: tpl.paper ?? 'a4',
    designDpi: tpl.design_dpi ?? null,
    labelWidthMm: tpl.label_width_mm ?? null,
    labelHeightMm: tpl.label_height_mm ?? null,
    enabled: tpl.enabled,
    note: tpl.note ?? '',
  }
}

const form = reactive<FormState>(createEmptyForm())
const { submitting, errorMessage, run } = useSubmitAction()

const triggerOptions = computed(() => [
  { label: t(`${p.value}.manualOnly`), value: null },
  ...(props.template?.available_triggers ?? []).map((trigger) => ({
    label: t(`${p.value}.triggers.${trigger}`),
    value: trigger,
  })),
])

const copiesRuleOptions = computed(
  () =>
    props.template?.copies_rules.map((rule) => ({
      label: t(`${p.value}.copiesRules.${rule}`),
      value: rule,
    })) ?? [],
)

// ── Field sources + auto-detected fields ───────────────────────────────

const fieldSources = ref<FieldSourceResponse[]>([])
const loadingFieldSources = ref(false)

async function loadFieldSources(): Promise<void> {
  if (!props.template) return
  loadingFieldSources.value = true
  try {
    fieldSources.value = await getFieldSources(props.template.classifier, form.trigger)
  } finally {
    loadingFieldSources.value = false
  }
}

const detectedPlaceholders = computed<string[]>(() => config.value.detectFields(form.source))

const jsonError = computed<string | null>(() => {
  if (!config.value.jsonSource || !form.source.trim()) return null
  try {
    JSON.parse(form.source)
    return null
  } catch (e) {
    return e instanceof Error ? e.message : t(`${p.value}.editor.errors.invalidJson`)
  }
})

const unmappedPlaceholders = computed(() =>
  detectedPlaceholders.value.filter((name) => !form.fieldMap[name]),
)

// The field map only gains entries while editing, so stale entries for
// removed fields would be resent and fail validation. Submitting only
// detected fields prevents that.
const prunedFieldMap = computed<Record<string, string>>(() =>
  Object.fromEntries(
    detectedPlaceholders.value
      .filter((name) => form.fieldMap[name])
      .map((name) => [name, form.fieldMap[name] as string]),
  ),
)

watch(
  () => form.trigger,
  () => loadFieldSources(),
)

// ── Preview + download ───────────────────────────────────────────────────

const previewRootId = ref<number | null>(null)
const previewText = ref<string | null>(null)
const previewImageUrl = ref<string | null>(null)
const previewWarnings = ref<string[]>([])
const previewLoading = ref(false)
const previewError = ref<string | null>(null)
const downloading = ref(false)
const downloadError = ref<string | null>(null)

function revokePreviewImage(): void {
  if (previewImageUrl.value) URL.revokeObjectURL(previewImageUrl.value)
  previewImageUrl.value = null
}

async function runPreview(): Promise<void> {
  if (!props.template || !previewRootId.value) return
  const { classifier, root_type: rootType } = props.template
  const rootId = previewRootId.value
  previewLoading.value = true
  previewError.value = null
  try {
    const [textResult, imageResult] = await Promise.all([
      config.value.renderedText ? previewPrintTemplate(classifier, rootType, rootId) : null,
      previewPrintTemplateImageUrl(classifier, rootType, rootId),
    ])
    previewText.value = textResult?.rendered_zpl ?? null
    revokePreviewImage()
    previewImageUrl.value = imageResult.url
    previewWarnings.value = [...(textResult?.warnings ?? []), ...imageResult.warnings]
  } catch (e) {
    previewError.value = extractApiError(e) ?? t(`${p.value}.preview.errors.unknown`)
    previewText.value = null
    revokePreviewImage()
  } finally {
    previewLoading.value = false
  }
}

async function runDownload(): Promise<void> {
  if (!props.template || !previewRootId.value) return
  downloading.value = true
  downloadError.value = null
  try {
    const result = await downloadPrintTemplate(
      props.template.classifier,
      props.template.root_type,
      previewRootId.value,
    )
    previewWarnings.value = result.warnings
  } catch (e) {
    downloadError.value = extractApiError(e) ?? t(`${p.value}.download.errors.unknown`)
  } finally {
    downloading.value = false
  }
}

const debouncedPreview = useDebounceFn(runPreview, 500)
watch(previewRootId, debouncedPreview)

// ── Lifecycle ───────────────────────────────────────────────────────────

onMounted(loadPrinters)

watch(visible, (isVisible) => {
  if (!isVisible) {
    revokePreviewImage()
    return
  }
  errorMessage.value = null
  previewRootId.value = null
  previewText.value = null
  previewWarnings.value = []
  previewError.value = null
  downloadError.value = null
  if (props.template) {
    Object.assign(form, formFromTemplate(props.template))
    loadFieldSources().catch(toastOnError())
  } else {
    Object.assign(form, createEmptyForm())
  }
})

// ── Submit ──────────────────────────────────────────────────────────────

async function onSubmit(): Promise<void> {
  const template = props.template
  if (!template) return
  if (jsonError.value) {
    errorMessage.value = jsonError.value
    return
  }
  if (unmappedPlaceholders.value.length) {
    errorMessage.value = t(`${p.value}.editor.errors.unmappedPlaceholders`, {
      count: unmappedPlaceholders.value.length,
      names: unmappedPlaceholders.value.join(', '),
    })
    return
  }

  await run(async () => {
    const saved = await store.update(template.classifier, {
      trigger: form.trigger,
      source: form.source.trim() || null,
      field_map: prunedFieldMap.value,
      printer_id: form.printerId,
      auto_print: form.autoPrint,
      copies_rule: form.copiesRule,
      copies_fixed: form.copiesFixed,
      max_copies: form.maxCopies,
      ...(config.value.paper ? { paper: form.paper } : {}),
      design_dpi: form.designDpi,
      label_width_mm: form.labelWidthMm,
      label_height_mm: form.labelHeightMm,
      enabled: form.enabled,
      note: form.note.trim() || null,
    })
    visible.value = false
    emit('saved', saved)
  }, t(`${p.value}.editor.errors.unknown`))
}

function onCancel(): void {
  visible.value = false
}

// ── Template file ──
// A template file is the source plus a settings file naming the classifier
// (see printTemplateFile.ts). An import fills the form from either or both;
// the export writes both files.

const { importFiles, exportFile, exportText } = useTemplateFileTransfer()

function onImport(): void {
  const template = props.template
  if (!template) return
  void importFiles(
    `.json,${config.value.sourceAccept}`,
    (files) => {
      // When the same role is picked twice, the last file counts.
      const newestFirst = [...files].reverse()
      const settingsFile = newestFirst.find((f) => templateFileKindOf(f.text) !== null)
      const sourceFile = newestFirst.find((f) => templateFileKindOf(f.text) === null)
      const { patch, ignored } = settingsFile
        ? printTemplateSettingsPatch(
            template,
            parseTemplateFile(settingsFile.text, 'print_template'),
            config.value.paper,
          )
        : { patch: {}, ignored: [] }
      Object.assign(form, patch, sourceFile ? { source: sourceFile.text } : {})
      return ignored
    },
    true,
  )
}

function onExport(): void {
  const template = props.template
  if (!template) return
  const extension = config.value.jsonSource ? 'json' : 'zpl'
  exportText(form.source, `${template.classifier}.source.${extension}`, 'text/plain')
  exportFile(
    'print_template',
    printTemplateSettingsContent(
      template.classifier,
      { ...form, fieldMap: prunedFieldMap.value },
      config.value.paper,
    ),
    `${template.classifier}.settings.json`,
  )
}

function onFileSelected(event: Event): void {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    form.source = String(reader.result ?? '')
  }
  reader.readAsText(file)
}
</script>

<template>
  <Dialog
class="fit-fields"
    v-model:visible="visible"
    modal
    :style="{ width: 'var(--dialog-width-full)' }"
    :breakpoints="{ '960px': '95vw' }"
  >
    <!-- The help opens the setup of a label, or the paper of a docket. -->
    <template #header>
      <span class="p-dialog-title">
        {{ template ? t(`${p}.classifiers.${template.classifier}`) : t(`${p}.editTemplate`) }}
        <HelpButton :slug="`resources/print-${kind}s`" :anchor="kind === 'docket' ? 'paper' : 'setup'" icon="mdi mdi-help" size="small" rounded />
      </span>
    </template>
    <form class="editor-form" @submit.prevent="onSubmit">
      <div class="editor-panes">
        <!-- ── Left: settings + source ─────────────────────────────── -->
        <div class="editor-pane">
          <div class="field-row">
            <div class="field">
              <label :id="id('trigger') + '-label'" :for="id('trigger')">{{ t(`${p}.editor.fields.trigger`) }}</label>
              <Select
                :id="id('trigger')"
                :aria-labelledby="id('trigger') + '-label'"
                v-model="form.trigger"
                :options="triggerOptions"
                option-label="label"
                option-value="value"
                fluid
              />
            </div>
            <div class="field">
              <label :id="id('printer') + '-label'" :for="id('printer')">{{ t(`${p}.editor.fields.printer`) }}</label>
              <Select
                :id="id('printer')"
                :aria-labelledby="id('printer') + '-label'"
                v-model="form.printerId"
                :options="printerOptions"
                option-label="name"
                option-value="id"
                :loading="loadingPrinters"
                show-clear
                fluid
              >
                <template #option="{ option }">
                  <span>{{ option.name }}</span>
                  <ArchivedOptionTag v-if="option.archived" />
                </template>
                <template #value>
                  <span v-if="selectedPrinter">{{ selectedPrinter.name }}</span>
                  <ArchivedOptionTag v-if="selectedPrinter?.archived" />
                </template>
              </Select>
              <ArchivedSelectionWarning v-if="isPrinterArchived(selectedPrinter)" />
            </div>
            <div v-if="config.paper" class="field">
              <label :id="id('paper') + '-label'" :for="id('paper')">{{ t(`${p}.editor.fields.paper`) }}</label>
              <Select
                :id="id('paper')"
                :aria-labelledby="id('paper') + '-label'"
                v-model="form.paper"
                :options="paperOptions"
                option-label="label"
                option-value="value"
                fluid
              />
            </div>
          </div>

          <div class="field-row">
            <div class="field">
              <label :for="id('auto-print')">{{ t(`${p}.editor.fields.autoPrint`) }}</label>
              <ToggleSwitch :id="id('auto-print')" v-model="form.autoPrint" :disabled="!form.trigger" />
            </div>
            <div class="field">
              <label :for="id('enabled')">{{ t(`${p}.editor.fields.enabled`) }}</label>
              <ToggleSwitch :id="id('enabled')" v-model="form.enabled" />
            </div>
          </div>

          <div class="field-row">
            <div class="field">
              <label :id="id('copies-rule') + '-label'" :for="id('copies-rule')">{{ t(`${p}.editor.fields.copiesRule`) }}</label>
              <Select
                :id="id('copies-rule')"
                :aria-labelledby="id('copies-rule') + '-label'"
                v-model="form.copiesRule"
                :options="copiesRuleOptions"
                option-label="label"
                option-value="value"
                fluid
              />
            </div>
            <div class="field">
              <label :for="id('copies-fixed')">{{ t(`${p}.editor.fields.copiesFixed`) }}</label>
              <InputNumber :id="id('copies-fixed')" v-model="form.copiesFixed" :min="1" fluid />
            </div>
            <div class="field">
              <label :for="id('max-copies')">{{ t(`${p}.editor.fields.maxCopies`) }}</label>
              <InputNumber
                :id="id('max-copies')"
                v-model="form.maxCopies"
                :min="1"
                fluid
                v-tooltip.top="t(`${p}.editor.fields.maxCopiesHint`)"
              />
            </div>
          </div>

          <div class="field">
            <div class="source-label-row">
              <label :for="id('source')">{{ t(`${p}.editor.fields.source`) }}</label>
              <label class="upload-button">
                <i class="mdi mdi-upload" aria-hidden="true" /> {{ t(`${p}.editor.fields.upload`) }}
                <input type="file" :accept="config.sourceAccept" hidden @change="onFileSelected" />
              </label>
            </div>
            <Textarea
              :id="id('source')"
              v-model="form.source"
              rows="12"
              fluid
              class="source-textarea"
              spellcheck="false"
            />
            <Message v-if="jsonError" severity="error" class="mt-1">{{ jsonError }}</Message>
          </div>

          <div class="field">
            <!-- eslint-disable-next-line vuejs-accessibility/label-has-for -- captions every select below, each names it through aria-labelledby -->
            <label :id="id('field-map')">{{ t(`${p}.editor.fields.fieldMap`) }}</label>
            <Message v-if="unmappedPlaceholders.length" severity="warn" class="mb-2">
              {{ t(`${p}.editor.errors.unmappedPlaceholders`, { count: unmappedPlaceholders.length, names: unmappedPlaceholders.join(', ') }) }}
            </Message>
            <div v-if="detectedPlaceholders.length === 0" class="text-muted">
              {{ t(`${p}.editor.fields.fieldMapEmpty`) }}
            </div>
            <div v-for="placeholder in detectedPlaceholders" :key="placeholder" class="field-map-row">
              <code :id="id(`placeholder-${placeholder}`)" class="placeholder-name">{{ config.fieldToken(placeholder) }}</code>
              <Select
                v-model="form.fieldMap[placeholder]"
                :aria-labelledby="`${id('field-map')} ${id(`placeholder-${placeholder}`)}`"
                :options="fieldSources"
                option-label="name"
                option-value="name"
                :loading="loadingFieldSources"
                :placeholder="t(`${p}.editor.fields.fieldMapPlaceholder`)"
                filter
                fluid
              >
                <template #option="{ option }">
                  <div class="field-source-option">
                    <span>{{ (option as FieldSourceResponse).name }}</span>
                    <span
                      v-if="(option as FieldSourceResponse).kind === 'computed'"
                      class="field-source-description"
                    >
                      {{ (option as FieldSourceResponse).description }}
                    </span>
                  </div>
                </template>
              </Select>
            </div>
          </div>

          <div class="field">
            <label :for="id('note')">{{ t(`${p}.editor.fields.note`) }}</label>
            <Textarea :id="id('note')" v-model="form.note" rows="2" fluid auto-resize />
          </div>
        </div>

        <!-- ── Right: preview ───────────────────────────────────────── -->
        <div class="editor-pane preview-pane">
          <div class="field">
            <label :for="id('preview-id')">{{ t(`${p}.editor.preview.recordId`) }}</label>
            <div class="record-id-row">
              <InputNumber
                :id="id('preview-id')"
                v-model="previewRootId"
                :min="1"
                fluid
                :use-grouping="false"
                v-tooltip.top="t(`${p}.editor.preview.recordIdHint`)"
              />
              <Button
                v-if="config.download"
                type="button"
                icon="mdi mdi-download-outline"
                severity="secondary"
                :disabled="!previewRootId"
                :loading="downloading"
                v-tooltip.top.focus="t(`${p}.download.action`)"
                :aria-label="t(`${p}.download.action`)"
                @click="runDownload"
              />
            </div>
            <Message v-if="downloadError" severity="error" class="mt-1">{{ downloadError }}</Message>
          </div>

          <div v-if="previewLoading" class="preview-loading">
            <ProgressSpinner style="width: 2rem; height: 2rem" />
          </div>
          <Message v-else-if="previewError" severity="error">{{ previewError }}</Message>
          <template v-else-if="previewImageUrl">
            <img :src="previewImageUrl" :alt="t(`${p}.previewAction`)" class="preview-image" />
            <Message v-for="warning in previewWarnings" :key="warning" severity="warn" class="mt-1">
              {{ warning }}
            </Message>
            <pre v-if="previewText" class="preview-zpl">{{ previewText }}</pre>
          </template>
          <div v-else class="preview-empty text-muted">
            {{ t(`${p}.editor.preview.empty`) }}
          </div>
        </div>
      </div>

      <Message v-if="errorMessage" severity="error" class="mt-2">{{ errorMessage }}</Message>

      <div class="form-footer">
        <Button
          type="button"
          icon="mdi mdi-file-import-outline"
          :label="t('templateFiles.importFile')"
          severity="secondary"
          text
          :disabled="submitting || !template"
          data-testid="print-template-import"
          @click="onImport"
        />
        <Button
          type="button"
          icon="mdi mdi-file-export-outline"
          :label="t('templateFiles.exportFile')"
          severity="secondary"
          text
          class="file-action"
          :disabled="submitting || !template"
          data-testid="print-template-export"
          @click="onExport"
        />
        <Button
          type="button"
          :label="t('common.cancel')"
          severity="secondary"
          @click="onCancel"
          :disabled="submitting"
        />
        <Button type="submit" :label="t('common.save')" :loading="submitting" />
      </div>
    </form>
  </Dialog>
</template>

<style scoped lang="scss">
.editor-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.editor-panes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-5);
  align-items: start;
}

.editor-pane {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  min-width: 0;
}

.field-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--space-3);
}

.field {
  min-width: 0;

  label {
    font-size: var(--font-size-sm);
    font-weight: 500;
  }
}

.source-label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-button {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  cursor: pointer;
  color: var(--p-primary-color);
}

.source-textarea {
  font-family: monospace;
  font-size: var(--font-size-sm);
}

.field-map-row {
  display: grid;
  grid-template-columns: 10rem 1fr;
  gap: var(--space-2);
  align-items: center;
  margin-bottom: var(--space-2);
}

.placeholder-name {
  font-size: var(--font-size-sm);
  background: var(--p-content-background);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--p-content-border-radius);
}

.field-source-option {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.field-source-description {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
}

.preview-pane {
  border-left: 1px solid var(--p-content-border-color);
  padding-left: var(--space-5);
}

.record-id-row {
  display: flex;
  gap: var(--space-2);
}

.preview-loading,
.preview-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6) 0;
}

.preview-image {
  max-width: 100%;
  border: 1px solid var(--p-content-border-color);
  background: var(--paper);
}

.preview-zpl {
  margin: 0;
  padding: var(--space-2) var(--space-3);
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  font-family: monospace;
  font-size: var(--font-size-xs);
  white-space: pre-wrap;
  max-height: 12rem;
  overflow-y: auto;
}

.text-muted {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-sm);
}

// The file actions sit at the start of the footer, the dialog's own actions at its end.
.file-action {
  margin-right: auto;
}
</style>
