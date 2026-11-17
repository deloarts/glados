<script setup lang="ts">
// The Data import tab: one import profile per spreadsheet import. A profile
// says where the header row is (detected from the column names, or a fixed
// row), how many rows below it the data starts, how many data rows one
// upload may hold, and which column names map to each field. The settings
// are loaded here, not with the aggregate, since no other tab needs them.
import { computed, onMounted, reactive, watch } from 'vue'
import { useI18n } from 'vue-i18n'

import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { permissionLabel } from '@/shared/utils/permissionLabels'
import { useAdminSettingsStore } from '../stores/adminSettingsStore'
import { useSettingsSave } from '../composables/useSettingsSave'
import { useTemplateFileTransfer } from '@/shared/composables/useTemplateFileTransfer'
import { parseTemplateFile, requireRecord, requireStringList, unknownKeys } from '@/shared/utils/templateFile'
import AdminSettingsTabShell from './AdminSettingsTabShell.vue'
import type {
  AdminDataImportSettings,
  DataImportProfileSettings,
} from '../types/adminSettingsTypes'

type HeaderMode = 'auto' | 'fixed'

interface ProfileForm {
  import_type: DataImportProfileSettings['import_type']
  header_mode: HeaderMode
  header_row: number
  data_offset: number
  max_rows: number
  fields: { key: string; column_names: string[] }[]
}

const { t } = useI18n()
const store = useAdminSettingsStore()
const { hasPermission } = usePermissions()

const canWrite = hasPermission(Permission.WRITE_SETTINGS)

const form = reactive<{ profiles: ProfileForm[] }>({ profiles: [] })

const headerModes: { value: HeaderMode; label: string }[] = [
  { value: 'auto', label: t('adminSettings.dataImport.headerAuto') },
  { value: 'fixed', label: t('adminSettings.dataImport.headerFixed') },
]

function toForm(profile: DataImportProfileSettings): ProfileForm {
  return {
    import_type: profile.import_type,
    header_mode: profile.header_row === null ? 'auto' : 'fixed',
    header_row: profile.header_row ?? 1,
    data_offset: profile.data_offset,
    max_rows: profile.max_rows,
    fields: profile.fields.map((f) => ({ key: f.key, column_names: [...f.column_names] })),
  }
}

watch(
  () => store.dataImport,
  (settings: AdminDataImportSettings | null) => {
    if (!settings) return
    form.profiles = settings.profiles.map(toForm)
  },
  { immediate: true },
)

onMounted(() => {
  void store.fetchDataImport()
})

function cleanNames(names: string[]): string[] {
  return names.map((n) => n.trim()).filter((n) => n.length > 0)
}

const { saving, onSave } = useSettingsSave(() =>
  store.saveDataImport({
    profiles: form.profiles.map((p) => ({
      import_type: p.import_type,
      header_row: p.header_mode === 'auto' ? null : p.header_row,
      data_offset: p.data_offset,
      max_rows: p.max_rows,
      column_names: Object.fromEntries(p.fields.map((f) => [f.key, cleanNames(f.column_names)])),
    })),
  }),
)

// ── Template file ──
// A file holds column names per import type and field. An import adds the
// names a field does not have yet, so files for several languages combine;
// the admin saves as usual. The export writes the names the form holds now.

const { importFiles, exportFile } = useTemplateFileTransfer()

const importBlocked = computed(() =>
  canWrite ? '' : t('common.permissionMissing', { permission: permissionLabel(t, Permission.WRITE_SETTINGS) }),
)

function onImport(): void {
  void importFiles(
    '.json',
    (files) => {
      const ignored = new Set<string>()
      const additions: { names: string[]; add: string[] }[] = []
      for (const file of files) {
        const content = parseTemplateFile(file.text, 'data_import_column_names')
        unknownKeys(content, ['column_names']).forEach((key) => ignored.add(key))
        const columnNames = requireRecord(content, 'column_names')
        for (const importType of Object.keys(columnNames)) {
          const profile = form.profiles.find((p) => p.import_type === importType)
          const fields = requireRecord(columnNames, importType)
          if (!profile) {
            ignored.add(importType)
            continue
          }
          for (const key of Object.keys(fields)) {
            const field = profile.fields.find((f) => f.key === key)
            const names = requireStringList(fields, key)
            if (field) additions.push({ names: field.column_names, add: names })
            else ignored.add(`${importType}.${key}`)
          }
        }
      }
      // Applied only once every file is read, so a bad file changes nothing.
      for (const { names, add } of additions) {
        for (const name of cleanNames(add)) {
          if (!names.some((n) => n.toLowerCase() === name.toLowerCase())) names.push(name)
        }
      }
      return [...ignored]
    },
    true,
  )
}

