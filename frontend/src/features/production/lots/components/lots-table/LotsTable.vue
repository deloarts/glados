<script setup lang="ts">
import { computed, provide, toRef, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { HelpButton } from '@/shared/help'
import { ReportExportDialog, useReportExport } from '@/shared/reports'
import { inspectionReportSpec } from '../../utils/inspectionReport'

import { TABLE_ROWS_PER_PAGE_OPTIONS } from '@/core/constants/table'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useLayoutStore } from '@/core/stores/layoutStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { MadeItemThumbnailCell } from '@/features/made-items'
import { OrderDetailDialog } from '@/features/orders'
import EmptyState from '@/shared/components/EmptyState.vue'
import UserDateCell from '@/shared/components/user/UserDateCell.vue'
import UserDateFilter from '@/shared/components/user/UserDateFilter.vue'
import { useDateRangeFilter } from '@/shared/composables/useDateRangeFilter'
import { useNumberRangeFilter } from '@/shared/composables/useNumberRangeFilter'

import LotStepCellBody from './LotStepCellBody.vue'
import LotSourceCell from './LotSourceCell.vue'
import LotItemCell from './LotItemCell.vue'
import LotLotNumberCell from './LotLotNumberCell.vue'
import LotProjectCell from './LotProjectCell.vue'
import LotFilterSelect from './LotFilterSelect.vue'
import LotDateRangeFilter from './LotDateRangeFilter.vue'
import NumberRangeFilter from '@/shared/components/table-filters/NumberRangeFilter.vue'
import TextFieldsFilter from '@/shared/components/forms/TextFieldsFilter.vue'
import LotStepFilterCell from './LotStepFilterCell.vue'
import LotSourceStatusCell from './LotSourceStatusCell.vue'
import LotSourceDeliveryDateCell from './LotSourceDeliveryDateCell.vue'
import LotRequiredDeliveryDateCell from './LotRequiredDeliveryDateCell.vue'
import LotStepsSimpleCell from './LotStepsSimpleCell.vue'
import { LOTS_TABLE_STEP_CONTEXT_KEY } from './lotsTableStepContext'
import { useLotsTableRowLayout } from './useLotsTableRowLayout'
import { useLotsTableDialogs } from './useLotsTableDialogs'
import { useLotPrinting } from './useLotPrinting'
import { useLotSourceApproval } from './useLotSourceApproval'
import { useLotsTableRowInteraction } from './useLotsTableRowInteraction'
import { useLotsTableBulkSelection } from './useLotsTableBulkSelection'
import { useLotsTableContextMenu } from './useLotsTableContextMenu'
import { useLotsTableFilterCards } from './useLotsTableFilterCards'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'
import SetPlannedDateDialog from '../SetPlannedDateDialog.vue'
import LotAuditTrailDialog from '../LotAuditTrailDialog.vue'
import LotRequiredDeliveryDateDialog from '../LotRequiredDeliveryDateDialog.vue'
import ScrapPiecesDialog from '../../../components/ScrapPiecesDialog.vue'
import { useProductionLotsStore } from '../../../stores/productionLotsStore'
import { useOpenQuoteRequestLinks } from '@/features/quote-requests'
import { useProductionLotsFiltersStore } from '../../stores/productionLotsFiltersStore'
import { useLotStepDeliveryAccessors } from '../../composables/useLotStepDeliveryAccessors'
import { useLotStepSelection } from '../../composables/useLotStepSelection'
import { useLotNumberCache } from '../../composables/useLotNumberCache'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import { STEP_CELL_SPECS, stepColumnClass } from '../../utils/lotStepColumns'
import LotRejectSourceDialog from '../LotRejectSourceDialog.vue'
import { lotPrioritySeverity, lotStatusSeverity } from '../../../utils/lotStatus'
import { LOT_LEADING_COLUMN_SPECS, LOT_TRAILING_COLUMN_SPECS } from './lotsTableColumns'

import type { DataTablePageEvent } from 'openvue/datatable'
import type { LotSummaryResponse } from '../../../types/productionLotsResponse'
import { DEMAND_STATUSES } from '@/core/utils/demandStatus'

const props = defineProps<{
  first: number
  rows: number
  showManageOrders: boolean
  showManageProduction: boolean
  showManageSource: boolean
  openDetailById: (id: number) => Promise<void>
}>()

