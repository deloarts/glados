<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { FilterMatchMode } from '@openvue/core/api'

import { OrderDetailDialog, getOrders } from '@/features/orders'
import { useOpenQuoteRequestLinks } from '@/features/quote-requests'
import { useSourceItemDemandsSelectionStore } from '../stores/sourceItemDemandsSelectionStore'
import { useSourceItemDemandsFiltersStore } from '../stores/sourceItemDemandsFiltersStore'
import { useSourceItemDemandsQuery } from '../composables/useSourceItemDemandsQuery'
import { useSourceItemsAllocationsStore } from '../stores/sourceItemsAllocationsStore'
import { useSourceItemDemandsRowActions } from '../composables/useSourceItemDemandsRowActions'
import { useBucketsStore, BucketTag, BucketFilterSelect } from '@/features/buckets'
import { LiveResource } from '@/core/realtime/resources'
import SourceItemDemandDetailDialog from './SourceItemDemandDetailDialog.vue'
import SourceItemManageAllocationsDialog from './SourceItemManageAllocationsDialog.vue'
import SourceItemDemandFulfillFromStockDialog from './SourceItemDemandFulfillFromStockDialog.vue'
import SourceItemDemandAllocationCell from './SourceItemDemandAllocationCell.vue'
import SourceItemDemandItemCell from './SourceItemDemandItemCell.vue'
import SourceItemDemandOrderCell from './SourceItemDemandOrderCell.vue'
import SourceItemDemandProjectCell from './SourceItemDemandProjectCell.vue'
import { getLots } from '../../api/getLots'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import { useRowOpenGuard } from '@/core/composables/useRowOpenGuard'
import { useDialogTarget } from '@/shared/composables/useDialogTarget'
import { useDemandTableData } from '@/shared/composables/useDemandTableData'
import { useDemandGrouping } from '@/shared/composables/useDemandGrouping'
import { formatUnit } from '@/shared/utils/units'
import DemandsTableShell from '@/shared/components/demands/DemandsTableShell.vue'
import ConfirmActionDialog from '@/shared/components/dialogs/ConfirmActionDialog.vue'
import LookupSelect from '@/shared/components/forms/LookupSelect.vue'
import TextFieldsFilter from '@/shared/components/forms/TextFieldsFilter.vue'
import {
  fetchDemandProjectOptions,
  fetchDemandProjectsByIds,
} from '@/shared/components/demands/demandProjectLookup'
import DemandStatusTag from '@/shared/components/demands/DemandStatusTag.vue'
import DemandQuantityCell from '@/shared/components/demands/DemandQuantityCell.vue'
import { demandIdColumnDef } from '@/shared/components/demands/demandColumnDefs'
import SourceItemDemandCancelDialog from './SourceItemDemandCancelDialog.vue'
import { useHostStore } from '@/core/host/stores/hostStore'
// A demand points at a bought item or a source item, so the thumbnail column
// renders the cell of whichever side is set.
import { BoughtItemThumbnailCell } from '@/features/bought-items'
import LookupMultiSelect from '@/shared/components/forms/LookupMultiSelect.vue'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'

import type { DataTableFilterMeta } from 'openvue/datatable'
import type { LookupOption } from '@/shared/components/forms/lookupMultiSelect'
import type { DemandsTableShellLabels } from '@/shared/components/demands/demandsTableShell'
import { DEMAND_STATUSES, DEMAND_STATUS_SEVERITY } from '@/core/utils/demandStatus'
import {
  useSourceItemDemandsStore,
  getSourceItemDemands,
  itemLabel,
  itemManufacturer,
  itemSublabel,
  SourceItemThumbnailCell,
} from '@/features/source-items'
import type { SourceItemDemandResponse } from '@/features/source-items'

const { t } = useI18n()
const { openLotDetail } = useLotDetail()

const demandsStore = useSourceItemDemandsStore()
const selectionStore = useSourceItemDemandsSelectionStore()
const filtersStore = useSourceItemDemandsFiltersStore()
const allocationsStore = useSourceItemsAllocationsStore()
const hostStore = useHostStore()
const bucketsStore = useBucketsStore()

