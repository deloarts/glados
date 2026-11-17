<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { useClipboard } from '@/core/composables/useClipboard'
import { useAppToast } from '@/core/composables/useAppToast'
import { FilterMatchMode } from '@openvue/core/api'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { useMadeItemsDemandsFiltersStore } from '../stores/madeItemsDemandsFiltersStore'
import { STEP_METHOD_SEPARATOR } from '../utils/stepMethodFilter'
import { useMadeItemDemandsQuery } from '../composables/useMadeItemDemandsQuery'
import { useMadeItemsAllocationsStore } from '../stores/madeItemsAllocationsStore'
import { useMadeItemsProcurementStore } from '../stores/madeItemsProcurementStore'
import { useBucketsStore, BucketTag, BucketFilterSelect } from '@/features/buckets'
import { fabricationMethodLabel, useFabricationMethodsStore } from '@/features/fabrication-methods'
import { inspectionMethodLabel, useInspectionMethodsStore } from '@/features/inspection-methods'
import LookupMultiSelect from '@/shared/components/forms/LookupMultiSelect.vue'
import type { LookupOption } from '@/shared/components/forms/lookupMultiSelect'
import { LiveResource } from '@/core/realtime/resources'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'

import MadeItemDemandDetailDialog from './MadeItemDemandDetailDialog.vue'
import MadeItemDemandCancelDialog from './MadeItemDemandCancelDialog.vue'
import MadeItemDemandFulfillFromStockDialog from './MadeItemDemandFulfillFromStockDialog.vue'
import LotCreateDialog from '../../lots/components/LotCreateDialog.vue'
import { getLots } from '../../api/getLots'
import { useLotNumberCache } from '../../lots/composables/useLotNumberCache'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useRowOpenGuard } from '@/core/composables/useRowOpenGuard'
import WithValue from '@/shared/components/WithValue.vue'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { useDialogTarget } from '@/shared/composables/useDialogTarget'
import {
  bulkStatusFailureToast,
  useDemandRowActions,
} from '@/shared/composables/useDemandRowActions'
import { useDemandTableData } from '@/shared/composables/useDemandTableData'
import { useDemandGrouping } from '@/shared/composables/useDemandGrouping'
import DemandsTableShell from '@/shared/components/demands/DemandsTableShell.vue'
import LookupSelect from '@/shared/components/forms/LookupSelect.vue'
import {
  fetchDemandProjectOptions,
  fetchDemandProjectsByIds,
} from '@/shared/components/demands/demandProjectLookup'
import DemandStatusTag from '@/shared/components/demands/DemandStatusTag.vue'
import DemandQuantityCell from '@/shared/components/demands/DemandQuantityCell.vue'
import { demandBucketMenuItems } from '@/shared/components/demands/demandBucketMenu'
import { demandContextMenu } from '@/shared/components/demands/demandContextMenu'
import { demandIdColumnDef, demandPriorityColumnDef } from '@/shared/components/demands/demandColumnDefs'

import type { DataTableFilterMeta } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'
import type { DemandsTableShellLabels } from '@/shared/components/demands/demandsTableShell'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { DEMAND_STATUSES, DEMAND_STATUS_SEVERITY, isEndedDemandStatus } from '@/core/utils/demandStatus'
import { formatUnit } from '@/shared/utils/units'
import {
  useMadeItemsDemandsStore,
  getMadeItemDemands,
  MadeItemThumbnailCell,
  useMadeItemLabel,
  MadeItemDetailDialog,
  useMadeItemDetail,
  groupMethodLabel,
  processGroups,
} from '@/features/made-items'
import type { MadeItemDemandResponse, MadeItemDemandStatus } from '@/features/made-items'

const { t, locale } = useI18n()
const { copyToClipboard } = useClipboard()
const toast = useAppToast()
const { withErrorToast, toastOnError } = useErrorToast()
const { hasPermission } = usePermissions()

const demandsStore = useMadeItemsDemandsStore()
const filtersStore = useMadeItemsDemandsFiltersStore()
const allocationsStore = useMadeItemsAllocationsStore()
const procurementStore = useMadeItemsProcurementStore()
const hostStore = useHostStore()
const bucketsStore = useBucketsStore()
const fabricationMethodsStore = useFabricationMethodsStore()
const inspectionMethodsStore = useInspectionMethodsStore()

