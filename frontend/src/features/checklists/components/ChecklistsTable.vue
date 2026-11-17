<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useConfirm } from 'openvue/useconfirm'

import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useAppToast } from '@/core/composables/useAppToast'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { extractApiError } from '@/core/utils/errors'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import { HelpButton } from '@/shared/help'
import EmptyState from '@/shared/components/EmptyState.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import { editingBy } from '@/shared/documents'
import { ReportExportDialog, useReportExport } from '@/shared/reports'
import { deleteChecklist } from '../api/deleteChecklist'
import { getChecklist } from '../api/getChecklist'
import { useChecklistRowMenu } from '../composables/useChecklistRowMenu'
import { useChecklistsTable } from '../composables/useChecklistsTable'
import type { ChecklistRow, ChecklistsScope } from '../composables/useChecklistsTable'
import type { ChecklistsContext } from '../stores/checklistsTableStores'
import type { ChecklistSummaryResponse } from '../types/checklist'
import { TYPE_ICONS, typeLabelKey } from '../utils/definitions'
import { completionOf, VERDICT_SEVERITY } from '../utils/owner'
import { checklistReportSpec } from '../utils/report'
import { CHECKLIST_TYPES, isChecklistType } from '../utils/types'
import ChecklistStatusTag from './ChecklistStatusTag.vue'

/**
 * The latest revision of every checklist in a scope, in a server-paged
 * table laid out like the catalogue: the actions column (shown through
 * Views) at the far left, the row number, then the columns with their
 * filters in the header row. On the tab of a project or product it is the
 * plain list: no filter row, no grouping and the row actions always shown,
 * since there is no views bar to show them. A right click opens the row's
 * context menu.
 */

const props = defineProps<{
  context: ChecklistsContext
  projectId?: number
  productId?: number
  /** Also lists the checklists of the projects built on `productId`. */
  includeProductProjects?: boolean
}>()

const { t } = useI18n()
const toast = useAppToast()
const confirm = useConfirm()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const table = useChecklistsTable(props.context, (): ChecklistsScope => ({
  projectId: props.projectId,
  productId: props.productId,
  includeProductProjects: props.includeProductProjects,
}))
const { view, filters, items, total, loading, failed, first, rows, onPage, onFilter, typeName, ownerLabel } = table

watchLoadingBar(() => loading.value)

const scoped = computed(() => props.context !== 'page')
const groupBy = computed(() => (scoped.value ? null : view.groupBy))

// A project's or product's own checklists all belong to it; with the
// product's projects included, the owner tells them apart.
const showOwner = computed(() => !scoped.value || props.includeProductProjects === true)

const any = computed(() => t('checklists.filters.any'))
const typeOptions = computed(() => CHECKLIST_TYPES.map((value) => ({ value, label: t(typeLabelKey(value)) })))
const ownerOptions = computed(() =>
  (['personal', 'project', 'product'] as const).map((value) => ({ value, label: t(`checklists.owner.${value}`) })),
)
const verdictOptions = computed(() =>
  (['open', 'passed', 'failed'] as const).map((value) => ({ value, label: t(`checklists.verdicts.${value}`) })),
)
const statusOptions = computed(() =>
  (['released', 'unreleased'] as const).map((value) => ({ value, label: t(`checklists.filters.status.${value}`) })),
)
const authorOptions = computed(() => [{ value: 'me', label: t('checklists.filters.me') }])

const GROUP_ICONS = {
  type: 'mdi-clipboard-list-outline',
  owner: 'mdi-folder-outline',
  verdict: 'mdi-flag-outline',
  status: 'mdi-check-decagram-outline',
}

function typeIcon(row: ChecklistSummaryResponse): string {
  return `mdi ${isChecklistType(row.type) ? TYPE_ICONS[row.type] : 'mdi-clipboard-check-outline'}`
}

const { visible: reportVisible, report, open: openReport } = useReportExport()

// The list holds summaries; the report needs the full revision.
async function print(row: ChecklistSummaryResponse): Promise<void> {
  try {
    const spec = checklistReportSpec(await getChecklist(row.id))
    if (spec) openReport(spec)
  } catch (e) {
    toast.error(row.title, extractApiError(e) ?? t('checklists.errors.unknown'))
  }
}