// Bucket names and colors are needed even if the menu never opened.
onMounted(() => {
  void bucketsStore.fetch('source_item_demand')
})

const statusOptions = computed(() =>
  DEMAND_STATUSES.map((s) => ({
    label: t(`sourceItems.demands.status.${s}`),
    value: s,
  })),
)

const {
  idFilter,
  statusFilter,
  creatorFilter,
  projectId,
  search,
  itemDimension,
  itemMaterial,
  itemType,
  lotIds,
  orderIds,
  desiredFrom,
  desiredTo,
  showFulfilled,
  showCanceled,
  clearTrigger,
  notFullyAllocatedOnly,
  bucketIds,
  includeUnbucketed,
  sortBy,
  sortDir,
  groupBy,
} = storeToRefs(filtersStore)

const { groupedItems, groupRowsBy } = useDemandGrouping({
  items: () => demandsStore.items,
  groupBy,
  statusLabel: (item) => t(`sourceItems.demands.status.${item.status}`),
  bucketName: (item) =>
    item.bucket_id !== null && item.bucket_id !== undefined
      ? bucketsStore.byId.source_item_demand[item.bucket_id]?.name
      : undefined,
  unbucketedLabel: () => t('sourceItems.demands.buckets.unbucketed'),
  ownGroups: { project: { field: '_projectGroup', label: (item) => item.project_number } },
})

// Filtering is server-side; this object only exists because
// filterDisplay="row" throws without an entry per filterable column.
const filters: DataTableFilterMeta = {
  id: { value: null, matchMode: FilterMatchMode.EQUALS },
  status: { value: null, matchMode: FilterMatchMode.EQUALS },
  desired_delivery_date: { value: null, matchMode: FilterMatchMode.CONTAINS },
  created: { value: null, matchMode: FilterMatchMode.CONTAINS },
}

// The lot and order column filters search server side; the page size is
// owned here, the shared component only passes the typed query through.
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

const desiredDateRange = useDateRangeFilter(desiredFrom, desiredTo)

// Filters without paging or sort, shared with the live row refetch and the export.
const { filterParams: buildFilterParams } = useSourceItemDemandsQuery()

const { items: liveItems, total: liveTotal } = storeToRefs(demandsStore)
const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useDemandTableData({
  items: liveItems,
  total: liveTotal,
  loading: () => demandsStore.loading,
  filterParams: buildFilterParams,
  sortBy,
  sortDir,
  fetchPage: (params) => demandsStore.refresh(params),
  fetchByIds: getSourceItemDemands,
  fetchSummaries: (ids) => allocationsStore.fetchSummaries(ids),
  liveResource: LiveResource.SOURCE_ITEM_DEMANDS,
  refreshTriggers: [() => demandsStore.refreshTrigger, () => selectionStore.refreshTrigger],
  selection: {
    get: () => selectionStore.selectedDemands,
    set: (demands) => {
      selectionStore.selectedDemands = demands
    },
  },
})

// Typed text filters fire on every keystroke, so they go through the
// debounced variant; the picks and toggles below refetch immediately.
watch([search, itemDimension, itemMaterial, itemType], resetAndFetchDebounced)

// The item column's one filter field edits the three item text filters.
const itemFilterFields = computed(() => [
  { key: 'dimension', label: t('sourceItems.demands.filters.dimension') },
  { key: 'material', label: t('sourceItems.demands.filters.material') },
  { key: 'type', label: t('sourceItems.demands.filters.type') },
])
const itemFilter = computed({
  get: () => ({
    dimension: itemDimension.value,
    material: itemMaterial.value,
    type: itemType.value,
  }),
  set: (value: Record<string, string>) => {
    itemDimension.value = value.dimension ?? ''
    itemMaterial.value = value.material ?? ''
    itemType.value = value.type ?? ''
  },
})

watch(projectId, resetAndFetch)

watch([statusFilter, creatorFilter, showFulfilled, showCanceled], resetAndFetch)

watch([idFilter, lotIds, orderIds], resetAndFetch)

watch(notFullyAllocatedOnly, resetAndFetch)

