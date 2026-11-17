<script setup lang="ts">
import { computed, defineAsyncComponent, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useUsersStore } from '@/core/stores/usersStore'
import { extractApiError } from '@/core/utils/errors'
import { useServerTable } from '@/core/composables/useServerTable'
import { watchLoadingBar } from '@/core/composables/useLoadingBar'
import { usePhoneLayout } from '@/core/composables/usePhoneLayout'
import { useResizablePanelWidth } from '@/shared/composables/useResizablePanelWidth'
import PageLayout from '@/shared/components/resource-view/PageLayout.vue'
import AsyncChunkLoading from '@/shared/components/layout/AsyncChunkLoading.vue'
import { MadeItemDetailDialog } from '@/features/made-items'
import { useMadeItemDetail } from '@/features/made-items'

import { useLotDetail } from '@/shared/composables/useLotDetail'
import { getLots } from '../../api/getLots'
import { useLiveRows } from '@/core/realtime/useLiveRows'
import { LiveResource } from '@/core/realtime/resources'
import { useProductionLotsStore } from '../../stores/productionLotsStore'
import { useProductionLotsSelectionStore } from '../stores/productionLotsSelectionStore'
import { useProductionLotsFiltersStore } from '../stores/productionLotsFiltersStore'
import { useProductionLotsEditStore } from '../stores/productionLotsEditStore'
import { useProductionLotsSourceStore } from '../stores/productionLotsSourceStore'
import LotsListManageOrdersPanel from '../components/LotsListManageOrdersPanel.vue'
import LotsListManageQuotesPanel from '../components/LotsListManageQuotesPanel.vue'
import LotsListManageProductionPanel from '../components/LotsListManageProductionPanel.vue'
import LotsListManageSourcePanel from '../components/LotsListManageSourcePanel.vue'
import LotsEditPanel from '../components/LotsEditPanel.vue'
import LotForceStatusConfirmDialog from '../components/LotForceStatusConfirmDialog.vue'
import LotEditStepsDialog from '../components/LotEditStepsDialog.vue'
import SourceItemDemandCreateDialog from '../components/SourceItemDemandCreateDialog.vue'
import LotMaterialSourceDialog from '../components/LotMaterialSourceDialog.vue'
import LotsControls from '../components/LotsControls.vue'
import LotsViews from '../components/LotsViews.vue'
import LotsTable from '../components/lots-table/LotsTable.vue'
import LotsPhoneList from '../components/lots-table/LotsPhoneList.vue'
import { buildLotFilterParams } from '../utils/lotFilterParams'

import type { MaterialSource } from '@/features/made-items'
import type { LotSummaryResponse } from '../../types/productionLotsResponse'
import type { LotFilterParams } from '../../types/productionLotsRequest'
import PanelResizeHandle from '@/shared/components/layout/PanelResizeHandle.vue'

// Lazy, so the heavy gantt library only loads for timeline visitors.
const LotsTimelineView = defineAsyncComponent({
  loader: () => import('./LotsTimelineView.vue'),
  loadingComponent: AsyncChunkLoading,
  delay: 200,
})

const route = useRoute()
const router = useRouter()
const { openLotDetail } = useLotDetail()
// A phone shows the lots as a short list for looking them up: no actions,
// no side panels, and a lot opens as its own page, so the back button
// returns to the list.
const { phoneMode } = usePhoneLayout()
const { t } = useI18n()
const toast = useAppToast()
const { hasPermission } = usePermissions()

const lotsStore = useProductionLotsStore()
const selectionStore = useProductionLotsSelectionStore()
const filtersStore = useProductionLotsFiltersStore()
const editStore = useProductionLotsEditStore()
const sourceStore = useProductionLotsSourceStore()
const madeItemDetail = useMadeItemDetail()
const usersStore = useUsersStore()

const isTimelineOpen = computed(() => route.name === 'ProductionLotsTimeline')

const canWrite = computed(() => hasPermission(Permission.WRITE_LOTS))
const canWriteOrders = computed(() => hasPermission(Permission.WRITE_ORDERS))

