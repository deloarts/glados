<script setup lang="ts">
import { onMounted, ref, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { storeToRefs } from 'pinia'
import type { DataTableSortEvent } from 'openvue/datatable'
import { formatISODate as formatDate } from '@/core/utils/dates'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useServerTable } from '@/core/composables/useServerTable'
import { useManagementResourceActions } from '@/shared/composables/useManagementResourceActions'

import { useSuppliersStore } from '@/features/suppliers'
import FabricationMethodFormDialog from './FabricationMethodFormDialog.vue'
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
import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import type { FabricationMethodResponse, FabricationMethodSortBy } from '@/features/fabrication-methods'

const { t } = useI18n()
const { localize } = useLocalizedText()
const toast = useAppToast()

const store = useFabricationMethodsStore()
const { tableItems: items, loading, filters, clearTrigger, search, sortBy, sortDir, showArchived } =
  storeToRefs(store)
watchLoadingBar(loading)
const suppliersStore = useSuppliersStore()
onMounted(() => {
  if (suppliersStore.items.length === 0) {
    void suppliersStore.refresh()
  }
})
function supplierName(supplierId: number | null): string | null {
  if (supplierId === null) return null
  return suppliersStore.getById(supplierId)?.name ?? null
}
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const canWrite = computed(() => hasPermission(Permission.WRITE_FABRICATION_METHODS))
const canDelete = computed(() => hasPermission(Permission.WRITE_FABRICATION_METHODS))

const editDialogVisible = ref(false)
const editingMethod = ref<FabricationMethodResponse | undefined>(undefined)

function onEditMethod(method: FabricationMethodResponse): void {
  editingMethod.value = method
  editDialogVisible.value = true
}

