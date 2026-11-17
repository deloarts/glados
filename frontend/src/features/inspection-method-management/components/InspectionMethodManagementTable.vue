<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { storeToRefs } from 'pinia'
import type { DataTableSortEvent } from 'openvue/datatable'
import { formatISODate as formatDate } from '@/core/utils/dates'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useServerTable } from '@/core/composables/useServerTable'
import { useManagementResourceActions } from '@/shared/composables/useManagementResourceActions'

import InspectionMethodFormDialog from './InspectionMethodFormDialog.vue'
import ResourceDetailDialog from '@/shared/components/dialogs/ResourceDetailDialog.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useRowDragReorder } from '@/shared/composables/useRowDragReorder'
import LabelTag from '@/shared/components/labels/LabelTag.vue'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { useInspectionMethodsStore } from '@/features/inspection-methods'
import type { InspectionMethodResponse, InspectionMethodSortBy } from '@/features/inspection-methods'

const { t } = useI18n()
const { localize } = useLocalizedText()
const toast = useAppToast()

const store = useInspectionMethodsStore()
const { tableItems: items, loading, filters, clearTrigger, search, sortBy, sortDir, showArchived } =
  storeToRefs(store)
watchLoadingBar(loading)
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const canWrite = computed(() => hasPermission(Permission.WRITE_INSPECTION_METHODS))
const canDelete = computed(() => hasPermission(Permission.WRITE_INSPECTION_METHODS))

const editDialogVisible = ref(false)
const editingMethod = ref<InspectionMethodResponse | undefined>(undefined)

function onEditMethod(method: InspectionMethodResponse): void {
  editingMethod.value = method
  editDialogVisible.value = true
}

function onSaved(method: InspectionMethodResponse): void {
  toast.success(localize(method.name), t('resources.inspectionMethods.editMethod'))
}

// Context menu, delete confirm and row opening come from
// useManagementResourceActions.
const {
  cm,
  contextMenuTarget: contextMenuItem,
  detailDialogVisible,
  detailTarget: detailMethod,
  contextMenuItems,
  onRowContextMenu,
  onRowClick,
  onDelete: onArchiveMethod,
  onRestore: onRestoreMethod,
} = useManagementResourceActions<InspectionMethodResponse>(store, {
  i18nPrefix: 'resources.inspectionMethods',
  entityLabel: (method) => localize(method.name),
  deletePermission: Permission.WRITE_INSPECTION_METHODS,
  archivable: { isArchived: (method) => method.archived },
  editItem: (method) => ({
    label: t('resources.inspectionMethods.editMethod'),
    icon: 'mdi mdi-pencil',
    disabled: !canWrite.value,
    command: () => onEditMethod(method),
  }),
})

// The grip in the first column drags a row to a new place in the hand-kept
// order pickers offer. It shows only to users who may reorder, and only
// while the table shows that order, since a sorted, searched or filtered
// page has other neighbours than the order a drop would change.
const showDragHandle = computed(() => canWrite.value && store.manualOrder)
const { handlePt, onRowReorder } = useRowDragReorder(
  () => items.value,
  (id, target, page) => store.place(id, target, page),
)

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: ({ first, rows }) => ({ skip: first, limit: rows }),
  fetch: (params) => store.refreshTable(params),
})

watch(filters, resetAndFetchDebounced, { deep: true })
watch(search, resetAndFetchDebounced)

watch(clearTrigger, () => {
  resetAndFetch()
})

watch([sortBy, sortDir], () => {
  resetAndFetch()
})

watch(showArchived, () => {
  resetAndFetch()
})

watch(
  () => store.refreshTrigger,
  () => fetchItems(),
)

// Server-side sort. The controlled sortField and sortOrder keep the header
// icon in step with the view's sort control.
function onSort(event: DataTableSortEvent): void {
  if (typeof event.sortField === 'string' && event.sortOrder) {
    store.setSort(
      event.sortField as InspectionMethodSortBy,
      event.sortOrder === 1 ? 'asc' : 'desc',
    )
  } else {
    store.clearSort()
  }
}

