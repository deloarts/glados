<script setup lang="ts">
// The admin "sync log" dialog: the newest-first pdm_sync_run history on top
// and the selected run's per-file entries below. pdm_sync_run has no live
// resource, so it reloads only on demand. The caller mounts it with v-if, so
// the runs load on open. The entries fetch is a no-op while no run is
// selected, so that table shows its "select a run" empty state.
import { computed, inject, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, routerKey } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { useServerTable } from '@/core/composables/useServerTable'
import { formatISODateTime, formatISOTime } from '@/core/utils/dates'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { TABLE_DEFAULT_ROWS } from '@/core/constants/table'
import { usePdmSyncLogStore } from '../../stores/pdmSyncLogStore'
import { kindLabel } from '../../utils/pdmKind'
import { pdmEntryActionSeverity, pdmEntryItemRoute } from '../../utils/pdmSyncEntries'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import EmptyState from '@/shared/components/EmptyState.vue'
import { formatElapsed } from '@/shared/utils/formatDuration'
import DemandDateRangeFilter from '@/shared/components/demands/DemandDateRangeFilter.vue'

import type { TagSeverity } from '@/core/types/tagSeverity'
import type { DataTableFilterMeta, DataTableRowSelectEvent } from 'openvue/datatable'
import type {
  PdmFileKind,
  PdmSyncEntryAction,
  PdmSyncRun,
  PdmSyncRunEntry,
  PdmSyncTrigger,
} from '../../types/adminSettingsTypes'

const { t } = useI18n()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
// Same defensive inject as PdmFilesDialog.vue: a spec that mounts this
// dialog standalone does not install a router by default.
const router = inject(routerKey, null)

const store = usePdmSyncLogStore()
const { triggers, startedFrom, startedTo, runError, action, kind, search } = storeToRefs(store)

// Both tables filter on the server through the store's filter state, which
// the row filter cells bind directly. OpenVue still reads each cell's model
// from a filters object, so the tables get this empty one.
const NO_FILTER_META: DataTableFilterMeta = {}

const visible = defineModel<boolean>('visible', { required: true })

// ── Runs table ───────────────────────────────────────────────────────────

const {
  first: runsFirst,
  resetAndFetch: resetAndFetchRuns,
  resetAndFetchDebounced: resetAndFetchRunsDebounced,
  onPage: onRunsPage,
} = useServerTable({
  fetchParams: (page) => ({ skip: page.first, limit: page.rows }),
  fetch: (page) => store.refresh(page),
})

const startedRange = useDateRangeFilter(startedFrom, startedTo)

watch([triggers, startedFrom, startedTo], resetAndFetchRuns)
watch(runError, resetAndFetchRunsDebounced)

const TRIGGERS: PdmSyncTrigger[] = ['scheduled', 'manual', 'initial', 'file_trigger', 'retry', 'reconciliation']

const triggerOptions = computed(() =>
  TRIGGERS.map((value) => ({ value, label: t(`adminSettings.pdmSyncLog.runs.trigger.${value}`) })),
)

function triggerSeverity(trigger: PdmSyncTrigger): TagSeverity | 'primary' {
  if (trigger === 'scheduled') return 'info'
  if (trigger === 'manual') return 'primary'
  if (trigger === 'file_trigger') return 'success'
  if (trigger === 'reconciliation' || trigger === 'initial') return 'secondary'
  return 'warn' // retry
}

function formatDuration(startedAt: string, finishedAt: string | null): string {
  if (finishedAt === null) return t('adminSettings.pdmSyncLog.runs.running')
  return formatElapsed(startedAt, finishedAt)
}

const COUNT_TAG_DEFS: {
  field:
    | 'files_seen'
    | 'changed'
    | 'ingested'
    | 'skipped'
    | 'conflicts'
    | 'errors'
    | 'missing'
    | 'folders_walked'
    | 'folders_skipped_cold'
  labelKey: string
  severity: TagSeverity
}[] = [
  { field: 'files_seen', labelKey: 'seen', severity: 'secondary' },
  { field: 'changed', labelKey: 'changed', severity: 'info' },
  { field: 'ingested', labelKey: 'ingested', severity: 'success' },
  { field: 'skipped', labelKey: 'skipped', severity: 'secondary' },
  { field: 'conflicts', labelKey: 'conflicts', severity: 'danger' },
  { field: 'errors', labelKey: 'errors', severity: 'danger' },
  { field: 'missing', labelKey: 'missing', severity: 'warn' },
  { field: 'folders_walked', labelKey: 'foldersWalked', severity: 'secondary' },
  { field: 'folders_skipped_cold', labelKey: 'foldersSkippedCold', severity: 'secondary' },
]

