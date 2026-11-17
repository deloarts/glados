<script setup lang="ts">
// The admin "reconciliation" dialog: an on-demand drift report between the
// catalogue and the PDM vault. A quick run reads only the database, a deep
// run also reads every linked file's write-back datacard. Every category tile
// renders, even at zero, so a clean vault says so; a click on a tile sets the
// category filter. The store owns the summary poll while a run is open, and
// this dialog stops it on unmount.
import { computed, inject, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { routerKey } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useLayoutStore } from '@/core/stores/layoutStore'
import { useServerTable } from '@/core/composables/useServerTable'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { extractApiError } from '@/core/utils/errors'
import { formatISODateTime } from '@/core/utils/dates'
import { TABLE_DEFAULT_ROWS } from '@/core/constants/table'
import { useMadeItemLabel } from '@/shared/utils/madeItemLabel'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { getPdmReconciliationFindings } from '../../api/getPdmReconciliationFindings'
import { usePdmReconciliationStore } from '../../stores/pdmReconciliationStore'
import { kindLabel } from '../../utils/pdmKind'
import {
  buildPdmReconciliationExportRows,
  writePdmReconciliationExportFile,
} from '../../utils/pdmReconciliationExport'
import { PDM_RECONCILIATION_CATEGORIES } from '../../types/adminSettingsTypes'
import EmptyState from '@/shared/components/EmptyState.vue'
import { formatElapsed } from '@/shared/utils/formatDuration'

import type { TagSeverity } from '@/core/types/tagSeverity'
import type { DataTableFilterMeta } from 'openvue/datatable'
import type {
  PdmFileKind,
  PdmReconciliationCategory,
  PdmReconciliationFinding,
  PdmReconciliationSeverity,
} from '../../types/adminSettingsTypes'

// Presentation-only mapping for the count tiles, mirroring the backend
// PdmReconciliationSeverity docstring's own grouping (stuck/lag/mismatch
// resolve themselves on the next poll, so "warning"; orphaned rows and
// duplicates need a manual look, so "error"; an unclaimed match is merely
// informative). A given finding's own `severity` field, not this map,
// still drives the Category Tag colour in the findings table below, since
// two findings of the same category are never guaranteed the same
// severity.
const CATEGORY_TILE_SEVERITY: Record<PdmReconciliationCategory, TagSeverity> = {
  orphaned_cad_row: 'danger',
  stuck_file: 'warn',
  revision_lag: 'warn',
  duplicate_part_number: 'danger',
  kind_mismatch: 'warn',
  document_missing: 'danger',
  document_unmatched: 'warn',
  unclaimed_match: 'info',
  writeback_drift: 'warn',
  status_mismatch: 'warn',
  replaced_without_successor: 'warn',
  successor_without_replaced: 'warn',
  part_number_drift: 'warn',
}

const EXPORT_MAX_ROWS = 5000
const EXPORT_PAGE_SIZE = 500

const { t } = useI18n()
const appToast = useAppToast()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const { hasPermission } = usePermissions()
// Same defensive inject as PdmFilesDialog.vue: a spec that mounts this
// dialog standalone does not install a router by default.
const router = inject(routerKey, null)
const { format: madeItemLabel } = useMadeItemLabel()

const canWrite = computed(() => hasPermission(Permission.WRITE_SETTINGS))
// Without write:settings Recheck stays visible but disabled, naming it.
const { missing } = useMissingPermission()
const writeBlocked = computed(() => missing(Permission.WRITE_SETTINGS))

const store = usePdmReconciliationStore()

// The findings table filters on the server through the store's filter
// state, which the row filter cells bind directly. OpenVue still reads each
// cell's model from a filters object, so the table gets this empty one.
const NO_FILTER_META: DataTableFilterMeta = {}

const visible = defineModel<boolean>('visible', { required: true })

const emit = defineEmits<{ 'open-files': [] }>()

onMounted(() => {
  void store.loadSummary()
})

onUnmounted(() => {
  store.stopPolling()
})

// ── Header: request a run ─────────────────────────────────────────────

const runOpen = computed(() => !!store.run && store.run.finished_at === null)
const canRequestRun = computed(() => canWrite.value && !runOpen.value)