const detailFields = computed(() => {
  const m = detailMethod.value
  if (!m) return []
  return [
    { label: t('resources.inspectionMethods.columns.name'), value: localize(m.name) },
    { label: t('resources.inspectionMethods.columns.description'), value: localize(m.description) || null },
    {
      label: t('resources.inspectionMethods.columns.creator'),
      value: m.creator?.full_name ?? null,
    },
    { label: t('resources.inspectionMethods.columns.created'), value: formatDate(m.created) },
    {
      label: t('resources.inspectionMethods.columns.changed'),
      value: formatDate(m.changed),
    },
    {
      label: t('resources.inspectionMethods.columns.defaultSetupMinutes'),
      value: m.default_setup_minutes === null ? null : String(m.default_setup_minutes),
    },
    {
      label: t('resources.inspectionMethods.columns.defaultMinutesPerPiece'),
      value: m.default_minutes_per_piece === null ? null : String(m.default_minutes_per_piece),
    },
    {
      label: t('resources.inspectionMethods.columns.defaultMachine'),
      value: m.default_machine_name,
    },
    {
      label: t('resources.inspectionMethods.columns.requiresEvidence'),
      value: m.requires_evidence ? t('common.yes') : t('common.no'),
    },
    {
      label: t('resources.inspectionMethods.columns.archived'),
      value: m.archived ? t('common.yes') : t('common.no'),
    },
  ]
})
</script>

