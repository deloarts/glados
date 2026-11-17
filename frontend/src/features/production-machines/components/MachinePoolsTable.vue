<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { storeToRefs } from 'pinia'

import { API_MAX_PAGE_SIZE, TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useMachinePoolsStore } from '../stores/machinePoolsStore'
import { getProductionMachines } from '../api/getProductionMachines'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useServerTable } from '@/core/composables/useServerTable'
import { filterMetaValue } from '@/core/utils/filterMeta'
import { useFilterMetaWatch } from '@/shared/composables/useFilterMetaWatch'
import { useFilterMetaModel } from '@/shared/composables/useFilterMetaModel'
import { useManagementResourceActions } from '@/shared/composables/useManagementResourceActions'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useRowDragReorder } from '@/shared/composables/useRowDragReorder'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'

import type { MachinePoolResponse } from '../types/machinePoolsResponse'
import type { ProductionMachineResponse } from '../types/productionMachinesResponse'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'

const emit = defineEmits<{
  edit: [pool: MachinePoolResponse]
}>()

const { t } = useI18n()
const toast = useAppToast()
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const store = useMachinePoolsStore()
const { filters, search, sortBy, sortDir, showActions, showArchived } = storeToRefs(store)
const creatorId = useFilterMetaModel<number>(filters, 'creator_id')
watchLoadingBar(() => store.loading)

// Fetched directly, since the machines store holds only the table's page.
// Archived machines are included, since a pool can reference one.
const machineOptions = ref<ProductionMachineResponse[]>([])
const machineOptionsLoading = ref(false)

// Filter option lists load when their dropdown first opens, or on mount when
// a filter kept in the store from an earlier visit needs its label resolved.
async function ensureMachineOptions(): Promise<void> {
  if (machineOptions.value.length > 0 || machineOptionsLoading.value) return
  machineOptionsLoading.value = true
  try {
    const result = await getProductionMachines({
      limit: API_MAX_PAGE_SIZE,
      include_archived: true,
      order_by: 'internal_name',
      order_dir: 'asc',
    })
    machineOptions.value = result.items
  } catch {
    toast.error(t('productionMachinePools.errors.unknown'))
  } finally {
    machineOptionsLoading.value = false
  }
}

onMounted(() => {
  if (filterMetaValue(filters.value, 'machine_id') != null) void ensureMachineOptions()
})

const canWrite = computed(() => hasPermission(Permission.WRITE_MACHINES))
const canDelete = computed(() => hasPermission(Permission.WRITE_MACHINES))

// The grip in the first column drags a row to a new place in the hand-kept
// order the pool lists and pickers show. It shows only to users who may
// reorder, and only while the table shows that order, since a sorted,
// searched or filtered page has other neighbours than the order a drop
// would change.
const showDragHandle = computed(() => canWrite.value && store.manualOrder)
const { handlePt, onRowReorder } = useRowDragReorder(
  () => store.tableItems,
  (id, target, page) => store.place(id, target, page),
)

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: ({ first, rows }) => ({ skip: first, limit: rows }),
  fetch: (params) => store.refreshTable(params),
})

watch(search, resetAndFetchDebounced)

// The typed name filter is debounced, dropdown filters fetch right away.
useFilterMetaWatch(filters, ['name'], resetAndFetchDebounced)
useFilterMetaWatch(filters, ['machine_id', 'creator_id'], resetAndFetch)

watch(showArchived, resetAndFetch)

watch([sortBy, sortDir], () => fetchItems())

watch(
  () => store.refreshTrigger,
  () => fetchItems(),
)

defineExpose({ refresh: fetchItems })

function onEdit(pool: MachinePoolResponse): void {
  emit('edit', pool)
}

// Context menu and the archive confirm come from useManagementResourceActions.
// Pools have no detail dialog, so the menu opens with the edit entry.
const {
  cm,
  contextMenuTarget: contextMenuItem,
  contextMenuItems,
  onRowContextMenu,
  onDelete: onArchive,
  onRestore,
} = useManagementResourceActions<MachinePoolResponse>(store, {
  i18nPrefix: 'productionMachinePools',
  entityLabel: (pool) => pool.name,
  deletePermission: Permission.WRITE_MACHINES,
  archivable: { isArchived: (pool) => pool.archived },
  showDetailItem: false,
  extraItems: (pool) => [
    {
      label: t('productionMachinePools.editPool'),
      icon: 'mdi mdi-pencil',
      disabled: !canWrite.value,
      command: () => onEdit(pool),
    },
  ],
})
</script>