function runCountTags(row: PdmSyncRun): { label: string; severity: TagSeverity }[] {
  return COUNT_TAG_DEFS.filter((def) => row[def.field] > 0).map((def) => ({
    severity: def.severity,
    label: `${t(`adminSettings.pdmSyncLog.runs.counts.${def.labelKey}`)}: ${row[def.field]}`,
  }))
}

function runRowClass(row: PdmSyncRun): string | undefined {
  return store.selectedRunId === row.id ? 'sync-run-row--selected' : undefined
}

// ── Entries table ────────────────────────────────────────────────────────

const {
  first: entriesFirst,
  resetAndFetch: resetAndFetchEntries,
  resetAndFetchDebounced: resetAndFetchEntriesDebounced,
  onPage: onEntriesPage,
} = useServerTable({
  fetchParams: (page) => ({ skip: page.first, limit: page.rows }),
  fetch: (page) =>
    store.selectedRunId !== null ? store.loadEntries(store.selectedRunId, page) : undefined,
})

const actionOptions = computed<{ label: string; value: PdmSyncEntryAction | null }[]>(() => [
  { label: t('adminSettings.pdmSyncLog.entries.action.all'), value: null },
  { label: t('adminSettings.pdmSyncLog.entries.action.created'), value: 'created' },
  { label: t('adminSettings.pdmSyncLog.entries.action.revised'), value: 'revised' },
  { label: t('adminSettings.pdmSyncLog.entries.action.updated'), value: 'updated' },
  { label: t('adminSettings.pdmSyncLog.entries.action.status'), value: 'status' },
  { label: t('adminSettings.pdmSyncLog.entries.action.claimed'), value: 'claimed' },
  { label: t('adminSettings.pdmSyncLog.entries.action.skipped'), value: 'skipped' },
  { label: t('adminSettings.pdmSyncLog.entries.action.conflict'), value: 'conflict' },
  { label: t('adminSettings.pdmSyncLog.entries.action.missing'), value: 'missing' },
  { label: t('adminSettings.pdmSyncLog.entries.action.error'), value: 'error' },
  { label: t('adminSettings.pdmSyncLog.entries.action.writeback'), value: 'writeback' },
  { label: t('adminSettings.pdmSyncLog.entries.action.writeback_error'), value: 'writeback_error' },
  { label: t('adminSettings.pdmSyncLog.entries.action.document'), value: 'document' },
  { label: t('adminSettings.pdmSyncLog.entries.action.document_error'), value: 'document_error' },
  { label: t('adminSettings.pdmSyncLog.entries.action.thumbnail'), value: 'thumbnail' },
  { label: t('adminSettings.pdmSyncLog.entries.action.thumbnail_error'), value: 'thumbnail_error' },
])

const kindOptions = computed<{ label: string; value: PdmFileKind | null }[]>(() => [
  { label: t('adminSettings.pdmSyncLog.entries.action.all'), value: null },
  ...(['made', 'bought', 'document'] as const).map((value) => ({ label: kindLabel(value), value })),
])

watch([action, kind], resetAndFetchEntries)
watch(search, resetAndFetchEntriesDebounced)

function onRunSelect(event: DataTableRowSelectEvent): void {
  store.selectedRunId = (event.data as PdmSyncRun).id
  resetAndFetchEntries()
}

const actionSeverity = pdmEntryActionSeverity
const entryItemRoute = pdmEntryItemRoute

function entryItemLabel(row: PdmSyncRunEntry): string | null {
  if (row.item_id === null) return null
  return t('adminSettings.pdmSyncLog.entries.itemLink', { id: row.item_id })
}

// ── Message detail dialog ───────────────────────────────────────────────

const messageDialogVisible = ref(false)
const messageDialogText = ref('')

