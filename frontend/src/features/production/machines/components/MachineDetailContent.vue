<script setup lang="ts">
// The card-grid body of the machine detail page. MachineDetailView.vue reads
// the refs below off a template ref to drive its InfoBar and ControlsBar.
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { usePermissions } from '@/core/composables/usePermissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { LiveResource } from '@/core/realtime/resources'
import { toLocalDayStart, todayStart } from '@/core/utils/dates'
import { extractApiError } from '@/core/utils/errors'
import { MadeItemDetailDialog, getMadeItems } from '@/features/made-items'
import { SourceItemDetailDialog } from '@/features/source-items'
import { usePrint } from '@/shared/print'

import { useProductionQueueStore } from '../../stores/productionQueueStore'
import { getLot } from '../../api/getLot'
import { formatDurationBetween, stepMethodLabel } from '../../utils/lotStepDisplay'
import { productionOrderStatusSeverity } from '../../utils/productionOrderStatus'
import {
  useSourceMaterialCache,
  useProductionOrderCancel,
  ProductionOrderSplitDialog,
  ProductionOrderMergeDialog,
  ProductionOrderStartDialog,
  ProductionOrderPauseDialog,
  ManufacturingAssessmentDialog,
} from '@/features/production/queue'
import { ProductionOrderDetailDialog } from '@/features/production/lots'
import ProductionOrderCompletionDialog from '../../components/ProductionOrderCompletionDialog.vue'
import ScrapPiecesDialog from '../../components/ScrapPiecesDialog.vue'
import MachineOrderListCard from './MachineOrderListCard.vue'
import MachineCurrentOrderCard from './MachineCurrentOrderCard.vue'

import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'
import type { LotResponse, LotStepResponse } from '../../types/productionLotsResponse'
import type { MachinePoolResponse } from '@/features/production-machines'
import type { MadeItemResponse } from '@/features/made-items'

const props = defineProps<{
  machineId: number
}>()

const { t } = useI18n()
const { withErrorToast } = useErrorToast()
const { hasPermission } = usePermissions()
const { confirmCancel } = useProductionOrderCancel()
const store = useProductionQueueStore()
const currentUserStore = useCurrentUserStore()

const canWrite = computed(() => hasPermission(Permission.WRITE_PRODUCTION_ORDERS))
const canManage = computed(() => hasPermission(Permission.MANAGE_PRODUCTION_ORDERS))

// Gates only the first-load skeleton; a live refresh patches in place.
const ready = ref(false)

onMounted(async () => {
  await withErrorToast(() => store.fetchAll(), {
    summary: t('production.machineDetail.loadError'),
  })
  ready.value = true
})

const machine = computed(() => store.machines.find((m) => m.id === props.machineId) ?? null)

const pools = computed<MachinePoolResponse[]>(() =>
  store.machinePools.filter((p) => p.machine_ids.includes(props.machineId)),
)

const machineOrders = computed(() => store.ordersByMachine.get(props.machineId) ?? [])

// Orders running or paused on this machine, normally one, rendered as a list
// for merge, split or reassignment edge cases.
const currentOrders = computed(() =>
  machineOrders.value.filter((o) => o.status === 'in_progress' || o.status === 'paused'),
)

// The queue board's Overdue+Today rule without its local scheduling
// fallback, which would need every active lot in the plant: trust
// planned_start, else a later not_before, else today. A date-less order
// counts as today, like on the board.
function isOverdueOrToday(order: ProductionOrderResponse): boolean {
  const today = todayStart().getTime()
  if (order.planned_start) {
    return toLocalDayStart(order.planned_start).getTime() <= today
  }
  if (order.not_before) {
    return toLocalDayStart(order.not_before).getTime() <= today
  }
  return true
}

const queuedOrders = computed(() =>
  machineOrders.value.filter((o) => o.status === 'queued' && isOverdueOrToday(o)),
)
const primaryCurrentOrder = computed(() => currentOrders.value[0] ?? null)
const nextQueuedOrder = computed(() => queuedOrders.value[0] ?? null)

// The order the ControlsBar acts on: the running or paused order, else the
// head of the queue, so Start always has a target.
const controlTarget = computed(() => primaryCurrentOrder.value ?? nextQueuedOrder.value)

interface PoolSection {
  pool: MachinePoolResponse
  orders: ProductionOrderResponse[]
}

