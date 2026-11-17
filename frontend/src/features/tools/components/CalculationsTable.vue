<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useConfirm } from 'openvue/useconfirm'

import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { TOAST_LIFE_LONG, useAppToast } from '@/core/composables/useAppToast'
import { useErrorToast } from '@/core/composables/useErrorToast'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { formatISODateTime } from '@/core/utils/dates'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import { HelpButton } from '@/shared/help'
import EmptyState from '@/shared/components/EmptyState.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import { editingBy } from '@/shared/documents'
import { ReportExportDialog, useReportExport } from '@/shared/reports'
import { deleteCalculation } from '../api/deleteCalculation'
import { getCalculationByPublicId } from '../api/getCalculationByPublicId'
import { useCalculationRowMenu } from '../composables/useCalculationRowMenu'
import { useCalculationsTable } from '../composables/useCalculationsTable'
import type { CalculationRow, CalculationsScope } from '../composables/useCalculationsTable'
import { SAVEABLE_TOOLS, toolByKey } from '../registry'
import type { CalculationsContext } from '../stores/calculationsTableStores'
import type { CalculationSummaryResponse } from '../types/calculation'
import { toolReportSpec } from '../utils/toolReport'

/**
 * Saved calculations in a server-paged table, laid out like the catalogue:
 * the actions column (shown through Views) at the far left, the row number,
 * then the columns with their filters in the header row. On the tab of a
 * project or product it is the plain list: no filter row, no grouping and
 * the row actions always shown, since there is no views bar to show them.
 * A right click opens the row's context menu.
 */

const props = defineProps<{
  context: CalculationsContext
  projectId?: number
  productId?: number
  /** Also lists the calculations of the projects built on `productId`. */
  includeProductProjects?: boolean
}>()

const { t } = useI18n()
const toast = useAppToast()
const { withErrorToast } = useErrorToast()
const confirm = useConfirm()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const table = useCalculationsTable(props.context, (): CalculationsScope => ({
  projectId: props.projectId,
  productId: props.productId,
  includeProductProjects: props.includeProductProjects,
}))
const { view, filters, items, total, loading, failed, first, rows, onPage, onFilter, toolLabel, ownerLabel } = table

watchLoadingBar(() => loading.value)

const scoped = computed(() => props.context !== 'page')
const groupBy = computed(() => (scoped.value ? null : view.groupBy))

// A project's or product's own calculations all belong to it; with the
// product's projects included, the owner tells them apart.
const showOwner = computed(() => !scoped.value || props.includeProductProjects === true)

const any = computed(() => t('tools.calculations.filters.any'))
const toolOptions = computed(() => SAVEABLE_TOOLS.map((tool) => ({ value: tool.key, label: t(tool.labelKey) })))
const ownerOptions = computed(() =>
  (['personal', 'project', 'product'] as const).map((value) => ({ value, label: t(`tools.calculations.owner.${value}`) })),
)
const statusOptions = computed(() =>
  (['draft', 'released'] as const).map((value) => ({ value, label: t(`tools.calculations.status.${value}`) })),
)
const authorOptions = computed(() => [{ value: 'me', label: t('tools.calculations.filters.me') }])

const GROUP_ICONS = { tool: 'mdi-toolbox', owner: 'mdi-folder-outline', status: 'mdi-check-decagram-outline' }

function toolIcon(row: CalculationSummaryResponse): string {
  return `mdi ${toolByKey(row.tool)?.icon ?? 'mdi-calculator-variant-outline'}`
}

function summary(row: CalculationSummaryResponse): string {
  return toolByKey(row.tool)?.summarize(row.results, t) ?? ''
}

/** The tool version a row was calculated with, when the tool has moved on since. */
function outdated(row: CalculationSummaryResponse): string {
  const current = toolByKey(row.tool)?.engineVersion
  if (current === undefined || row.engine_version >= current) return ''
  return t('tools.calculations.list.outdated', { saved: row.engine_version, current })
}

