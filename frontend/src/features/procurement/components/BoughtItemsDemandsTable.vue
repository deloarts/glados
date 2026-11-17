<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { FilterMatchMode } from '@openvue/core/api'

import { useBoughtItemsDemandsFiltersStore } from '../stores/boughtItemsDemandsFiltersStore'
import { useBoughtItemsAllocationsStore } from '../stores/boughtItemsAllocationsStore'
import { useBoughtItemsProcurementStore } from '../stores/boughtItemsProcurementStore'
import { useBucketsStore, BucketTag, BucketFilterSelect } from '@/features/buckets'
import { LiveResource } from '@/core/realtime/resources'
import { fetchSupplierLookupByIds, fetchSupplierLookupOptions } from '@/features/suppliers'

import BoughtItemDemandDetailDialog from './BoughtItemDemandDetailDialog.vue'
import BoughtItemManageAllocationsDialog from './BoughtItemManageAllocationsDialog.vue'
import BoughtItemDemandFulfillFromStockDialog from './BoughtItemDemandFulfillFromStockDialog.vue'
import { OrderDetailDialog, getOrders } from '@/features/orders'
import { useOpenQuoteRequestLinks } from '@/features/quote-requests'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useBoughtItemsDemandsRowActions } from '../composables/useBoughtItemsDemandsRowActions'
import { useBoughtItemDemandsQuery } from '../composables/useBoughtItemDemandsQuery'
import BoughtItemDemandAllocationCell from './BoughtItemDemandAllocationCell.vue'
import BoughtItemDemandItemCell from './BoughtItemDemandItemCell.vue'
import BoughtItemDemandOrderCell from './BoughtItemDemandOrderCell.vue'
import { useRowOpenGuard } from '@/core/composables/useRowOpenGuard'
import WithValue from '@/shared/components/WithValue.vue'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { useDialogTarget } from '@/shared/composables/useDialogTarget'
import { useDemandTableData } from '@/shared/composables/useDemandTableData'
import { useDemandGrouping } from '@/shared/composables/useDemandGrouping'
import DemandsTableShell from '@/shared/components/demands/DemandsTableShell.vue'
import ConfirmActionDialog from '@/shared/components/dialogs/ConfirmActionDialog.vue'
import LookupSelect from '@/shared/components/forms/LookupSelect.vue'
import {
  fetchDemandProjectOptions,
  fetchDemandProjectsByIds,
} from '@/shared/components/demands/demandProjectLookup'
import DemandStatusTag from '@/shared/components/demands/DemandStatusTag.vue'
import DemandQuantityCell from '@/shared/components/demands/DemandQuantityCell.vue'
import LookupMultiSelect from '@/shared/components/forms/LookupMultiSelect.vue'
import { demandIdColumnDef, demandPriorityColumnDef } from '@/shared/components/demands/demandColumnDefs'

import type { DataTableFilterMeta } from 'openvue/datatable'
import type { LookupOption } from '@/shared/components/forms/lookupMultiSelect'
import type { DemandsTableShellLabels } from '@/shared/components/demands/demandsTableShell'
import { getEmptyPlaceholder } from '@/core/utils/emptyValue'
import { DEMAND_STATUSES } from '@/core/utils/demandStatus'
import { formatUnit } from '@/shared/utils/units'
import { demandDisplayStatus, type DemandDisplayStatus } from '../utils/demandDisplayStatus'
import {
  useBoughtItemsDemandsStore,
  getDemands,
  BoughtItemThumbnailCell,
  BoughtItemDetailDialog,
  useBoughtItemDetail,
} from '@/features/bought-items'
import type { BoughtItemDemandResponse } from '@/features/bought-items'

const { t } = useI18n()

const demandsStore = useBoughtItemsDemandsStore()
const filtersStore = useBoughtItemsDemandsFiltersStore()
const allocationsStore = useBoughtItemsAllocationsStore()
const procurementStore = useBoughtItemsProcurementStore()
const hostStore = useHostStore()
const bucketsStore = useBucketsStore()