function remove(row: ChecklistSummaryResponse): void {
  async function onAccept(): Promise<void> {
    try {
      await deleteChecklist(row.id)
      toast.success(row.title, t('checklists.toasts.delete'))
      table.reload()
    } catch (e) {
      toast.error(row.title, extractApiError(e) ?? t('checklists.errors.unknown'))
    }
  }

  confirm.require({
    group: `checklists-${props.context}`,
    header: t('checklists.confirm.delete.header'),
    message: t('checklists.confirm.delete.message'),
    icon: 'mdi mdi-delete-outline',
    rejectProps: { label: t('common.cancel'), severity: 'secondary' },
    acceptProps: { label: t('checklists.confirm.delete.accept'), severity: 'danger' },
    accept: () => void onAccept(),
  })
}

const { cm, contextMenuItem, contextMenuItems, onRowContextMenu, permissions, open } = useChecklistRowMenu({
  print: (row) => void print(row),
  remove,
})
// A released revision is kept as a record; only the latest draft is deleted.
const canDelete = (row: ChecklistSummaryResponse): boolean => permissions(row).delete

defineExpose({ reload: table.reload })
</script>

<template>
  <div class="cl-table-wrap">
    <Message v-if="failed" severity="error" class="cl-table-error">{{ t('checklists.errors.loadList') }}</Message>
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
      class="cl-table clickable-rows"
      data-testid="checklists-table"
      @page="onPage"
      @filter="onFilter"
      @row-click="(e) => open(e.data)"
      @row-contextmenu="onRowContextMenu"
    >
      <template v-if="groupBy" #groupheader="{ data }: { data: ChecklistRow }">
        <div class="group-header">
          <i :class="`mdi ${GROUP_ICONS[groupBy]}`" aria-hidden="true" />
          <span class="group-header-label">{{ data._group }}</span>
        </div>
      </template>
      <template #empty>
        <EmptyState icon="mdi mdi-clipboard-check-outline" :message="t('checklists.list.empty')" />
      </template>

      <Column v-if="scoped || view.showActions" frozen style="width: 7rem" :show-filter-menu="false">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <div class="row-actions" :data-testid="`cl-row-actions-${data.id}`">
            <Button
              v-tooltip.focus="t('checklists.actions.open')"
              :aria-label="t('checklists.actions.open')"
              icon="mdi mdi-open-in-app"
              size="small"
              severity="secondary"
              text
              rounded
              @click="open(data)"
            />
            <Button
              v-tooltip.focus="t('checklists.actions.print')"
              :aria-label="t('checklists.actions.print')"
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

      <Column field="type" :header="t('checklists.list.type')" :show-filter-menu="false" style="min-width: 10rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <span class="type-cell">
            <i :class="typeIcon(data)" aria-hidden="true" />
            {{ typeName(data) }}
          </span>
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <Select
            v-model="filterModel.value"
            :options="typeOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="any"
            :aria-label="t('common.filterBy', { column: t('checklists.list.type') })"
            size="small"
            fluid
            @change="filterCallback()"
            @clear="filterCallback()"
          />
        </template>
      </Column>
      <Column field="document_number" :header="t('checklists.list.number')" :show-filter-menu="false" style="min-width: 8rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <span class="document-number" :data-testid="`cl-number-${data.id}`">
            {{ data.document_number }}
            <i
              v-if="editingBy(data) !== null"
              v-tooltip.bottom="t('documents.table.editing', { name: editingBy(data) })"
              class="mdi mdi-lock-outline lock-icon"
              :aria-label="t('documents.table.editing', { name: editingBy(data) })"
              :data-testid="`cl-locked-${data.id}`"
            />
          </span>
        </template>
      </Column>
      <Column :header="t('documents.table.revision')" :show-filter-menu="false" style="min-width: 6rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <Tag
            v-tooltip.bottom="data.revision_reason ?? ''"
            :value="t('documents.revision.tag', { revision: data.revision })"
            severity="secondary"
            :data-testid="`cl-revision-${data.id}`"
          />
        </template>
      </Column>
      <Column field="title" :header="t('checklists.list.title')" :show-filter-menu="false" style="min-width: 16rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <span class="title-text">{{ data.title }}</span>
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <InputText
            v-model="filterModel.value"
            :placeholder="t('checklists.filters.search')"
            :aria-label="t('common.filterBy', { column: t('checklists.list.title') })"
            size="small"
            fluid
            data-testid="cl-filter-title"
            @input="filterCallback()"
          />
        </template>
      </Column>
      <Column :header="t('checklists.list.designation')" :show-filter-menu="false" style="min-width: 9rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <span :data-testid="`cl-designation-${data.id}`">{{ data.designation ?? '' }}</span>
        </template>
      </Column>
      <Column v-if="showOwner" field="owner" :header="t('checklists.list.owner')" :show-filter-menu="false" style="min-width: 10rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">{{ ownerLabel(data) }}</template>
        <template #filter="{ filterModel, filterCallback }">
          <Select
            v-model="filterModel.value"
            :options="ownerOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="any"
            :aria-label="t('common.filterBy', { column: t('checklists.list.owner') })"
            size="small"
            fluid
            @change="filterCallback()"
            @clear="filterCallback()"
          />
        </template>
      </Column>
      <Column field="verdict" :header="t('checklists.list.result')" :show-filter-menu="false" style="min-width: 10rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <Tag :value="t(`checklists.verdicts.${data.verdict}`)" :severity="VERDICT_SEVERITY[data.verdict]" />
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <Select
            v-model="filterModel.value"
            :options="verdictOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="any"
            :aria-label="t('common.filterBy', { column: t('checklists.list.result') })"
            size="small"
            fluid
            @change="filterCallback()"
            @clear="filterCallback()"
          />
        </template>
      </Column>
      <Column :header="t('checklists.list.completionHeader')" :show-filter-menu="false" style="min-width: 7rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <span
            v-tooltip.bottom="`${data.answered_count} / ${data.item_count}`"
            class="completion"
            :data-testid="`cl-completion-${data.id}`"
          >
            {{ t('checklists.list.completion', { percent: completionOf(data) }) }}
          </span>
        </template>
      </Column>
      <Column :header="t('checklists.list.findings')" :show-filter-menu="false" style="min-width: 6rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <Tag
            v-if="data.finding_count > 0"
            :value="String(data.finding_count)"
            severity="warn"
            :data-testid="`cl-findings-${data.id}`"
          />
          <span v-else class="completion" :data-testid="`cl-findings-${data.id}`">0</span>
        </template>
      </Column>
      <Column field="status" :header="t('checklists.list.status')" :show-filter-menu="false" style="min-width: 10rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <ChecklistStatusTag :checklist="data" />
          <Tag
            v-if="data.invalid_at"
            v-tooltip.bottom="data.invalid_reason ?? ''"
            :value="t('documents.status.invalid')"
            severity="danger"
            class="status-invalid"
            :data-testid="`cl-invalid-${data.id}`"
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
            :aria-label="t('common.filterBy', { column: t('checklists.list.status') })"
            size="small"
            fluid
            @change="filterCallback()"
            @clear="filterCallback()"
          />
        </template>
      </Column>
      <Column :header="t('documents.table.released')" :show-filter-menu="false" style="min-width: 10rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <UserDateCell
            :date="data.released_at"
            :user-id="data.released_by_id"
            :name="data.released_by_full_name"
            :data-testid="`cl-released-${data.id}`"
          />
        </template>
      </Column>
      <Column field="author" :header="t('checklists.list.author')" :show-filter-menu="false" style="min-width: 10rem">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
          <UserDateCell :date="data.created" :user-id="data.creator_id" :name="data.creator_full_name" />
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <Select
            v-model="filterModel.value"
            :options="authorOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="t('checklists.filters.anyone')"
            :aria-label="t('common.filterBy', { column: t('checklists.list.author') })"
            size="small"
            fluid
            data-testid="cl-filter-author"
            @change="filterCallback()"
            @clear="filterCallback()"
          />
        </template>
      </Column>
      <Column :header="t('checklists.list.changed')" style="min-width: 7rem" :show-filter-menu="false">
        <template #body="{ data }: { data: ChecklistSummaryResponse }">
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
      data-testid="cl-row-menu"
      @hide="contextMenuItem = null"
    />
    <ConfirmDialog :group="`checklists-${context}`" />
    <ReportExportDialog v-model:visible="reportVisible" :report="report">
      <template #handbook>
        <HelpButton slug="resources/report-export" icon="mdi mdi-help" rounded />
      </template>
    </ReportExportDialog>
  </div>
</template>

<style scoped lang="scss">
.cl-table-wrap {
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.cl-table-error {
  margin-bottom: var(--space-2);
}

// The whole row opens the checklist, like a catalogue row.
.cl-table {
  flex: 1;
  min-height: 0;

  // One line per row, like the catalogue; the table scrolls sideways when
  // the columns need more room than the page has.
  :deep(td) {
    white-space: nowrap;
  }
}

.type-cell {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}

.title-text {
  font-weight: 600;
}

.completion {
  font-size: var(--font-size-sm);
  font-variant-numeric: tabular-nums;
  color: var(--p-text-muted-color);
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