// The pool's machine-unresolved backlog, shared by every member machine.
const poolSections = computed<PoolSection[]>(() =>
  pools.value.map((pool) => ({
    pool,
    orders: (store.ordersByPool.get(pool.id) ?? []).filter(isOverdueOrToday),
  })),
)

type MachineRunState = 'running' | 'paused' | 'idle'

const machineState = computed<MachineRunState>(() => {
  if (currentOrders.value.some((o) => o.status === 'in_progress')) return 'running'
  if (currentOrders.value.some((o) => o.status === 'paused')) return 'paused'
  return 'idle'
})

const machineStateTagSeverity = computed<string>(() => {
  if (machineState.value === 'running') return productionOrderStatusSeverity.in_progress
  if (machineState.value === 'paused') return productionOrderStatusSeverity.paused
  return 'secondary'
})

// ── Lot data, scoped to the orders this page renders ─────
// Fetches only the lots behind visible orders, deduped, so the cards' lot
// based permission and manual-position checks still work.
const visibleOrders = computed<ProductionOrderResponse[]>(() => [
  ...currentOrders.value,
  ...queuedOrders.value,
  ...poolSections.value.flatMap((section) => section.orders),
])

const lotsById = ref(new Map<number, LotResponse>())

watch(
  visibleOrders,
  async (orders) => {
    const missingIds = [...new Set(orders.map((o) => o.lot_id))].filter(
      (id) => !lotsById.value.has(id),
    )
    if (missingIds.length === 0) return
    // Fail soft per lot so one 404 does not reject the batch; affected cards
    // fall back to denormalized fields until the next live signal.
    const fetched = await Promise.all(missingIds.map((id) => getLot(id).catch(() => null)))
    const next = new Map(lotsById.value)
    for (const lot of fetched) {
      if (lot) next.set(lot.id, lot)
    }
    lotsById.value = next
  },
  { immediate: true },
)

function positionFor(order: ProductionOrderResponse) {
  return lotsById.value.get(order.lot_id)?.positions?.find((p) => p.id === order.lot_position_id)
}

function stepsFor(order: ProductionOrderResponse): LotStepResponse[] {
  return positionFor(order)?.steps ?? []
}

function processMethodLabel(order: ProductionOrderResponse): string | null {
  const steps = stepsFor(order)
  if (steps.length === 0) return null
  return [...new Set(steps.map((s) => stepMethodLabel(s)))].join(', ')
}

// The hero shows only the primary current order's method.
const primaryProcessMethod = computed(() =>
  primaryCurrentOrder.value ? processMethodLabel(primaryCurrentOrder.value) : null,
)

const primaryCurrentLot = computed<LotResponse | null>(() =>
  primaryCurrentOrder.value ? (lotsById.value.get(primaryCurrentOrder.value.lot_id) ?? null) : null,
)

function cardBindings(order: ProductionOrderResponse) {
  return {
    order,
    canWrite: canWrite.value,
    canManage: canManage.value,
    draggable: false,
    processMethod: processMethodLabel(order),
    lot: lotsById.value.get(order.lot_id) ?? null,
    onStart: onCardStart,
    onPause: onCardPause,
    onSplit: onCardSplit,
    onMerge: onCardMerge,
    onComplete: onCardComplete,
    onCancel: onCardCancel,
    onScrap: onCardScrap,
    onTogglePin,
  }
}

// ── Item card: the current order's made item ────────────────────────────
const madeItem = ref<MadeItemResponse | null>(null)
const itemLoading = ref(false)

watch(
  () => primaryCurrentOrder.value?.made_item_id ?? null,
  async (id) => {
    if (id === null) {
      madeItem.value = null
      return
    }
    itemLoading.value = true
    try {
      const page = await getMadeItems({ id, limit: 1 })
      madeItem.value = page.items[0] ?? null
    } finally {
      itemLoading.value = false
    }
  },
  { immediate: true },
)

// ── Card action handlers ─

const splitTarget = ref<ProductionOrderResponse | null>(null)
const mergeTarget = ref<ProductionOrderResponse | null>(null)
const startTarget = ref<ProductionOrderResponse | null>(null)
const pauseTarget = ref<ProductionOrderResponse | null>(null)
const completionTarget = ref<ProductionOrderResponse | null>(null)
const assessmentTarget = ref<ProductionOrderResponse | null>(null)