async function onRequestRun(deep: boolean): Promise<void> {
  try {
    await store.requestRun(deep)
    appToast.success(t('adminSettings.pdmReconciliation.requested'))
  } catch (err: unknown) {
    appToast.error(
      t('adminSettings.pdmReconciliation.requestFailed'),
      extractApiError(err) ?? t('adminSettings.errors.unknown'),
    )
  }
}

function categoryLabel(category: string): string {
  return t(`adminSettings.pdmReconciliation.categories.${category}.label`)
}

function categoryDescription(category: string): string {
  return t(`adminSettings.pdmReconciliation.categories.${category}.description`)
}

function severityLabel(severity: string): string {
  return t(`adminSettings.pdmReconciliation.severity.${severity}`)
}

function severityTagSeverity(severity: PdmReconciliationSeverity): TagSeverity {
  if (severity === 'error') return 'danger'
  if (severity === 'warning') return 'warn'
  return 'info'
}

function triggerLabel(trigger: string): string {
  return t(`adminSettings.pdmSyncLog.runs.trigger.${trigger}`)
}

function formatRunDuration(startedAt: string, finishedAt: string | null): string {
  if (finishedAt === null) return t('adminSettings.pdmReconciliation.running')
  return formatElapsed(startedAt, finishedAt)
}

const lastRunLine = computed<string | null>(() => {
  const run = store.run
  if (!run) return null
  return t('adminSettings.pdmReconciliation.lastRun', {
    date: formatISODateTime(run.started_at),
    duration: formatRunDuration(run.started_at, run.finished_at),
    trigger: triggerLabel(run.trigger),
  })
})

// ── Category count tiles ─────────────────────────────────────────────

const categoryTiles = computed(() =>
  PDM_RECONCILIATION_CATEGORIES.map((category) => ({
    category,
    label: categoryLabel(category),
    description: categoryDescription(category),
    count: store.counts[category] ?? 0,
    severity: CATEGORY_TILE_SEVERITY[category],
  })),
)

function onTileClick(category: PdmReconciliationCategory): void {
  store.category = category
  onFilterChange()
}

// ── Findings table ───────────────────────────────────────────────────

const { first, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: (page) => ({ skip: page.first, limit: page.rows }),
  fetch: (page) => store.loadFindings(page),
})

watch([() => store.search, () => store.partNumber, () => store.message], resetAndFetchDebounced)

function onFilterChange(): void {
  resetAndFetch()
}

const categoryOptions = computed<{ label: string; value: PdmReconciliationCategory | null }[]>(() => [
  { label: t('adminSettings.pdmReconciliation.filters.allCategories'), value: null },
  ...PDM_RECONCILIATION_CATEGORIES.map((category) => ({ label: categoryLabel(category), value: category })),
])

const kindOptions = computed<{ label: string; value: PdmFileKind | null }[]>(() => [
  { label: t('adminSettings.pdmReconciliation.filters.allKinds'), value: null },
  { label: t('adminSettings.itemFields.madeSection'), value: 'made' },
  { label: t('adminSettings.itemFields.boughtSection'), value: 'bought' },
  {
    label: t('adminSettings.solidworksPdm.pdm.sync.watchedFolders.exportedDocuments'),
    value: 'document',
  },
])

function itemRoute(row: PdmReconciliationFinding): string | null {
  if (row.item_id === null || row.kind === null) return null
  return row.kind === 'made'
    ? `/catalogue/made-items/${row.item_id}`
    : `/catalogue/bought-items/${row.item_id}`
}

function onOpenItem(row: PdmReconciliationFinding): void {
  const to = itemRoute(row)
  if (router && to) void router.push(to)
}

function onOpenFiles(): void {
  emit('open-files')
}

const recheckingFileId = ref<number | null>(null)

