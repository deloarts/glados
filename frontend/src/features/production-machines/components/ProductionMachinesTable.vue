<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'

import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useProductionMachinesStore } from '../stores/productionMachinesStore'
import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { useServerTable } from '@/core/composables/useServerTable'
import { filterMetaValue } from '@/core/utils/filterMeta'
import { useFilterMetaWatch } from '@/shared/composables/useFilterMetaWatch'
import { useFilterMetaModel } from '@/shared/composables/useFilterMetaModel'
import { useManagementResourceActions } from '@/shared/composables/useManagementResourceActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useRowDragReorder } from '@/shared/composables/useRowDragReorder'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'
import { machineStatus, machineStatusSeverity, machineStatusTooltip } from '../utils/machineStatus'

import type { ProductionMachineResponse } from '../types/productionMachinesResponse'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { groupRowsByLabel } from '@/core/utils/tableRowGrouping'
import { labelName, localizeLabel } from '@/shared/utils/localizeLabel'
import LabelTag from '@/shared/components/labels/LabelTag.vue'

const emit = defineEmits<{
  edit: [machine: ProductionMachineResponse]
  manageCalendar: [machine: ProductionMachineResponse]
  addDowntime: [machine: ProductionMachineResponse]
}>()

const { t } = useI18n()
const router = useRouter()
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const store = useProductionMachinesStore()
const { filters, search, sortBy, sortDir, groupBy, showActions, showArchived } = storeToRefs(store)
const creatorId = useFilterMetaModel<number>(filters, 'creator_id')
watchLoadingBar(() => store.loading)

const fabricationMethodsStore = useFabricationMethodsStore()

// Filter option lists load when their dropdown first opens, or on mount when
// a filter kept in the store from an earlier visit needs its label resolved.
function ensureFabricationMethods(): void {
  if (fabricationMethodsStore.items.length === 0) {
    void fabricationMethodsStore.refresh()
  }
}

onMounted(() => {
  if (filterMetaValue(filters.value, 'fabrication_method_id') != null) ensureFabricationMethods()
})

const canWrite = computed(() => hasPermission(Permission.WRITE_MACHINES))
const canDelete = computed(() => hasPermission(Permission.WRITE_MACHINES))
const { missing } = useMissingPermission()

// A machine with queued, in-progress or paused orders is not archived; the
// boards would lose those orders with it.
function archiveBlockedReason(machine: ProductionMachineResponse): string {
  return machine.live_order_count
    ? t('productionMachines.archiveBlocked', machine.live_order_count)
    : ''
}

function archiveTooltip(machine: ProductionMachineResponse): string {
  return (
    missing(Permission.WRITE_MACHINES) || archiveBlockedReason(machine) || t('common.archive')
  )
}

// The grip in the first column drags a row to a new place in the hand-kept
// order pickers offer. It shows only to users who may reorder, and only
// while the table shows that order, since a sorted, searched, grouped or filtered
// page has other neighbours than the order a drop would change.
const showDragHandle = computed(() => canWrite.value && store.manualOrder && !groupBy.value)
const { handlePt, onRowReorder } = useRowDragReorder(
  () => store.tableItems,
  (id, target, page) => store.place(id, target, page),
)

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: ({ first, rows }) => ({ skip: first, limit: rows }),
  fetch: (params) => store.refreshTable(params),
})

watch(search, resetAndFetchDebounced)

// Typed text filters are debounced, dropdown filters fetch right away.
useFilterMetaWatch(filters, ['internal_name', 'vendor', 'model'], resetAndFetchDebounced)
useFilterMetaWatch(filters, ['fabrication_method_id', 'creator_id'], resetAndFetch)

watch(showArchived, resetAndFetch)

watch([sortBy, sortDir], () => fetchItems())

watch(
  () => store.refreshTrigger,
  () => fetchItems(),
)

const groupedItems = computed(() => {
  if (groupBy.value !== 'capability') return store.tableItems

  return groupRowsByLabel(
    store.tableItems,
    '_capabilityGroup',
    (item) => localizeLabel(item.fabrication_methods[0]?.name) || getEmptyPlaceholder(),
  )
})

defineExpose({ refresh: fetchItems })

function statusTooltip(machine: ProductionMachineResponse): string {
  return machineStatusTooltip(machine, t)
}

// The machine page belongs to the production feature.
function openDetail(machine: ProductionMachineResponse): void {
  void router.push(`/production/machines/${machine.id}`)
}

function onEdit(machine: ProductionMachineResponse): void {
  emit('edit', machine)
}

function onManageCalendar(machine: ProductionMachineResponse): void {
  emit('manageCalendar', machine)
}

function onAddDowntime(machine: ProductionMachineResponse): void {
  emit('addDowntime', machine)
}