// Bucket names and colors are needed even if the menu never opened.
onMounted(() => {
  void bucketsStore.fetch('bought_item_demand')
})

const boughtItemDetail = useBoughtItemDetail()

const {
  search,
  projectId,
  itemArticleName,
  itemManufacturerId,
  statusFilter,
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
  idFilter,
  orderIds,
  sortBy,
  sortDir,
  groupBy,
} = storeToRefs(filtersStore)

// Filtering is server-side; this object only exists because
// filterDisplay="row" throws without an entry per filterable column.
const filters: DataTableFilterMeta = {
  id: { value: null, matchMode: FilterMatchMode.EQUALS },
  status: { value: null, matchMode: FilterMatchMode.EQUALS },
  high_priority: { value: null, matchMode: FilterMatchMode.EQUALS },
  desired_delivery_date: { value: null, matchMode: FilterMatchMode.CONTAINS },
  created: { value: null, matchMode: FilterMatchMode.CONTAINS },
}

const selectedDemand = ref<BoughtItemDemandResponse | null>(null)
const showDetail = ref(false)
const showManageAllocations = ref(false)

const {
  target: orderDetailId,
  visible: showOrderDetail,
  open: openOrderDetail,
} = useDialogTarget<number>()

const statusOptions = computed(() =>
  DEMAND_STATUSES.map((s) => ({ label: t(`boughtItems.demands.status.${s}`), value: s })),
)

const priorityOptions = computed(() => [
  { label: t('boughtItems.demands.filters.priorityAny'), value: null },
  { label: t('boughtItems.demands.filters.priorityHigh'), value: true },
  { label: t('boughtItems.demands.filters.priorityNormal'), value: false },
])

const { groupedItems, groupRowsBy } = useDemandGrouping({
  items: () => demandsStore.items,
  groupBy,
  statusLabel: (item) => t(`boughtItems.demands.status.${item.status}`),
  bucketName: (item) =>
    item.bucket_id !== null ? bucketsStore.byId.bought_item_demand[item.bucket_id]?.name : undefined,
  unbucketedLabel: () => t('boughtItems.demands.buckets.unbucketed'),
  ownGroups: {
    project: { field: '_projectGroup', label: (item) => item.project_number },
    manufacturer: {
      field: '_manufacturerGroup',
      label: (item) => item.item?.manufacturer_name ?? getEmptyPlaceholder(),
    },
  },
})

const desiredDateRange = useDateRangeFilter(desiredFrom, desiredTo)

const createdDateRange = useDateRangeFilter(createdFrom, createdTo)

// Feeds the order column's lookup filter. Only the first page of matches is
// offered, typing narrows it server-side.
function toOrderOption(order: { id: number; order_number: string; supplier_name: string }): LookupOption {
  return { id: order.id, label: order.order_number, sublabel: order.supplier_name }
}

async function fetchOrderOptions(query: string): Promise<LookupOption[]> {
  const response = await getOrders({ search: query || undefined, limit: 15 })
  return response.items.map(toOrderOption)
}

async function fetchOrdersByIds(ids: number[]): Promise<LookupOption[]> {
  const response = await getOrders({ ids })
  return response.items.map(toOrderOption)
}

// Filters without paging or sort, shared with the live row refetch and the export.
const { filterParams: buildFilterParams } = useBoughtItemDemandsQuery()

const { items: liveItems, total: liveTotal } = storeToRefs(demandsStore)
// Selected rows are kept in step with the list because
// BoughtItemsDemandsManageOrder works on procurementStore.selectedDemands.
const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useDemandTableData({
  items: liveItems,
  total: liveTotal,
  loading: () => demandsStore.loading,
  filterParams: buildFilterParams,
  sortBy,
  sortDir,
  fetchPage: (params) => demandsStore.refresh(params),
  fetchByIds: getDemands,
  fetchSummaries: (ids) => allocationsStore.fetchSummaries(ids),
  liveResource: LiveResource.BOUGHT_ITEM_DEMANDS,
  refreshTriggers: [() => procurementStore.refreshTrigger, () => demandsStore.refreshTrigger],
  selection: {
    get: () => procurementStore.selectedDemands,
    set: (demands) => {
      procurementStore.selectedDemands = demands
    },
  },
})

