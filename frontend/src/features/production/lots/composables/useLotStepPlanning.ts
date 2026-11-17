import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { hasAction } from '@/core/utils/lifecycleActions'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'
import { useProductionQueueStore } from '../../stores/productionQueueStore'
import { findStepNeighbors } from '../../utils/lotStepNeighbors'
import { stepMethodLabel } from '../../utils/lotStepDisplay'
import { resolvePlannedStepInfo } from '../utils/lotStepPlannedInfo'
import { activeOrderFor, reassignableOrder } from '../utils/lotStepPositionOrders'

import type {
  PlannedDateContext,
  PlannedDateEditTarget,
} from '../../composables/useLotStepDeliveryInfo'
import type { PlannedStepInfo } from '../components/DeliveryDateCell.vue'
import type { LotPositionResponse, LotStepResponse } from '../../types/productionLotsResponse'
import type { ProductionOrderResponse } from '../../types/productionOrdersResponse'

export interface LotStepPlanningProps {
  lotId: number
  steps: LotStepResponse[]
  madeItemId: number
  madeItemPartNumber: string
  madeItemRevision: string
  madeItemArticleName: string
}

/**
 * Planned dates and completion for the lot step list. Both work on the
 * position's single active production order, resolved against the queue
 * store's full orders, which carry the planned dates, planner and status
 * the lighter position summary lacks.
 */
export function useLotStepPlanning(props: LotStepPlanningProps) {
  const { t } = useI18n()
  const { hasPermission } = usePermissions()
  const detailStore = useProductionLotDetailStore()
  const queueStore = useProductionQueueStore()

  function fullOrderFor(order: { id: number } | null): ProductionOrderResponse | undefined {
    if (!order) return undefined
    return queueStore.orders.find((o) => o.id === order.id)
  }

  function plannedInfoFor(position: LotPositionResponse | undefined): PlannedStepInfo {
    if (!position) return { date: null, startDate: null, plannedByLabel: null }
    const order = activeOrderFor(position)
    return resolvePlannedStepInfo({
      position,
      activeOrder: order,
      fullOrder: fullOrderFor(order),
      autoPlannerLabel: t('production.lots.plannedDate.autoPlanner'),
    })
  }

  function stepContextFor(step: LotStepResponse): PlannedDateContext {
    const { prevStep, nextStep } = findStepNeighbors(props.steps, step.id)
    return {
      lotId: props.lotId,
      madeItem: {
        id: props.madeItemId,
        partNumber: props.madeItemPartNumber,
        revision: props.madeItemRevision,
        articleName: props.madeItemArticleName,
      },
      thisStep: { fabricationMethodName: stepMethodLabel(step) },
      prevStep: prevStep ? { fabricationMethodName: stepMethodLabel(prevStep) } : null,
      nextStep: nextStep ? { fabricationMethodName: stepMethodLabel(nextStep) } : null,
    }
  }

  // Only internal positions are editable here: resending an external
  // position's dates needs the order item's quantity and unit, which the
  // position summary lacks. The Manage Orders panel covers that case.
  function plannedEditTarget(
    step: LotStepResponse,
    position: LotPositionResponse | undefined,
  ): PlannedDateEditTarget {
    const order = reassignableOrder(position)
    if (!order) return null
    const full = fullOrderFor(order)
    if (!full) return null
    return {
      kind: 'internal',
      orderId: order.id,
      editVersion: order.edit_version,
      currentPlannedStart: full.planned_start,
      currentPlannedEnd: full.planned_end,
      ...stepContextFor(step),
    }
  }

  const showSetPlannedDate = ref(false)
  const plannedDateEditTarget = ref<PlannedDateEditTarget>(null)

  function openSetPlannedDate(target: PlannedDateEditTarget): void {
    if (!target) return
    plannedDateEditTarget.value = target
    showSetPlannedDate.value = true
  }

  async function onPlannedDateSaved(): Promise<void> {
    await Promise.all([queueStore.fetchOrders(), detailStore.refetch()])
  }

  // Completion is offered only for an unambiguous order that offers it, the
  // same gate as the queue card's complete action.
  function completableOrder(
    position: LotPositionResponse | undefined,
  ): ProductionOrderResponse | null {
    const full = fullOrderFor(activeOrderFor(position))
    return full && hasAction(full, 'record_completion') ? full : null
  }

  // Completing an inspection position needs write:inspections, so without
  // it the trigger is disabled rather than opening a dialog that would refuse.
  function canCompletePosition(position: LotPositionResponse | undefined): boolean {
    const hasInspectionStep = (position?.steps ?? []).some((s) => s.role === 'inspection')
    return !hasInspectionStep || hasPermission(Permission.WRITE_INSPECTIONS)
  }

  const showCompletion = ref(false)
  const completionTarget = ref<ProductionOrderResponse | null>(null)
  const completionSteps = ref<LotStepResponse[]>([])

  function openCompletion(
    order: ProductionOrderResponse,
    position: LotPositionResponse | undefined,
  ): void {
    completionTarget.value = order
    completionSteps.value = position?.steps ?? []
    showCompletion.value = true
  }

  // recordCompletion already updates the queue store from its response; the
  // position-level rollups such as quantity_completed live on the lot.
  async function onCompletionRecorded(): Promise<void> {
    showCompletion.value = false
    await detailStore.refetch()
  }

  return {
    plannedInfoFor,
    plannedEditTarget,
    showSetPlannedDate,
    plannedDateEditTarget,
    openSetPlannedDate,
    onPlannedDateSaved,
    completableOrder,
    canCompletePosition,
    showCompletion,
    completionTarget,
    completionSteps,
    openCompletion,
    onCompletionRecorded,
  }
}