const emit = defineEmits<{
  page: [event: DataTablePageEvent]
  'open-lot': [lot: LotSummaryResponse]
  'edit-steps': [lot: LotSummaryResponse]
  'force-status': [lot: LotSummaryResponse, action: 'complete' | 'cancel']
  'add-source-item': [lot: LotSummaryResponse]
  'demand-source-item': [lot: LotSummaryResponse]
}>()

const { t } = useI18n()
const { hasPermission } = usePermissions()
const { isTableGridlinesEnabled, isTableStripedEnabled } = storeToRefs(useLayoutStore())

const lotsStore = useProductionLotsStore()
// The open quote requests asking suppliers for the shown lots' positions.
const { lotPositions: quoteLinks } = useOpenQuoteRequestLinks(() => ({
  lotPositionIds: lotsStore.items.flatMap((lot) => (lot.positions ?? []).map((p) => p.id)),
}))
const filtersStore = useProductionLotsFiltersStore()
const hostStore = useHostStore()

const {
  statusFilter,
  priorityFilter,
  projectNumber,
  creatorFilter,
  createdFrom,
  createdTo,
  changedByFilter,
  changedFrom,
  changedTo,
  lotNumber,
  targetDateFrom,
  targetDateTo,
  quantityMin,
  quantityMax,
  sourceStatus,
  sourceDeliveryFrom,
  sourceDeliveryTo,
} = storeToRefs(filtersStore)

// Each date-range filter maps its from/to pair through one writable computed.
const createdRange = useDateRangeFilter(createdFrom, createdTo)
const changedRange = useDateRangeFilter(changedFrom, changedTo)
const quantityRange = useNumberRangeFilter(quantityMin, quantityMax)
const targetDateRange = useDateRangeFilter(targetDateFrom, targetDateTo)
const sourceDeliveryRange = useDateRangeFilter(sourceDeliveryFrom, sourceDeliveryTo)
const { itemFilterFields, itemFilter, sourceFilterFields, sourceFilter } = useLotsTableFilterCards()

const sourceStatusOptions = computed(() =>
  DEMAND_STATUSES.map((s) => ({
    label: t(`sourceItems.demands.status.${s}`),
    value: s,
  })),
)

const canWrite = computed(() => hasPermission(Permission.WRITE_LOTS))
const canManage = computed(() => hasPermission(Permission.MANAGE_LOTS))
const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))
// Scrapping is a production-order action.
const canWriteProductionOrders = computed(() => hasPermission(Permission.WRITE_PRODUCTION_ORDERS))

const lotNumberCache = useLotNumberCache()
const { openLotDetail } = useLotDetail()

const {
  statusOptions,
  priorityOptions,
  visibleLots,
  subheaderGroupRowsBy,
  maxPositionCount,
  isColumnModeActive,
  stepGroupCount,
  stepGroupHeader,
  stepGroupClass,
  sourceGroupSpan,
  flatPositionRows,
  tableValue,
  rowHoverListeners,
  rowClass,
  cardEl,
  groupField,
  filters,
  lotOf,
  groupOf,
} = useLotsTableRowLayout(isTableStripedEnabled, toRef(props, 'showManageSource'))

const {
  stepPlannedInfo,
  stepConfirmedDelivery,
  stepPlannedEditTarget,
  stepSourceOrderInfo,
  stepPosition,
  lotHasPastTargetDateConflict,
} = useLotStepDeliveryAccessors(visibleLots)

const { isStepClickable, isStepSelected, isStepResolving, stepSeverity, onStepClick } =
  useLotStepSelection(toRef(props, 'showManageOrders'), toRef(props, 'showManageProduction'))

// Resolves the replacement-lot ids of the status cell to lot numbers. The
// store replaces items wholesale, so a shallow watch sees every change.
watch(
  visibleLots,
  (lots) => {
    for (const lot of lots) {
      for (const id of lot.replacement_lot_ids ?? []) {
        lotNumberCache.ensureLoaded(id)
      }
    }
  },
  { immediate: true },
)