watch([search, itemArticleName], resetAndFetchDebounced)

watch(projectId, resetAndFetch)

watch(itemManufacturerId, resetAndFetch)

watch([statusFilter, highPriorityFilter, creatorFilter, showFulfilled, showCanceled], resetAndFetch)

watch(notFullyAllocatedOnly, resetAndFetch)

watch([bucketIds, includeUnbucketed, idFilter, orderIds], resetAndFetch)

// Date ranges are watched on the store refs themselves rather than refetched
// from the picker's callback, so any writer of those refs triggers a fetch.
watch([desiredFrom, desiredTo, createdFrom, createdTo], resetAndFetch)

watch(clearTrigger, resetAndFetch)

function openDetail(demand: BoughtItemDemandResponse): void {
  selectedDemand.value = demand
  showDetail.value = true
}

const { guard: guardRowOpen } = useRowOpenGuard<number>()

function openManageAllocations(demand: BoughtItemDemandResponse): void {
  selectedDemand.value = demand
  showManageAllocations.value = true
}

const {
  target: fulfillFromStockDemand,
  visible: showFulfillFromStock,
  open: openFulfillFromStock,
} = useDialogTarget<BoughtItemDemandResponse>()

const {
  onTableClickCapture,
  onRowClick,
  onRowSelect,
  contextMenuItem,
  contextMenuItems,
  showBulkCancel,
  bulkCancelTargets,
  confirmBulkCancel,
  showFulfil,
  fulfilTargets,
  confirmFulfil,
  addToPanel,
  canWriteAllocations,
} = useBoughtItemsDemandsRowActions({
  openDetail,
  openManageAllocations,
  openFulfillFromStock,
  guardRowOpen,
  fetchItems,
})

// The open quote requests asking suppliers for the shown demands.
const { boughtDemands: quoteLinks } = useOpenQuoteRequestLinks(() => ({
  boughtDemandIds: demandsStore.items.map((d) => d.id),
}))

function onDemandUpdated(): void {
  fetchItems()
  showDetail.value = false
}

function demandStatusSeverity(status: DemandDisplayStatus): string {
  switch (status) {
    case 'open':
      return 'secondary'
    case 'partially_allocated':
    case 'allocated':
      return 'warn'
    case 'partially_ordered':
    case 'ordered':
      return 'info'
    case 'partially_delivered':
      return 'contrast'
    case 'fulfilled':
      return 'success'
    case 'canceled':
      return 'danger'
    default:
      return 'secondary'
  }
}

