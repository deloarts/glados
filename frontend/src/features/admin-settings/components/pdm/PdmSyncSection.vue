<!--
  The "Synchronisation" block of the SolidWorks PDM settings: poll status, sync
  settings, watched folders and the workflow state pickers per item kind. Each
  field is its own v-model, so the parent tab keeps the form. Validation comes
  from utils/pdmSync.ts, which mirrors the backend's UpdatePdmSettings rules
  and is shared with the tab, so Save blocks on the hints shown here.
-->
<script setup lang="ts">
import { computed, onMounted, ref, useId, watch, type ModelRef, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'
import { storeToRefs } from 'pinia'

import { Permission } from '@/core/auth/permissions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useAdminSettingsStore } from '../../stores/adminSettingsStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatDateTimeOrDash } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { normalizeExtension, validatePdmSync } from '../../utils/pdmSync'
import PdmDocumentCategoriesTable from './PdmDocumentCategoriesTable.vue'
import PdmFolderPickerDialog from './PdmFolderPickerDialog.vue'
import type { PdmWatchedFolder } from '../../types/adminSettingsTypes'

const SNAPSHOT_STATE_SEVERITY: Record<string, string> = {
  pending: 'info',
  ingested: 'success',
  skipped: 'secondary',
  missing: 'warn',
  conflict: 'danger',
  error: 'danger',
}

const { t } = useI18n()
// Prefixes the ids that tie each label to its control.
const uid = useId()
const confirm = useConfirm()
const store = useAdminSettingsStore()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const props = defineProps<{
  canWrite: boolean
  configured: boolean
  // Read-only: the toggle governs the whole integration and lives on
  // PdmConnectionSection. The validation hints here only need its value.
  enabled: boolean
  lastPollAt: string | null
  lastPollError: string | null
  lastPollSummary: string | null
  snapshotCounts: Record<string, number>
}>()

// canWrite is write:settings; without it the section's controls stay
// visible but disabled, naming the missing permission.
const { missing } = useMissingPermission()
const writeBlocked = computed(() => (props.canWrite ? '' : missing(Permission.WRITE_SETTINGS)))

const watchedFolders = defineModel<PdmWatchedFolder[]>('watchedFolders', { required: true })
// One released/obsolete/replaced triple per item kind: made and bought
// items need not share a PDM workflow (docs/reference/pdm-settings.md).
const madeReleasedStateIds = defineModel<number[]>('madeReleasedStateIds', { required: true })
const madeObsoleteStateIds = defineModel<number[]>('madeObsoleteStateIds', { required: true })
const madeReplacedStateIds = defineModel<number[]>('madeReplacedStateIds', { required: true })
const boughtReleasedStateIds = defineModel<number[]>('boughtReleasedStateIds', { required: true })
const boughtObsoleteStateIds = defineModel<number[]>('boughtObsoleteStateIds', { required: true })
const boughtReplacedStateIds = defineModel<number[]>('boughtReplacedStateIds', { required: true })
// Exported documents only sync from these states, whatever their workflow.
const documentReleasedStateIds = defineModel<number[]>('documentReleasedStateIds', {
  required: true,
})
const pollIntervalMinutes = defineModel<number>('pollIntervalMinutes', { required: true })
const coldFolderMaxMultiplier = defineModel<number>('coldFolderMaxMultiplier', { required: true })
const ingestConcurrency = defineModel<number>('ingestConcurrency', { required: true })
const cadItemsReadOnly = defineModel<boolean>('cadItemsReadOnly', { required: true })
const writebackEnabled = defineModel<boolean>('writebackEnabled', { required: true })
const madeItemExtensions = defineModel<string[]>('madeItemExtensions', { required: true })
const boughtItemExtensions = defineModel<string[]>('boughtItemExtensions', { required: true })
const documentCategories = defineModel<Record<string, string>>('documentCategories', {
  required: true,
})
// Extension to the item kinds that do not receive that document.
const documentExcludedKinds = defineModel<Record<string, string[]>>('documentExcludedKinds', {
  required: true,
})
const thumbnailsEnabled = defineModel<boolean>('thumbnailsEnabled', { required: true })
const stuckAfterDays = defineModel<number>('stuckAfterDays', { required: true })