// Bucket names and colors are needed even if the menu never opened.
onMounted(() => {
  void bucketsStore.fetch('made_item_demand')
})

// Method catalogues load the first time the picker opens.
function ensureStepMethodsLoaded(): void {
  if (fabricationMethodsStore.items.length === 0) void fabricationMethodsStore.refresh()
  if (inspectionMethodsStore.items.length === 0) void inspectionMethodsStore.refresh()
}

const lotNumberCache = useLotNumberCache()
const { openLotDetail } = useLotDetail()
const madeItemDetail = useMadeItemDetail()
const { format: madeItemLabel } = useMadeItemLabel()

// summaries is replaced wholesale, so a shallow watch suffices.
watch(
  () => allocationsStore.summaries,
  (summaries) => {
    for (const summary of Object.values(summaries)) {
      for (const lotId of summary.lot_ids ?? []) {
        lotNumberCache.ensureLoaded(lotId)
      }
    }
  },
)

const canWrite = computed(() => hasPermission(Permission.WRITE_DEMAND_ITEMS))
const canWriteAllocations = computed(() => hasPermission(Permission.WRITE_ALLOCATIONS))
const canWriteLots = computed(() => hasPermission(Permission.WRITE_LOTS))
// The status submenus offer only fulfilled and canceled, which are
// irreversible, so the backend's demand status rule reserves them for
// holders of both write:demand_items and manage:demand_items.
const canSetStatus = computed(
  () =>
    hasPermission(Permission.WRITE_DEMAND_ITEMS) && hasPermission(Permission.MANAGE_DEMAND_ITEMS),
)

const {
  search,
  idFilter,
  projectId,
  itemArticleName,
  statuses,
  highPriorityFilter,
  creatorFilter,
  showFulfilled,
  showCanceled,
  desiredFrom,
  desiredTo,
  createdFrom,
  createdTo,
  clearTrigger,
  notFullyAllocatedOnly,
  bucketIds,
  includeUnbucketed,
  stepMethods,
  lotIds,
  sortBy,
  sortDir,
  groupBy,
} = storeToRefs(filtersStore)

// Filtering is server-side; this object only exists because
// filterDisplay="row" throws without an entry per filterable column.
const filters: DataTableFilterMeta = {
  id: { value: null, matchMode: FilterMatchMode.EQUALS },
  status: { value: null, matchMode: FilterMatchMode.EQUALS },
  project_number: { value: null, matchMode: FilterMatchMode.CONTAINS },
  item_article_name: { value: null, matchMode: FilterMatchMode.CONTAINS },
  high_priority: { value: null, matchMode: FilterMatchMode.EQUALS },
  desired_delivery_date: { value: null, matchMode: FilterMatchMode.CONTAINS },
  created: { value: null, matchMode: FilterMatchMode.CONTAINS },
}

const selectedDemand = ref<MadeItemDemandResponse | null>(null)
const showDetail = ref(false)

const statusOptions = computed(() =>
  DEMAND_STATUSES.map((s) => ({ label: t(`madeItems.demands.status.${s}`), value: s })),
)

const { groupedItems, groupRowsBy } = useDemandGrouping({
  items: () => demandsStore.items,
  groupBy,
  statusLabel: (item) => t(`madeItems.demands.status.${item.status}`),
  bucketName: (item) =>
    item.bucket_id !== null && item.bucket_id !== undefined
      ? bucketsStore.byId.made_item_demand[item.bucket_id]?.name
      : undefined,
  unbucketedLabel: () => t('madeItems.demands.buckets.unbucketed'),
  ownGroups: { project: { field: '_projectGroup', label: (item) => item.project_number } },
})

const stepMethodOptions = computed(() => [
  {
    label: t('madeItems.demands.filters.fabricationMethods'),
    items: fabricationMethodsStore.activeItems.map((method) => ({
      label: fabricationMethodLabel(method),
      value: `fabrication${STEP_METHOD_SEPARATOR}${method.id}`,
    })),
  },
  {
    label: t('madeItems.demands.filters.inspectionMethods'),
    items: inspectionMethodsStore.activeItems.map((method) => ({
      label: inspectionMethodLabel(method),
      value: `inspection${STEP_METHOD_SEPARATOR}${method.id}`,
    })),
  },
])

