import { useI18n } from 'vue-i18n'
import { hasAction } from '@/core/utils/lifecycleActions'
import { useAppToast } from '@/core/composables/useAppToast'

import type { Ref } from 'vue'

import { useProductionLotsSelectionStore } from '../stores/productionLotsSelectionStore'
import { useProductionLotsStore } from '../../stores/productionLotsStore'
import { useMachineCapability } from '../../composables/useMachineCapability'
import { pseudoPosition } from '../../utils/lotStepDisplay'
import { lotPositionKindSeverity } from '../../utils/lotStatus'

import type {
  LotPositionResponse,
  LotSummaryResponse,
  LotSummaryStepResponse,
} from '../../types/productionLotsResponse'

// Step clickability and selection for the Manage Orders and Manage
// Production batch flows.
export function useLotStepSelection(
  showManageOrders: Ref<boolean>,
  showManageProduction: Ref<boolean>,
) {
  const { t } = useI18n()
  const toast = useAppToast()
  const selectionStore = useProductionLotsSelectionStore()
  const lotsStore = useProductionLotsStore()
  const { machineCoversPosition, poolCoversPosition } = useMachineCapability()

  // null when no machine or pool is chosen yet.
  function targetCoversPosition(position: Pick<LotPositionResponse, 'steps'>): boolean | null {
    const machine = selectionStore.selectedMachine
    if (machine) return machineCoversPosition(position, machine)
    const pool = selectionStore.selectedPool
    if (pool) return poolCoversPosition(position, pool)
    return null
  }

  function isStepClickable(lot: LotSummaryResponse, step: LotSummaryStepResponse): boolean {
    if (showManageOrders.value) {
      // The position offers an external assignment: no live order line, an
      // unassigned or internal kind and quantity left to order.
      return hasAction(step, 'assign_external')
    }
    if (showManageProduction.value) {
      const position = pseudoPosition(lot, step.position_id)
      // The position offers an internal assignment: quantity left on a lot
      // that is not finished. Unassigned starts an order, external tops up into
      // a mixed position, internal tops up its own share.
      if (hasAction(step, 'assign_internal') && !step.position_needs_machine) {
        return targetCoversPosition(position) ?? true
      }
      if (step.position_needs_machine) {
        // Filling in a machine routes the order to one machine, so a pool cannot.
        const machine = selectionStore.selectedMachine
        if (!machine) return false
        return machineCoversPosition(position, machine)
      }
    }
    return false
  }

  function isStepSelected(lot: LotSummaryResponse, step: LotSummaryStepResponse): boolean {
    return selectionStore.items.some(
      (i) => i.lotId === lot.id && i.position.id === step.position_id,
    )
  }

  function isStepResolving(lot: LotSummaryResponse, step: LotSummaryStepResponse): boolean {
    return selectionStore.resolvingKeys.has(`${lot.id}:${step.position_id}`)
  }

  // With a target chosen, assignable steps the target cannot perform read as
  // danger. Success is reserved for completed positions.
  function stepSeverity(lot: LotSummaryResponse, step: LotSummaryStepResponse): string {
    const machine = selectionStore.selectedMachine
    const hasTarget = machine !== null || selectionStore.selectedPool !== null
    // Needs-machine steps are machine-only, so a pool never flags them.
    const targetable =
      step.position_kind === 'unassigned' || (step.position_needs_machine && machine !== null)
    if (showManageProduction.value && hasTarget && targetable) {
      const position = pseudoPosition(lot, step.position_id)
      if (targetCoversPosition(position) === false) return 'danger'
    }
    if (step.position_status === 'completed') return 'success'
    // An inspection step always reads as info.
    if (step.role === 'inspection') return 'info'
    return lotPositionKindSeverity[step.position_kind]
  }

  async function onStepClick(
    lot: LotSummaryResponse,
    step: LotSummaryStepResponse,
    event: MouseEvent,
  ): Promise<void> {
    if (!isStepClickable(lot, step)) return
    event.stopPropagation()

    const capabilityCheck = showManageProduction.value
      ? (position: LotPositionResponse) => targetCoversPosition(position) !== false
      : undefined

    const mode = showManageOrders.value ? 'orders' : 'machines'
    const result = await selectionStore.toggleStep(lot.id, step.position_id, mode, capabilityCheck)
    if (result === 'unavailable') {
      toast.warn(t('production.lots.listManage.unavailable'))
      lotsStore.triggerRefresh()
    }
  }

  return {
    isStepClickable,
    isStepSelected,
    isStepResolving,
    stepSeverity,
    onStepClick,
  }
}