const shellLabels = computed<DemandsTableShellLabels>(() => ({
  desiredDelivery: t('boughtItems.demands.columns.desiredDelivery'),
  created: t('boughtItems.demands.columns.created'),
  dateFilterPlaceholder: t('boughtItems.demands.filters.filterBy'),
  creatorPlaceholder: t('orders.filters.any'),
  bulkCancelHeader: t('boughtItems.demands.contextMenu.bulkCancelHeader'),
  bulkCancelMessage: t(
    'boughtItems.demands.contextMenu.bulkCancelConfirm',
    { count: bulkCancelTargets.value.length },
    bulkCancelTargets.value.length,
  ),
  bulkCancelAction: t('boughtItems.demands.contextMenu.bulkCancelAction'),
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
    :group-icons="{ project: 'mdi mdi-folder-outline', manufacturer: 'mdi mdi-cart' }"
    :show-selection-column="
      procurementStore.selectedDemands.length > 0 ||
      filtersStore.showManageOrderPanel ||
      filtersStore.showManageStockPanel ||
      filtersStore.showManageQuotePanel
    "
    :show-actions="filtersStore.showActions"
    actions-width="10.5rem"
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
        v-tooltip.focus="t('boughtItems.demands.detail.title', { id: data.id })"
        :aria-label="t('boughtItems.demands.detail.title', { id: data.id })"
        @click="openDetail(data)"
      />
      <Button
        icon="mdi mdi-sitemap"
        size="small"
        severity="secondary"
        text
        rounded
        v-tooltip.focus="t('boughtItems.demands.detail.manageAllocationsTooltip', { id: data.id })"
        :aria-label="t('boughtItems.demands.detail.manageAllocationsTooltip', { id: data.id })"
        @click="openManageAllocations(data)"
      />
      <Button
        icon="mdi mdi-package-variant-closed"
        size="small"
        severity="secondary"
        text
        rounded
        :disabled="!canWriteAllocations"
        v-tooltip.focus="t('boughtItems.demands.controls.manageStock')"
        :aria-label="t('boughtItems.demands.controls.manageStock')"
        @click="addToPanel(data, 'stock')"
      />
    </template>

    <template #columns>
      <Column v-bind="demandIdColumnDef(t('boughtItems.demands.columns.id'), '6rem')">
        <template #filter>
          <InputNumber
            v-model="idFilter"
            :min="1"
            :max-fraction-digits="0"
            :use-grouping="false"
            :placeholder="t('boughtItems.demands.filters.filterBy')"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column
        class="phone-col"
        field="status"
        :header="t('boughtItems.demands.columns.status')"
        style="width: 8rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: BoughtItemDemandResponse }">
          <WithValue :value="allocationsStore.getSummary(data.id)" v-slot="{ value: summary }">
            <DemandStatusTag
              :label="t(`boughtItems.demands.status.${demandDisplayStatus(data, summary)}`)"
              :severity="demandStatusSeverity(demandDisplayStatus(data, summary))"
            />
          </WithValue>
        </template>
        <template #filter>
          <Select
            v-model="statusFilter"
            :aria-label="t('boughtItems.demands.columns.status')"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="t('boughtItems.demands.filters.any')"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column
        :header="t('boughtItems.demands.buckets.column')"
        style="width: 8rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: BoughtItemDemandResponse }">
          <BucketTag :bucket-id="data.bucket_id" resource-type="bought_item_demand" />
        </template>
        <template #filter>
          <BucketFilterSelect
            resource-type="bought_item_demand"
            v-model:bucket-ids="bucketIds"
            v-model:include-unbucketed="includeUnbucketed"
            :aria-label="t('boughtItems.demands.buckets.column')"
          />
        </template>
      </Column>

      <Column
        class="phone-col"
        :header="t('boughtItems.demands.columns.quantity')"
        style="width: 8rem"
        body-style="text-align: left"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: BoughtItemDemandResponse }">
          <DemandQuantityCell :quantity="data.quantity" :unit="formatUnit(data.unit)" />
        </template>
      </Column>

      <Column
        :header="t('boughtItems.demands.columns.project')"
        style="width: 12rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: BoughtItemDemandResponse }">
          <div class="item-cell">
            <RouterLink
              class="project-number project-link"
              :to="`/workspace/projects/${data.project_id}`"
              >{{ data.project_number }}</RouterLink
            >
            <span class="project-info"
              >{{ data.project_customer }}
              {{ data.project_description }}</span
            >
          </div>
        </template>
        <template #filter>
          <LookupSelect
            v-model="projectId"
            :aria-label="t('boughtItems.demands.columns.project')"
            :fetch="fetchDemandProjectOptions"
            :fetch-by-ids="fetchDemandProjectsByIds"
            :placeholder="t('boughtItems.demands.filters.any')"
          />
        </template>
      </Column>

      <Column
        v-if="hostStore.storageEnabled"
        class="phone-thumbnail"
        style="width: 3.25rem; min-width: 3.25rem; padding: var(--space-1) var(--space-2)"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: BoughtItemDemandResponse }">
          <BoughtItemThumbnailCell
            :item-id="data.item_id"
            :item-name="data.item_article_name"
          />
        </template>
      </Column>

      <Column
        class="phone-col"
        :header="t('boughtItems.demands.columns.item')"
        style="width: 16rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: BoughtItemDemandResponse }">
          <BoughtItemDemandItemCell :demand="data" @open-item="boughtItemDetail.openDetailById" />
        </template>
        <template #filter>
          <InputText
            v-model="itemArticleName"
            :placeholder="t('boughtItems.demands.filters.searchBy')"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column
        :header="t('boughtItems.demands.columns.manufacturer')"
        style="width: 12rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: BoughtItemDemandResponse }">
          {{ data.item?.manufacturer_name ?? getEmptyPlaceholder() }}
        </template>
        <template #filter>
          <LookupSelect
            v-model="itemManufacturerId"
            :aria-label="t('boughtItems.demands.columns.manufacturer')"
            :fetch="fetchSupplierLookupOptions"
            :fetch-by-ids="fetchSupplierLookupByIds"
            :placeholder="t('boughtItems.demands.filters.any')"
          />
        </template>
      </Column>

      <Column
        :header="t('boughtItems.demands.columns.allocated')"
        style="width: 14rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: BoughtItemDemandResponse }">
          <BoughtItemDemandAllocationCell :demand-id="data.id" :status="data.status" />
        </template>
      </Column>

      <Column
        :header="t('boughtItems.demands.columns.order')"
        style="width: 10rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }: { data: BoughtItemDemandResponse }">
          <BoughtItemDemandOrderCell
            :demand-id="data.id"
            :quote-requests="quoteLinks[data.id]"
            @open-order="openOrderDetail"
          />
        </template>
        <template #filter>
          <LookupMultiSelect
            v-model="orderIds"
            :aria-label="t('boughtItems.demands.columns.order')"
            :fetch="fetchOrderOptions"
            :fetch-by-ids="fetchOrdersByIds"
            :placeholder="t('boughtItems.demands.filters.any')"
          />
        </template>
      </Column>

      <Column v-bind="demandPriorityColumnDef(t('boughtItems.demands.columns.highPriority'))">
        <template #body="{ data }: { data: BoughtItemDemandResponse }">
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
            :aria-label="t('boughtItems.demands.columns.highPriority')"
            :options="priorityOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="t('boughtItems.demands.filters.priorityAny')"
            size="small"
            fluid
          />
        </template>
      </Column>
    </template>
  </DemandsTableShell>

  <ConfirmActionDialog
    v-model:visible="showFulfil"
    :header="t('boughtItems.demands.contextMenu.fulfilHeader')"
    :message="
      t('boughtItems.demands.contextMenu.fulfilConfirm', { count: fulfilTargets.length }, fulfilTargets.length)
    "
    :confirm-label="t('boughtItems.demands.contextMenu.fulfilAction')"
    confirm-severity="primary"
    @confirm="confirmFulfil"
  />

  <BoughtItemDemandDetailDialog
    v-model:visible="showDetail"
    :demand="selectedDemand"
    @updated="onDemandUpdated"
  />

  <BoughtItemDetailDialog
    v-model:visible="boughtItemDetail.showDetail.value"
    :item="boughtItemDetail.detailItem.value"
  />

  <BoughtItemManageAllocationsDialog
    v-model:visible="showManageAllocations"
    :demand-id="selectedDemand != null ? selectedDemand.id : null"
    :demand-unit="selectedDemand != null ? selectedDemand.unit : ''"
    :item-id="selectedDemand != null ? selectedDemand.item_id : null"
    :item-order-code="selectedDemand != null ? selectedDemand.item_order_code_1 : null"
    :item-article-name="selectedDemand != null ? selectedDemand.item_article_name : null"
    @changed="onDemandUpdated"
  />

  <BoughtItemDemandFulfillFromStockDialog
    v-model:visible="showFulfillFromStock"
    :demand="fulfillFromStockDemand"
    @fulfilled="fetchItems"
  />

  <OrderDetailDialog v-model:visible="showOrderDetail" :order-id="orderDetailId" />
</template>

<style scoped lang="scss">
.item-cell {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.project-number {
  font-size: var(--font-size-md);
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

.project-info {
  display: block;
  font-size: var(--font-size-xs);
  color: var(--p-text-muted-color);
  max-width: 11rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