const showSplit = ref(false)
const showMerge = ref(false)
const showStart = ref(false)
const showPause = ref(false)
const showCompletion = ref(false)
const showAssessment = ref(false)

const scrapDialogRef = ref<InstanceType<typeof ScrapPiecesDialog> | null>(null)

// Skips the dialog when there is nothing to ask: no operator choice (shared
// accounts only) and no machine choice (unresolved pool orders only).
async function onCardStart(order: ProductionOrderResponse): Promise<void> {
  const needsMachineSelection = order.machine_pool_id != null && order.machine_id === null
  if (!currentUserStore.isSharedAccount && !needsMachineSelection) {
    await withErrorToast(() => store.start(order.id), {
      summary: t('productionQueue.card.startError'),
    })
    return
  }

  startTarget.value = order
  showStart.value = true
}

function onCardPause(order: ProductionOrderResponse): void {
  pauseTarget.value = order
  showPause.value = true
}

function onCardSplit(order: ProductionOrderResponse): void {
  splitTarget.value = order
  showSplit.value = true
}

function onCardMerge(order: ProductionOrderResponse): void {
  mergeTarget.value = order
  showMerge.value = true
}

function onCardComplete(order: ProductionOrderResponse): void {
  completionTarget.value = order
  showCompletion.value = true
}

const completionSteps = computed(() =>
  completionTarget.value ? stepsFor(completionTarget.value) : [],
)

async function onTogglePin(order: ProductionOrderResponse): Promise<void> {
  await withErrorToast(() => store.togglePinned(order), {
    summary: t('productionQueue.card.pinError'),
  })
}

async function onCardCancel(order: ProductionOrderResponse): Promise<void> {
  if (!(await confirmCancel(order))) return
  await withErrorToast(() => store.cancel(order.id, order.edit_version), {
    summary: t('productionQueue.card.cancelError'),
  })
}

function onCompletionRecorded(updated: ProductionOrderResponse): void {
  showCompletion.value = false
  if (updated.status === 'completed') {
    assessmentTarget.value = updated
    showAssessment.value = true
  }
}

function onCardScrap(order: ProductionOrderResponse): void {
  void scrapDialogRef.value?.open({ kind: 'order', order })
}

// The scrap endpoint returns the lot, not the order, so there is nothing to
// patch directly.
function onPiecesScrapped(): void {
  void store.fetchOrders()
}

// ── ControlsBar mirrors of ProductionOrderCard's visibility rules ──
// These computeds repeat the card's rules for the order the controls bar acts
// on, so a change to when the card shows an action must be made here too.
const controlLot = computed(() =>
  controlTarget.value ? (lotsById.value.get(controlTarget.value.lot_id) ?? null) : null,
)

const controlSteps = computed<LotStepResponse[]>(() => {
  const order = controlTarget.value
  if (!order) return []
  return controlLot.value?.positions?.find((p) => p.id === order.lot_position_id)?.steps ?? []
})

const controlIsManualPosition = computed(
  () =>
    controlSteps.value.length > 0 &&
    controlSteps.value.every((s) => !s.fabrication_method_requires_machine),
)

const controlNeedsMachineOrPool = computed(() => {
  const order = controlTarget.value
  if (!order) return false
  return (
    !controlIsManualPosition.value && order.machine_id === null && order.machine_pool_id == null
  )
})

const controlCanOperateInspection = computed(() => {
  const hasInspectionStep = controlSteps.value.some((s) => s.role === 'inspection')
  return !hasInspectionStep || hasPermission(Permission.WRITE_INSPECTIONS)
})

const controlStartBlocked = computed(() => {
  const order = controlTarget.value
  if (!order) return true
  return controlNeedsMachineOrPool.value || !controlCanOperateInspection.value || !order.can_start
})

const controlStartBlockedTooltip = computed<string | undefined>(() => {
  if (controlNeedsMachineOrPool.value) return t('productionQueue.card.noMachineTooltip')
  if (!controlCanOperateInspection.value) return t('productionQueue.card.inspectionPermissionTooltip')
  if (controlTarget.value && !controlTarget.value.can_start) {
    return t('productionQueue.card.cannotStartTooltip')
  }
  return undefined
})