const kindOptions = computed(() => [
  {
    label: t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.byKind'),
    value: 'by_kind' as const,
  },
  { label: t('adminSettings.itemFields.madeSection'), value: 'made' as const },
  { label: t('adminSettings.itemFields.boughtSection'), value: 'bought' as const },
  {
    label: t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.exportedDocuments'),
    value: 'documents' as const,
  },
])

// "By datacard" reuses the exact same label as the per-row `kind` picker's
// own `by_kind` option (same underlying idea, a different field) rather
// than duplicating the translation.
const matchByOptions = computed(() => [
  {
    label: t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.byKind'),
    value: 'datacard' as const,
  },
  {
    label: t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.matchByFilename'),
    value: 'filename' as const,
  },
])

const FILENAME_PATTERN_EXAMPLE = '^(?P<part_number>ZT-\\d{2}-\\d{5})_(?P<revision>[A-Z]+)\\.pdf$'
const filenamePatternHint = computed(() =>
  t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.filenamePattern.hint', {
    example: FILENAME_PATTERN_EXAMPLE,
  }),
)

// ── File types (made/bought file extension chips) ───────────────────────
// Same interaction as AdminSettingsTabMail's alert_recipients Tag list:
// normalizeExtension collapses "SLDPRT" / ".sldprt" to the same entry, and
// blanks and duplicates are ignored.

const madeExtensionInput = ref('')
const boughtExtensionInput = ref('')

// Two lists rather than one generic pair of functions taking the target ref
// as an argument: a top-level ref/model referenced from the template is
// auto-unwrapped by the SFC compiler, so a template call like
// `addExtension(madeItemExtensions, ...)` would pass the already unwrapped
// `string[]`, not the ref itself.
type ExtensionList = 'made' | 'bought'

function extensionModel(list: ExtensionList): Ref<string[]> {
  return list === 'made' ? madeItemExtensions : boughtItemExtensions
}

function extensionInput(list: ExtensionList): Ref<string> {
  return list === 'made' ? madeExtensionInput : boughtExtensionInput
}

function addExtension(list: ExtensionList): void {
  const input = extensionInput(list)
  const ext = normalizeExtension(input.value)
  input.value = ''
  if (!ext) return
  const model = extensionModel(list)
  if (model.value.includes(ext)) return
  model.value = [...model.value, ext]
}

function removeExtension(list: ExtensionList, extension: string): void {
  const model = extensionModel(list)
  model.value = model.value.filter((e) => e !== extension)
}

const validation = computed(() =>
  validatePdmSync({
    enabled: props.enabled,
    watchedFolders: watchedFolders.value,
    madeReleasedStateIds: madeReleasedStateIds.value,
    boughtReleasedStateIds: boughtReleasedStateIds.value,
  }),
)

function confirmRemoveFolder(index: number): void {
  const folder = watchedFolders.value[index]
  if (!folder) return
  confirm.require({
    message: t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.removeConfirm', {
      path: folder.path.trim() || t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.unnamed'),
    }),
    header: t('common.delete'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('common.delete'), severity: 'danger' },
    accept: () => {
      watchedFolders.value = watchedFolders.value.filter((_, i) => i !== index)
    },
  })
}

// ── Folder picker (one dialog shared by every row's "Choose Folder" and by
// "Watch folder") ─────────────────────────────────────────────────────────
const pickerVisible = ref(false)
const pickerRowIndex = ref<number | null>(null)
// 'row' edits an existing row's path in place (its own current folder is
// trivially already watched, so it stays pickable); 'add' appends a new row
// on apply, and must not let the user pick a folder already on the list.
const pickerMode = ref<'row' | 'add'>('row')
const pickerAllowWatched = computed(() => pickerMode.value === 'row')
const watchedPaths = computed(() => watchedFolders.value.map((folder) => folder.path))

function openPicker(index: number): void {
  pickerMode.value = 'row'
  pickerRowIndex.value = index
  pickerVisible.value = true
}

function openAddPicker(): void {
  pickerMode.value = 'add'
  pickerRowIndex.value = null
  pickerVisible.value = true
}