// Context menu and the archive confirm come from useManagementResourceActions.
// The machine page replaces a detail dialog, so the menu opens with its link.
const {
  cm,
  contextMenuTarget: contextMenuItem,
  contextMenuItems,
  onRowContextMenu,
  onDelete: onArchive,
  onRestore,
} = useManagementResourceActions<ProductionMachineResponse>(store, {
  i18nPrefix: 'productionMachines',
  entityLabel: (machine) => machine.internal_name,
  deletePermission: Permission.WRITE_MACHINES,
  deleteBlockedReason: archiveBlockedReason,
  archivable: { isArchived: (machine) => machine.archived },
  showDetailItem: false,
  extraItems: (machine) => [
    {
      label: t('productionMachines.viewMachine'),
      icon: 'mdi mdi-open-in-new',
      command: () => openDetail(machine),
    },
    { separator: true },
    {
      label: t('productionMachines.editMachine'),
      icon: 'mdi mdi-pencil',
      disabled: !canWrite.value,
      command: () => onEdit(machine),
    },
    {
      label: t('productionMachines.calendar.manage'),
      icon: 'mdi mdi-calendar-clock',
      command: () => onManageCalendar(machine),
    },
    {
      label: t('productionMachines.downtime.addDowntime'),
      icon: 'mdi mdi-alert-octagon-outline',
      disabled: !canWrite.value,
      command: () => onAddDowntime(machine),
    },
  ],
})
</script>