<template>
  <DataTable
    :value="store.tableItems"
    v-model:filters="filters"
    filter-display="row"
    data-key="id"
    lazy
    paginator
    :total-records="store.total"
    :first="first"
    :rows="rows"
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    @page="onPage"
    scrollable
    scroll-height="flex"
    size="small"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    resizable-columns
    column-resize-mode="fit"
    v-model:context-menu-selection="contextMenuItem"
    @row-reorder="onRowReorder"
    @row-contextmenu="onRowContextMenu"
  >
    <Column
      v-if="showDragHandle"
      row-reorder
      row-reorder-icon="mdi mdi-drag-vertical"
      :pt="handlePt"
      class="column-fit"
    />
    <Column
      v-if="showActions"
      :header="t('productionMachinePools.columns.actions')"
      class="column-fit"
    >
      <template #body="{ data }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            :disabled="!canWrite"
            v-tooltip.top.focus="t('productionMachinePools.editPool')"
            :aria-label="t('productionMachinePools.editPool')"
            @click="onEdit(data as MachinePoolResponse)"
          />
          <Button
            v-if="(data as MachinePoolResponse).archived"
            icon="mdi mdi-archive-arrow-up-outline"
            size="small"
            severity="secondary"
            text
            :disabled="!canDelete"
            v-tooltip.top.focus="t('common.restore')"
            :aria-label="t('common.restore')"
            @click="onRestore(data as MachinePoolResponse)"
          />
          <Button
            v-else
            icon="mdi mdi-archive-outline"
            size="small"
            severity="danger"
            text
            :disabled="!canDelete"
            v-tooltip.top.focus="t('common.archive')"
            :aria-label="t('common.archive')"
            @click="onArchive(data as MachinePoolResponse)"
          />
        </div>
      </template>
    </Column>
    <Column header="#" header-style="width: 3rem" body-class="row-number">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>
    <Column
      field="name"
      :header="t('productionMachinePools.columns.name')"
      :show-filter-menu="false"
      style="min-width: 10rem"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('productionMachinePools.filters.filterBy')"
          :aria-label="t('common.filterBy', { column: t('productionMachinePools.columns.name') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      filter-field="machine_id"
      :header="t('productionMachinePools.columns.machines')"
      :show-filter-menu="false"
      style="min-width: 14rem"
    >
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="machineOptions"
          option-label="internal_name"
          option-value="id"
          :loading="machineOptionsLoading"
          show-clear
          filter
          :placeholder="t('productionMachinePools.filters.any')"
          :aria-label="
            t('common.filterBy', { column: t('productionMachinePools.columns.machines') })
          "
          size="small"
          fluid
          @before-show="ensureMachineOptions"
          @change="filterCallback()"
        />
      </template>
      <template #body="{ data }">
        <div class="machine-tags">
          <Tag
            v-for="machine in (data as MachinePoolResponse).machines"
            :key="machine.id"
            :value="machine.internal_name"
          />
          <span v-if="(data as MachinePoolResponse).machines.length === 0" class="text-muted">{{
            getEmptyPlaceholder()
          }}</span>
        </div>
      </template>
    </Column>
    <Column v-if="showArchived" :header="t('common.archivedTag')" style="width: 8rem">
      <template #body="{ data }">
        <Tag
          v-if="(data as MachinePoolResponse).archived"
          :value="t('common.archivedTag')"
          severity="warn"
          icon="mdi mdi-archive-outline"
          v-tooltip.top="t('common.archivedTagTooltip')"
        />
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('productionMachinePools.columns.note')" style="min-width: 10rem">
      <template #body="{ data }">
        <span v-if="(data as MachinePoolResponse).note">
          {{ (data as MachinePoolResponse).note }}
        </span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column
      filter-field="creator_id"
      :header="t('productionMachinePools.columns.created')"
      :show-filter-menu="false"
      style="width: 10rem"
    >
      <template #body="{ data }">
        <UserDateCell
          :date="(data as MachinePoolResponse).created"
          :user-id="(data as MachinePoolResponse).creator_id"
          :name="(data as MachinePoolResponse).creator_full_name"
        />
      </template>
      <template #filter>
        <UserDateFilter
          v-model:user-id="creatorId"
          :column="t('productionMachinePools.columns.created')"
          :placeholder="t('productionMachinePools.filters.any')"
          user-only
        />
      </template>
    </Column>
    <Column style="width: 100%" />

    <template #empty>
      <EmptyState :message="t('productionMachinePools.table.empty')" />
    </template>
  </DataTable>

  <ContextMenu ref="cm" :model="contextMenuItems" @hide="contextMenuItem = null" />
</template>

<style scoped lang="scss">
.machine-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}
</style>
