<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { useEntityFormDialog } from '@/shared/composables/useEntityFormDialog'
import { useTemplateFileTransfer } from '@/shared/composables/useTemplateFileTransfer'
import {
  TemplateFileError,
  optionalString,
  parseTemplateFile,
  requireNumber,
  requireRecordList,
  requireString,
  requireStringMap,
  templateFileName,
  unknownKeys,
} from '@/shared/utils/templateFile'
import { createPlcEnvironment, updatePlcEnvironment } from '../api/plcEnvironmentsApi'
import { usePlcEnvironmentsStore } from '../stores/plcEnvironmentsStore'
import {
  PLC_EXPORT_SOURCES,
  PLC_PREFIX_KEYS,
  type PlcEnvironment,
  type PlcEnvironmentSettings,
  type PlcExportColumnSource,
} from '../types/productDevice'

/**
 * Creates or edits a PLC environment: its name, whether it is the default,
 * the prefix per signal type, the longest tag, the character conversion,
 * the tag tables and the columns of the export. A new one starts from the
 * settings of Siemens TIA Portal (`template`).
 */
const props = defineProps<{
  environment?: PlcEnvironment
  /** The settings a new environment starts from. */
  template?: PlcEnvironmentSettings
}>()

const emit = defineEmits<{ saved: [environment: PlcEnvironment] }>()
const visible = defineModel<boolean>('visible', { default: false })

const { t } = useI18n()
const store = usePlcEnvironmentsStore()

interface ConversionRow {
  key: number
  source: string
  target: string
}

interface ColumnRow {
  key: number
  header: string
  source: PlcExportColumnSource
  value: string
}

interface FormState {
  name: string
  is_default: boolean
  prefixes: Record<string, string>
  max_tag_length: number
  conversions: ConversionRow[]
  tag_table: string
  safety_tag_table: string
  export_sheet: string
  export_columns: ColumnRow[]
}

let nextKey = 0

function formFrom(settings: PlcEnvironmentSettings, isDefault: boolean): FormState {
  return {
    name: settings.name,
    is_default: isDefault,
    prefixes: Object.fromEntries(PLC_PREFIX_KEYS.map((key) => [key, settings.prefixes[key] ?? ''])),
    max_tag_length: settings.max_tag_length,
    conversions: settings.conversions.map((c) => ({ key: nextKey++, source: c.source, target: c.target })),
    tag_table: settings.tag_table,
    safety_tag_table: settings.safety_tag_table ?? '',
    export_sheet: settings.export_sheet,
    export_columns: settings.export_columns.map((c) => ({
      key: nextKey++,
      header: c.header,
      source: c.source,
      value: c.value ?? '',
    })),
  }
}

function emptyForm(): FormState {
  const template = props.template
  if (template) return formFrom({ ...template, name: '' }, false)
  return {
    name: '',
    is_default: false,
    prefixes: Object.fromEntries(PLC_PREFIX_KEYS.map((key) => [key, ''])),
    max_tag_length: 128,
    conversions: [],
    tag_table: '',
    safety_tag_table: '',
    export_sheet: '',
    export_columns: [],
  }
}

const { form, submitting, errorMessage, isEditMode, onSubmit, onCancel } = useEntityFormDialog<
  PlcEnvironment,
  FormState