const {
  search,
  projectNumber,
  itemArticleName,
  itemPartNumber,
  statusFilter,
  priorityFilter,
  creatorFilter,
  createdFrom,
  createdTo,
  changedByFilter,
  changedFrom,
  changedTo,
  needsAssignmentOnly,
  needsApprovalOnly,
  lotNumber,
  targetDateFrom,
  targetDateTo,
  quantityMin,
  quantityMax,
  sourceText,
  sourceDimension,
  sourceType,
  sourceStatus,
  sourceDeliveryFrom,
  sourceDeliveryTo,
  stepMethod,
  stepStatus,
  stepSetupMin,
  stepSetupMax,
  stepPerPieceMin,
  stepPerPieceMax,
  stepPlannedStartFrom,
  stepPlannedStartTo,
  stepPlannedEndFrom,
  stepPlannedEndTo,
  stepDeliveryFrom,
  stepDeliveryTo,
  stepNote,
  clearTrigger,
  sortBy,
  sortDir,
} = storeToRefs(filtersStore)

// Filters without paging or sort, shared with the live ids refetch.
function buildFilterParams(): LotFilterParams {
  return buildLotFilterParams(filtersStore, {
    smartFilterEnabled: filtersStore.smartFilterEnabled,
    // Manage Quotes asks for the positions Manage Orders could assign.
    showManageOrders: showManageOrders.value || showManageQuotes.value,
    showManageProduction: showManageProduction.value,
    showManageSource: showManageSource.value,
    coverageFilterArmed: filtersStore.coverageFilterArmed,
    selectedMachineId: selectionStore.selectedMachine?.id ?? null,
    selectedPoolId: selectionStore.selectedPool?.id ?? null,
  })
}

function buildParams(base: { skip: number; limit: number }) {
  return {
    ...base,
    ...buildFilterParams(),
    ...(sortBy.value ? { order_by: sortBy.value, order_dir: sortDir.value } : {}),
  }
}

const { first, rows, fetchItems, resetAndFetch, resetAndFetchDebounced, onPage } = useServerTable({
  fetchParams: ({ first, rows }) => buildParams({ skip: first, limit: rows }),
  fetch: async (params) => {
    await lotsStore.refresh(params)
    void usersStore.ensureLoaded()
  },
})

const { loading, items: liveItems, total: liveTotal } = storeToRefs(lotsStore)
watchLoadingBar(loading)

useLiveRows<LotSummaryResponse>({
  resource: LiveResource.PRODUCTION_LOTS,
  items: liveItems,
  total: liveTotal,
  fetchByIds: async (ids) => {
    const response = await getLots({ ...buildFilterParams(), ids })
    return response.items
  },
  onFullRefresh: fetchItems,
})

// Typed inputs (text and numbers) debounce so a fetch does not fire on
// every keystroke; pickers and date ranges refetch at once. A date range
// writes its from and to refs in the same tick, so it still fetches once.
watch(
  [
    search,
    projectNumber,
    itemArticleName,
    itemPartNumber,
    lotNumber,
    sourceText,
    sourceDimension,
    sourceType,
    stepNote,
    quantityMin,
    quantityMax,
    stepSetupMin,
    stepSetupMax,
    stepPerPieceMin,
    stepPerPieceMax,
  ],
  resetAndFetchDebounced,
)

watch(
  [
    statusFilter,
    priorityFilter,
    creatorFilter,
    needsAssignmentOnly,
    needsApprovalOnly,
    createdFrom,
    createdTo,
    changedByFilter,
    changedFrom,
    changedTo,
    targetDateFrom,
    targetDateTo,
    sourceStatus,
    sourceDeliveryFrom,
    sourceDeliveryTo,
    stepMethod,
    stepStatus,
    stepPlannedStartFrom,
    stepPlannedStartTo,
    stepPlannedEndFrom,
    stepPlannedEndTo,
    stepDeliveryFrom,
    stepDeliveryTo,
  ],
  resetAndFetch,
)