const {
  showSetPlannedDate,
  plannedDateEditTarget,
  openSetPlannedDate,
  onPlannedDateSaved,
  showOrderDetail,
  orderDetailId,
  openOrderDetail,
  showAuditTrail,
  auditTrailLot,
  openAuditTrail,
  requiredDeliveryDialogRef,
  openSetRequiredDelivery,
  onRequiredDeliverySaved,
  scrapDialogRef,
  openScrapPieces,
  onPiecesScrapped,
} = useLotsTableDialogs()

const { isPrintingLot, onPrintLot } = useLotPrinting()

const {
  approvingSourceLotId,
  rejectingSource,
  rejectSourceLot,
  showRejectSource,
  approveSourceRow,
  openRejectSourceRow,
  confirmRejectSourceRow,
} = useLotSourceApproval()

provide(LOTS_TABLE_STEP_CONTEXT_KEY, {
  isStepClickable,
  isStepSelected,
  isStepResolving,
  stepSeverity,
  onStepClick: (lot, step, event) => void onStepClick(lot, step, event),
  stepPlannedInfo,
  stepConfirmedDelivery,
  stepPlannedEditTarget,
  stepSourceOrderInfo,
  stepPosition,
  quoteRequestsOf: (positionId) => quoteLinks.value[positionId],
  lotHasPastTargetDateConflict,
  openSetPlannedDate,
  openDetailById: props.openDetailById,
  openOrderDetail,
})

const { canOpenRow, onRowClick, onRowSelect } = useLotsTableRowInteraction(
  toRef(props, 'showManageOrders'),
  toRef(props, 'showManageProduction'),
  toRef(props, 'showManageSource'),
  lotOf,
  (lot) => emit('open-lot', lot),
)

const { rowSelectionTarget, isIdleSelection, editSelection, markRowClick, onSelectionUpdate } =
  useLotsTableBulkSelection(toRef(props, 'showManageSource'), isColumnModeActive, flatPositionRows, () => canWrite.value)

const { visible: reportVisible, report, open: openReport } = useReportExport()

const { cm, contextMenuItem, onRowContextMenu, contextMenuItems } = useLotsTableContextMenu(
  lotOf,
  canWrite,
  canManage,
  canPrint,
  canWriteProductionOrders,
  isPrintingLot,
  onPrintLot,
  openAuditTrail,
  {
    openLot: (lot) => emit('open-lot', lot),
    editSteps: (lot) => emit('edit-steps', lot),
    setRequiredDelivery: (lot) => openSetRequiredDelivery(lot),
    forceStatus: (lot, action) => emit('force-status', lot, action),
    addSourceItem: (lot) => emit('add-source-item', lot),
    demandSourceItem: (lot) => emit('demand-source-item', lot),
    scrapPieces: (lot) => openScrapPieces(lot),
    inspectionReport: (lot) =>
      openReport(inspectionReportSpec(lot, t('production.lots.report.title', { lot: lot.lot_number }))),
  },
)
</script>

