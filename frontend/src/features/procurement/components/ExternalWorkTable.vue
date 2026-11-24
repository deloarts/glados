<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { FilterMatchMode } from '@openvue/core/api'

import { useFabricationMethodsStore } from '@/features/fabrication-methods'
import { MadeItemDetailDialog, useMadeItemDetail } from '@/features/made-items'
import { OrderDetailDialog } from '@/features/orders'
import { LotPositionAssignDialog, LotPositionProvisionDialog } from '@/features/production'
import {
  SupplierFormDialog,
  fetchSupplierLookupByIds,
  fetchSupplierLookupOptions,
  getSupplier,
} from '@/features/suppliers'
import type { SupplierResponse } from '@/features/suppliers'
import { useAppToast } from '@/core/composables/useAppToast'
import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { formatDateOrDash } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import EmptyState from '@/shared/components/EmptyState.vue'
import DemandDateRangeFilter from '@/shared/components/demands/DemandDateRangeFilter.vue'
import DemandQuantityCell from '@/shared/components/demands/DemandQuantityCell.vue'
import LookupSelect from '@/shared/components/forms/LookupSelect.vue'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import { useLocalizedText } from '@/shared/composables/useLocalizedText'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import { DEFAULT_UNIT, formatUnit } from '@/shared/utils/units'
import { useExternalWorkRowMenu } from '../composables/useExternalWorkRowMenu'
import { useExternalWorkStore } from '../stores/externalWorkStore'
import { externalWorkDateTooltip } from '../utils/externalWorkTooltip'
import ExternalWorkGroupHeader from './ExternalWorkGroupHeader.vue'
import ExternalWorkLotCell from './ExternalWorkLotCell.vue'
import ExternalWorkLotFilter from './ExternalWorkLotFilter.vue'
import ExternalWorkSupplierCell from './ExternalWorkSupplierCell.vue'
import {
  externalWorkGroupLabel,
  externalWorkStage,
  externalWorkSupplier,
  summarizeExternalWorkGroup,
} from '../utils/externalWork'

import type { DataTableFilterMeta, DataTablePageEvent, DataTableRowClickEvent } from 'openvue/datatable'
import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { ExternalWorkAlert, ExternalWorkRow, ExternalWorkStage } from '../types/externalWork'

type GroupedRow = ExternalWorkRow & { _group: string }

const STAGES: ExternalWorkStage[] = [
  'unassigned',
  'pending',
  'requested',
  'ordered',
  'at_supplier',
  'partially_back',
]
const ALERTS: ExternalWorkAlert[] = ['not_ready_in_time', 'overdue', 'no_target_date']

const STAGE_SEVERITY: Record<ExternalWorkStage, string> = {
  unassigned: 'warn',
  pending: 'secondary',
  requested: 'info',
  ordered: 'info',
  at_supplier: 'secondary',
  partially_back: 'success',
}

const { t } = useI18n()
const toast = useAppToast()
const { localize } = useLocalizedText()
const { openLotDetail } = useLotDetail()
const store = useExternalWorkStore()
const methodsStore = useFabricationMethodsStore()
const madeItemDetail = useMadeItemDetail()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())
const {
  stages,
  part,
  lotIds,
  projectIds,
  productIds,
  methodId,
  readyFrom,
  readyTo,
  latestFrom,
  latestTo,
  backByFrom,
  backByTo,
  supplierId,
  alerts,
} = storeToRefs(store)

// ── Rows and groups ────────────────────────────────────────────────────

// The page grouped on the client: rows of one group sit together, each
// group keeping the server's order by latest pickup.
const groupedItems = computed<GroupedRow[]>(() => {
  const groupBy = store.groupBy
  const rows = store.items.map((row) => ({
    ...row,
    _group: groupBy
      ? externalWorkGroupLabel(row, groupBy, localize) || t('procurement.externalWork.noGroup')
      : '',
  }))
  if (!groupBy) return rows
  // Array.prototype.sort is stable, so equal groups keep the server's order.
  return [...rows].sort((a, b) => a._group.localeCompare(b._group))
})