<template>
  <DataTable
    :value="items"
    v-model:filters="filters"
    v-model:context-menu-selection="contextMenuItem"
    filter-display="row"
    data-key="id"
    lazy
    paginator
    :total-records="store.total"
    :first="first"
    :rows="rows"
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    @page="onPage"
    :sort-field="sortBy ?? undefined"
    :sort-order="sortBy ? (sortDir === 'asc' ? 1 : -1) : undefined"
    removable-sort
    @sort="onSort"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    scrollable
    scroll-height="flex"
    resizable-columns
    column-resize-mode="fit"
    class="inspection-methods-table inspection-methods-rows-clickable"
    @row-reorder="onRowReorder"
    @row-contextmenu="onRowContextMenu"
    selection-mode="single"
    @row-click="onRowClick"
    @row-select="onRowClick"
  >
    <template #empty>
      <EmptyState />
    </template>

    <Column
      v-if="showDragHandle"
      row-reorder
      row-reorder-icon="mdi mdi-drag-vertical"
      :pt="handlePt"
      class="column-fit"
    />
    <Column
      v-if="store.showActions"
      :header="t('resources.inspectionMethods.columns.actions')"
      class="column-fit"
    >
      <template #body="{ data }: { data: InspectionMethodResponse }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            :disabled="!canWrite"
            v-tooltip.top.focus="t('resources.inspectionMethods.editMethod')"
            :aria-label="t('resources.inspectionMethods.editMethod')"
            @click.stop="onEditMethod(data)"
          />
          <Button
            v-if="!data.archived"
            icon="mdi mdi-archive-outline"
            size="small"
            severity="danger"
            text
            :disabled="!canDelete"
            v-tooltip.top.focus="t('common.archive')"
            :aria-label="t('common.archive')"
            @click.stop="onArchiveMethod(data)"
          />
          <Button
            v-else
            icon="mdi mdi-archive-arrow-up-outline"
            size="small"
            severity="secondary"
            text
            :disabled="!canDelete"
            v-tooltip.top.focus="t('common.restore')"
            :aria-label="t('common.restore')"
            @click.stop="onRestoreMethod(data)"
          />
        </div>
      </template>
    </Column>
    <Column header="#" header-style="width: 3rem" body-class="row-number">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>
    <Column
      field="name"
      :header="t('resources.inspectionMethods.columns.name')"
      :show-filter-menu="false"
      sortable
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.inspectionMethods.filters.name')"
          :aria-label="t('common.filterBy', { column: t('resources.inspectionMethods.columns.name') })"
          size="small"
          fluid
        />
      </template>
      <template #body="{ data }: { data: InspectionMethodResponse }">{{ localize(data.name) }}</template>
    </Column>
    <Column
      field="description"
      :header="t('resources.inspectionMethods.columns.description')"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: InspectionMethodResponse }">
        <span v-if="localize(data.description)">{{ localize(data.description) }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('resources.inspectionMethods.columns.label')" style="width: 10rem">
      <template #body="{ data }: { data: InspectionMethodResponse }">
        <LabelTag :label="data" />
      </template>
    </Column>
    <!-- A dash means no default, so a step carries no estimate. -->
    <Column
      :header="t('resources.inspectionMethods.columns.defaultDurations')"
      style="width: 11rem"
    >
      <template #body="{ data }: { data: InspectionMethodResponse }">
        <span
          v-if="data.default_setup_minutes !== null || data.default_minutes_per_piece !== null"
        >
          {{ data.default_setup_minutes ?? 0 }}
          {{ t('resources.inspectionMethods.columns.minSetupShort') }}
          &middot;
          {{ data.default_minutes_per_piece ?? 0 }}
          {{ t('resources.inspectionMethods.columns.minPerPieceShort') }}
        </span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <!-- A dash means the QA step stays manual work without a machine. -->
    <Column
      :header="t('resources.inspectionMethods.columns.defaultMachine')"
      style="width: 11rem"
    >
      <template #body="{ data }: { data: InspectionMethodResponse }">
        <span v-if="data.default_machine_name">{{ data.default_machine_name }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>

    <Column :header="t('resources.inspectionMethods.columns.flags')" style="width: 9rem">
      <template #body="{ data }: { data: InspectionMethodResponse }">
        <div class="flag-tags">
          <Tag
            v-if="data.requires_evidence"
            :value="t('resources.inspectionMethods.requiresEvidenceTag')"
            severity="info"
            icon="mdi mdi-file-document-outline"
            v-tooltip.top="t('resources.inspectionMethods.requiresEvidenceTagTooltip')"
          />
          <Tag
            v-if="data.archived"
            :value="t('common.archivedTag')"
            severity="warn"
            icon="mdi mdi-archive-outline"
            v-tooltip.top="t('resources.inspectionMethods.archivedTagTooltip')"
          />
          <span v-if="!data.requires_evidence && !data.archived" class="text-muted">{{
            getEmptyPlaceholder()
          }}</span>
        </div>
      </template>
    </Column>
    <Column
      field="created"
      :header="t('resources.inspectionMethods.columns.created')"
      sortable
      style="width: 8rem"
    >
      <template #body="{ data }: { data: InspectionMethodResponse }">
        <UserDateCell :date="data.created" :user="data.creator" />
      </template>
    </Column>
    <Column :header="t('resources.inspectionMethods.columns.changed')" style="width: 8rem">
      <template #body="{ data }: { data: InspectionMethodResponse }">
        <UserDateCell :date="data.changed" :user="data.changed_by" />
      </template>
    </Column>
    <Column style="width: 100%" />
  </DataTable>

  <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />

  <InspectionMethodFormDialog
    v-model:visible="editDialogVisible"
    :method="editingMethod"
    @saved="onSaved"
  />

  <ResourceDetailDialog
    v-model:visible="detailDialogVisible"
    :title="t('resources.inspectionMethods.showDetails')"
    :fields="detailFields"
  />
</template>

<style scoped lang="scss">
.inspection-methods-table {
  width: 100%;
}

.inspection-methods-rows-clickable {
  :deep(.p-datatable-tbody) > tr {
    cursor: pointer;
  }
}

.flag-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
</style>