function toLotOption(lot: { id: number; lot_number: string; made_item_article_name: string }): LookupOption {
  return { id: lot.id, label: lot.lot_number, sublabel: lot.made_item_article_name }
}

async function fetchLotOptions(query: string): Promise<LookupOption[]> {
  const response = await getLots({ search: query || undefined, limit: 15 })
  return response.items.map(toLotOption)
}

async function fetchLotsByIds(ids: number[]): Promise<LookupOption[]> {
  const response = await getLots({ ids })
  return response.items.map(toLotOption)
}

const priorityOptions = computed(() => [
  { label: t('madeItems.demands.filters.priorityAny'), value: null },
  { label: t('madeItems.demands.filters.priorityHigh'), value: true },
  { label: t('madeItems.demands.filters.priorityNormal'), value: false },
])

const desiredDateRange = useDateRangeFilter(desiredFrom, desiredTo)

const createdDateRange = useDateRangeFilter(createdFrom, createdTo)

// Filters without paging or sort, shared with the live row refetch and the export.
const { filterParams: buildFilterParams } = useMadeItemDemandsQuery()

const { items: liveItems, total: liveTotal } = storeToRefs(demandsStore)
// The Manage panels and the create-lot action work on selectedDemands, so
// the selection follows the list.
const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useDemandTableData({
  items: liveItems,
  total: liveTotal,
  loading: () => demandsStore.loading,
  filterParams: buildFilterParams,
  sortBy,
  sortDir,
  fetchPage: (params) => demandsStore.refresh(params),
  fetchByIds: getMadeItemDemands,
  fetchSummaries: (ids) => allocationsStore.fetchSummaries(ids),
  liveResource: LiveResource.MADE_ITEM_DEMANDS,
  refreshTriggers: [() => demandsStore.refreshTrigger, () => procurementStore.refreshTrigger],
  selection: {
    get: () => procurementStore.selectedDemands,
    set: (demands) => {
      procurementStore.selectedDemands = demands
    },
  },
})

watch([search, itemArticleName], resetAndFetchDebounced)

watch(projectId, resetAndFetch)

watch([statuses, highPriorityFilter, creatorFilter, showFulfilled, showCanceled], resetAndFetch)

watch(notFullyAllocatedOnly, resetAndFetch)

watch([bucketIds, includeUnbucketed], resetAndFetch)

watch([idFilter, stepMethods, lotIds], resetAndFetch)

// Date ranges are watched on the store refs themselves rather than refetched
// from the picker's callback, so any writer of those refs triggers a fetch.
watch([desiredFrom, desiredTo, createdFrom, createdTo], resetAndFetch)

watch(clearTrigger, resetAndFetch)

function openDetail(demand: MadeItemDemandResponse): void {
  selectedDemand.value = demand
  showDetail.value = true
}

const { guard: guardRowOpen } = useRowOpenGuard<number>()

const {
  target: fulfillFromStockDemand,
  visible: showFulfillFromStock,
  open: openFulfillFromStock,
} = useDialogTarget<MadeItemDemandResponse>()

const {
  target: createLotDemand,
  visible: showCreateLot,
  open: openCreateLot,
} = useDialogTarget<MadeItemDemandResponse>()

const {
  target: cancelDemand,
  visible: showCancel,
  open: openCancel,
} = useDialogTarget<MadeItemDemandResponse>()

// Row actions shared with the bought and source item demand tables.
const rowActions = useDemandRowActions<MadeItemDemandStatus, MadeItemDemandResponse>({
  getSelection: () => procurementStore.selectedDemands,
  setSelection: (demands) => {
    procurementStore.selectedDemands = demands
  },
  hasPanelOpen: () => filtersStore.showManageLotsPanel || filtersStore.showManageStockPanel,
  openDetail,
  guardRowOpen,
  fetchItems,
  updateStatus: (id, status) => demandsStore.updateStatus(id, status),
  setBucket: (id, bucketId) => demandsStore.setBucket(id, bucketId),
  canceledStatus: 'canceled',
})
const { onTableClickCapture, onRowClick, onRowSelect, contextMenuItem, contextMenuTargets } =
  rowActions