const summaries = computed(() => {
  const byGroup = new Map<string, ExternalWorkRow[]>()
  for (const row of groupedItems.value) {
    byGroup.set(row._group, [...(byGroup.get(row._group) ?? []), row])
  }
  return new Map([...byGroup].map(([group, rows]) => [group, summarizeExternalWorkGroup(rows)]))
})

function summaryOf(row: GroupedRow) {
  return summaries.value.get(row._group) ?? { count: 0, critical: 0, nextLatestPickup: null }
}

function readySource(row: ExternalWorkRow): string {
  return row.planned_pickup_date ? t('procurement.externalWork.source.forecast') : ''
}

function backBySource(row: ExternalWorkRow): string {
  if (row.back_by_source === 'supplier') return t('procurement.externalWork.source.supplier')
  if (row.back_by_source === 'latest_pickup') return t('procurement.externalWork.source.forecast')
  return ''
}

function alertText(row: ExternalWorkRow): string {
  if (row.alert === 'not_ready_in_time') {
    return t('procurement.externalWork.alert.notReadyInTime', {
      date: formatDateOrDash(row.planned_pickup_date),
    })
  }
  if (row.alert === 'overdue') return t('procurement.externalWork.alert.overdue')
  if (row.alert === 'no_target_date') return t('procurement.externalWork.alert.noTargetDate')
  return ''
}

// How a date came about, shown on hover over its second line as in the lots
// table, in a tooltip as wide as the calculation.
function tooltipOf(
  row: ExternalWorkRow,
  date: 'ready' | 'latest' | 'backBy',
): { value: string | undefined; class: string } {
  const terms = {
    ready: row.ready_from_terms,
    latest: row.latest_pickup_terms,
    backBy: row.back_by_terms,
  }[date]
  const value = externalWorkDateTooltip(terms, {
    t,
    localize,
    leadTimeSign: date === 'latest' ? '−' : '+',
    stale: row.explanation_stale && date !== 'backBy',
  })
  return { value, class: 'tooltip-calculation' }
}

function rowSupplierId(row: ExternalWorkRow): number | null {
  return row.order_item_id !== null ? row.supplier_id : row.suggested_supplier_id
}

// ── Filters ────────────────────────────────────────────────────────────

// Filtering is server side; the object only exists because
// filter-display="row" needs an entry per filterable column.
const filters: DataTableFilterMeta = {
  stage: { value: null, matchMode: FilterMatchMode.EQUALS },
  part: { value: null, matchMode: FilterMatchMode.CONTAINS },
  lot: { value: null, matchMode: FilterMatchMode.EQUALS },
  method: { value: null, matchMode: FilterMatchMode.EQUALS },
  ready: { value: null, matchMode: FilterMatchMode.CONTAINS },
  latest: { value: null, matchMode: FilterMatchMode.CONTAINS },
  backBy: { value: null, matchMode: FilterMatchMode.CONTAINS },
  supplier: { value: null, matchMode: FilterMatchMode.EQUALS },
  alert: { value: null, matchMode: FilterMatchMode.EQUALS },
}

const readyRange = useDateRangeFilter(readyFrom, readyTo)
const latestRange = useDateRangeFilter(latestFrom, latestTo)
const backByRange = useDateRangeFilter(backByFrom, backByTo)

const stageOptions = computed(() =>
  STAGES.map((stage) => ({ value: stage, label: t(`procurement.externalWork.stage.${stage}`) })),
)
const alertOptions = computed(() =>
  ALERTS.map((alert) => ({ value: alert, label: t(`procurement.externalWork.alertLabel.${alert}`) })),
)
const methodOptions = computed(() =>
  methodsStore.activeItems.map((method) => ({ value: method.id, label: localize(method.name) })),
)

// The method catalogue loads the first time its filter opens.
function ensureMethodsLoaded(): void {
  if (methodsStore.items.length === 0) void methodsStore.refresh()
}

watch(
  [
    stages,
    lotIds,
    projectIds,
    productIds,
    methodId,
    readyFrom,
    readyTo,
    latestFrom,
    latestTo,
    backByFrom,
    backByTo,
    supplierId,
    alerts,
  ],
  () => void store.refilter(),
  { deep: true },
)