// Asks the trigger worker to re-read the file now, which also heals a
// part-number drift without waiting for the file's next change.
async function onRecheck(row: PdmReconciliationFinding): Promise<void> {
  if (row.file_id === null) return
  recheckingFileId.value = row.file_id
  try {
    await store.recheckFile(row.file_id)
    appToast.success(t('adminSettings.pdmReconciliation.recheckRequested'))
  } catch (err: unknown) {
    appToast.error(
      t('adminSettings.pdmReconciliation.recheckFailed'),
      extractApiError(err) ?? t('adminSettings.errors.unknown'),
    )
  } finally {
    recheckingFileId.value = null
  }
}

// ── Message detail dialog ────────────────────────────────────────────

const messageDialogVisible = ref(false)
const messageDialogText = ref('')

function showMessage(row: PdmReconciliationFinding): void {
  messageDialogText.value = row.message
  messageDialogVisible.value = true
}

// ── Excel export ─────────────────────────────────────────────────────
// Re-fetches every page of the current filter directly (not through the
// store's own single-page state) so the export always reflects the full
// filtered result set, not just whatever page happens to be on screen,
// capped at EXPORT_MAX_ROWS so a very large, unfiltered report can't hang
// the browser building a many-thousand-row sheet.

const exporting = ref(false)

