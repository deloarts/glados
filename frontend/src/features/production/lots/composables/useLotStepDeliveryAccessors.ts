import type { Ref } from 'vue'

import {
  useLotStepDeliveryInfo,
  type ConfirmedDeliveryInfo,
  type PlannedDateEditTarget,
  type PlannedInfo,
  type SourceOrderInfo,
} from '../../composables/useLotStepDeliveryInfo'
import type {
  LotSummaryPositionResponse,
  LotSummaryResponse,
  LotSummaryStepResponse,
} from '../../types/productionLotsResponse'

// Reshapes useLotStepDeliveryInfo's (lot, position) accessors into
// (lot, step) ones for Column Mode, which has the step object at hand.
export function useLotStepDeliveryAccessors(lots: Ref<LotSummaryResponse[]>) {
  const {
    positionFor,
    plannedDateFor,
    confirmedDeliveryFor,
    editTargetFor,
    sourceOrderInfoFor,
    lotHasPastTargetDateConflict,
  } = useLotStepDeliveryInfo(lots)

  // The forward-looking plan, met or not.
  function stepPlannedInfo(
    lot: LotSummaryResponse,
    step: LotSummaryStepResponse | undefined,
  ): PlannedInfo | null {
    return step ? plannedDateFor(positionFor(lot.id, step.position_id)) : null
  }

  // What actually arrived or finished, derived from the planned info so the
  // two columns agree on the latest entry.
  function stepConfirmedDelivery(
    lot: LotSummaryResponse,
    step: LotSummaryStepResponse | undefined,
  ): ConfirmedDeliveryInfo | null {
    const planned = stepPlannedInfo(lot, step)
    return planned ? confirmedDeliveryFor(planned) : null
  }

  function stepPlannedEditTarget(
    lot: LotSummaryResponse,
    step: LotSummaryStepResponse | undefined,
  ): PlannedDateEditTarget {
    return step ? editTargetFor(lot.id, step.id) : null
  }

  function stepSourceOrderInfo(
    lot: LotSummaryResponse,
    step: LotSummaryStepResponse | undefined,
  ): SourceOrderInfo | null {
    return step ? sourceOrderInfoFor(positionFor(lot.id, step.position_id)) : null
  }

  // The position behind a step, for tooltips built from position fields.
  function stepPosition(
    lot: LotSummaryResponse,
    step: LotSummaryStepResponse | undefined,
  ): LotSummaryPositionResponse | undefined {
    return step ? positionFor(lot.id, step.position_id) : undefined
  }

  return {
    stepPlannedInfo,
    stepConfirmedDelivery,
    stepPlannedEditTarget,
    stepSourceOrderInfo,
    stepPosition,
    lotHasPastTargetDateConflict,
  }
}