function onPickerApply(path: string, folderId: number): void {
  if (pickerMode.value === 'add') {
    watchedFolders.value = [
      ...watchedFolders.value,
      {
        path,
        kind: 'by_kind',
        recursive: true,
        enabled: true,
        match_by: null,
        filename_pattern: null,
        folder_id: folderId,
      },
    ]
    return
  }
  const row = pickerRowIndex.value !== null ? watchedFolders.value[pickerRowIndex.value] : undefined
  if (row) {
    row.path = path
    row.folder_id = folderId
  }
  pickerRowIndex.value = null
}

// A hand-typed path may not match folder_id any more, so it is cleared here,
// keeping the InputText's v-model free of a side-effecting setter.
function onPathInput(row: PdmWatchedFolder, value: string): void {
  row.path = value
  row.folder_id = null
}

// ── Released/obsolete state pickers, fed by GET …/pdm/workflows ─────────
const loadingWorkflows = ref(false)
const workflowsLoadFailed = ref(false)

async function loadWorkflows(): Promise<void> {
  loadingWorkflows.value = true
  workflowsLoadFailed.value = false
  try {
    await store.loadPdmWorkflows()
  } catch {
    workflowsLoadFailed.value = true
  } finally {
    loadingWorkflows.value = false
  }
}

onMounted(() => {
  if (props.configured) void loadWorkflows()
})

// Settings can still be loading when this section first mounts (configured
// starts false until the fetch resolves), so catch the transition too, not
// just the mounted snapshot.
watch(
  () => props.configured,
  (isConfigured, wasConfigured) => {
    if (isConfigured && !wasConfigured && store.pdmWorkflows.length === 0) void loadWorkflows()
  },
)

const workflowStateOptions = computed(() =>
  store.pdmWorkflows.flatMap((workflow) =>
    workflow.states.map((state) => ({
      label: `${workflow.workflow_name} › ${state.state_name}`,
      value: state.state_id,
    })),
  ),
)

const SYNC_KEY = 'adminSettings.solidworksPdm.pdm.sync'

interface StateSelectRow {
  model: ModelRef<number[]>
  labelKey: string
  hintKey: string
}

/** The workflow-state pickers, one group per item kind and one for exported documents. */
const stateSelectGroups: { titleKey: string; rows: StateSelectRow[] }[] = [
  {
    titleKey: 'adminSettings.itemFields.madeSection',
    rows: [
      { model: madeReleasedStateIds, labelKey: 'releasedStates', hintKey: 'releasedStatesHint' },
      { model: madeObsoleteStateIds, labelKey: 'obsoleteStates', hintKey: 'obsoleteStatesHint' },
      { model: madeReplacedStateIds, labelKey: 'replacedStates', hintKey: 'replacedStatesHint' },
    ],
  },
  {
    titleKey: 'adminSettings.itemFields.boughtSection',
    rows: [
      { model: boughtReleasedStateIds, labelKey: 'releasedStates', hintKey: 'releasedStatesHint' },
      { model: boughtObsoleteStateIds, labelKey: 'obsoleteStates', hintKey: 'obsoleteStatesHint' },
      { model: boughtReplacedStateIds, labelKey: 'replacedStates', hintKey: 'replacedStatesHint' },
    ],
  },
  {
    titleKey: `${SYNC_KEY}.watchedFolders.exportedDocuments`,
    rows: [
      {
        model: documentReleasedStateIds,
        labelKey: 'releasedStates',
        hintKey: 'documentReleasedStatesHint',
      },
    ],
  },
]

// ── Status block ─────────────────────────────────────────────────────────
const lastPollDisplay = computed(() => formatDateTimeOrDash(props.lastPollAt))

function snapshotStateLabel(state: string): string {
  const key = `adminSettings.solidworksPdm.pdm.sync.status.states.${state}`
  const known = ['pending', 'ingested', 'skipped', 'missing', 'conflict', 'error']
  return known.includes(state) ? t(key) : state
}

const nonZeroSnapshotCounts = computed(() =>
  Object.entries(props.snapshotCounts).filter(([, count]) => count > 0),
)

// The "Watch folder" button lives in the tab's ControlsBar but opens this
// section's folder picker in "add" mode, so the picker state stays here.
defineExpose({ openAddPicker })
</script>