// The text boxes refilter once typing pauses.
let textTimer: ReturnType<typeof setTimeout> | null = null
watch([() => store.search, part], () => {
  if (textTimer) clearTimeout(textTimer)
  textTimer = setTimeout(() => void store.refilter(), 300)
})
onBeforeUnmount(() => {
  if (textTimer) clearTimeout(textTimer)
})

// ── Detail dialogs ─────────────────────────────────────────────────────

const showOrderDetail = ref(false)
const orderDetailId = ref<number | null>(null)

function openOrder(row: ExternalWorkRow): void {
  if (row.order_id === null) return
  orderDetailId.value = row.order_id
  showOrderDetail.value = true
}

const showSupplier = ref(false)
const supplier = ref<SupplierResponse | undefined>(undefined)

async function openSupplier(row: ExternalWorkRow): Promise<void> {
  const id = rowSupplierId(row)
  if (id === null) return
  try {
    supplier.value = await getSupplier(id)
    showSupplier.value = true
  } catch (e) {
    toast.error(externalWorkSupplier(row), extractApiError(e) ?? undefined)
  }
}

// ── Context menu ───────────────────────────────────────────────────────

const contextMenu = ref()
const rowMenu = useExternalWorkRowMenu(() => store.fetch())
const { menuRow, dialogLotId, dialogPosition, showAssign, showProvision } = rowMenu

function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
  contextMenu.value?.show(event.originalEvent)
}

// ── Table events ───────────────────────────────────────────────────────

function onRowClick(event: DataTableRowClickEvent): void {
  openLotDetail((event.data as ExternalWorkRow).lot_id)
}

function onPage(event: DataTablePageEvent): void {
  void store.setPage(event.first, event.rows)
}

// The schedule walk rewrites the dates after lot, order and line changes.
useLiveRefresh(
  [LiveResource.PRODUCTION_LOTS, LiveResource.PRODUCTION_ORDERS, LiveResource.ORDERS],
  () => store.fetch(),
)

onMounted(() => {
  void store.fetch()
})
</script>