const reportBulkStatusFailures = bulkStatusFailureToast(toast, t, 'madeItems.demands')

async function setStatus(
  demand: MadeItemDemandResponse,
  status: MadeItemDemandStatus,
): Promise<void> {
  // Canceling cascades into lots, orders and raw-material demands, so a
  // dialog shows the impact first.
  if (status === 'canceled') {
    openCancel(demand)
    return
  }

  await withErrorToast(
    async () => {
      await demandsStore.updateStatus(demand.id, status)
      fetchItems()
    },
    {
      summary: demand.item_article_name,
      fallbackMessage: t('madeItems.demands.detail.errors.unknown'),
    },
  )
}

// Bulk status changes do not go through the cancel-impact dialog.
const { setStatusForTargets, bulkCancelTargets, showBulkCancel, requestBulkCancel } = rowActions

function confirmBulkCancel(): void {
  rowActions.confirmBulkCancel(reportBulkStatusFailures)
}

function bucketSubmenuItems(targets: MadeItemDemandResponse[]): MenuItem[] {
  return demandBucketMenuItems(
    bucketsStore.items.made_item_demand,
    (bucketId) => rowActions.assignBucket(targets, bucketId),
    t('madeItems.demands.buckets.noBucket'),
  )
}

function onLotCreated(): void {
  if (createLotDemand.value) {
    allocationsStore.fetchSummaries([createLotDemand.value.id]).catch(toastOnError())
  }
}

function addToPanel(demand: MadeItemDemandResponse, panel: 'lots' | 'stock'): void {
  if (!procurementStore.selectedDemands.some((d) => d.id === demand.id)) {
    procurementStore.selectedDemands = [...procurementStore.selectedDemands, demand]
  }
  filtersStore.openPanel(panel, { keepSelection: true })
}

const contextMenuItems = computed<MenuItem[]>(() =>
  demandContextMenu({
    t,
    keyPrefix: 'madeItems.demands',
    targets: contextMenuTargets.value,
    canEdit: canWrite.value,
    canSetStatus: canSetStatus.value,
    canWriteBuckets: canWrite.value,
    canWriteAllocations: canWriteAllocations.value,
    showCopyPlaceholder: true,
    bucketItems: bucketSubmenuItems,
    openDetail,
    setStatus,
    fulfilTargets: (targets) => setStatusForTargets(targets, 'fulfilled', reportBulkStatusFailures),
    requestBulkCancel,
    panel: {
      label: t('madeItems.demands.contextMenu.addToLots'),
      icon: 'mdi mdi-ticket-outline',
      disabled: !canWriteLots.value,
      open: () => filtersStore.openPanel('lots', { keepSelection: true }),
      addDemand: (demand) => addToPanel(demand, 'lots'),
    },
    openStockPanel: () => filtersStore.openPanel('stock', { keepSelection: true }),
    singleEntries: (demand) => [
      {
        label: t('madeItems.demands.detail.fulfillFromStock'),
        icon: 'mdi mdi-package-variant-closed',
        disabled: !canWriteAllocations.value,
        command: () => openFulfillFromStock(demand),
      },
      {
        label: t('madeItems.demands.contextMenu.createLot'),
        icon: 'mdi mdi-factory',
        disabled: !canWriteLots.value,
        command: () => openCreateLot(demand),
      },
    ],
    copyToClipboard,
  }),
)

function onDemandUpdated(): void {
  fetchItems()
  showDetail.value = false
}

const shellLabels = computed<DemandsTableShellLabels>(() => ({
  desiredDelivery: t('madeItems.demands.columns.desiredDelivery'),
  created: t('madeItems.demands.columns.created'),
  dateFilterPlaceholder: t('madeItems.demands.filters.filterBy'),
  creatorPlaceholder: t('madeItems.demands.filters.any'),
  bulkCancelHeader: t('madeItems.demands.contextMenu.bulkCancelHeader'),
  bulkCancelMessage: t(
    'madeItems.demands.contextMenu.bulkCancelConfirm',
    { count: bulkCancelTargets.value.length },
    bulkCancelTargets.value.length,
  ),
  bulkCancelAction: t('madeItems.demands.contextMenu.bulkCancelAction'),
}))
</script>