>({
  visible,
  entity: () => props.environment,
  emptyForm,
  formFromEntity: (environment) => formFrom(environment, environment.is_default),
  validate: (form) => {
    if (!form.name.trim()) return t('productDevices.plc.errors.nameRequired')
    if (!form.tag_table.trim() || !form.export_sheet.trim()) return t('productDevices.plc.errors.tableRequired')
    if (form.conversions.some((c) => c.source === '')) return t('productDevices.plc.errors.sourceRequired')
    const sources = form.conversions.map((c) => c.source)
    if (new Set(sources).size !== sources.length) return t('productDevices.plc.errors.sourceTwice')
    if (form.export_columns.length === 0) return t('productDevices.plc.errors.columnRequired')
    if (form.export_columns.some((c) => !c.header.trim())) return t('productDevices.plc.errors.headerRequired')
    return null
  },
  save: async (form, isEdit, environment) => {
    const body = {
      name: form.name.trim(),
      is_default: form.is_default,
      prefixes: { ...form.prefixes },
      max_tag_length: form.max_tag_length,
      conversions: form.conversions.map((c) => ({ source: c.source, target: c.target })),
      tag_table: form.tag_table.trim(),
      safety_tag_table: form.safety_tag_table.trim() || null,
      export_sheet: form.export_sheet.trim(),
      export_columns: form.export_columns.map((c) => ({
        header: c.header.trim(),
        source: c.source,
        value: c.source === 'constant' ? c.value : null,
      })),
    }
    const saved =
      isEdit && environment ? await updatePlcEnvironment(environment.id, body) : await createPlcEnvironment(body)
    store.upsert(saved)
    return saved
  },
  onSaved: (saved) => emit('saved', saved),
  unknownErrorMessage: t('productDevices.resources.errors.unknown'),
})

// The default stays the default until another one takes its place.
const defaultLocked = computed(() => isEditMode.value && props.environment?.is_default === true)

const sourceOptions = computed(() =>
  PLC_EXPORT_SOURCES.map((value) => ({ value, label: t(`productDevices.plc.sources.${value}`) })),
)

function move<T>(list: T[], index: number, delta: number): void {
  const target = index + delta
  if (target < 0 || target >= list.length) return
  const [row] = list.splice(index, 1)
  if (row !== undefined) list.splice(target, 0, row)
}

function addConversion(): void {
  form.conversions.push({ key: nextKey++, source: '', target: '_' })
}

function addColumn(): void {
  form.export_columns.push({ key: nextKey++, header: '', source: 'constant', value: '' })
}

// ── Template file ──
// An import fills the form, keeping whether this one is the default; the
// admin saves as usual. The export writes what the form holds now.

const FILE_KEYS = [
  'name',
  'prefixes',
  'max_tag_length',
  'conversions',
  'tag_table',
  'safety_tag_table',
  'export_sheet',
  'export_columns',
]

const { importFiles, exportFile } = useTemplateFileTransfer()

function settingsFromFile(content: Record<string, unknown>): PlcEnvironmentSettings {
  return {
    name: requireString(content, 'name'),
    prefixes: requireStringMap(content, 'prefixes'),
    max_tag_length: requireNumber(content, 'max_tag_length'),
    conversions: requireRecordList(content, 'conversions').map((c) => ({
      source: requireString(c, 'source'),
      target: requireString(c, 'target'),
    })),
    tag_table: requireString(content, 'tag_table'),
    safety_tag_table: optionalString(content, 'safety_tag_table'),
    export_sheet: requireString(content, 'export_sheet'),
    export_columns: requireRecordList(content, 'export_columns').map((c) => {
      const source = requireString(c, 'source') as PlcExportColumnSource
      if (!PLC_EXPORT_SOURCES.includes(source)) throw new TemplateFileError('invalidContent', 'export_columns')
      return { header: requireString(c, 'header'), source, value: optionalString(c, 'value') }
    }),
  }
}

function onImport(): void {
  void importFiles('.json', ([file]) => {
    const content = parseTemplateFile(file!.text, 'plc_environment')
    const settings = settingsFromFile(content)
    Object.assign(form, formFrom(settings, form.is_default))
    const ignoredPrefixes = Object.keys(settings.prefixes)
      .filter((key) => !(PLC_PREFIX_KEYS as readonly string[]).includes(key))
      .map((key) => `prefixes.${key}`)
    return [...unknownKeys(content, FILE_KEYS), ...ignoredPrefixes]
  })
}