<template>
  <DataTable
    :value="groupedItems"
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
    :row-group-mode="groupBy ? 'subheader' : undefined"
    group-rows-by="_capabilityGroup"
    resizable-columns
    column-resize-mode="fit"
    v-model:context-menu-selection="contextMenuItem"
    @row-reorder="onRowReorder"
    @row-contextmenu="onRowContextMenu"
  >
    <template v-if="groupBy" #groupheader="{ data }">
      <div class="group-header">
        <i class="mdi mdi-cog-outline" aria-hidden="true" />
        <span class="group-header-label">{{ data._capabilityGroup }}</span>
      </div>
    </template>

    <Column
      v-if="showDragHandle"
      row-reorder
      row-reorder-icon="mdi mdi-drag-vertical"
      :pt="handlePt"
      class="column-fit"
    />
    <Column
      v-if="showActions"
      :header="t('productionMachines.columns.actions')"
      class="column-fit"
    >
      <template #body="{ data }">
        <div class="row-actions">
          <Button
            icon="mdi mdi-open-in-new"
            size="small"
            severity="secondary"
            text
            v-tooltip.top.focus="t('productionMachines.viewMachine')"
            :aria-label="t('productionMachines.viewMachine')"
            @click="openDetail(data as ProductionMachineResponse)"
          />
          <Button
            icon="mdi mdi-calendar-clock"
            size="small"
            severity="secondary"
            text
            v-tooltip.top.focus="t('productionMachines.calendar.manage')"
            :aria-label="t('productionMachines.calendar.manage')"
            @click="onManageCalendar(data as ProductionMachineResponse)"
          />
          <Button
            icon="mdi mdi-pencil"
            size="small"
            severity="secondary"
            text
            :disabled="!canWrite"
            v-tooltip.top.focus="t('productionMachines.editMachine')"
            :aria-label="t('productionMachines.editMachine')"
            @click="onEdit(data as ProductionMachineResponse)"
          />
          <Button
            v-if="(data as ProductionMachineResponse).archived"
            icon="mdi mdi-archive-arrow-up-outline"
            size="small"
            severity="secondary"
            text
            :disabled="!canDelete"
            v-tooltip.top.focus="t('common.restore')"
            :aria-label="t('common.restore')"
            @click="onRestore(data as ProductionMachineResponse)"
          />
          <span v-else v-tooltip.top="archiveTooltip(data as ProductionMachineResponse)">
            <Button
              icon="mdi mdi-archive-outline"
              size="small"
              severity="danger"
              text
              :disabled="!canDelete || (data as ProductionMachineResponse).live_order_count > 0"
              :aria-label="t('common.archive')"
              @click="onArchive(data as ProductionMachineResponse)"
            />
          </span>
        </div>
      </template>
    </Column>

    <Column header="#" header-style="width: 3rem" body-class="row-number">
      <template #body="{ index }">{{ first + index + 1 }}</template>
    </Column>
    <Column
      field="internal_name"
      :header="t('productionMachines.columns.internalName')"
      :show-filter-menu="false"
      style="min-width: 10rem"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('productionMachines.filters.filterBy')"
          :aria-label="t('common.filterBy', { column: t('productionMachines.columns.internalName') })"
          size="small"
          fluid
        />
      </template>
      <template #body="{ data }">
        <!-- The name link is the always-visible way to the machine's page. -->
        <RouterLink
          class="machine-link"
          :to="`/production/machines/${(data as ProductionMachineResponse).id}`"
          @click.stop
          >{{ (data as ProductionMachineResponse).internal_name }}</RouterLink
        >
      </template>
    </Column>
    <Column
      field="status"
      :header="t('productionMachines.columns.status')"
      style="width: 9rem"
    >
      <template #body="{ data }">
        <Tag
          :value="t(`productionMachines.status.${machineStatus(data as ProductionMachineResponse)}`)"
          :severity="machineStatusSeverity[machineStatus(data as ProductionMachineResponse)]"
          :class="{ 'status-tag-muted': (data as ProductionMachineResponse).archived }"
          v-tooltip.top="statusTooltip(data as ProductionMachineResponse)"
        />
      </template>
    </Column>
    <Column
      field="vendor"
      :header="t('productionMachines.columns.vendor')"
      :show-filter-menu="false"
      style="min-width: 8rem"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('productionMachines.filters.filterBy')"
          :aria-label="t('common.filterBy', { column: t('productionMachines.columns.vendor') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      field="model"
      :header="t('productionMachines.columns.model')"
      :show-filter-menu="false"
      style="min-width: 8rem"
    >
      <template #filter="{ filterModel, filterCallback }">
        <InputText
          v-model="filterModel.value"
          @input="filterCallback()"
          :placeholder="t('productionMachines.filters.filterBy')"
          :aria-label="t('common.filterBy', { column: t('productionMachines.columns.model') })"
          size="small"
          fluid
        />
      </template>
    </Column>
    <Column
      filter-field="fabrication_method_id"
      :header="t('productionMachines.columns.capabilities')"
      :show-filter-menu="false"
      style="min-width: 14rem"
    >
      <template #filter="{ filterModel, filterCallback }">
        <Select
          v-model="filterModel.value"
          :options="fabricationMethodsStore.items"
          :option-label="labelName"
          option-value="id"
          :loading="fabricationMethodsStore.loading"
          show-clear
          filter
          :placeholder="t('productionMachines.filters.any')"
          :aria-label="
            t('common.filterBy', { column: t('productionMachines.columns.capabilities') })
          "
          size="small"
          fluid
          @before-show="ensureFabricationMethods"
          @change="filterCallback()"
        />
      </template>
      <template #body="{ data }">
        <div class="capability-tags">
          <Tag
            v-if="(data as ProductionMachineResponse).is_qa_machine"
            severity="info"
            icon="mdi mdi-check-decagram"
            :value="t('productionMachines.qaMachineTag')"
            v-tooltip.top="t('productionMachines.qaMachineTooltip')"
          />
          <LabelTag
            v-for="method in (data as ProductionMachineResponse).fabrication_methods"
            :key="method.id"
            :label="method"
          />
          <Tag
            v-if="(data as ProductionMachineResponse).archived"
            :value="t('common.archivedTag')"
            severity="warn"
            icon="mdi mdi-archive-outline"
            v-tooltip.top="t('common.archivedTagTooltip')"
          />
          <span
            v-if="
              (data as ProductionMachineResponse).fabrication_methods.length === 0 &&
              !(data as ProductionMachineResponse).is_qa_machine &&
              !(data as ProductionMachineResponse).archived
            "
            class="text-muted"
            >{{ getEmptyPlaceholder() }}</span
          >
        </div>
      </template>
    </Column>
    <Column :header="t('productionMachines.columns.maxPartDimension')" style="width: 10rem">
      <template #body="{ data }">
        <span v-if="(data as ProductionMachineResponse).max_part_dimension">
          {{ (data as ProductionMachineResponse).max_part_dimension }}
        </span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column :header="t('productionMachines.columns.note')" style="min-width: 10rem">
      <template #body="{ data }">
        <span v-if="(data as ProductionMachineResponse).note">
          {{ (data as ProductionMachineResponse).note }}
        </span>
        <span v-else class="text-muted">{{ getEmptyPlaceholder() }}</span>
      </template>
    </Column>
    <Column
      filter-field="creator_id"
      :header="t('productionMachines.columns.created')"
      :show-filter-menu="false"
      style="width: 10rem"
    >
      <template #body="{ data }">
        <UserDateCell
          :date="(data as ProductionMachineResponse).created"
          :user-id="(data as ProductionMachineResponse).creator_id"
          :name="(data as ProductionMachineResponse).creator_full_name"
        />
      </template>
      <template #filter>
        <UserDateFilter
          v-model:user-id="creatorId"
          :column="t('productionMachines.columns.created')"
          :placeholder="t('productionMachines.filters.any')"
          user-only
        />
      </template>
    </Column>
    <Column style="width: 100%" />

    <template #empty>
      <EmptyState :message="t('productionMachines.table.empty')" />
    </template>
  </DataTable>

  <ContextMenu
    ref="cm"
    :model="contextMenuItems"
    :pt="disabledItemTooltipPt"
    @hide="contextMenuItem = null"
  />
</template>

<style scoped lang="scss">
.group-header-label {
  font-weight: bold;
  padding-left: var(--space-4);
}

// Plain cell text; hover reveals the link.
.machine-link {
  color: inherit;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.capability-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

// Muted, so an archived row does not compete with a live machine's state.
.status-tag-muted {
  opacity: 0.6;
}
</style>