watch([bucketIds, includeUnbucketed], resetAndFetch)

// Date ranges are watched on the store refs themselves rather than refetched
// from the picker's callback, so any writer of those refs triggers a fetch.
watch([desiredFrom, desiredTo], resetAndFetch)

watch(clearTrigger, resetAndFetch)

const selectedDemand = ref<SourceItemDemandResponse | null>(null)
const showDetail = ref(false)
const showManageAllocations = ref(false)

const {
  target: orderDetailId,
  visible: showOrderDetail,
  open: openOrderDetail,
} = useDialogTarget<number>()

const {
  target: fulfillFromStockDemand,
  visible: showFulfillFromStock,
  open: openFulfillFromStock,
} = useDialogTarget<SourceItemDemandResponse>()

function openDetail(demand: SourceItemDemandResponse): void {
  selectedDemand.value = demand
  showDetail.value = true
}

const { guard: guardRowOpen } = useRowOpenGuard<number>()

function openManageAllocations(demand: SourceItemDemandResponse): void {
  selectedDemand.value = demand
  showManageAllocations.value = true
}

const {
  onTableClickCapture,
  onRowClick,
  onRowSelect,
  contextMenuItem,
  contextMenuItems,
  showBulkCancel,
  bulkCancelTargets,
  showFulfil,
  fulfilTargets,
  confirmFulfil,
  showCancelPrompt,
  cancelPromptTargets,
  onCancelChosen,
  addToPanel,
  canWriteAllocations,
} = useSourceItemDemandsRowActions({
  openDetail,
  openManageAllocations,
  openFulfillFromStock,
  guardRowOpen,
  fetchItems,
})

function onDemandUpdated(): void {
  fetchItems()
  showDetail.value = false
}

// The open quote requests asking suppliers for the shown demands.
const { sourceDemands: quoteLinks } = useOpenQuoteRequestLinks(() => ({
  sourceDemandIds: demandsStore.items.map((d) => d.id),
}))

const shellLabels = computed<DemandsTableShellLabels>(() => ({
  desiredDelivery: t('sourceItems.demands.columns.desiredDelivery'),
  created: t('sourceItems.demands.columns.created'),
  dateFilterPlaceholder: t('sourceItems.demands.filters.filterBy'),
  creatorPlaceholder: t('sourceItems.demands.filters.any'),
  bulkCancelHeader: t('sourceItems.demands.contextMenu.bulkCancelHeader'),
  bulkCancelMessage: t(
    'sourceItems.demands.contextMenu.bulkCancelConfirm',
    { count: bulkCancelTargets.value.length },
    bulkCancelTargets.value.length,
  ),
  bulkCancelAction: t('sourceItems.demands.contextMenu.bulkCancelAction'),
}))
</script>