const { visible: reportVisible, report, open: openReport } = useReportExport()

// The list holds summaries; the report needs the full record.
async function print(row: CalculationSummaryResponse): Promise<void> {
  const tool = toolByKey(row.tool)
  if (!tool) return
  await withErrorToast(
    async () => {
      const spec = toolReportSpec(tool, await getCalculationByPublicId(row.public_id))
      if (spec) openReport(spec)
    },
    {
      summary: row.title,
      fallbackMessage: t('tools.calculations.errors.notFound'),
      life: TOAST_LIFE_LONG,
    },
  )
}

function remove(row: CalculationSummaryResponse): void {
  confirm.require({
    group: `calculations-${props.context}`,
    header: t('tools.calculations.confirm.delete.header'),
    message: t('tools.calculations.confirm.delete.message'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('tools.calculations.confirm.delete.accept'), severity: 'danger' },
    accept: () =>
      void withErrorToast(
        async () => {
          await deleteCalculation(row.id)
          toast.success(row.title, t('tools.calculations.toasts.delete'))
          table.reload()
        },
        {
          summary: row.title,
          fallbackMessage: t('tools.calculations.errors.unknown'),
          life: TOAST_LIFE_LONG,
        },
      ),
  })
}

const { cm, contextMenuItem, contextMenuItems, onRowContextMenu, permissions, open } = useCalculationRowMenu({
  print: (row) => void print(row),
  remove,
})
// A released revision is kept as a record; only a draft is deleted.
const canDelete = (row: CalculationSummaryResponse): boolean => permissions(row).delete
</script>