watch(clearTrigger, resetAndFetch)

watch([sortBy, sortDir], () => fetchItems())

watch(
  () => lotsStore.refreshTrigger,
  () => fetchItems(),
)

function openLot(lot: LotSummaryResponse): void {
  if (phoneMode.value) {
    void router.push({ name: 'LotDetail', params: { id: lot.id } })
    return
  }
  openLotDetail(lot.id)
}

// ── Force status dialog ──────────────────────────────────────────────

const showForceStatus = ref(false)
const forceStatusAction = ref<'complete' | 'cancel'>('cancel')
const forceStatusLotId = ref<number | null>(null)
// The edit version of the lot as listed when the dialog opened.
const forceStatusEditVersion = ref(0)
const forceStatusSubmitting = ref(false)

function openForceStatus(lot: LotSummaryResponse, action: 'complete' | 'cancel'): void {
  forceStatusLotId.value = lot.id
  forceStatusEditVersion.value = lot.edit_version
  forceStatusAction.value = action
  showForceStatus.value = true
}

async function confirmForceStatus(reason: string | null): Promise<void> {
  if (forceStatusLotId.value === null) return
  forceStatusSubmitting.value = true
  try {
    if (forceStatusAction.value === 'complete') {
      await lotsStore.complete(forceStatusLotId.value, forceStatusEditVersion.value, reason)
    } else {
      await lotsStore.cancel(forceStatusLotId.value, forceStatusEditVersion.value, reason)
    }
    showForceStatus.value = false
  } catch (e) {
    toast.error(
      forceStatusAction.value === 'complete'
        ? t('production.lots.detail.completeError')
        : t('production.lots.detail.cancelError'),
      extractApiError(e) ?? undefined,
    )
  } finally {
    forceStatusSubmitting.value = false
  }
}

// ── Edit steps dialog ────────────────────────────────────────────────

const showEditSteps = ref(false)
const editStepsLotId = ref<number | null>(null)

function openEditSteps(lot: LotSummaryResponse): void {
  editStepsLotId.value = lot.id
  showEditSteps.value = true
}

// The dialog edits the lot-detail store, so the list refreshes on close.
watch(showEditSteps, (isVisible, wasVisible) => {
  if (!isVisible && wasVisible) lotsStore.triggerRefresh()
})

// ── Demand source item dialog ──────────────────────────────────────────

const showDemandSourceItem = ref(false)
const demandSourceItemLot = ref<LotSummaryResponse | null>(null)

function openDemandSourceItem(lot: LotSummaryResponse): void {
  demandSourceItemLot.value = lot
  showDemandSourceItem.value = true
}

function onSourceItemDemandCreated(): void {
  lotsStore.triggerRefresh()
}

// ── Material source dialog ───────────────────────────────────────────

const showAddSourceItem = ref(false)
const addSourceItemLot = ref<LotSummaryResponse | null>(null)

const addSourceItemCurrentSource = computed<MaterialSource>(() => ({
  bought_item_id: addSourceItemLot.value?.source_bought_item_id ?? null,
  source_item_id: addSourceItemLot.value?.source_item_id ?? null,
  made_item_id: addSourceItemLot.value?.source_made_item_id ?? null,
}))

function openAddSourceItem(lot: LotSummaryResponse): void {
  addSourceItemLot.value = lot
  showAddSourceItem.value = true
}

function onSourceItemUpdated(): void {
  lotsStore.triggerRefresh()
}

// ── Docked panels (Manage Orders / Manage Production / Edit) ───────────

const showManageOrders = ref(false)
const showManageQuotes = ref(false)
const showManageProduction = ref(false)
const showManageSource = ref(false)

// At most one docked panel is ever open; each toggle closes the others.
function toggleManageOrders(): void {
  showManageOrders.value = !showManageOrders.value
  if (showManageOrders.value) {
    showManageQuotes.value = false
    showManageProduction.value = false
    showManageSource.value = false
    if (editStore.editMode) editStore.toggleEditMode()
  }
  selectionStore.clearSelection()
  sourceStore.clearSelection()
}