function onSaved(method: FabricationMethodResponse): void {
  toast.success(localize(method.name), t('resources.fabricationMethods.editMethod'))
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
} = useManagementResourceActions<FabricationMethodResponse>(store, {
  i18nPrefix: 'resources.fabricationMethods',
  entityLabel: (method) => localize(method.name),
  deletePermission: Permission.WRITE_FABRICATION_METHODS,
  archivable: { isArchived: (method) => method.archived },
  editItem: (method) => ({
    label: t('resources.fabricationMethods.editMethod'),
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
      event.sortField as FabricationMethodSortBy,
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
    { label: t('resources.fabricationMethods.columns.name'), value: localize(m.name) },
    { label: t('resources.fabricationMethods.columns.description'), value: localize(m.description) || null },
    {
      label: t('resources.fabricationMethods.columns.creator'),
      value: m.creator?.full_name ?? null,
    },
    { label: t('resources.fabricationMethods.columns.created'), value: formatDate(m.created) },
    {
      label: t('resources.fabricationMethods.columns.changed'),
      value: formatDate(m.changed),
    },
    {
      label: t('resources.fabricationMethods.columns.requiredExternal'),
      value: m.required_external ? t('common.yes') : t('common.no'),
    },
    {
      label: t('resources.fabricationMethods.columns.defaultSupplier'),
      value: supplierName(m.default_supplier_id),
    },
    {
      label: t('resources.fabricationMethods.columns.waitAfterMinutes'),
      value: m.wait_after_minutes === null ? null : String(m.wait_after_minutes),
    },
    {
      label: t('resources.fabricationMethods.columns.defaultForAssemblies'),
      value: m.default_for_assemblies ? t('common.yes') : t('common.no'),
    },
    {
      label: t('resources.fabricationMethods.columns.archived'),
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
    class="fabrication-methods-table fabrication-methods-rows-clickable"
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
      :header="t('resources.fabricationMethods.columns.actions')"
      class="column-fit"
    >
      <template #body="{ data }: { data: FabricationMethodResponse }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            :disabled="!canWrite"
            v-tooltip.top.focus="t('resources.fabricationMethods.editMethod')"
            :aria-label="t('resources.fabricationMethods.editMethod')"
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
      :header="t('resources.fabricationMethods.columns.name')"
      :show-filter-menu="false"
      sortable
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('resources.fabricationMethods.filters.name')"
          :aria-label="t('common.filterBy', { column: t('resources.fabricationMethods.columns.name') })"
          size="small"
          fluid
        />
      </template>
      <template #body="{ data }: { data: FabricationMethodResponse }">{{ localize(data.name) }}</template>
    </Column>
    <Column
      field="description"
      :header="t('resources.fabricationMethods.columns.description')"
      :show-filter-menu="false"
    >
      <template #body="{ data }: { data: FabricationMethodResponse }">
        <span v-if="localize(data.description)">{{ localize(data.description) }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('resources.fabricationMethods.columns.label')" style="width: 10rem">
      <template #body="{ data }: { data: FabricationMethodResponse }">
        <LabelTag :label="data" />
      </template>
    </Column>
    <Column
      :header="t('resources.fabricationMethods.columns.requiresMachine')"
      style="width: 8rem"
    >
      <template #body="{ data }: { data: FabricationMethodResponse }">
        <Tag
          v-if="!data.requires_machine"
          :value="t('resources.fabricationMethods.manualTag')"
          severity="secondary"
          icon="mdi mdi-hand-back-right-outline"
          v-tooltip.top="t('resources.fabricationMethods.manualTagTooltip')"
        />
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('resources.fabricationMethods.columns.flags')" style="width: 9rem">
      <template #body="{ data }: { data: FabricationMethodResponse }">
        <div class="flag-tags">
          <Tag
            v-if="data.required_external"
            :value="t('resources.fabricationMethods.externalTag')"
            severity="info"
            icon="mdi mdi-truck-outline"
            v-tooltip.top="t('resources.fabricationMethods.externalTagTooltip')"
          />
          <Tag
            v-if="data.default_for_assemblies"
            :value="t('resources.fabricationMethods.assemblyDefaultTag')"
            severity="success"
            icon="mdi mdi-star-outline"
            v-tooltip.top="t('resources.fabricationMethods.assemblyDefaultTagTooltip')"
          />
          <Tag
            v-if="data.archived"
            :value="t('common.archivedTag')"
            severity="warn"
            icon="mdi mdi-archive-outline"
            v-tooltip.top="t('resources.fabricationMethods.archivedTagTooltip')"
          />
          <span
            v-if="!data.required_external && !data.default_for_assemblies && !data.archived"
            class="text-muted"
            >{{ getEmptyPlaceholder() }}</span
          >
        </div>
      </template>
    </Column>
    <Column
      :header="t('resources.fabricationMethods.columns.defaultSupplier')"
      style="width: 10rem"
    >
      <template #body="{ data }: { data: FabricationMethodResponse }">
        <span v-if="supplierName(data.default_supplier_id)">{{
          supplierName(data.default_supplier_id)
        }}</span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column
      field="created"
      :header="t('resources.fabricationMethods.columns.created')"
      sortable
      style="width: 8rem"
    >
      <template #body="{ data }: { data: FabricationMethodResponse }">
        <UserDateCell :date="data.created" :user="data.creator" />
      </template>
    </Column>
    <Column :header="t('resources.fabricationMethods.columns.changed')" style="width: 8rem">
      <template #body="{ data }: { data: FabricationMethodResponse }">
        <UserDateCell :date="data.changed" :user="data.changed_by" />
      </template>
    </Column>
    <Column style="width: 100%" />
  </DataTable>

  <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />

  <FabricationMethodFormDialog
    v-model:visible="editDialogVisible"
    :method="editingMethod"
    @saved="onSaved"
  />

  <ResourceDetailDialog
    v-model:visible="detailDialogVisible"
    :title="t('resources.fabricationMethods.showDetails')"
    :fields="detailFields"
  />
</template>

<style scoped lang="scss">
.fabrication-methods-table {
  width: 100%;
}

.fabrication-methods-rows-clickable {
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