<template>
  <div class="pdm-sync-section">
    <p class="section-label">{{ t('adminSettings.solidworksPdm.pdm.sync.title') }}</p>

    <p class="group-label">{{ t('adminSettings.solidworksPdm.pdm.sync.status.title') }}</p>

    <p class="status-line">
      <i class="mdi mdi-clock-outline" aria-hidden="true" />
      {{ t('adminSettings.solidworksPdm.pdm.sync.status.lastRun', { date: lastPollDisplay }) }}
      <span v-if="lastPollSummary" class="status-summary">({{ lastPollSummary }})</span>
    </p>

    <Message v-if="lastPollError" severity="error" :closable="false">{{ lastPollError }}</Message>

    <div v-if="nonZeroSnapshotCounts.length > 0" class="snapshot-tags">
      <Tag
        v-for="[state, count] in nonZeroSnapshotCounts"
        :key="state"
        :severity="SNAPSHOT_STATE_SEVERITY[state] ?? 'secondary'"
        :value="`${snapshotStateLabel(state)}: ${count}`"
      />
    </div>

    <div class="field-row field-row--toggle">
      <label :for="`${uid}-cad-items-read-only`">
        {{ t('adminSettings.solidworksPdm.pdm.sync.cadItemsReadOnly') }}
        <span class="hint">{{ t('adminSettings.solidworksPdm.pdm.sync.cadItemsReadOnlyHint') }}</span>
      </label>
      <ToggleSwitch v-model="cadItemsReadOnly" :input-id="`${uid}-cad-items-read-only`" :disabled="!canWrite" />
    </div>

    <div class="field-row field-row--toggle">
      <label :for="`${uid}-writeback-enabled`">
        {{ t('adminSettings.solidworksPdm.pdm.sync.writebackEnabled') }}
        <span class="hint">{{ t('adminSettings.solidworksPdm.pdm.sync.writebackEnabledHint') }}</span>
      </label>
      <ToggleSwitch v-model="writebackEnabled" :input-id="`${uid}-writeback-enabled`" :disabled="!canWrite" />
    </div>

    <Message v-if="enabled && validation.missingEnabledFolder" severity="error" :closable="false">
      {{ t('adminSettings.solidworksPdm.pdm.sync.validation.missingEnabledFolder') }}
    </Message>
    <Message v-if="enabled && validation.missingReleasedState" severity="error" :closable="false">
      {{ t('adminSettings.solidworksPdm.pdm.sync.validation.missingReleasedState') }}
    </Message>

    <p class="group-label">{{ t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.title') }}</p>

    <DataTable
      :value="watchedFolders"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
    >
      <template #empty>
        {{ t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.empty') }}
      </template>

      <Column style="width: 6rem">
        <template #body="{ index }: { index: number }">
          <div class="actions-cell">
            <Button
              icon="mdi mdi-folder-search-outline"
              size="small"
              text
              severity="secondary"
              :disabled="!canWrite || !configured"
              v-tooltip.top.focus="
                t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.pickFolder')
              "
              :aria-label="t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.pickFolder')"
              @click="openPicker(index)"
            />
            <Button
              icon="mdi mdi-delete-outline"
              size="small"
              severity="danger"
              text
              :disabled="!canWrite"
              v-tooltip.top.focus="t('common.delete')"
              :aria-label="t('common.delete')"
              @click="confirmRemoveFolder(index)"
            />
          </div>
        </template>
      </Column>
      <Column
        :header="t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.columns.kind')"
        style="width: 11rem"
      >
        <template #body="{ data }: { data: PdmWatchedFolder }">
          <Select
            v-model="data.kind"
            :aria-label="t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.columns.kind')"
            :options="kindOptions"
            option-label="label"
            option-value="value"
            :disabled="!canWrite"
            fluid
          />
        </template>
      </Column>
      <Column
        :header="t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.columns.matchBy')"
        style="width: 10rem"
      >
        <template #body="{ data }: { data: PdmWatchedFolder }">
          <Select
            v-if="data.kind === 'documents'"
            v-model="data.match_by"
            :aria-label="t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.columns.matchBy')"
            :options="matchByOptions"
            option-label="label"
            option-value="value"
            :disabled="!canWrite"
            fluid
          />
          <span v-else class="hint">{{ getEmptyPlaceholder() }}</span>
        </template>
      </Column>
      <Column
        :header="t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.columns.filenamePattern')"
        style="min-width: 14rem"
      >
        <template #body="{ data }: { data: PdmWatchedFolder }">
          <InputText
            v-if="data.kind === 'documents' && data.match_by === 'filename'"
            :model-value="data.filename_pattern ?? ''"
            size="small"
            fluid
            :disabled="!canWrite"
            :placeholder="FILENAME_PATTERN_EXAMPLE"
            @update:model-value="(value?: string) => (data.filename_pattern = value ?? '')"
          />
          <span v-else class="hint">{{ getEmptyPlaceholder() }}</span>
        </template>
      </Column>
      <Column
        :header="t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.columns.recursive')"
        style="width: 6rem"
        class="toggle-column"
      >
        <template #body="{ data }: { data: PdmWatchedFolder }">
          <ToggleSwitch v-model="data.recursive" :disabled="!canWrite" />
        </template>
      </Column>
      <Column
        :header="t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.columns.enabled')"
        style="width: 6rem"
        class="toggle-column"
      >
        <template #body="{ data }: { data: PdmWatchedFolder }">
          <ToggleSwitch v-model="data.enabled" :disabled="!canWrite" />
        </template>
      </Column>
      <Column
        :header="t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.columns.path')"
        style="min-width: 16rem"
      >
        <template #body="{ data }: { data: PdmWatchedFolder }">
          <InputText
            :model-value="data.path"
            size="small"
            fluid
            :disabled="!canWrite"
            :placeholder="t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.pathPlaceholder')"
            v-tooltip.top="
              data.folder_id !== null
                ? t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.folderIdTooltip', {
                    id: data.folder_id,
                  })
                : undefined
            "
            @update:model-value="(value?: string) => onPathInput(data, value ?? '')"
          />
        </template>
      </Column>
    </DataTable>

    <Message v-if="validation.emptyPath" severity="error" :closable="false">
      {{ t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.validation.emptyPath') }}
    </Message>
    <Message v-if="validation.duplicatePath" severity="error" :closable="false">
      {{ t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.validation.duplicatePath') }}
    </Message>
    <Message v-if="validation.missingFilenamePattern" severity="error" :closable="false">
      {{ t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.validation.missingFilenamePattern') }}
    </Message>
    <p class="hint">{{ t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.byKindHint') }}</p>
    <p class="hint">{{ filenamePatternHint }}</p>

    <p class="group-label">{{ t('adminSettings.solidworksPdm.pdm.sync.fileTypesSection') }}</p>

    <div class="field-row">
      <label :for="`${uid}-made-item-extensions`">
        {{ t('adminSettings.solidworksPdm.pdm.sync.madeItemExtensions.label') }}
        <span class="hint">{{
          t('adminSettings.solidworksPdm.pdm.sync.madeItemExtensions.hint')
        }}</span>
      </label>
      <div class="extension-list">
        <Tag
          v-for="extension in madeItemExtensions"
          :key="extension"
          :value="extension"
          severity="secondary"
          class="extension-tag"
        >
          <template #default>
            {{ extension }}
            <span v-tooltip.top="writeBlocked || undefined">
              <Button
                icon="mdi mdi-close"
                text
                rounded
                size="small"
                class="extension-remove"
                :disabled="!canWrite"
                :aria-label="
                  t('adminSettings.solidworksPdm.pdm.sync.madeItemExtensions.remove', { extension })
                "
                @click="removeExtension('made', extension)"
              />
            </span>
          </template>
        </Tag>
        <div class="extension-add-row" v-tooltip.top="writeBlocked || undefined">
          <InputText
            v-model="madeExtensionInput"
            :id="`${uid}-made-item-extensions`"
            size="small"
            :disabled="!canWrite"
            :placeholder="t('adminSettings.solidworksPdm.pdm.sync.madeItemExtensions.placeholder')"
            @keydown.enter.prevent="addExtension('made')"
          />
          <Button
            icon="mdi mdi-plus"
            size="small"
            severity="secondary"
            :disabled="!canWrite"
            :aria-label="t('adminSettings.solidworksPdm.pdm.sync.madeItemExtensions.add')"
            @click="addExtension('made')"
          />
        </div>
      </div>
    </div>

    <div class="field-row">
      <label :for="`${uid}-bought-item-extensions`">
        {{ t('adminSettings.solidworksPdm.pdm.sync.boughtItemExtensions.label') }}
        <span class="hint">{{
          t('adminSettings.solidworksPdm.pdm.sync.boughtItemExtensions.hint')
        }}</span>
      </label>
      <div class="extension-list">
        <Tag
          v-for="extension in boughtItemExtensions"
          :key="extension"
          :value="extension"
          severity="secondary"
          class="extension-tag"
        >
          <template #default>
            {{ extension }}
            <span v-tooltip.top="writeBlocked || undefined">
              <Button
                icon="mdi mdi-close"
                text
                rounded
                size="small"
                class="extension-remove"
                :disabled="!canWrite"
                :aria-label="
                  t('adminSettings.solidworksPdm.pdm.sync.boughtItemExtensions.remove', { extension })
                "
                @click="removeExtension('bought', extension)"
              />
            </span>
          </template>
        </Tag>
        <div class="extension-add-row" v-tooltip.top="writeBlocked || undefined">
          <InputText
            v-model="boughtExtensionInput"
            :id="`${uid}-bought-item-extensions`"
            size="small"
            :disabled="!canWrite"
            :placeholder="
              t('adminSettings.solidworksPdm.pdm.sync.boughtItemExtensions.placeholder')
            "
            @keydown.enter.prevent="addExtension('bought')"
          />
          <Button
            icon="mdi mdi-plus"
            size="small"
            severity="secondary"
            :disabled="!canWrite"
            :aria-label="t('adminSettings.solidworksPdm.pdm.sync.boughtItemExtensions.add')"
            @click="addExtension('bought')"
          />
        </div>
      </div>
    </div>

    <p class="group-label">
      {{ t('adminSettings.solidworksPdm.pdm.sync.documentCategoriesSection') }}
    </p>
    <p class="hint">{{ t('adminSettings.solidworksPdm.pdm.sync.documentCategories.hint') }}</p>

    <PdmDocumentCategoriesTable
      v-model:document-categories="documentCategories"
      v-model:document-excluded-kinds="documentExcludedKinds"
      :can-write="canWrite"
    />

    <div class="field-row field-row--toggle">
      <label :for="`${uid}-thumbnails-enabled`">
        {{ t('adminSettings.solidworksPdm.pdm.sync.thumbnailsEnabled') }}
        <span class="hint">{{ t('adminSettings.solidworksPdm.pdm.sync.thumbnailsEnabledHint') }}</span>
      </label>
      <ToggleSwitch v-model="thumbnailsEnabled" :input-id="`${uid}-thumbnails-enabled`" :disabled="!canWrite" />
    </div>

    <div class="field-row">
      <label :for="`${uid}-poll-interval-minutes`">{{ t('adminSettings.solidworksPdm.pdm.sync.pollIntervalMinutes') }}</label>
      <InputNumber
        v-model="pollIntervalMinutes"
        :input-id="`${uid}-poll-interval-minutes`"
        class="sync-fixed-width"
        :min="1"
        :max="1440"
        :use-grouping="false"
        :disabled="!canWrite"
      />
    </div>

    <div class="field-row">
      <label :for="`${uid}-cold-folder-max-multiplier`">
        {{ t('adminSettings.solidworksPdm.pdm.sync.coldFolderMaxMultiplier') }}
        <span class="hint">{{
          t('adminSettings.solidworksPdm.pdm.sync.coldFolderMaxMultiplierHint')
        }}</span>
      </label>
      <InputNumber
        v-model="coldFolderMaxMultiplier"
        :input-id="`${uid}-cold-folder-max-multiplier`"
        class="sync-fixed-width"
        :min="1"
        :max="64"
        :use-grouping="false"
        :disabled="!canWrite"
      />
    </div>

    <div class="field-row">
      <label :for="`${uid}-ingest-concurrency`">
        {{ t('adminSettings.solidworksPdm.pdm.sync.ingestConcurrency') }}
        <span class="hint">{{ t('adminSettings.solidworksPdm.pdm.sync.ingestConcurrencyHint') }}</span>
      </label>
      <InputNumber
        v-model="ingestConcurrency"
        :input-id="`${uid}-ingest-concurrency`"
        class="sync-fixed-width"
        :min="1"
        :max="16"
        :use-grouping="false"
        :disabled="!canWrite"
      />
    </div>

    <div class="field-row">
      <label :for="`${uid}-stuck-after-days`">
        {{ t('adminSettings.solidworksPdm.pdm.sync.stuckAfterDays') }}
        <span class="hint">{{ t('adminSettings.solidworksPdm.pdm.sync.stuckAfterDaysHint') }}</span>
      </label>
      <InputNumber
        v-model="stuckAfterDays"
        :input-id="`${uid}-stuck-after-days`"
        class="sync-fixed-width"
        :min="1"
        :max="365"
        :use-grouping="false"
        :disabled="!canWrite"
      />
    </div>

    <p class="group-label">{{ t('adminSettings.solidworksPdm.pdm.sync.statesSection') }}</p>
    <p class="hint">{{ t('adminSettings.solidworksPdm.pdm.sync.statesSectionHint') }}</p>

    <template v-for="group in stateSelectGroups" :key="group.titleKey">
      <p class="subsection-label">{{ t(group.titleKey) }}</p>

      <div v-for="row in group.rows" :key="row.labelKey" class="field-row">
        <label :id="`${uid}-value-label-${group.titleKey}-${row.labelKey}`" :for="`${uid}-value-${group.titleKey}-${row.labelKey}`">
          {{ t(`${SYNC_KEY}.${row.labelKey}`) }}
          <span class="hint">{{ t(`${SYNC_KEY}.${row.hintKey}`) }}</span>
        </label>
        <MultiSelect
          v-model="row.model.value"
          :input-id="`${uid}-value-${group.titleKey}-${row.labelKey}`"
          :aria-labelledby="`${uid}-value-label-${group.titleKey}-${row.labelKey}`"
          class="sync-fixed-width"
          :options="workflowStateOptions"
          option-label="label"
          option-value="value"
          display="chip"
          filter
          fluid
          :loading="loadingWorkflows"
          :disabled="!canWrite"
          :placeholder="t(`${SYNC_KEY}.statesPlaceholder`)"
        />
      </div>
    </template>

    <Message v-if="workflowsLoadFailed" severity="warn" :closable="false">
      <div class="workflows-error">
        <span>{{ t('adminSettings.solidworksPdm.pdm.sync.workflowsLoadFailed') }}</span>
        <Button :label="t('common.reload')" size="small" text @click="loadWorkflows" />
      </div>
    </Message>

    <PdmFolderPickerDialog
      v-model:visible="pickerVisible"
      :watched-paths="watchedPaths"
      :allow-watched="pickerAllowWatched"
      @apply="onPickerApply"
    />
  </div>
</template>

<style scoped lang="scss">
.pdm-sync-section {
  display: contents;
}

.group-label {
  margin: var(--space-1) 0 0;
  font-size: var(--font-size-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

// A lighter-weight heading than .group-label, introduces the made/bought
// split within the workflow-states group rather than a whole new section
// (mirrors AdminSettingsTabNumbering's own .subsection-label).
.subsection-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--p-text-color);
  margin-top: var(--space-1);
}

.actions-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
}

// Mirrors AdminSettingsTabMail's own alert-recipients chip list.
.extension-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  align-items: center;
}

.extension-tag {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
}

.extension-remove {
  width: 1.5rem;
  height: 1.5rem;
  opacity: 0.7;

  &:hover {
    opacity: 1;
  }
}

.extension-add-row {
  display: flex;
  gap: var(--space-2);
  align-items: center;
}

.toggle-column {
  text-align: center;
}

// Shared by the workflow state MultiSelects and the tuning InputNumbers so
// they all line up. InputNumber already gets this via the global .field-row
// rule, but MultiSelect isn't in that selector list and would stretch to the
// full grid column with `fluid` alone.
.sync-fixed-width {
  width: 100%;
  max-width: 24rem;
}

.workflows-error {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.status-line {
  margin: 0;
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.status-summary {
  color: var(--p-text-color);
}

.snapshot-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
</style>