async function onExport(): Promise<void> {
  exporting.value = true
  try {
    const all: PdmReconciliationFinding[] = []
    let skip = 0

    while (all.length < EXPORT_MAX_ROWS) {
      const page = await getPdmReconciliationFindings(
        store.buildFindingsParams({ skip, limit: EXPORT_PAGE_SIZE }),
      )
      all.push(...page.items)
      skip += EXPORT_PAGE_SIZE
      if (page.items.length < EXPORT_PAGE_SIZE || all.length >= page.total) break
    }

    const rows = buildPdmReconciliationExportRows(all.slice(0, EXPORT_MAX_ROWS), {
      category: categoryLabel,
      severity: severityLabel,
      kind: kindLabel,
    })
    await writePdmReconciliationExportFile(rows, {
      headers: {
        category: t('adminSettings.pdmReconciliation.exportFile.columns.category'),
        severity: t('adminSettings.pdmReconciliation.exportFile.columns.severity'),
        kind: t('adminSettings.pdmReconciliation.exportFile.columns.kind'),
        partNumber: t('adminSettings.pdmReconciliation.exportFile.columns.partNumber'),
        revision: t('adminSettings.pdmReconciliation.exportFile.columns.revision'),
        message: t('adminSettings.pdmReconciliation.exportFile.columns.message'),
        count: t('adminSettings.pdmReconciliation.exportFile.columns.count'),
      },
      sheetName: t('adminSettings.pdmReconciliation.exportFile.sheetName'),
      filename: t('adminSettings.pdmReconciliation.exportFile.filename'),
    })
  } catch (err: unknown) {
    appToast.error(t('adminSettings.errors.unknown'), extractApiError(err) ?? undefined)
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    modal
    maximizable
    :header="t('adminSettings.pdmReconciliation.dialogTitle')"
    :style="{ width: 'var(--dialog-width-full)', height: '80vh' }"
    content-class="pdm-reconciliation-dialog-content"
  >
    <div class="run-actions">
      <Button
        :label="t('adminSettings.pdmReconciliation.quickButton')"
        icon="mdi mdi-flash-outline"
        text
        severity="contrast"
        :loading="store.requesting"
        :disabled="!canRequestRun"
        @click="onRequestRun(false)"
      />
      <Button
        :label="t('adminSettings.pdmReconciliation.deepButton')"
        icon="mdi mdi-magnify-scan"
        text
        severity="contrast"
        :loading="store.requesting"
        :disabled="!canRequestRun"
        v-tooltip.top="t('adminSettings.pdmReconciliation.deepButtonTooltip')"
        @click="onRequestRun(true)"
      />
    </div>

    <template v-if="store.run">
      <div class="category-tiles">
        <button
          v-for="tile in categoryTiles"
          :key="tile.category"
          type="button"
          class="category-tile"
          :class="{
            'category-tile--muted': tile.count === 0,
            'category-tile--active': store.category === tile.category,
          }"
          v-tooltip.top="tile.description"
          @click="onTileClick(tile.category)"
        >
          <Tag :severity="tile.severity" :value="String(tile.count)" />
          <span class="category-tile-label">{{ tile.label }}</span>
        </button>
      </div>

      <div class="findings-controls">
        <Button
          icon="mdi mdi-refresh"
          text
          severity="contrast"
          :loading="store.findingsLoading"
          v-tooltip.top="t('common.reload')"
          :aria-label="t('common.reload')"
          @click="resetAndFetch"
        />
        <IconField>
          <InputIcon class="mdi mdi-magnify" />
          <InputText v-model="store.search" :placeholder="t('common.search')" />
        </IconField>
        <Button
          :label="t('adminSettings.pdmReconciliation.export')"
          icon="mdi mdi-file-excel-outline"
          text
          severity="contrast"
          :loading="exporting"
          :disabled="store.findingsTotal === 0"
          @click="onExport"
        />
      </div>

      <DataTable
        class="findings-table fixed-layout-table ellipsis-cells"
        :value="store.findings"
        data-key="id"
        lazy
        :total-records="store.findingsTotal"
        :rows="TABLE_DEFAULT_ROWS"
        :first="first"
        paginator
        scrollable
        scroll-height="flex"
        size="small"
        :loading="store.findingsLoading"
        :filters="NO_FILTER_META"
        filter-display="row"
        :show-gridlines="isTableGridlinesEnabled"
        :striped-rows="isTableStripedEnabled"
        @page="onPage"
      >
        <template #empty>
          <EmptyState :message="t('adminSettings.pdmReconciliation.noFindings')" />
        </template>

        <Column :header="t('adminSettings.pdmReconciliation.columns.actions')" style="width: 9rem">
          <template #body="{ data }: { data: PdmReconciliationFinding }">
            <div class="row-actions">
              <Button
                v-if="router && itemRoute(data)"
                icon="mdi mdi-open-in-new"
                size="small"
                text
                severity="secondary"
                v-tooltip.top="t('adminSettings.pdmReconciliation.openItem')"
                :aria-label="t('adminSettings.pdmReconciliation.openItem')"
                @click="onOpenItem(data)"
              />
              <span v-if="data.file_id !== null" v-tooltip.top="writeBlocked || undefined">
                <Button
                  icon="mdi mdi-refresh"
                  size="small"
                  text
                  severity="secondary"
                  :disabled="!canWrite"
                  :loading="recheckingFileId === data.file_id"
                  v-tooltip.top="t('adminSettings.pdmReconciliation.recheck')"
                  :aria-label="t('adminSettings.pdmReconciliation.recheck')"
                  data-testid="pdm-reconciliation-recheck"
                  @click="onRecheck(data)"
                />
              </span>
              <Button
                v-if="data.file_id !== null"
                icon="mdi mdi-file-sync-outline"
                size="small"
                text
                severity="secondary"
                v-tooltip.top="t('adminSettings.pdmReconciliation.openFiles')"
                :aria-label="t('adminSettings.pdmReconciliation.openFiles')"
                @click="onOpenFiles"
              />
            </div>
          </template>
        </Column>

        <Column
          column-key="category"
          :header="t('adminSettings.pdmReconciliation.columns.category')"
          :show-filter-menu="false"
          style="width: 14rem"
        >
          <template #filter>
            <Select
              class="select-placeholder-as-value"
              v-model="store.category"
              :options="categoryOptions"
              option-label="label"
              option-value="value"
              :placeholder="t('adminSettings.pdmReconciliation.filters.allCategories')"
              :aria-label="t('adminSettings.pdmReconciliation.filters.category')"
              size="small"
              fluid
              @update:model-value="onFilterChange"
            />
          </template>
          <template #body="{ data }: { data: PdmReconciliationFinding }">
            <Tag :severity="severityTagSeverity(data.severity)" :value="categoryLabel(data.category)" />
          </template>
        </Column>

        <Column
          column-key="kind"
          :header="t('adminSettings.pdmReconciliation.columns.kind')"
          :show-filter-menu="false"
          style="width: 11rem"
        >
          <template #filter>
            <Select
              class="select-placeholder-as-value"
              v-model="store.kind"
              :options="kindOptions"
              option-label="label"
              option-value="value"
              :placeholder="t('adminSettings.pdmReconciliation.filters.allKinds')"
              :aria-label="t('adminSettings.pdmReconciliation.filters.kind')"
              size="small"
              fluid
              @update:model-value="onFilterChange"
            />
          </template>
          <template #body="{ data }: { data: PdmReconciliationFinding }">{{ kindLabel(data.kind) }}</template>
        </Column>

        <Column
          column-key="part_number"
          :header="t('adminSettings.pdmReconciliation.columns.partNumber')"
          :show-filter-menu="false"
          style="width: 12rem"
        >
          <template #filter>
            <InputText
              v-model="store.partNumber"
              :aria-label="t('common.filterBy', { column: t('adminSettings.pdmReconciliation.columns.partNumber') })"
              size="small"
              fluid
            />
          </template>
          <template #body="{ data }: { data: PdmReconciliationFinding }">
            {{ madeItemLabel(data.part_number, data.revision) }}
          </template>
        </Column>

        <!-- No fixed width: the one column that takes up the remaining
             table width, same convention as PdmFilesDialog's own "error"
             column. -->
        <Column
          column-key="message"
          :header="t('adminSettings.pdmReconciliation.columns.message')"
          :show-filter-menu="false"
        >
          <template #filter>
            <InputText
              v-model="store.message"
              :aria-label="t('common.filterBy', { column: t('adminSettings.pdmReconciliation.columns.message') })"
              size="small"
              fluid
            />
          </template>
          <template #body="{ data }: { data: PdmReconciliationFinding }">
            <span
              class="message-cell"
              role="button"
              tabindex="0"
              v-tooltip.top="data.message"
              @click="showMessage(data)"
              @keydown.enter="showMessage(data)"
              @keydown.space.prevent="showMessage(data)"
              >{{ data.message }}</span
            >
          </template>
        </Column>

        <Column :header="t('adminSettings.pdmReconciliation.columns.count')" style="width: 6rem">
          <template #body="{ data }: { data: PdmReconciliationFinding }">{{ data.count }}</template>
        </Column>

      </DataTable>
    </template>

    <div v-else class="empty-note">{{ t('adminSettings.pdmReconciliation.empty') }}</div>

    <template v-if="lastRunLine" #footer>
      <p class="last-run-line">{{ lastRunLine }}</p>
    </template>
  </Dialog>

  <Dialog
    v-model:visible="messageDialogVisible"
    modal
    :header="t('adminSettings.pdmReconciliation.messageDialogTitle')"
    style="width: var(--dialog-width-md)"
  >
    <p class="message-dialog-text">{{ messageDialogText }}</p>
  </Dialog>
</template>

<style scoped lang="scss">
// :global, not :deep: the dialog is teleported out of this component, so
// .p-dialog-content never carries the scoped-style attribute and a :deep
// selector would not match it. Turning off its default overflow-y:auto is
// what stops the dialog body scrolling; the table below scrolls instead.
:global(.pdm-reconciliation-dialog-content) {
  display: flex;
  flex-direction: column;
  min-height: 0;
  gap: var(--space-2);
  overflow: hidden;
}

.run-actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

// The dialog footer is justify-content: flex-end, and this is its only
// child, so the auto margin is what keeps the line left-aligned.
.last-run-line {
  margin: 0 auto 0 0;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.category-tiles {
  flex: 0 0 auto;
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.category-tile {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) var(--space-2);
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-content-border-radius);
  background: var(--p-content-background);
  cursor: pointer;
  font: inherit;
  color: var(--p-text-color);

  &:hover {
    border-color: var(--p-primary-color);
  }
}

.category-tile--muted {
  opacity: 0.55;
}

.category-tile--active {
  border-color: var(--p-primary-color);
  background: var(--p-highlight-bg);
}

.category-tile-label {
  font-size: var(--font-size-sm);
}

.findings-controls {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.findings-table {
  flex: 1 1 auto;
  min-height: 0;
  // Matches the synced-files dialog's breathing room above its table.
  margin-top: var(--space-5);

  // The sum of the declared column widths plus room for the one column that
  // declares none.
  --table-min-width: 60rem;
}

.message-cell {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.message-dialog-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.empty-note {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