function onExport(): void {
  exportFile(
    'plc_environment',
    {
      name: form.name.trim(),
      prefixes: { ...form.prefixes },
      max_tag_length: form.max_tag_length,
      conversions: form.conversions.map((c) => ({ source: c.source, target: c.target })),
      tag_table: form.tag_table.trim(),
      safety_tag_table: form.safety_tag_table.trim() || null,
      export_sheet: form.export_sheet.trim(),
      export_columns: form.export_columns.map((c) => ({
        header: c.header.trim(),
        source: c.source,
        value: c.source === 'constant' ? c.value : null,
      })),
    },
    templateFileName(form.name || 'plc_environment', 'json'),
  )
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    :header="isEditMode ? t('productDevices.plc.editEnvironment') : t('productDevices.plc.createEnvironment')"
    :style="{ width: 'var(--dialog-width-lg)' }"
  >
    <form class="plc-form" @submit.prevent="onSubmit">
      <div class="settings-fields">
        <p class="section-label">{{ t('productDevices.plc.sections.general') }}</p>
        <div class="field-row">
          <label for="plc-name">{{ t('productDevices.plc.fields.name') }}</label>
          <InputText id="plc-name" v-model="form.name" :maxlength="100" data-testid="plc-name" />
        </div>
        <div class="field-row field-row--toggle">
          <label for="plc-default">{{ t('productDevices.plc.fields.isDefault') }}</label>
          <ToggleSwitch v-model="form.is_default" input-id="plc-default" :disabled="defaultLocked" />
          <small class="hint">{{ t('productDevices.plc.hints.isDefault') }}</small>
        </div>
        <div class="field-row">
          <label for="plc-length">
            {{ t('productDevices.plc.fields.maxTagLength') }}
            <small class="hint">{{ t('productDevices.plc.hints.maxTagLength') }}</small>
          </label>
          <InputNumber
            v-model="form.max_tag_length"
            input-id="plc-length"
            :min="8"
            :max="1024"
            :use-grouping="false"
            data-testid="plc-length"
          />
        </div>
        <div class="field-row">
          <label for="plc-table">{{ t('productDevices.plc.fields.tagTable') }}</label>
          <InputText id="plc-table" v-model="form.tag_table" :maxlength="100" />
        </div>
        <div class="field-row">
          <label for="plc-safety-table">
            {{ t('productDevices.plc.fields.safetyTagTable') }}
            <small class="hint">{{ t('productDevices.plc.hints.safetyTagTable') }}</small>
          </label>
          <InputText id="plc-safety-table" v-model="form.safety_tag_table" :maxlength="100" />
        </div>

        <Divider />

        <p class="section-label">{{ t('productDevices.plc.sections.prefixes') }}</p>
        <p class="hint">{{ t('productDevices.plc.hints.prefixes') }}</p>
        <div v-for="key in PLC_PREFIX_KEYS" :key="key" class="field-row">
          <label :for="`plc-prefix-${key}`">{{ t(`productDevices.plc.prefixKeys.${key}`) }}</label>
          <InputText
            :id="`plc-prefix-${key}`"
            v-model="form.prefixes[key]"
            :maxlength="20"
            :data-testid="`plc-prefix-${key}`"
          />
        </div>

        <Divider />

        <p class="section-label">{{ t('productDevices.plc.sections.conversions') }}</p>
        <p class="hint">{{ t('productDevices.plc.hints.conversions') }}</p>
        <div class="conversions">
          <div v-for="(row, index) in form.conversions" :key="row.key" class="conversion" data-testid="plc-conversion">
            <InputText
              v-model="row.source"
              :maxlength="10"
              size="small"
              :aria-label="t('productDevices.plc.fields.source')"
              :placeholder="t('productDevices.plc.fields.source')"
            />
            <i class="mdi mdi-arrow-right arrow" aria-hidden="true" />
            <InputText
              v-model="row.target"
              :maxlength="10"
              size="small"
              :aria-label="t('productDevices.plc.fields.target')"
              :placeholder="t('productDevices.plc.fields.removed')"
            />
            <Button
              type="button"
              icon="mdi mdi-close"
              size="small"
              text
              severity="danger"
              :aria-label="t('productDevices.resources.removeRow')"
              @click="form.conversions.splice(index, 1)"
            />
          </div>
        </div>
        <Button
          type="button"
          icon="mdi mdi-plus"
          :label="t('productDevices.plc.addConversion')"
          size="small"
          text
          class="add"
          data-testid="plc-add-conversion"
          @click="addConversion"
        />

        <Divider />

        <p class="section-label">{{ t('productDevices.plc.sections.export') }}</p>
        <div class="field-row">
          <label for="plc-sheet">{{ t('productDevices.plc.fields.exportSheet') }}</label>
          <InputText id="plc-sheet" v-model="form.export_sheet" :maxlength="100" />
        </div>
        <p class="hint">{{ t('productDevices.plc.hints.columns') }}</p>
        <div v-for="(row, index) in form.export_columns" :key="row.key" class="column" data-testid="plc-column">
          <InputText
            v-model="row.header"
            :maxlength="100"
            size="small"
            class="column-header"
            :aria-label="t('productDevices.plc.fields.header')"
            :placeholder="t('productDevices.plc.fields.header')"
          />
          <Select
            v-model="row.source"
            :options="sourceOptions"
            option-label="label"
            option-value="value"
            size="small"
            class="column-source"
            :aria-label="t('productDevices.plc.fields.columnSource')"
          />
          <InputText
            v-model="row.value"
            :maxlength="200"
            size="small"
            class="column-value"
            :disabled="row.source !== 'constant'"
            :aria-label="t('productDevices.plc.fields.value')"
            :placeholder="t('productDevices.plc.fields.value')"
          />
          <div class="row-actions">
            <Button
              type="button"
              icon="mdi mdi-arrow-up"
              size="small"
              text
              severity="secondary"
              :disabled="index === 0"
              :aria-label="t('productDevices.resources.moveUp')"
              @click="move(form.export_columns, index, -1)"
            />
            <Button
              type="button"
              icon="mdi mdi-arrow-down"
              size="small"
              text
              severity="secondary"
              :disabled="index === form.export_columns.length - 1"
              :aria-label="t('productDevices.resources.moveDown')"
              @click="move(form.export_columns, index, 1)"
            />
            <Button
              type="button"
              icon="mdi mdi-close"
              size="small"
              text
              severity="danger"
              :aria-label="t('productDevices.resources.removeRow')"
              @click="form.export_columns.splice(index, 1)"
            />
          </div>
        </div>
        <Button
          type="button"
          icon="mdi mdi-plus"
          :label="t('productDevices.plc.addColumn')"
          size="small"
          text
          class="add"
          @click="addColumn"
        />
      </div>

      <Message v-if="errorMessage" severity="error">{{ errorMessage }}</Message>

      <div class="form-footer">
        <Button
          type="button"
          icon="mdi mdi-file-import-outline"
          :label="t('templateFiles.importFile')"
          severity="secondary"
          text
          :disabled="submitting"
          data-testid="plc-import"
          @click="onImport"
        />
        <Button
          type="button"
          icon="mdi mdi-file-export-outline"
          :label="t('templateFiles.exportFile')"
          severity="secondary"
          text
          class="file-action"
          :disabled="submitting"
          data-testid="plc-export"
          @click="onExport"
        />
        <Button type="button" :label="t('common.cancel')" severity="secondary" :disabled="submitting" @click="onCancel" />
        <Button type="submit" :label="t('common.save')" :loading="submitting" data-testid="plc-save" />
      </div>
    </form>
  </Dialog>
</template>

<style scoped lang="scss">
.plc-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.conversions {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(15rem, 1fr));
  gap: var(--space-1) var(--space-4);
}

.conversion {
  display: flex;
  align-items: center;
  gap: var(--space-1);

  :deep(input) {
    width: 4.5rem;
  }
}

.arrow {
  color: var(--p-text-muted-color);
}

.column {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.column-header {
  flex: 2;
  min-width: 0;
}

.column-source {
  flex: 2;
  min-width: 0;
}

.column-value {
  flex: 1;
  min-width: 0;
}

.add {
  align-self: flex-start;
}

// The file actions sit at the start of the footer, the dialog's own actions at its end.
.file-action {
  margin-right: auto;
}
</style>