<template>
  <DataTable
    :value="groupedItems"
    data-key="position_id"
    lazy
    paginator
    always-show-paginator
    :total-records="store.total"
    :first="store.first"
    :rows="store.rows"
    :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
    :loading="store.loading"
    scrollable
    scroll-height="flex"
    :show-gridlines="isTableGridlinesEnabled"
    :striped-rows="isTableStripedEnabled"
    size="small"
    table-style="min-width: 80rem"
    filter-display="row"
    :filters="filters"
    :row-group-mode="store.groupBy ? 'subheader' : undefined"
    :group-rows-by="store.groupBy ? '_group' : undefined"
    context-menu
    v-model:context-menu-selection="menuRow"
    class="phone-columns clickable-rows"
    data-testid="external-work-table"
    @page="onPage"
    @row-click="onRowClick"
    @row-contextmenu="onRowContextMenu"
  >
    <template v-if="store.groupBy" #groupheader="{ data }">
      <ExternalWorkGroupHeader
        :label="(data as GroupedRow)._group"
        :group-by="store.groupBy"
        :summary="summaryOf(data as GroupedRow)"
      />
    </template>
    <template #empty>
      <EmptyState />
    </template>

    <Column header="#" header-style="width: 3rem" body-class="row-number" class="phone-row-number">
      <template #body="{ index }">{{ store.first + index + 1 }}</template>
    </Column>

    <Column
      field="stage"
      class="column-fit phone-col"
      :header="t('procurement.externalWork.columns.status')"
      :show-filter-menu="false"
    >
      <template #body="{ data }">
        <Tag
          :severity="STAGE_SEVERITY[externalWorkStage(data as ExternalWorkRow)]"
          :value="t(`procurement.externalWork.stage.${externalWorkStage(data as ExternalWorkRow)}`)"
        />
      </template>
      <template #filter>
        <MultiSelect
          v-model="stages"
          :options="stageOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('procurement.externalWork.filters.any')"
          :aria-label="t('procurement.externalWork.columns.status')"
          :max-selected-labels="1"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column class="column-fit" :header="t('procurement.externalWork.columns.quantity')">
      <!-- A lot position counts pieces, whatever unit its supplier line uses. -->
      <template #body="{ data }">
        <DemandQuantityCell :quantity="(data as ExternalWorkRow).quantity" :unit="formatUnit(DEFAULT_UNIT)" />
      </template>
    </Column>

    <Column
      field="lot"
      class="column-fit"
      :header="t('procurement.externalWork.columns.lotProject')"
      :show-filter-menu="false"
    >
      <template #body="{ data }">
        <ExternalWorkLotCell :row="data as ExternalWorkRow" />
      </template>
      <template #filter>
        <ExternalWorkLotFilter
          v-model:lot-ids="lotIds"
          v-model:project-ids="projectIds"
          v-model:product-ids="productIds"
          :column="t('procurement.externalWork.columns.lotProject')"
        />
      </template>
    </Column>

    <Column
      field="part"
      class="column-fit phone-col"
      :header="t('procurement.externalWork.columns.item')"
      :show-filter-menu="false"
    >
      <template #body="{ data }">
        <div class="cell-stack">
          <a
            class="link strong"
            role="button"
            tabindex="0"
            @click.stop="madeItemDetail.openDetailById((data as ExternalWorkRow).made_item_id)"
            @keydown.enter.stop="madeItemDetail.openDetailById((data as ExternalWorkRow).made_item_id)"
            >{{ (data as ExternalWorkRow).part_number || '—' }}</a
          >
          <span class="muted">{{ (data as ExternalWorkRow).article_name }}</span>
        </div>
      </template>
      <template #filter>
        <InputText
          v-model="part"
          :placeholder="t('procurement.externalWork.filters.part')"
          :aria-label="t('procurement.externalWork.columns.item')"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column
      field="method"
      class="column-fit"
      :header="t('procurement.externalWork.columns.method')"
      :show-filter-menu="false"
    >
      <!-- The step tags of the made items demand table. -->
      <template #body="{ data }">
        <Tag
          v-for="method in (data as ExternalWorkRow).fabrication_methods"
          :key="method.id"
          :value="localize(method.name)"
          severity="secondary"
          class="method-tag"
        />
      </template>
      <template #filter>
        <Select
          v-model="methodId"
          :options="methodOptions"
          option-label="label"
          option-value="value"
          show-clear
          :placeholder="t('procurement.externalWork.filters.any')"
          :aria-label="t('procurement.externalWork.columns.method')"
          size="small"
          fluid
          @before-show="ensureMethodsLoaded"
        />
      </template>
    </Column>

    <Column
      field="supplier"
      class="column-fit"
      :header="t('procurement.externalWork.columns.supplier')"
      :show-filter-menu="false"
    >
      <template #body="{ data }">
        <ExternalWorkSupplierCell
          :row="data as ExternalWorkRow"
          @open-supplier="(row) => void openSupplier(row)"
          @open-order="openOrder"
        />
      </template>
      <template #filter>
        <LookupSelect
          v-model="supplierId"
          :aria-label="t('procurement.externalWork.columns.supplier')"
          :fetch="fetchSupplierLookupOptions"
          :fetch-by-ids="fetchSupplierLookupByIds"
          :placeholder="t('procurement.externalWork.filters.any')"
        />
      </template>
    </Column>

    <Column
      field="ready"
      class="column-fit"
      :header="t('procurement.externalWork.columns.readyFrom')"
      :show-filter-menu="false"
    >
      <template #body="{ data }">
        <div class="cell-stack">
          <span :class="{ danger: (data as ExternalWorkRow).alert === 'not_ready_in_time' }">
            {{
              (data as ExternalWorkRow).ready_now
                ? t('procurement.externalWork.source.ready')
                : formatDateOrDash((data as ExternalWorkRow).planned_pickup_date)
            }}
          </span>
          <span
            v-if="!(data as ExternalWorkRow).ready_now"
            v-tooltip.top="tooltipOf(data as ExternalWorkRow, 'ready')"
            class="muted"
          >
            {{ readySource(data as ExternalWorkRow) }}
          </span>
        </div>
      </template>
      <template #filter>
        <DemandDateRangeFilter
          v-model="readyRange"
          :placeholder="t('procurement.externalWork.filters.any')"
          @clear-click="readyRange = null"
        />
      </template>
    </Column>

    <Column
      field="latest"
      class="column-fit phone-col"
      :header="t('procurement.externalWork.columns.latestPickup')"
      :show-filter-menu="false"
    >
      <template #body="{ data }">
        <div class="cell-stack">
          <span class="strong" :class="{ danger: (data as ExternalWorkRow).alert === 'overdue' }">
            {{ formatDateOrDash((data as ExternalWorkRow).latest_pickup_date) }}
          </span>
          <span
            v-if="(data as ExternalWorkRow).latest_pickup_date"
            v-tooltip.top="tooltipOf(data as ExternalWorkRow, 'latest')"
            class="muted"
          >
            {{ t('procurement.externalWork.source.fromTarget') }}
          </span>
        </div>
      </template>
      <template #filter>
        <DemandDateRangeFilter
          v-model="latestRange"
          :placeholder="t('procurement.externalWork.filters.any')"
          @clear-click="latestRange = null"
        />
      </template>
    </Column>

    <Column
      field="backBy"
      class="column-fit"
      :header="t('procurement.externalWork.columns.backBy')"
      :show-filter-menu="false"
    >
      <template #body="{ data }">
        <div class="cell-stack">
          <span>{{ formatDateOrDash((data as ExternalWorkRow).back_by_date) }}</span>
          <span v-tooltip.top="tooltipOf(data as ExternalWorkRow, 'backBy')" class="muted">{{
            backBySource(data as ExternalWorkRow)
          }}</span>
        </div>
      </template>
      <template #filter>
        <DemandDateRangeFilter
          v-model="backByRange"
          :placeholder="t('procurement.externalWork.filters.any')"
          @clear-click="backByRange = null"
        />
      </template>
    </Column>

    <Column
      field="alert"
      :header="t('procurement.externalWork.columns.alert')"
      style="min-width: 14rem"
      :show-filter-menu="false"
    >
      <template #body="{ data }">
        <span
          v-if="(data as ExternalWorkRow).alert"
          class="alert"
          :class="{ muted: (data as ExternalWorkRow).alert === 'no_target_date' }"
        >
          <i
            v-if="(data as ExternalWorkRow).alert !== 'no_target_date'"
            class="mdi mdi-alert-outline"
            aria-hidden="true"
          />
          {{ alertText(data as ExternalWorkRow) }}
        </span>
      </template>
      <template #filter>
        <MultiSelect
          v-model="alerts"
          :options="alertOptions"
          option-label="label"
          option-value="value"
          :placeholder="t('procurement.externalWork.filters.any')"
          :aria-label="t('procurement.externalWork.columns.alert')"
          :max-selected-labels="1"
          size="small"
          fluid
        />
      </template>
    </Column>

    <Column />
  </DataTable>

  <ContextMenu
    ref="contextMenu"
    :model="rowMenu.items.value"
    :pt="disabledItemTooltipPt"
    @hide="menuRow = null"
  />

  <OrderDetailDialog v-model:visible="showOrderDetail" :order-id="orderDetailId" />
  <MadeItemDetailDialog
    v-model:visible="madeItemDetail.showDetail.value"
    :item="madeItemDetail.detailItem.value"
  />
  <SupplierFormDialog v-model:visible="showSupplier" :supplier="supplier" />
  <LotPositionAssignDialog
    v-model:visible="showAssign"
    :lot-id="dialogLotId"
    :position="dialogPosition"
    @assigned="void store.fetch()"
  />
  <LotPositionProvisionDialog
    v-model:visible="showProvision"
    :lot-id="dialogLotId"
    :position="dialogPosition"
  />
</template>

<style scoped lang="scss">
.cell-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.strong {
  font-weight: 600;
}

.method-tag {
  margin-right: var(--space-1);
}

.muted {
  color: var(--p-text-muted-color);
  font-size: var(--font-size-xs);
}

.link {
  color: inherit;
  text-decoration: none;
  cursor: pointer;

  &:hover {
    text-decoration: underline;
    color: var(--p-primary-color);
  }
}

.danger {
  color: var(--p-red-600);
  font-weight: 600;
}

.alert {
  display: inline-flex;
  align-items: flex-start;
  gap: var(--space-1);
  color: var(--p-red-600);
  font-size: var(--font-size-xs);

  &.muted {
    color: var(--p-text-muted-color);
  }
}
</style>