<template>
  <SourceItemDemandCancelDialog
    v-model:visible="showCancelPrompt"
    :demands="cancelPromptTargets"
    @confirm="onCancelChosen"
  />
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
      selectionStore.selectedDemands.length > 0 ||
      filtersStore.showManageOrderPanel ||
      filtersStore.showManageStockPanel ||
      filtersStore.showManageQuotePanel
    "
    :show-actions="filtersStore.showActions"
    actions-width="10.5rem"
    table-min-width="58rem"
    :context-menu-items="contextMenuItems"
    :labels="shellLabels"
    v-model:selection="selectionStore.selectedDemands"
    v-model:context-menu-selection="contextMenuItem"
    v-model:bulk-cancel-visible="showBulkCancel"
    v-model:desired-range="desiredDateRange"
    v-model:creator-id="creatorFilter"
    @page="onPage"
    @row-click="onRowClick"
    @row-select="onRowSelect"
    @table-click-capture="onTableClickCapture"
  >
    <template #row-actions="{ data }">
      <Button
        icon="mdi mdi-open-in-new"
        size="small"
        severity="secondary"
        text
        rounded
        v-tooltip.focus="t('sourceItems.demands.detail.title', { id: data.id })"
        :aria-label="t('sourceItems.demands.detail.title', { id: data.id })"
        @click="openDetail(data)"
      />
      <Button
        icon="mdi mdi-sitemap"
        size="small"
        severity="secondary"
        text
        rounded
        v-tooltip.focus="t('sourceItems.demands.contextMenu.manageAllocations')"
        :aria-label="t('sourceItems.demands.contextMenu.manageAllocations')"
        @click="openManageAllocations(data)"
      />
      <Button
        icon="mdi mdi-package-variant-closed"
        size="small"
        severity="secondary"
        text
        rounded
        :disabled="!canWriteAllocations"
        v-tooltip.focus="t('sourceItems.demands.controls.manageStock')"
        :aria-label="t('sourceItems.demands.controls.manageStock')"
        @click="addToPanel(data, 'stock')"
      />
    </template>

    <template #columns>
      <Column v-bind="demandIdColumnDef(t('sourceItems.demands.columns.id'), '5rem')">
        <template #filter>
          <InputNumber
            v-model="idFilter"
            :min="1"
            :max-fraction-digits="0"
            :use-grouping="false"
            :placeholder="t('sourceItems.demands.filters.filterBy')"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column
        class="phone-col"
        field="status"
        :header="t('sourceItems.demands.columns.status')"
        style="width: 8rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <DemandStatusTag
            :label="t(`sourceItems.demands.status.${(data as SourceItemDemandResponse).status}`)"
            :severity="DEMAND_STATUS_SEVERITY[(data as SourceItemDemandResponse).status]"
          />
        </template>
        <template #filter>
          <Select
            v-model="statusFilter"
            :aria-label="t('sourceItems.demands.columns.status')"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            show-clear
            :placeholder="t('sourceItems.demands.filters.any')"
            size="small"
            fluid
          />
        </template>
      </Column>

      <Column
        :header="t('sourceItems.demands.buckets.column')"
        style="width: 8rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <BucketTag
            :bucket-id="(data as SourceItemDemandResponse).bucket_id ?? null"
            resource-type="source_item_demand"
          />
        </template>
        <template #filter>
          <BucketFilterSelect
            resource-type="source_item_demand"
            v-model:bucket-ids="bucketIds"
            v-model:include-unbucketed="includeUnbucketed"
            :aria-label="t('sourceItems.demands.buckets.column')"
          />
        </template>
      </Column>

      <Column
        class="phone-col"
        :header="t('sourceItems.demands.columns.quantity')"
        style="width: 8rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <DemandQuantityCell
            :quantity="(data as SourceItemDemandResponse).quantity"
            :unit="formatUnit((data as SourceItemDemandResponse).unit)"
          />
        </template>
      </Column>

      <Column
        :header="t('sourceItems.demands.columns.project')"
        style="width: 12rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <SourceItemDemandProjectCell :demand="data as SourceItemDemandResponse" />
        </template>
        <template #filter>
          <LookupSelect
            v-model="projectId"
            :aria-label="t('sourceItems.demands.columns.project')"
            :fetch="fetchDemandProjectOptions"
            :fetch-by-ids="fetchDemandProjectsByIds"
            :placeholder="t('sourceItems.demands.filters.any')"
          />
        </template>
      </Column>

      <Column
        v-if="hostStore.storageEnabled"
        class="phone-thumbnail"
        :header="t('sourceItems.demands.columns.image')"
        style="width: 3.25rem; min-width: 3.25rem; padding: var(--space-1) var(--space-2)"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <BoughtItemThumbnailCell
            v-if="(data as SourceItemDemandResponse).bought_item_id"
            :item-id="(data as SourceItemDemandResponse).bought_item_id!"
            :item-name="itemLabel(data as SourceItemDemandResponse)"
          />
          <SourceItemThumbnailCell
            v-else-if="(data as SourceItemDemandResponse).source_item_id"
            :item-id="(data as SourceItemDemandResponse).source_item_id!"
            :item-name="itemLabel(data as SourceItemDemandResponse)"
            :dimension="(data as SourceItemDemandResponse).source_item?.dimension"
          />
        </template>
      </Column>

      <Column
        class="phone-col"
        :header="t('sourceItems.demands.columns.item')"
        style="width: 16rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <SourceItemDemandItemCell :demand="data as SourceItemDemandResponse" />
        </template>
        <template #filter>
          <TextFieldsFilter
            v-model="itemFilter"
            :column="t('sourceItems.demands.columns.item')"
            :fields="itemFilterFields"
            :placeholder="t('sourceItems.demands.filters.any')"
          />
        </template>
      </Column>

      <Column
        :header="t('sourceItems.demands.columns.manufacturer')"
        style="width: 12rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          {{ itemManufacturer(data as SourceItemDemandResponse) }}
        </template>
      </Column>

      <Column
        :header="t('sourceItems.demands.columns.allocated')"
        style="width: 14rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <SourceItemDemandAllocationCell
            :demand-id="(data as SourceItemDemandResponse).id"
            :status="(data as SourceItemDemandResponse).status"
            :unit="formatUnit((data as SourceItemDemandResponse).unit)"
          />
        </template>
      </Column>

      <Column
        :header="t('sourceItems.demands.columns.lot')"
        style="width: 10rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <a
            class="lot-link"
            role="button"
            tabindex="0"
            @click.stop="openLotDetail((data as SourceItemDemandResponse).lot_id)"
            @keydown.enter.stop="openLotDetail((data as SourceItemDemandResponse).lot_id)"
            >{{ (data as SourceItemDemandResponse).lot_number }}</a
          >
        </template>
        <template #filter>
          <LookupMultiSelect
            v-model="lotIds"
            :aria-label="t('sourceItems.demands.columns.lot')"
            :fetch="fetchLotOptions"
            :fetch-by-ids="fetchLotsByIds"
            :placeholder="t('sourceItems.demands.filters.any')"
          />
        </template>
      </Column>

      <Column
        :header="t('sourceItems.demands.columns.order')"
        style="width: 10rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <SourceItemDemandOrderCell
            :demand-id="(data as SourceItemDemandResponse).id"
            :quote-requests="quoteLinks[(data as SourceItemDemandResponse).id]"
            @open-order="openOrderDetail"
          />
        </template>
        <template #filter>
          <LookupMultiSelect
            v-model="orderIds"
            :aria-label="t('sourceItems.demands.columns.order')"
            :fetch="fetchOrderOptions"
            :fetch-by-ids="fetchOrdersByIds"
            :placeholder="t('sourceItems.demands.filters.any')"
          />
        </template>
      </Column>
    </template>
  </DemandsTableShell>

  <ConfirmActionDialog
    v-model:visible="showFulfil"
    :header="t('sourceItems.demands.contextMenu.fulfilHeader')"
    :message="
      t('sourceItems.demands.contextMenu.fulfilConfirm', { count: fulfilTargets.length }, fulfilTargets.length)
    "
    :confirm-label="t('sourceItems.demands.contextMenu.fulfilAction')"
    confirm-severity="primary"
    @confirm="confirmFulfil"
  />

  <SourceItemDemandDetailDialog
    v-model:visible="showDetail"
    :demand="selectedDemand"
    @updated="onDemandUpdated"
  />

  <SourceItemManageAllocationsDialog
    v-model:visible="showManageAllocations"
    :demand-id="selectedDemand != null ? selectedDemand.id : null"
    :demand-unit="selectedDemand != null ? selectedDemand.unit : ''"
    :bought-item-id="selectedDemand != null ? selectedDemand.bought_item_id : null"
    :source-item-id="selectedDemand != null ? selectedDemand.source_item_id : null"
    :project-id="selectedDemand != null ? selectedDemand.project_id : null"
    :item-article-name="selectedDemand != null ? itemLabel(selectedDemand) : null"
    :item-order-code="selectedDemand != null ? itemSublabel(selectedDemand) : null"
    @changed="onDemandUpdated"
  />

  <SourceItemDemandFulfillFromStockDialog
    v-model:visible="showFulfillFromStock"
    :demand="fulfillFromStockDemand"
    @fulfilled="fetchItems"
  />

  <OrderDetailDialog v-model:visible="showOrderDetail" :order-id="orderDetailId" />
</template>

<style scoped lang="scss">
.lot-link {
  font-weight: 600;
  color: inherit;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}
</style>