function toggleManageQuotes(): void {
  showManageQuotes.value = !showManageQuotes.value
  if (showManageQuotes.value) {
    showManageOrders.value = false
    showManageProduction.value = false
    showManageSource.value = false
    if (editStore.editMode) editStore.toggleEditMode()
  }
  selectionStore.clearSelection()
  sourceStore.clearSelection()
}

function toggleManageProduction(): void {
  showManageProduction.value = !showManageProduction.value
  if (showManageProduction.value) {
    showManageOrders.value = false
    showManageQuotes.value = false
    showManageSource.value = false
    if (editStore.editMode) editStore.toggleEditMode()
  }
  selectionStore.clearSelection()
  sourceStore.clearSelection()
}

function toggleManageSource(): void {
  showManageSource.value = !showManageSource.value
  if (showManageSource.value) {
    showManageOrders.value = false
    showManageQuotes.value = false
    showManageProduction.value = false
    if (editStore.editMode) editStore.toggleEditMode()
  }
  selectionStore.clearSelection()
  sourceStore.clearSelection()
}

watch(
  () => editStore.editMode,
  (isEditMode) => {
    if (!isEditMode) return
    showManageOrders.value = false
    showManageQuotes.value = false
    showManageProduction.value = false
    showManageSource.value = false
    selectionStore.clearSelection()
    sourceStore.clearSelection()
  },
)

// Opening Manage Production arms the coverage filter.
watch(showManageProduction, (open) => {
  filtersStore.coverageFilterArmed = open
})

// Opening any Manage panel arms the actionable filter, and closing all of
// them disarms it.
watch(
  [showManageOrders, showManageQuotes, showManageProduction, showManageSource],
  ([orders, quotes, production, source]) => {
    filtersStore.actionableFilterArmed = orders || quotes || production || source
  },
)

// Actionable filtering happens on the backend, so the list refetches when a
// panel opens or closes, the production target changes, or either filter is
// toggled. The coverage flag is watched directly because Clear disarms it
// without closing the panel.
watch(
  [
    showManageOrders,
    showManageQuotes,
    showManageProduction,
    showManageSource,
    () => selectionStore.selectedMachine,
    () => selectionStore.selectedPool,
    () => filtersStore.coverageFilterArmed,
    () => filtersStore.smartFilterEnabled,
  ],
  () => {
    first.value = 0
    void lotsStore.refresh(buildParams({ skip: first.value, limit: rows.value }))
  },
)

const isManageOrdersOpen = computed(
  () => canWrite.value && canWriteOrders.value && showManageOrders.value,
)
const isManageQuotesOpen = computed(
  () => canWrite.value && canWriteOrders.value && showManageQuotes.value,
)
const isManageProductionOpen = computed(() => canWrite.value && showManageProduction.value)
const isManageSourceOpen = computed(() => canWrite.value && showManageSource.value)
const isEditPanelOpen = computed(() => canWrite.value && editStore.editMode)
const isAnyPanelOpen = computed(
  () =>
    isManageOrdersOpen.value ||
    isManageQuotesOpen.value ||
    isManageProductionOpen.value ||
    isManageSourceOpen.value ||
    isEditPanelOpen.value,
)

const {
  width: panelWidth,
  isResizing,
  min: panelMin,
  onResizeStart,
  onResizeKey,
} = useResizablePanelWidth({
  defaultWidth: 480,
  min: 220,
})

function onAssigned(): void {
  lotsStore.triggerRefresh()
  selectionStore.clearSelection()
}

function onSourceAssigned(): void {
  lotsStore.triggerRefresh()
  sourceStore.clearSelection()
}
</script>