<template>
  <div class="calc-table-wrap">
    <Message v-if="failed" severity="error" class="calc-table-error">{{ t('tools.calculations.errors.loadList') }}</Message>
    <DataTable
      v-model:filters="filters"
      :value="items"
      data-key="id"
      lazy
      paginator
      :total-records="total"
      :first="first"
      :rows="rows"
      :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
      :filter-display="scoped ? undefined : 'row'"
      :row-group-mode="groupBy ? 'subheader' : undefined"
      :group-rows-by="groupBy ? '_group' : undefined"
      table-style="min-width: 50rem"
      scrollable
      scroll-height="flex"
      size="small"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled"
      v-model:context-menu-selection="contextMenuItem"
      context-menu
      class="calc-table clickable-rows"
      data-testid="calculations-table"
      @page="onPage"
      @filter="onFilter"
      @row-click="(e) => open(e.data)"
      @row-contextmenu="onRowContextMenu"
    >
      <template v-if="groupBy" #groupheader="{ data }: { data: CalculationRow }">
        <div class="group-header">
          <i :class="`mdi ${GROUP_ICONS[groupBy]}`" aria-hidden="true" />
          <span class="group-header-label">{{ data._group }}</span>
        </div>
      </template>
      <template #empty>
        <EmptyState icon="mdi mdi-calculator-variant-outline" :message="t('tools.calculations.list.empty')" />
      </template>

      <Column v-if="scoped || view.showActions" frozen style="width: 7rem" :show-filter-menu="false">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <div class="row-actions" :data-testid="`calc-row-actions-${data.id}`">
            <Button
              v-tooltip.focus="t('tools.calculations.actions.open')"
              :aria-label="t('tools.calculations.actions.open')"
              icon="mdi mdi-open-in-app"
              size="small"
              severity="secondary"
              text
              rounded
              @click="open(data)"
            />
            <Button
              v-tooltip.focus="t('tools.calculations.actions.print')"
              :aria-label="t('tools.calculations.actions.print')"
              icon="mdi mdi-printer-outline"
              size="small"
              severity="secondary"
              text
              rounded
              @click="print(data)"
            />
            <Button
              v-tooltip.focus="t('common.delete')"
              :aria-label="t('common.delete')"
              icon="mdi mdi-delete-outline"
              size="small"
              severity="danger"
              text
              rounded
              :disabled="!canDelete(data)"
              @click="remove(data)"
            />
          </div>
        </template>
      </Column>
      <Column
        frozen
        header="#"
        header-style="width: 3rem"
        body-class="row-number"
        :show-filter-menu="false"
      >
        <template #body="{ index }">{{ first + index + 1 }}</template>
      </Column>

      <Column field="tool" :header="t('tools.calculations.list.tool')" :show-filter-menu="false" style="min-width: 11rem">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <span class="tool-cell">
            <i :class="toolIcon(data)" aria-hidden="true" />
            {{ toolLabel(data) }}
          </span>
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <Select
            v-model="filterModel.value"
            :options="toolOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="any"
            :aria-label="t('common.filterBy', { column: t('tools.calculations.list.tool') })"
            size="small"
            fluid
            @change="filterCallback()"
            @clear="filterCallback()"
          />
        </template>
      </Column>
      <Column field="document_number" :header="t('tools.calculations.list.number')" :show-filter-menu="false" style="min-width: 8rem">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <span class="document-number" :data-testid="`calc-number-${data.id}`">
            {{ data.document_number }}
            <i
              v-if="editingBy(data) !== null"
              v-tooltip.bottom="t('documents.table.editing', { name: editingBy(data) })"
              class="mdi mdi-lock-outline lock-icon"
              :aria-label="t('documents.table.editing', { name: editingBy(data) })"
              :data-testid="`calc-locked-${data.id}`"
            />
          </span>
        </template>
      </Column>
      <Column :header="t('documents.table.revision')" :show-filter-menu="false" style="min-width: 6rem">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <Tag
            v-tooltip.bottom="data.revision_reason ?? ''"
            :value="t('documents.revision.tag', { revision: data.revision })"
            severity="secondary"
            :data-testid="`calc-revision-${data.id}`"
          />
        </template>
      </Column>
      <Column field="title" :header="t('tools.calculations.list.title')" :show-filter-menu="false" style="min-width: 16rem">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <span class="title-text">{{ data.title }}</span>
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            :placeholder="t('tools.calculations.filters.search')"
            :aria-label="t('common.filterBy', { column: t('tools.calculations.list.title') })"
            size="small"
            fluid
            data-testid="calc-filter-title"
            @input="filterCallback()"
          />
        </template>
      </Column>
      <Column :header="t('tools.calculations.list.note')" :show-filter-menu="false" style="min-width: 10rem">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <span v-tooltip.bottom="data.note ?? ''" class="note-cell">{{ data.note ?? '' }}</span>
        </template>
      </Column>
      <Column :header="t('tools.calculations.list.result')" :show-filter-menu="false" style="min-width: 14rem">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <span v-tooltip.bottom="summary(data)" class="result-cell">{{ summary(data) }}</span>
        </template>
      </Column>
      <Column :header="t('tools.calculations.list.toolVersion')" :show-filter-menu="false" style="min-width: 7rem">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <span class="version-cell" :data-testid="`calc-version-${data.id}`">
            {{ data.engine_version }}
            <i
              v-if="outdated(data)"
              v-tooltip.bottom="outdated(data)"
              class="mdi mdi-alert-outline version-outdated"
              :aria-label="outdated(data)"
              :data-testid="`calc-outdated-${data.id}`"
            />
          </span>
        </template>
      </Column>
      <Column v-if="showOwner" field="owner" :header="t('tools.calculations.list.owner')" :show-filter-menu="false" style="min-width: 10rem">
        <template #body="{ data }: { data: CalculationSummaryResponse }">{{ ownerLabel(data) }}</template>
        <template #filter="{ filterModel, filterCallback }">
          <Select
            v-model="filterModel.value"
            :options="ownerOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="any"
            :aria-label="t('common.filterBy', { column: t('tools.calculations.list.owner') })"
            size="small"
            fluid
            @change="filterCallback()"
            @clear="filterCallback()"
          />
        </template>
      </Column>
      <Column field="status" :header="t('tools.calculations.list.status')" :show-filter-menu="false" style="min-width: 9rem">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <Tag
            v-if="data.released_at"
            v-tooltip.bottom="
              t('tools.calculations.status.releasedBy', {
                name: data.released_by_full_name ?? '',
                date: formatISODateTime(data.released_at),
              })
            "
            :value="t('tools.calculations.status.released')"
            severity="success"
          />
          <Tag v-else :value="t('tools.calculations.status.draft')" severity="secondary" />
          <Tag
            v-if="data.invalid_at"
            v-tooltip.bottom="data.invalid_reason ?? ''"
            :value="t('tools.calculations.status.invalid')"
            severity="danger"
            class="status-invalid"
            :data-testid="`calc-invalid-${data.id}`"
          />
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <Select
            v-model="filterModel.value"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="any"
            :aria-label="t('common.filterBy', { column: t('tools.calculations.list.status') })"
            size="small"
            fluid
            @change="filterCallback()"
            @clear="filterCallback()"
          />
        </template>
      </Column>
      <Column :header="t('documents.table.released')" :show-filter-menu="false" style="min-width: 10rem">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <UserDateCell
            :date="data.released_at"
            :user-id="data.released_by_id"
            :name="data.released_by_full_name"
            :data-testid="`calc-released-${data.id}`"
          />
        </template>
      </Column>
      <Column field="author" :header="t('tools.calculations.list.author')" :show-filter-menu="false" style="min-width: 10rem">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <UserDateCell :date="data.created" :user-id="data.creator_id" :name="data.creator_full_name" />
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <Select
            v-model="filterModel.value"
            :options="authorOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="t('tools.calculations.filters.anyone')"
            :aria-label="t('common.filterBy', { column: t('tools.calculations.list.author') })"
            size="small"
            fluid
            data-testid="calc-filter-author"
            @change="filterCallback()"
            @clear="filterCallback()"
          />
        </template>
      </Column>
      <Column :header="t('tools.calculations.list.changed')" style="min-width: 7rem" :show-filter-menu="false">
        <template #body="{ data }: { data: CalculationSummaryResponse }">
          <UserDateCell
            :date="data.changed ?? data.created"
            :user-id="data.changed ? data.changed_by_id : data.creator_id"
            :name="data.changed ? data.changed_by_full_name : data.creator_full_name"
          />
        </template>
      </Column>
      <Column style="width: 100%" :show-filter-menu="false" />
    </DataTable>
    <ContextMenu
      ref="cm"
      :model="contextMenuItems"
      :pt="disabledItemTooltipPt"
      data-testid="calc-row-menu"
      @hide="contextMenuItem = null"
    />
    <ConfirmDialog :group="`calculations-${context}`" />
    <ReportExportDialog v-model:visible="reportVisible" :report="report">
      <template #handbook>
        <HelpButton slug="resources/report-export" icon="mdi mdi-help" rounded />
      </template>
    </ReportExportDialog>
  </div>
</template>

<style scoped lang="scss">
.calc-table-wrap {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.calc-table-error {
  margin-bottom: var(--space-2);
}

// The whole row opens the calculation, like a catalogue row.
.calc-table {
  flex: 1;
  min-height: 0;

  // One line per row, like the catalogue; the table scrolls sideways when
  // the columns need more room than the page has.
  :deep(td) {
    white-space: nowrap;
  }
}

.tool-cell {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.title-text {
  font-weight: 600;
}

// The calculated result in one line, cut off with its full text on hover.
.result-cell {
  display: block;
  max-width: 28rem;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--p-text-muted-color);
}

.note-cell {
  display: block;
  max-width: 16rem;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--p-text-muted-color);
}

.version-cell {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-variant-numeric: tabular-nums;
}

.version-outdated {
  color: var(--p-orange-500);
}

.lock-icon {
  margin-left: var(--space-1);
  color: var(--p-text-muted-color);
}

.status-invalid {
  margin-left: var(--space-1);
}

.group-header {
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.group-header-label {
  font-weight: bold;
}
.document-number {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
</style>
