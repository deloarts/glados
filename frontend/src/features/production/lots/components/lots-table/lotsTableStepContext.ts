import type { InjectionKey } from 'vue'

import type { OpenQuoteRequestRef } from '@/features/quote-requests'

import type {
  ConfirmedDeliveryInfo,
  PlannedDateEditTarget,
  PlannedInfo,
  SourceOrderInfo,
} from '../../../composables/useLotStepDeliveryInfo'
import type {
  LotSummaryPositionResponse,
  LotSummaryResponse,
  LotSummaryStepResponse,
} from '../../../types/productionLotsResponse'

// Behavior LotsTable provides once and every nested column and cell
// component injects, since the leaf cells sit several levels down.
export interface LotsTableStepContext {
  isStepClickable(lot: LotSummaryResponse, step: LotSummaryStepResponse): boolean
  isStepSelected(lot: LotSummaryResponse, step: LotSummaryStepResponse): boolean
  isStepResolving(lot: LotSummaryResponse, step: LotSummaryStepResponse): boolean
  stepSeverity(lot: LotSummaryResponse, step: LotSummaryStepResponse): string
  onStepClick(lot: LotSummaryResponse, step: LotSummaryStepResponse, event: MouseEvent): void
  stepPlannedInfo(
    lot: LotSummaryResponse,
    step: LotSummaryStepResponse | undefined,
  ): PlannedInfo | null
  stepConfirmedDelivery(
    lot: LotSummaryResponse,
    step: LotSummaryStepResponse | undefined,
  ): ConfirmedDeliveryInfo | null
  stepPlannedEditTarget(
    lot: LotSummaryResponse,
    step: LotSummaryStepResponse | undefined,
  ): PlannedDateEditTarget
  stepSourceOrderInfo(
    lot: LotSummaryResponse,
    step: LotSummaryStepResponse | undefined,
  ): SourceOrderInfo | null
  stepPosition(
    lot: LotSummaryResponse,
    step: LotSummaryStepResponse | undefined,
  ): LotSummaryPositionResponse | undefined
  /** The open quote requests asking suppliers for the position. */
  quoteRequestsOf(positionId: number): OpenQuoteRequestRef[] | undefined
  lotHasPastTargetDateConflict(lotId: number): boolean
  openSetPlannedDate(target: PlannedDateEditTarget): void
  openDetailById(id: number): Promise<void>
  openOrderDetail(orderId: number): void
}

export const LOTS_TABLE_STEP_CONTEXT_KEY: InjectionKey<LotsTableStepContext> =
  Symbol('lotsTableStepContext')