// ── ControlsBar dialogs (Open Item / Open Source Material / Open Order) ──
const { resolve: resolveSourceItem } = useSourceMaterialCache()
const controlSourceItem = computed(() => resolveSourceItem(controlLot.value?.source_item_id ?? null))

const controlCanOpenItem = computed(() => controlTarget.value !== null && madeItem.value !== null)
const controlCanOpenSourceItem = computed(
  () => controlTarget.value !== null && controlSourceItem.value !== null,
)

const showItemDialog = ref(false)
const showSourceItemDialog = ref(false)
const showOrderDialog = ref(false)

function openItemDialog(): void {
  if (!controlCanOpenItem.value) return
  showItemDialog.value = true
}

function openSourceItemDialog(): void {
  if (!controlCanOpenSourceItem.value) return
  showSourceItemDialog.value = true
}

function openOrderDialog(): void {
  if (!controlTarget.value) return
  showOrderDialog.value = true
}

// Started-by needs the lot's event log, which this page never fetches, so
// it stays null and the dialog hides it.
const controlOrderEndedBy = computed(() => {
  const order = controlTarget.value
  if (!order || order.status !== 'completed' || !order.completions?.length) return null
  const last = order.completions[order.completions.length - 1]
  return (last?.recorded_by ?? last?.operator)?.full_name ?? null
})

const controlOrderDuration = computed(() => {
  const order = controlTarget.value
  if (!order?.actual_start || !order?.actual_end) return null
  return formatDurationBetween(order.actual_start, order.actual_end)
})

// ── Print ──
// Gated by PRINT_DOCUMENTS alone, since reprinting a lost docket or label
// does not need write access to the order.
const toast = useAppToast()
const printService = usePrint()
const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))

type OrderPrintClassifier = 'production_order_label' | 'production_order_docket'

const printing = ref<OrderPrintClassifier | null>(null)

async function onPrint(classifier: OrderPrintClassifier): Promise<void> {
  const order = controlTarget.value
  if (!order) return
  const i18nStem = classifier === 'production_order_label' ? 'printLabel' : 'printDocket'
  printing.value = classifier
  try {
    const [job] = await printService.print({
      root_type: 'production_order',
      root_id: order.id,
      items: [{ classifier }],
    })
    if (job?.status === 'sent') {
      toast.success(order.production_order_number, t(`productionQueue.card.${i18nStem}Sent`))
    } else {
      toast.error(
        order.production_order_number,
        job?.error_message ?? t(`productionQueue.card.${i18nStem}Failed`),
      )
    }
  } catch (e) {
    toast.error(
      order.production_order_number,
      extractApiError(e) ?? t(`productionQueue.card.${i18nStem}Failed`),
    )
  } finally {
    printing.value = null
  }
}

// ── Live updates ──
function refreshLive(resources: { machines?: boolean; pools?: boolean; orders?: boolean }): void {
  void store.refreshLive(resources).catch(() => {})
}

useLiveRefresh([LiveResource.PRODUCTION_MACHINES], () => refreshLive({ machines: true }))
useLiveRefresh([LiveResource.MACHINE_POOLS], () => refreshLive({ pools: true }))
useLiveRefresh([LiveResource.PRODUCTION_ORDERS, LiveResource.PRODUCTION_LOTS], () => {
  // A lot signal can mean changed steps or positions, so drop the whole cache
  // and re-fetch every visible lot.
  lotsById.value = new Map()
  refreshLive({ orders: true })
})

defineExpose({
  machine,
  ready,
  pools,
  machineState,
  machineStateTagSeverity,
  canWrite,
  controlTarget,
  controlCanOperateInspection,
  controlStartBlocked,
  controlStartBlockedTooltip,
  onCardStart,
  onCardPause,
  onCardComplete,
  onCardCancel,
  onCardScrap,
  canPrint,
  printing,
  onPrint,
  controlCanOpenItem,
  controlCanOpenSourceItem,
  openItemDialog,
  openSourceItemDialog,
  openOrderDialog,
})
</script>