function onExport(): void {
  exportFile(
    'data_import_column_names',
    {
      column_names: Object.fromEntries(
        form.profiles.map((p) => [
          p.import_type,
          Object.fromEntries(p.fields.map((f) => [f.key, cleanNames(f.column_names)])),
        ]),
      ),
    },
    'column_names.json',
  )
}
</script>

<template>
  <AdminSettingsTabShell>
    <template #controls>
      <Toolbar>
        <template #start>
          <Button
            :label="t('common.save')"
            icon="mdi mdi-content-save"
            text
            severity="contrast"
            :loading="saving"
            :disabled="!canWrite || form.profiles.length === 0"
            data-testid="data-import-save"
            @click="onSave"
          />
          <span v-tooltip.bottom="importBlocked">
            <Button
              :label="t('templateFiles.importFile')"
              icon="mdi mdi-file-import-outline"
              text
              severity="contrast"
              :disabled="!canWrite || form.profiles.length === 0"
              data-testid="data-import-import"
              @click="onImport"
            />
          </span>
          <Button
            :label="t('templateFiles.exportFile')"
            icon="mdi mdi-file-export-outline"
            text
            severity="contrast"
            :disabled="form.profiles.length === 0"
            data-testid="data-import-export"
            @click="onExport"
          />
        </template>
      </Toolbar>
    </template>

    <div class="settings-fields">
      <p class="hint">{{ t('adminSettings.dataImport.intro') }}</p>

      <template v-for="(profile, index) in form.profiles" :key="profile.import_type">
        <Divider v-if="index > 0" />
        <p class="section-label" :data-testid="`data-import-profile-${profile.import_type}`">
          {{ t(`adminSettings.dataImport.types.${profile.import_type}`) }}
        </p>

        <div class="field-row">
          <label :id="`data-import-${profile.import_type}-header-mode-label`" :for="`data-import-${profile.import_type}-header-mode`">
            {{ t('adminSettings.dataImport.headerRow') }}
            <span class="hint">{{ t('adminSettings.dataImport.headerRowHint') }}</span>
          </label>
          <div class="data-import-inline">
            <Select
              v-model="profile.header_mode"
              :input-id="`data-import-${profile.import_type}-header-mode`"
              :aria-labelledby="`data-import-${profile.import_type}-header-mode-label`"
              :options="headerModes"
              option-label="label"
              option-value="value"
              :disabled="!canWrite"
            />
            <InputNumber
              v-if="profile.header_mode === 'fixed'"
              v-model="profile.header_row"
              :aria-label="t('adminSettings.dataImport.headerRowNumber')"
              :min="1"
              :max="100"
              :use-grouping="false"
              :disabled="!canWrite"
            />
          </div>
        </div>

        <div class="field-row">
          <label :for="`data-import-${profile.import_type}-offset`">
            {{ t('adminSettings.dataImport.dataOffset') }}
            <span class="hint">{{ t('adminSettings.dataImport.dataOffsetHint') }}</span>
          </label>
          <InputNumber
            v-model="profile.data_offset"
            :input-id="`data-import-${profile.import_type}-offset`"
            :min="1"
            :max="100"
            :use-grouping="false"
            :disabled="!canWrite"
          />
        </div>

        <div class="field-row">
          <label :for="`data-import-${profile.import_type}-max-rows`">
            {{ t('adminSettings.dataImport.maxRows') }}
            <span class="hint">{{ t('adminSettings.dataImport.maxRowsHint') }}</span>
          </label>
          <InputNumber
            v-model="profile.max_rows"
            :input-id="`data-import-${profile.import_type}-max-rows`"
            :min="1"
            :max="1000"
            :use-grouping="false"
            :disabled="!canWrite"
          />
        </div>

        <p class="hint">{{ t('adminSettings.dataImport.columnNamesHint') }}</p>
        <div v-for="field in profile.fields" :key="field.key" class="field-row">
          <label :for="`data-import-${profile.import_type}-${field.key}`">
            {{ t(`adminSettings.dataImport.fields.${field.key}`) }}
          </label>
          <AutoComplete
            v-model="field.column_names"
            :input-id="`data-import-${profile.import_type}-${field.key}`"
            multiple
            :typeahead="false"
            fluid
            :placeholder="t('adminSettings.dataImport.columnNamesPlaceholder')"
            :disabled="!canWrite"
          />
        </div>
      </template>
    </div>
  </AdminSettingsTabShell>
</template>

<style scoped lang="scss">
p.hint {
  margin: 0;
}

.data-import-inline {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}
</style>