<template>

  <PageLayout
    :class="{ 'is-resizing-ew': isResizing }"
    :data-class="isTimelineOpen ? undefined : 'lots-table-data'"
    :card="false"
  >
    <template v-if="!phoneMode" #controls>
      <LotsControls
        :show-manage-orders="showManageOrders"
        :show-manage-quotes="showManageQuotes"
        :show-manage-production="showManageProduction"
        :show-manage-source="showManageSource"
        @toggle-manage-orders="toggleManageOrders"
        @toggle-manage-quotes="toggleManageQuotes"
        @toggle-manage-production="toggleManageProduction"
        @toggle-manage-source="toggleManageSource"
      />
    </template>
    <template #views>
      <LotsViews />
    </template>

    <template v-if="!isTimelineOpen && !phoneMode" #panels>
      <LotsListManageOrdersPanel
        v-if="isManageOrdersOpen"
        :style="{ width: panelWidth + 'px' }"
        @assigned="onAssigned"
      />
      <LotsListManageQuotesPanel
        v-if="isManageQuotesOpen"
        :style="{ width: panelWidth + 'px' }"
      />
      <LotsListManageProductionPanel
        v-if="isManageProductionOpen"
        :style="{ width: panelWidth + 'px' }"
        @assigned="onAssigned"
      />
      <LotsListManageSourcePanel
        v-if="isManageSourceOpen"
        :style="{ width: panelWidth + 'px' }"
        @assigned="onSourceAssigned"
      />
      <LotsEditPanel v-if="isEditPanelOpen" :style="{ width: panelWidth + 'px' }" />
      <PanelResizeHandle v-if="isAnyPanelOpen" :width="panelWidth" :min="panelMin" @start="onResizeStart" @key="onResizeKey" />
    </template>

    <LotsTimelineView v-if="isTimelineOpen" />
    <LotsPhoneList
      v-else-if="phoneMode"
      :first="first"
      :rows="rows"
      @page="onPage"
      @open-lot="openLot"
    />
    <LotsTable
      v-else
      :first="first"
      :rows="rows"
      :show-manage-orders="showManageOrders || showManageQuotes"
      :show-manage-production="showManageProduction"
      :show-manage-source="showManageSource"
      :open-detail-by-id="madeItemDetail.openDetailById"
      @page="onPage"
      @open-lot="openLot"
      @edit-steps="openEditSteps"
      @force-status="openForceStatus"
      @add-source-item="openAddSourceItem"
      @demand-source-item="openDemandSourceItem"
    />
  </PageLayout>

  <MadeItemDetailDialog
    v-model:visible="madeItemDetail.showDetail.value"
    :item="madeItemDetail.detailItem.value"
  />

  <LotForceStatusConfirmDialog
    v-model:visible="showForceStatus"
    :lot-id="forceStatusLotId"
    :action="forceStatusAction"
    :submitting="forceStatusSubmitting"
    @confirm="confirmForceStatus"
  />

  <LotEditStepsDialog
    v-model:visible="showEditSteps"
    :lot-id="editStepsLotId"
    :can-write="canWrite"
  />

  <SourceItemDemandCreateDialog
    v-model:visible="showDemandSourceItem"
    :lot-id="demandSourceItemLot?.id ?? null"
    :lot-quantity="demandSourceItemLot?.quantity ?? 0"
    @created="onSourceItemDemandCreated"
  />

  <LotMaterialSourceDialog
    v-model:visible="showAddSourceItem"
    :lot-id="addSourceItemLot?.id ?? null"
    :made-item-id="addSourceItemLot?.made_item_id ?? null"
    :current-source="addSourceItemCurrentSource"
    :current-demand-status="addSourceItemLot?.demand_status ?? null"
    :input-demand-id="addSourceItemLot?.input_demand_id ?? null"
    :edit-version="addSourceItemLot?.edit_version ?? null"
    @updated="onSourceItemUpdated"
    @conflict="onSourceItemUpdated"
  />
</template>

<style scoped lang="scss">
.is-resizing-ew {
  user-select: none;
  cursor: ew-resize;
}

:deep(.lots-table-data) {
  display: flex;
  flex-direction: row;
  gap: var(--space-1);
}
</style>
