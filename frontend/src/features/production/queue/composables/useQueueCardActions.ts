import { computed, ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { usePermissions } from '@/core/composables/usePermissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'
import { useDialogTarget } from '@/shared/composables/useDialogTarget'
import { useProductionQueueStore } from '../../stores/productionQueueStore'
import { isStaticColumn } from '../../utils/queueColumnRouting'
import { useProductionOrderCancel } from './useProductionOrderCancel'

import type ScrapPiecesDialog from '../../components/ScrapPiecesDialog.vue'
import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'
import type { LotPositionResponse, LotResponse } from '../../types/productionLotsResponse'
import type { BoardColumn } from './useQueueBoardColumns'

export interface QueueCardActionsOptions {
  lotsById: Ref<Map<number, LotResponse>>
  positionFor: (order: ProductionOrderResponse) => LotPositionResponse | undefined
  processMethodLabel: (order: ProductionOrderResponse) => string | null
}

/**
 * Production order card actions on the queue board and the dialogs they
 * open. `cardBindings` returns the props and listeners every card on the
 * board shares, so the template binds them with a single v-bind.
 */
export function useQueueCardActions(options: QueueCardActionsOptions) {
  const { t } = useI18n()
  const { withErrorToast } = useErrorToast()
  const { hasPermission } = usePermissions()
  const store = useProductionQueueStore()
  const currentUserStore = useCurrentUserStore()
  const { confirmCancel } = useProductionOrderCancel()

  const canWrite = computed(() => hasPermission(Permission.WRITE_PRODUCTION_ORDERS))
  const canManage = computed(() => hasPermission(Permission.MANAGE_PRODUCTION_ORDERS))

  const { target: splitTarget, visible: showSplit, open: onCardSplit } =
    useDialogTarget<ProductionOrderResponse>()
  const { target: mergeTarget, visible: showMerge, open: onCardMerge } =
    useDialogTarget<ProductionOrderResponse>()
  const { target: startTarget, visible: showStart, open: openStart } =
    useDialogTarget<ProductionOrderResponse>()
  const { target: pauseTarget, visible: showPause, open: onCardPause } =
    useDialogTarget<ProductionOrderResponse>()
  const { target: completionTarget, visible: showCompletion, open: onCardComplete } =
    useDialogTarget<ProductionOrderResponse>()
  const { target: assessmentTarget, visible: showAssessment, open: openAssessment } =
    useDialogTarget<ProductionOrderResponse>()

  const scrapDialogRef = ref<InstanceType<typeof ScrapPiecesDialog> | null>(null)

  // The start dialog only asks for an operator (shared accounts) and a
  // machine (orders on a pool without a resolved machine). With neither to
  // ask, the order starts right away.
  async function onCardStart(order: ProductionOrderResponse): Promise<void> {
    const needsMachineSelection = order.machine_pool_id != null && order.machine_id === null
    if (!currentUserStore.isSharedAccount && !needsMachineSelection) {
      await withErrorToast(() => store.start(order.id), {
        summary: t('productionQueue.card.startError'),
      })
      return
    }
    openStart(order)
  }

  const completionSteps = computed(() =>
    completionTarget.value ? (options.positionFor(completionTarget.value)?.steps ?? []) : [],
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
    if (updated.status === 'completed') openAssessment(updated)
  }

  function onCardScrap(order: ProductionOrderResponse): void {
    void scrapDialogRef.value?.open({ kind: 'order', order })
  }

  // The scrap endpoint returns the lot, not the order, so the board refetches
  // its orders to show current quantities and status.
  function onPiecesScrapped(): void {
    void store.fetchOrders()
  }

  function cardBindings(
    order: ProductionOrderResponse,
    kind: BoardColumn['kind'],
    isDraggable: boolean,
  ) {
    return {
      order,
      canWrite: canWrite.value,
      canManage: canManage.value,
      draggable: isDraggable,
      processMethod: options.processMethodLabel(order),
      lot: options.lotsById.value.get(order.lot_id) ?? null,
      hideNoMachineConflict: isStaticColumn(kind),
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

  return {
    canWrite,
    splitTarget,
    showSplit,
    mergeTarget,
    showMerge,
    startTarget,
    showStart,
    pauseTarget,
    showPause,
    completionTarget,
    showCompletion,
    completionSteps,
    assessmentTarget,
    showAssessment,
    scrapDialogRef,
    onCompletionRecorded,
    onPiecesScrapped,
    cardBindings,
  }
}