<template>
  <DemandsTableShell
    :items="groupedItems"
    :total="demandsStore.total"
    :first="first"
    :rows="rows"
    :filters="filters"
    :group-by="groupBy"
    :group-rows-by="groupRowsBy"
    :group-icons="{ project: 'mdi mdi-folder-outline' }"
    :show-selection-column="
      procurementStore.selectedDemands.length > 0 ||
      filtersStore.showManageLotsPanel ||
      filtersStore.showManageStockPanel
    "
    :show-actions="filtersStore.showActions"
    actions-width="8rem"
    :context-menu-items="contextMenuItems"
    :labels="shellLabels"
    v-model:selection="procurementStore.selectedDemands"
    v-model:context-menu-selection="contextMenuItem"
    v-model:bulk-cancel-visible="showBulkCancel"
    v-model:desired-range="desiredDateRange"
    v-model:creator-id="creatorFilter"
    v-model:created-range="createdDateRange"
    @page="onPage"
    @row-click="onRowClick"
    @row-select="onRowSelect"
    @table-click-capture="onTableClickCapture"
    @confirm-bulk-cancel="confirmBulkCancel"
  >
    <template #row-actions="{ data }">
      <Button
        icon="mdi mdi-open-in-new"
        size="small"
        severity="secondary"
        text
        rounded
        v-tooltip.focus="t('madeItems.demands.detail.title', { id: data.id })"
        :aria-label="t('madeItems.demands.detail.title', { id: data.id })"
        @click="openDetail(data)"
      />
      <Button
        icon="mdi mdi-package-variant-closed"
        size="small"
        severity="secondary"
        text
        rounded
        :disabled="!canWriteAllocations"
        v-tooltip.focus="t('madeItems.demands.controls.manageStock')"
        :aria-label="t('madeItems.demands.controls.manageStock')"
        @click="addToPanel(data, 'stock')"
      />
    </template>

    <template #columns>
      <Column v-bind="demandIdColumnDef(t('madeItems.demands.columns.id'), '6rem')">
        <template #filter>
          <InputNumber
            v-model="idFilter"
            :use-grouping="false"
            :min="1"
            :placeholder="t('madeItems.demands.filters.id')"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column
        class="phone-col"
        field="status"
        :header="t('madeItems.demands.columns.status')"
        style="width: 8rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: MadeItemDemandResponse }">
          <DemandStatusTag
            :label="t(`madeItems.demands.status.${data.status}`)"
            :severity="DEMAND_STATUS_SEVERITY[data.status]"
          />
        </template>
        <template #filter>
          <MultiSelect
            v-model="statuses"
            :aria-label="t('madeItems.demands.columns.status')"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="t('madeItems.demands.filters.any')"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column
        :header="t('madeItems.demands.buckets.column')"
        style="width: 8rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: MadeItemDemandResponse }">
          <BucketTag :bucket-id="data.bucket_id ?? null" resource-type="made_item_demand" />
        </template>
        <template #filter>
          <BucketFilterSelect
            v-model:bucket-ids="bucketIds"
            v-model:include-unbucketed="includeUnbucketed"
            :aria-label="t('madeItems.demands.buckets.column')"
            resource-type="made_item_demand"
          />
        </template>
      </Column>

      <Column
        class="phone-col"
        :header="t('madeItems.demands.columns.quantity')"
        style="width: 8rem"
        body-style="text-align: left"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: MadeItemDemandResponse }">
          <DemandQuantityCell :quantity="data.quantity" :unit="formatUnit(data.unit)" />
        </template>
      </Column>

      <Column
        field="project_number"
        :header="t('madeItems.demands.columns.project')"
        style="width: 12rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: MadeItemDemandResponse }">
          <div class="item-cell">
            <RouterLink
              class="project-number project-link"
              :to="`/workspace/projects/${data.project_id}`"
              >{{ data.project_number }}</RouterLink
            >
            <span class="project-customer">{{ data.project_customer }}</span>
            <span class="project-description">{{ data.project_description }}</span>
          </div>
        </template>
        <template #filter>
          <LookupSelect
            v-model="projectId"
            :aria-label="t('madeItems.demands.columns.project')"
            :fetch="fetchDemandProjectOptions"
            :fetch-by-ids="fetchDemandProjectsByIds"
            :placeholder="t('madeItems.demands.filters.any')"
          />
        </template>
      </Column>

      <Column
        v-if="hostStore.storageEnabled"
        class="phone-thumbnail"
        style="width: 3.25rem; min-width: 3.25rem; padding: var(--space-1) var(--space-2)"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: MadeItemDemandResponse }">
          <MadeItemThumbnailCell :item-id="data.made_item_id" :item-name="data.item_article_name" />
        </template>
      </Column>

      <Column
        class="phone-col"
        field="item_article_name"
        :header="t('madeItems.demands.columns.item')"
        style="width: 16rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: MadeItemDemandResponse }">
          <div class="item-cell">
            <span
              v-if="data.item_part_number"
              class="item-name item-link"
              role="button"
              tabindex="0"
              @click.stop="madeItemDetail.openDetailById(data.made_item_id)"
              @keydown.enter="madeItemDetail.openDetailById(data.made_item_id)"
              >{{ madeItemLabel(data.item_part_number, data.item_revision) }}</span
            >
            <span
              v-else
              class="item-name-warning item-link"
              role="button"
              tabindex="0"
              @click.stop="madeItemDetail.openDetailById(data.made_item_id)"
              @keydown.enter="madeItemDetail.openDetailById(data.made_item_id)"
            >
              <i class="mdi mdi-alert" aria-hidden="true" />
              {{ t('madeItems.demands.noPartNumber') }}
            </span>
            <span class="item-code">{{ data.item_article_name }}</span>
            <Tag
              v-if="data.is_alteration"
              :value="t('madeItems.demands.alterationTag')"
              severity="warn"
              icon="mdi mdi-wrench"
              v-tooltip="
                `${madeItemLabel(
                  data.alteration_of_made_item_part_number,
                  data.alteration_of_made_item_revision,
                )} - ${data.alteration_of_made_item_article_name}`
              "
              style="margin-top: var(--space-1); align-self: flex-start"
            />
          </div>
        </template>
        <template #filter>
          <InputText
            v-model="itemArticleName"
            :placeholder="t('madeItems.demands.filters.searchBy')"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column
        :header="t('madeItems.demands.columns.steps')"
        style="width: 12rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: MadeItemDemandResponse }">
          <Tag
            v-for="group in processGroups(data.item?.processes ?? [])"
            :key="group.groupIndex"
            :value="
              group.processes.length > 1
                ? `${groupMethodLabel(group, locale)} (${group.processes.length})`
                : groupMethodLabel(group, locale)
            "
            style="margin-right: var(--space-1)"
            severity="secondary"
          />
        </template>
        <template #filter>
          <MultiSelect
            v-model="stepMethods"
            :aria-label="t('madeItems.demands.columns.steps')"
            :options="stepMethodOptions"
            option-label="label"
            option-value="value"
            option-group-label="label"
            option-group-children="items"
            :loading="fabricationMethodsStore.loading || inspectionMethodsStore.loading"
            filter
            display="chip"
            show-clear
            :placeholder="t('madeItems.demands.filters.any')"
            size="small"
            fluid
            @before-show="ensureStepMethodsLoaded"
          />
        </template>
      </Column>

      <Column
        :header="t('madeItems.demands.columns.allocated')"
        style="width: 14rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: MadeItemDemandResponse }">
          <WithValue :value="allocationsStore.getSummary(data.id)" v-slot="{ value: summary }">
            <template v-if="summary">
              <div class="alloc-cell">
                <span class="alloc-numbers">
                  {{ summary.allocated + summary.fulfilled_from_stock }}
                  /
                  {{ summary.total }}
                  {{ formatUnit(summary.unit) }}
                </span>
                <Tag
                  v-if="!isEndedDemandStatus(data.status) && summary.unallocated > 0"
                  :value="`-${summary.unallocated}`"
                  severity="warn"
                  class="alloc-tag"
                  v-tooltip="t('common.unallocatedTooltip', { quantity: summary.unallocated, unit: formatUnit(summary.unit) })"
                />
                <i
                  v-else-if="summary.unallocated <= 0"
                  class="mdi mdi-check-circle"
                  style="color: var(--p-green-500); font-size: var(--font-size-md)"
                  aria-hidden="true"
                />
              </div>
            </template>
            <i
              v-else-if="allocationsStore.loadingSummaries"
              class="mdi mdi-loading mdi-spin muted"
              aria-hidden="true"
            />
            <span v-else class="muted">{{ getEmptyPlaceholder() }}</span>
          </WithValue>
        </template>
      </Column>

      <Column :header="t('madeItems.demands.columns.lots')" style="width: 10rem" :show-filter-menu="false">
        <template #body="{ data }: { data: MadeItemDemandResponse }">
          <WithValue :value="allocationsStore.getSummary(data.id)" v-slot="{ value: summary }">
            <div v-if="summary?.lot_ids?.length" class="lot-tags">
              <a
                v-for="lotId in summary!.lot_ids ?? []"
                :key="lotId"
                class="lot-tag-link"
                role="button"
                tabindex="0"
                @click.stop="openLotDetail(lotId)"
                @keydown.enter.stop="openLotDetail(lotId)"
              >
                <Tag :value="lotNumberCache.lotNumber(lotId)" severity="secondary" />
              </a>
            </div>
            <span v-else class="muted">{{ getEmptyPlaceholder() }}</span>
          </WithValue>
        </template>
        <template #filter>
          <LookupMultiSelect
            v-model="lotIds"
            :aria-label="t('madeItems.demands.columns.lots')"
            :fetch="fetchLotOptions"
            :fetch-by-ids="fetchLotsByIds"
            :placeholder="t('madeItems.demands.filters.any')"
          />
        </template>
      </Column>

      <Column v-bind="demandPriorityColumnDef(t('madeItems.demands.columns.highPriority'))">
        <template #body="{ data }: { data: MadeItemDemandResponse }">
          <i
            v-if="data.high_priority"
            class="mdi mdi-alert-circle"
            style="color: var(--p-orange-500)"
            aria-hidden="true"
          />
        </template>
        <template #filter>
          <Select
            v-model="highPriorityFilter"
            :aria-label="t('madeItems.demands.columns.highPriority')"
            :options="priorityOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="t('madeItems.demands.filters.priorityAny')"
            size="small"
            fluid
          />
        </template>
      </Column>
    </template>
  </DemandsTableShell>

  <MadeItemDemandDetailDialog
    v-model:visible="showDetail"
    :demand="selectedDemand"
    @updated="onDemandUpdated"
  />

  <MadeItemDetailDialog
    v-model:visible="madeItemDetail.showDetail.value"
    :item="madeItemDetail.detailItem.value"
  />

  <MadeItemDemandFulfillFromStockDialog
    v-model:visible="showFulfillFromStock"
    :demand="fulfillFromStockDemand"
    @fulfilled="fetchItems"
  />

  <LotCreateDialog
    v-model:visible="showCreateLot"
    :preset-item="createLotDemand?.item ?? null"
    :preset-demand="createLotDemand"
    @created="onLotCreated"
  />

  <MadeItemDemandCancelDialog v-model:visible="showCancel" :demand="cancelDemand" @canceled="fetchItems" />
</template>

<style scoped lang="scss">
.item-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.item-link {
  cursor: pointer;
  color: inherit;
  width: fit-content;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.item-name {
  font-size: var(--font-size-md);
  font-weight: 600;
}

.item-name-warning {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-weight: 500;
  font-size: var(--font-size-sm);
  color: var(--p-orange-500);
}

.item-code,
.project-customer {
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
}

.project-description {
  display: block;
  font-size: var(--font-size-sm);
  color: var(--p-text-muted-color);
  max-width: 11rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-number {
  font-weight: 600;
}

.project-link {
  color: inherit;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.alloc-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.alloc-numbers {
  font-size: var(--font-size-sm);
}

.alloc-tag {
  font-size: var(--font-size-xs);
}

.muted {
  color: var(--p-text-muted-color);
}

.lot-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
}

.lot-tag-link {
  text-decoration: none;
}
</style>