<template>
  <div class="card" ref="cardEl" v-on="rowHoverListeners">
    <DataTable
      :value="tableValue"
      :data-key="isColumnModeActive ? 'rowKey' : 'id'"
      :row-group-mode="
        isColumnModeActive ? 'rowspan' : filtersStore.groupBy ? 'subheader' : undefined
      "
      :group-rows-by="isColumnModeActive ? 'lotId' : subheaderGroupRowsBy"
      :selection-mode="isIdleSelection ? 'multiple' : rowSelectionTarget ? undefined : canOpenRow ? 'single' : undefined"
      :meta-key-selection="isIdleSelection"
      :selection="rowSelectionTarget ? editSelection : undefined"
      @update:selection="onSelectionUpdate"
      :show-gridlines="isTableGridlinesEnabled"
      :striped-rows="isTableStripedEnabled && !isColumnModeActive"
      :row-class="rowClass"
      lazy
      paginator
      :total-records="lotsStore.total"
      :first="first"
      :rows="rows"
      :rows-per-page-options="TABLE_ROWS_PER_PAGE_OPTIONS"
      @page="emit('page', $event)"
      scrollable
      scroll-height="flex"
      filter-display="row"
      :filters="filters"
      size="small"
      @row-click="(e) => (markRowClick(e), onRowClick(e))"
      @row-select="onRowSelect"
      v-model:context-menu-selection="contextMenuItem"
      @row-contextmenu="onRowContextMenu"
      :class="['clickable-rows', { 'lots-table--column-mode': isColumnModeActive }]"
    >
      <template v-if="filtersStore.groupBy && !isColumnModeActive" #groupheader="{ data }">
        <div class="group-header">
          <i
            v-if="filtersStore.groupBy === 'priority'"
            class="mdi mdi-priority-high"
            aria-hidden="true"
          />
          <i
            v-else-if="filtersStore.groupBy === 'project'"
            class="mdi mdi-folder-outline"
            aria-hidden="true"
          />
          <i v-else class="mdi mdi-flag-outline" aria-hidden="true" />
          <span class="group-header-label">{{
            data._statusGroup ?? data._priorityGroup ?? data._projectGroup
          }}</span>
        </div>
      </template>

      <!-- The two-row header of every mode: Source and Step groups over their
           sub-columns, with the lot-level columns spanning both. Widescreen Mode
           repeats the Step group per position. -->
      <ColumnGroup key="lots-column-group" type="header">
        <Row>
          <Column
            v-if="rowSelectionTarget"
            selection-mode="multiple"
            :rowspan="2"
            style="width: 3rem"
          />
          <Column
            v-for="spec in LOT_LEADING_COLUMN_SPECS"
            :key="spec.key"
            :header="t(spec.headerKey)"
            :rowspan="2"
            :style="{ width: spec.width }"
          />
          <Column
            v-if="hostStore.storageEnabled"
            :rowspan="2"
            style="width: 3.25rem; min-width: 3.25rem"
          />
          <Column :header="t('production.lots.columns.item')" :rowspan="2" style="width: 16rem" />
          <!-- Source also spans the material's delivery date. -->
          <Column
            :header="t('production.lots.columns.source')"
            :colspan="sourceGroupSpan"
            style="width: 24rem"
          />
          <!-- Simple Mode's steps are tags in one cell, so there is nothing
               to group them over. -->
          <Column
            v-if="filtersStore.simpleMode"
            :header="t('production.lots.columns.steps')"
            :rowspan="2"
            style="width: 16rem"
          />
          <Column
            v-for="n in stepGroupCount"
            v-else
            :key="`step-group-header-${n}`"
            :header="stepGroupHeader(n)"
            :colspan="8"
            :class="stepGroupClass(n)"
          />
          <Column
            v-for="spec in LOT_TRAILING_COLUMN_SPECS"
            :key="spec.key"
            :header="t(spec.headerKey)"
            :rowspan="2"
            :style="{ width: spec.width }"
          />
          <Column :rowspan="2" />
        </Row>
        <Row>
          <Column
            :header="t('production.lots.columns.sourceItem')"
            :style="{ width: filtersStore.simpleMode ? '10rem' : '8rem' }"
          />
          <Column
            v-if="!filtersStore.simpleMode"
            :header="t('production.lots.columns.sourceStatus')"
            style="width: 6rem"
          />
          <Column :header="t('production.lots.columns.sourceDelivery')" style="width: 10rem" />
          <template v-if="!filtersStore.simpleMode">
            <template v-for="n in stepGroupCount" :key="`step-group-subheader-${n}`">
              <Column
                v-for="spec in STEP_CELL_SPECS"
                :key="`step-group-subheader-${n}-${spec.kind}`"
                :header="t(spec.headerKey)"
                :style="{ width: spec.headerWidth }"
                :class="stepGroupClass(n)"
              />
            </template>
          </template>
        </Row>
      </ColumnGroup>

      <!-- ── Lot-level columns (leading) ── -->
      <!-- Every column needs its own columnKey, since the lot-level columns share
           one field and would otherwise collide when Column Mode is re-entered. -->
      <Column
        v-if="rowSelectionTarget"
        selection-mode="multiple"
        column-key="select"
        :field="groupField"
        style="width: 3rem"
        :show-filter-menu="false"
      />
      <Column
        :header="t('production.lots.columns.rowNumber')"
        column-key="rowNumber"
        :field="groupField"
        style="width: 3.5rem"
        body-class="row-number"
        :show-filter-menu="false"
      >
        <template #body="{ index }">{{ first + index + 1 }}</template>
      </Column>
      <Column
        :header="t('production.lots.columns.lotNumber')"
        column-key="lotNumber"
        :field="groupField"
        style="width: 10rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <LotLotNumberCell :lot="lotOf(data)" />
        </template>
        <template #filter>
          <InputText
            v-model="lotNumber"
            :placeholder="t('production.lots.filters.searchBy')"
            size="small"
            fluid
          />
        </template>
      </Column>
      <Column
        :header="t('production.lots.columns.status')"
        column-key="status"
        :field="groupField"
        style="width: 9rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <div class="status-cell">
            <Tag
              :value="t(`production.lots.status.${lotOf(data).status}`)"
              :severity="lotStatusSeverity[lotOf(data).status]"
            />
            <div v-if="(lotOf(data).quantity_scrapped ?? 0) > 0" class="scrap-note">
              <span class="scrap-note-text">{{
                t('production.lots.scrapNote', { n: lotOf(data).quantity_scrapped })
              }}</span>
              <a
                v-for="replacementId in lotOf(data).replacement_lot_ids ?? []"
                :key="replacementId"
                class="scrap-note-link"
                role="button"
                tabindex="0"
                @click.stop="openLotDetail(replacementId)"
                @keydown.enter.stop="openLotDetail(replacementId)"
                >{{ lotNumberCache.lotNumber(replacementId) }}</a
              >
            </div>
          </div>
        </template>
        <template #filter>
          <LotFilterSelect v-model="statusFilter" :aria-label="t('production.lots.columns.status')" :options="statusOptions" option-label="label" option-value="value" />
        </template>
      </Column>
      <Column
        :header="t('production.lots.columns.priority')"
        column-key="priority"
        :field="groupField"
        style="width: 8rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <Tag
            :value="t(`production.lots.priority.${lotOf(data).priority}`)"
            :severity="lotPrioritySeverity[lotOf(data).priority]"
          />
        </template>
        <template #filter>
          <LotFilterSelect v-model="priorityFilter" :aria-label="t('production.lots.columns.priority')" :options="priorityOptions" option-label="label" option-value="value" />
        </template>
      </Column>
      <Column
        :header="t('production.lots.columns.requiredDeliveryDate')"
        column-key="requiredDeliveryDate"
        :field="groupField"
        style="width: 10rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <LotRequiredDeliveryDateCell
            :lot="lotOf(data)"
            :has-past-target-date-conflict="lotHasPastTargetDateConflict(lotOf(data).id)"
          />
        </template>
        <template #filter>
          <LotDateRangeFilter v-model="targetDateRange" />
        </template>
      </Column>
      <Column
        :header="t('production.lots.columns.project')"
        column-key="project"
        :field="groupField"
        style="width: 12rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <LotProjectCell :lot="lotOf(data)" />
        </template>
        <template #filter>
          <InputText
            v-model="projectNumber"
            :placeholder="t('production.lots.filters.searchBy')"
            size="small"
            fluid
          />
        </template>
      </Column>
      <Column
        :header="t('production.lots.columns.quantity')"
        column-key="quantity"
        :field="groupField"
        style="width: 11rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          {{ lotOf(data).quantity_completed }} / {{ lotOf(data).quantity }}
        </template>
        <template #filter>
          <NumberRangeFilter
            v-model="quantityRange"
            :fraction-digits="3"
            :column="t('production.lots.columns.quantity')"
          />
        </template>
      </Column>
      <Column
        v-if="hostStore.storageEnabled"
        column-key="thumbnail"
        :field="groupField"
        style="width: 3.25rem; min-width: 3.25rem; padding: var(--space-1) var(--space-2)"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <MadeItemThumbnailCell
            :item-id="lotOf(data).made_item_id"
            :item-name="lotOf(data).made_item_article_name"
          />
        </template>
      </Column>
      <Column
        :header="t('production.lots.columns.item')"
        column-key="item"
        :field="groupField"
        style="width: 16rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <LotItemCell :lot="lotOf(data)" :open-detail-by-id="openDetailById" />
        </template>
        <template #filter>
          <TextFieldsFilter
            v-model="itemFilter"
            :column="t('production.lots.columns.item')"
            :fields="itemFilterFields"
            :placeholder="t('production.lots.filters.any')"
          />
        </template>
      </Column>
      <!-- The ColumnGroup supplies the headers; the source variants share one
           body. -->
      <Column
        :header="t(filtersStore.simpleMode ? 'production.lots.columns.source' : 'production.lots.columns.sourceItem')"
        :column-key="filtersStore.simpleMode ? 'source' : 'sourceItem'"
        :field="groupField"
        :style="{ width: filtersStore.simpleMode ? '10rem' : '8rem' }"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <LotSourceCell :lot="lotOf(data)" />
        </template>
        <template #filter>
          <TextFieldsFilter
            v-model="sourceFilter"
            :column="t('production.lots.columns.sourceItem')"
            :fields="sourceFilterFields"
            :placeholder="t('production.lots.filters.any')"
          />
        </template>
      </Column>
      <Column
        v-if="!filtersStore.simpleMode"
        :header="t('production.lots.columns.sourceStatus')"
        column-key="sourceStatus"
        :field="groupField"
        style="width: 6rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <LotSourceStatusCell
            :lot="lotOf(data)"
            :can-manage="canManage"
            :approving-source-lot-id="approvingSourceLotId"
            @approve="approveSourceRow"
            @reject="openRejectSourceRow"
          />
        </template>
        <template #filter>
          <LotFilterSelect
            v-model="sourceStatus"
            :aria-label="t('production.lots.columns.sourceStatus')"
            :options="sourceStatusOptions"
            option-label="label"
            option-value="value"
          />
        </template>
      </Column>
      <Column
        :header="t('production.lots.columns.sourceDeliveryDate')"
        column-key="sourceDeliveryDate"
        :field="groupField"
        style="width: 10rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <LotSourceDeliveryDateCell :lot="lotOf(data)" />
        </template>
        <template #filter>
          <LotDateRangeFilter v-model="sourceDeliveryRange" />
        </template>
      </Column>

      <!-- ── Steps ── -->
      <!-- Simple Mode: all steps as compact tags in one cell. -->
      <Column
        v-if="filtersStore.simpleMode"
        :header="t('production.lots.columns.steps')"
        column-key="steps"
        style="width: 16rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <LotStepsSimpleCell :lot="lotOf(data)" />
        </template>
        <!-- One cell for all steps, so only the two filters that read
             well stacked: method and status. -->
        <template #filter>
          <div class="step-filter-stack">
            <LotStepFilterCell kind="method" />
            <LotStepFilterCell kind="status" />
          </div>
        </template>
      </Column>
      <!-- Column Mode: one set of step columns, one table row per position. -->
      <template v-else-if="isColumnModeActive">
        <Column
          v-for="spec in STEP_CELL_SPECS"
          :key="`step-col-${spec.kind}`"
          :column-key="`step-col-${spec.kind}`"
          :header="t(spec.headerKey)"
          :style="{ width: spec.bodyWidth }"
          :show-filter-menu="false"
        >
          <template #body="{ data }">
            <LotStepCellBody :kind="spec.kind" :lot="lotOf(data)" :group="groupOf(data, 1)" />
          </template>
          <template #filter>
            <LotStepFilterCell :kind="spec.kind" />
          </template>
        </Column>
      </template>
      <!-- Widescreen Mode: the step columns repeated per position. -->
      <template v-else>
        <template v-for="n in maxPositionCount" :key="`step-group-body-${n}`">
          <Column
            v-for="spec in STEP_CELL_SPECS"
            :key="`step-group-body-${n}-${spec.kind}`"
            :column-key="`step-group-body-${n}-${spec.kind}`"
            :style="{ width: spec.bodyWidth }"
            :show-filter-menu="false"
            :class="stepColumnClass(n)"
          >
            <template #body="{ data }">
              <LotStepCellBody :kind="spec.kind" :lot="lotOf(data)" :group="groupOf(data, n)" />
            </template>
            <!-- A step filter matches any position of the lot, so the
                 inputs sit in the first group only; the repeated groups
                 keep an empty filter cell. -->
            <template v-if="n === 1" #filter>
              <LotStepFilterCell :kind="spec.kind" />
            </template>
          </Column>
        </template>
      </template>

      <!-- ── Lot-level columns (trailing) ── -->
      <Column
        :header="t('production.lots.columns.created')"
        column-key="created"
        :field="groupField"
        style="width: 10rem"
        :show-filter-menu="false"
      >
        <!-- Explicit body, since field only drives the rowspan grouping. -->
        <template #body="{ data }">
          <UserDateCell :date="lotOf(data).created" :user="lotOf(data).creator" />
        </template>
        <template #filter>
          <UserDateFilter
            v-model:user-id="creatorFilter"
            v-model:range="createdRange"
            :column="t('production.lots.columns.created')"
            :placeholder="t('production.lots.filters.any')"
          />
        </template>
      </Column>
      <Column
        :header="t('production.lots.columns.changed')"
        column-key="changed"
        :field="groupField"
        style="width: 10rem"
        :show-filter-menu="false"
      >
        <template #body="{ data }">
          <UserDateCell :date="lotOf(data).changed" :user="lotOf(data).changed_by" />
        </template>
        <template #filter>
          <UserDateFilter
            v-model:user-id="changedByFilter"
            v-model:range="changedRange"
            :column="t('production.lots.columns.changed')"
            :placeholder="t('production.lots.filters.any')"
          />
        </template>
      </Column>

      <!-- Needs an empty body, since field only drives the rowspan grouping. -->
      <Column column-key="spacer" :field="groupField">
        <template #body></template>
      </Column>

      <template #empty>
        <EmptyState />
      </template>
    </DataTable>

    <ContextMenu
      ref="cm"
      :model="contextMenuItems"
      :pt="disabledItemTooltipPt"
      @hide="contextMenuItem = null"
    />
    <ReportExportDialog v-model:visible="reportVisible" :report="report">
      <template #handbook>
        <HelpButton slug="production/inspection-report" icon="mdi mdi-help" rounded />
      </template>
    </ReportExportDialog>
  </div>

  <SetPlannedDateDialog
    v-model:visible="showSetPlannedDate"
    :target="plannedDateEditTarget"
    @saved="onPlannedDateSaved"
  />

  <OrderDetailDialog v-model:visible="showOrderDetail" :order-id="orderDetailId" />

  <LotAuditTrailDialog v-model:visible="showAuditTrail" :lot="auditTrailLot" />

  <LotRequiredDeliveryDateDialog
    ref="requiredDeliveryDialogRef"
    @saved="onRequiredDeliverySaved"
  />

  <LotRejectSourceDialog
    v-model:visible="showRejectSource"
    :lot-number="rejectSourceLot?.lot_number ?? ''"
    :loading="rejectingSource"
    @confirm="confirmRejectSourceRow"
  />

  <ScrapPiecesDialog ref="scrapDialogRef" @scrapped="onPiecesScrapped" />