<template>
  <div class="machine-detail">
    <template v-if="!ready">
      <div class="record-grid">
        <Skeleton
          v-for="area in ['area-current', 'area-queue', 'area-pool']"
          :key="area"
          :class="area"
          border-radius="var(--p-content-border-radius)"
        />
      </div>
    </template>

    <template v-else-if="machine">
      <div class="record-grid">
        <MachineCurrentOrderCard
          class="record-card record-card--scroll area-current"
          :orders="currentOrders"
          :made-item="madeItem"
          :item-loading="itemLoading"
          :process-method="primaryProcessMethod"
          :lot="primaryCurrentLot"
        />

        <MachineOrderListCard
          class="record-card record-card--scroll area-queue"
          :title="t('production.machineDetail.queue.title')"
          :orders="queuedOrders"
          :empty-message="t('production.machineDetail.queue.empty')"
          :card-bindings="cardBindings"
        />

        <div class="area-pool">
          <template v-if="poolSections.length > 0">
            <MachineOrderListCard
              v-for="section in poolSections"
              :key="section.pool.id"
              class="record-card record-card--scroll"
              :title="t('production.machineDetail.pool.title', { pool: section.pool.name })"
              :orders="section.orders"
              :empty-message="t('production.machineDetail.pool.empty')"
              :card-bindings="cardBindings"
            />
          </template>
          <div v-else class="empty-note pool-none">
            {{ t('production.machineDetail.pool.none') }}
          </div>
        </div>
      </div>
    </template>

    <div v-else class="machine-detail-notfound">
      {{ t('production.machineDetail.notFound') }}
    </div>

    <ProductionOrderSplitDialog v-model:visible="showSplit" :order="splitTarget" />
    <ProductionOrderMergeDialog v-model:visible="showMerge" :order="mergeTarget" :orders="store.orders" />
    <ProductionOrderStartDialog v-model:visible="showStart" :order="startTarget" />
    <ProductionOrderPauseDialog v-model:visible="showPause" :order="pauseTarget" />
    <ProductionOrderCompletionDialog
      v-model:visible="showCompletion"
      :order="completionTarget"
      :steps="completionSteps"
      @recorded="onCompletionRecorded"
    />
    <ManufacturingAssessmentDialog v-model:visible="showAssessment" :order="assessmentTarget" />
    <ScrapPiecesDialog ref="scrapDialogRef" @scrapped="onPiecesScrapped" />

    <MadeItemDetailDialog v-model:visible="showItemDialog" :item="madeItem" />
    <SourceItemDetailDialog v-model:visible="showSourceItemDialog" :item="controlSourceItem" />
    <ProductionOrderDetailDialog
      v-model:visible="showOrderDialog"
      :order="controlTarget"
      :started-by="null"
      :ended-by="controlOrderEndedBy"
      :duration="controlOrderDuration"
      :assessment="controlTarget?.assessment ?? null"
    />
  </div>
</template>

<style scoped lang="scss">
.machine-detail {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.machine-detail-notfound {
  display: flex;
  justify-content: center;
  padding: var(--space-6);
  color: var(--p-text-muted-color);
}

// Three columns: the current-order hero takes the remaining space, the
// queue and pool columns are wider than a board column because their cards
// carry more detail. Every column scrolls its own content.
.record-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(30rem, 1fr) minmax(24rem, 28rem) minmax(24rem, 28rem);
  grid-template-rows: minmax(0, 1fr);
  grid-template-areas: 'current queue pool';
  gap: var(--space-4);

  // Tablet: the current order spans a full row, the two queue columns share
  // the second. Rows size automatically so the page scrolls.
  @media (max-width: $bp-lg) {
    grid-template-columns: 1fr 1fr;
    grid-template-rows: none;
    grid-auto-rows: minmax(18rem, auto);
    grid-template-areas:
      'current current'
      'queue pool';
  }

  // Phone: not even two columns fit next to each other; fully stacked.
  @media (max-width: $bp-sm) {
    grid-template-columns: 1fr;
    grid-template-areas:
      'current'
      'queue'
      'pool';
  }
}

.area-current {
  grid-area: current;
}
.area-queue {
  grid-area: queue;
}

// Holds one stacked card per pool, since a machine can belong to several.
.area-pool {
  grid-area: pool;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  min-height: 0;
}

.area-pool .record-card {
  flex: 1 1 0;
  min-height: 0;
}

.pool-none {
  display: flex;
  align-items: center;
  height: 100%;
}

// The layout of .record-card and .record-card--scroll lives in _openvue.scss.
.empty-note {
  padding: var(--space-2) 0;
}
</style>