function showMessage(row: PdmSyncRunEntry): void {
  if (!row.message) return
  messageDialogText.value = row.message
  messageDialogVisible.value = true
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    maximizable
    :header="t('adminSettings.pdmSyncLog.dialogTitle')"
    :style="{ width: 'var(--dialog-width-full)', height: '80vh' }"
    content-class="pdm-sync-log-dialog-content"
  >
    <div class="runs-section">
      <DataTable
        class="runs-table fixed-layout-table ellipsis-cells"
        :value="store.runs"
        data-key="id"
        lazy
        :total-records="store.total"
        :rows="TABLE_DEFAULT_ROWS"
        :first="runsFirst"
        paginator
        scrollable
        scroll-height="flex"
        size="small"
        :loading="store.loading"
        :filters="NO_FILTER_META"
        filter-display="row"
        :show-gridlines="isTableGridlinesEnabled"
        :striped-rows="isTableStripedEnabled"
        selection-mode="single"
        :row-class="runRowClass"
        @page="onRunsPage"
        @row-select="onRunSelect"
      >
        <template #empty>
          <EmptyState :message="t('adminSettings.pdmSyncLog.runs.empty')" />
        </template>

        <Column
          column-key="started_at"
          :header="t('adminSettings.pdmSyncLog.runs.columns.startedAt')"
          :show-filter-menu="false"
          style="width: 11rem"
        >
          <template #body="{ data }: { data: PdmSyncRun }">{{ formatISODateTime(data.started_at) }}</template>
          <template #filter>
            <DemandDateRangeFilter
              v-model="startedRange"
              :placeholder="t('adminSettings.pdmSyncLog.filters.dateRange')"
              @clear-click="startedRange = null"
            />
          </template>
        </Column>

        <Column
          column-key="trigger"
          :header="t('adminSettings.pdmSyncLog.runs.columns.trigger')"
          :show-filter-menu="false"
          style="width: 9rem"
        >
          <template #filter>
            <MultiSelect
              v-model="triggers"
              :options="triggerOptions"
              option-label="label"
              option-value="value"
              :placeholder="t('adminSettings.pdmSyncLog.filters.anyTrigger')"
              :aria-label="t('common.filterBy', { column: t('adminSettings.pdmSyncLog.runs.columns.trigger') })"
              :max-selected-labels="1"
              size="small"
              fluid
            />
          </template>
          <template #body="{ data }: { data: PdmSyncRun }">
            <Tag
              :severity="triggerSeverity(data.trigger)"
              :value="t(`adminSettings.pdmSyncLog.runs.trigger.${data.trigger}`)"
            />
          </template>
        </Column>

        <Column :header="t('adminSettings.pdmSyncLog.runs.columns.duration')" style="width: 7rem">
          <template #body="{ data }: { data: PdmSyncRun }">
            {{ formatDuration(data.started_at, data.finished_at) }}
          </template>
        </Column>

        <Column :header="t('adminSettings.pdmSyncLog.runs.columns.result')" style="width: 22rem">
          <template #body="{ data }: { data: PdmSyncRun }">
            <div class="count-tags">
              <Tag
                v-for="tag in runCountTags(data)"
                :key="tag.label"
                :severity="tag.severity"
                :value="tag.label"
              />
            </div>
          </template>
        </Column>

        <!-- No fixed width: the one column that takes up the remaining
             table width, same convention as PdmFilesDialog's own "error"
             column. -->
        <Column
          column-key="error"
          :header="t('adminSettings.pdmSyncLog.runs.columns.error')"
          :show-filter-menu="false"
        >
          <template #filter>
            <InputText
              v-model="runError"
              :aria-label="t('common.filterBy', { column: t('adminSettings.pdmSyncLog.runs.columns.error') })"
              size="small"
              fluid
            />
          </template>
          <template #body="{ data }: { data: PdmSyncRun }">
            <span v-if="data.error" class="truncate-cell" v-tooltip.top="data.error">{{
              data.error
            }}</span>
            <span v-else>{{ getEmptyPlaceholder() }}</span>
          </template>
        </Column>
      </DataTable>
    </div>

    <Divider />

    <div class="entries-section">
      <div class="entries-controls">
        <Button
          :label="t('common.reload')"
          icon="mdi mdi-refresh"
          text
          severity="contrast"
          :loading="store.entriesLoading"
          :disabled="store.selectedRunId === null"
          @click="resetAndFetchEntries"
        />
      </div>

      <DataTable
        class="entries-table fixed-layout-table ellipsis-cells"
        :value="store.entries"
        data-key="id"
        lazy
        :total-records="store.entriesTotal"
        :rows="TABLE_DEFAULT_ROWS"
        :first="entriesFirst"
        paginator
        scrollable
        scroll-height="flex"
        size="small"
        :loading="store.entriesLoading"
        :filters="NO_FILTER_META"
        filter-display="row"
        :show-gridlines="isTableGridlinesEnabled"
        :striped-rows="isTableStripedEnabled"
        @page="onEntriesPage"
      >
        <template #empty>
          <EmptyState
            :message="
              store.selectedRunId === null
                ? t('adminSettings.pdmSyncLog.entries.noRunSelected')
                : t('adminSettings.pdmSyncLog.entries.empty')
            "
          />
        </template>

        <Column
          column-key="action"
          :header="t('adminSettings.pdmSyncLog.entries.columns.action')"
          :show-filter-menu="false"
          style="width: 11rem"
        >
          <template #filter>
            <Select
              v-model="action"
              :options="actionOptions"
              option-label="label"
              option-value="value"
              :aria-label="t('common.filterBy', { column: t('adminSettings.pdmSyncLog.entries.columns.action') })"
              size="small"
              fluid
            />
          </template>
          <template #body="{ data }: { data: PdmSyncRunEntry }">
            <Tag
              :severity="actionSeverity(data.action)"
              :value="t(`adminSettings.pdmSyncLog.entries.action.${data.action}`)"
            />
          </template>
        </Column>

        <Column
          column-key="file"
          :header="t('adminSettings.pdmSyncLog.entries.columns.file')"
          :show-filter-menu="false"
          style="width: 14rem"
        >
          <template #filter>
            <InputText
              v-model="search"
              :aria-label="t('common.filterBy', { column: t('adminSettings.pdmSyncLog.entries.columns.file') })"
              size="small"
              fluid
            />
          </template>
          <template #body="{ data }: { data: PdmSyncRunEntry }">
            <div class="file-cell">
              <span class="file-name">{{ data.name }}</span>
              <span class="file-path" v-tooltip.top="data.path">{{ data.path }}</span>
            </div>
          </template>
        </Column>

        <Column
          column-key="kind"
          :header="t('adminSettings.pdmSyncLog.entries.columns.kind')"
          :show-filter-menu="false"
          style="width: 11rem"
        >
          <template #filter>
            <Select
              v-model="kind"
              :options="kindOptions"
              option-label="label"
              option-value="value"
              :aria-label="t('common.filterBy', { column: t('adminSettings.pdmSyncLog.entries.columns.kind') })"
              size="small"
              fluid
            />
          </template>
          <template #body="{ data }: { data: PdmSyncRunEntry }">{{ kindLabel(data.kind) }}</template>
        </Column>

        <Column :header="t('adminSettings.pdmSyncLog.entries.columns.item')" style="width: 9rem">
          <template #body="{ data }: { data: PdmSyncRunEntry }">
            <RouterLink v-if="router && entryItemRoute(data)" :to="entryItemRoute(data)!" class="item-link">
              {{ entryItemLabel(data) }}
            </RouterLink>
            <span v-else-if="entryItemLabel(data)">{{ entryItemLabel(data) }}</span>
            <span v-else>{{ getEmptyPlaceholder() }}</span>
          </template>
        </Column>

        <!-- No fixed width: the wide, free-flowing column, same convention
             as the runs table's own "error" column. -->
        <Column :header="t('adminSettings.pdmSyncLog.entries.columns.message')">
          <template #body="{ data }: { data: PdmSyncRunEntry }">
            <span
              v-if="data.message"
              class="truncate-cell message-cell"
              role="button"
              tabindex="0"
              v-tooltip.top="data.message"
              @click="showMessage(data)"
              @keydown.enter="showMessage(data)"
              @keydown.space.prevent="showMessage(data)"
              >{{ data.message }}</span
            >
            <span v-else>{{ getEmptyPlaceholder() }}</span>
          </template>
        </Column>

        <Column :header="t('adminSettings.pdmSyncLog.entries.columns.time')" style="width: 6rem">
          <template #body="{ data }: { data: PdmSyncRunEntry }">{{ formatISOTime(data.created_at) }}</template>
        </Column>
      </DataTable>
    </div>
  </Dialog>

  <Dialog
    v-model:visible="messageDialogVisible"
    modal
    :header="t('adminSettings.pdmSyncLog.messageDialogTitle')"
    style="width: var(--dialog-width-md)"
  >
    <p class="message-dialog-text">{{ messageDialogText }}</p>
  </Dialog>
</template>

<style scoped lang="scss">
// :global, not :deep: the dialog is teleported out of this component, so
// .p-dialog-content never carries the scoped-style attribute and a :deep
// selector would not match it. Turning off its default overflow-y:auto is
// what stops the dialog body scrolling; the two tables scroll instead.
:global(.pdm-sync-log-dialog-content) {
  display: flex;
  flex-direction: column;
  min-height: 0;
  gap: var(--space-2);
  overflow: hidden;
}

// The entries table gets half the dialog; the runs history takes what is
// left once the Divider and gaps are paid for.
.runs-section {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.entries-section {
  flex: 0 0 50%;
  display: flex;
  flex-direction: column;
  min-height: 0;
  gap: var(--space-2);
}

.runs-table,
.entries-table {
  flex: 1 1 auto;
  min-height: 0;

  // The sum of the declared column widths plus room for the one column that
  // declares none.
  --table-min-width: 59rem;
}

// The entries table declares its own column widths, wider than the runs table.
.entries-table {
  --table-min-width: 61rem;
}

.entries-controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
  flex: 0 0 auto;
}

.count-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.file-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  min-width: 0;
}

.file-name {
  font-size: var(--font-size-sm);
}

.file-path {
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-link {
  color: var(--p-primary-color);
}

.truncate-cell {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.message-cell {
  cursor: pointer;
}

.message-dialog-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

// rowClass-driven highlight for the runs table's currently selected row;
// selectionMode="single" is deliberately unpaired with v-model:selection
// (binding both breaks keyboard row access), so this is the only visual
// cue a row is selected.
:deep(tr.sync-run-row--selected) {
  background: var(--p-highlight-bg) !important;
}
</style>