</template>

<style scoped lang="scss">
.card {
  flex: 1 1 0%;
  min-width: 0;
}

.group-header-label {
  font-weight: bold;
  padding-left: var(--space-4);
}

.status-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--space-1);
}

.step-filter-stack {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.scrap-note {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: var(--space-1);
}

.scrap-note-text {
  font-size: var(--font-size-xs);
  font-weight: 600;
  color: var(--p-red-500);
}

.scrap-note-link {
  font-size: var(--font-size-xs);
  color: var(--p-red-500);
  text-decoration: underline;
  cursor: pointer;

  &:hover {
    color: var(--p-primary-color);
  }
}

/* stylelint-disable selector-disallowed-list -- the lot rows are styled by the classes rowClass sets on OpenVue's rows and cells, and must outrank the theme's own row rules */
:deep(.p-datatable-thead > tr > th),
:deep(.p-datatable-tbody > tr > td) {
  white-space: nowrap;
}

:deep(.step-col-shade) {
  background: var(--p-datatable-row-striped-background) !important;
}

// ── Column Mode row blocks ───────────────────────────────────────────

// Striping per lot. Selected rows are excluded so the selection background
// still shows.
:deep(.p-datatable-tbody > tr.lot-row--striped:not(.p-datatable-row-selected)) {
  background: var(--p-datatable-row-striped-background);
}

// Every row of the hovered lot. main.scss uses !important for the hovered
// row, so this has to as well.
:deep(.p-datatable-tbody > tr.lot-row--hovered > td) {
  background: color-mix(in srgb, var(--p-primary-color) 10%, transparent) !important;
}

// Merged cells anchor to the top so alignMergedCells' padding places them
// against the first step row; other cells keep the normal centring.
:deep(.lots-table--column-mode .p-datatable-tbody > tr > td[rowspan]) {
  vertical-align: top;
}
/* stylelint-enable selector-disallowed-list */
</style>
