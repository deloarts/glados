import { ref } from 'vue'

import { useProductionLotsStore } from '../../../stores/productionLotsStore'

import type { PlannedDateEditTarget } from '../../../composables/useLotStepDeliveryInfo'
import type { LotSummaryResponse } from '../../../types/productionLotsResponse'
import type { ScrapDialogTarget } from '../../../components/ScrapPiecesDialog.vue'

/** Structural, since only open() is called. */
interface LotRequiredDeliveryDateDialogApi {
  open(lot: LotSummaryResponse): void
}

interface ScrapPiecesDialogApi {
  open(target: ScrapDialogTarget): Promise<void>
}

// The simple dialogs LotsTable owns, each a visibility flag or template ref
// plus the row it was opened for.
export function useLotsTableDialogs() {
  const lotsStore = useProductionLotsStore()

  const showSetPlannedDate = ref(false)
  const plannedDateEditTarget = ref<PlannedDateEditTarget>(null)

  function openSetPlannedDate(target: PlannedDateEditTarget): void {
    if (!target) return
    plannedDateEditTarget.value = target
    showSetPlannedDate.value = true
  }

  function onPlannedDateSaved(): void {
    lotsStore.triggerRefresh()
  }

  const showOrderDetail = ref(false)
  const orderDetailId = ref<number | null>(null)

  function openOrderDetail(orderId: number): void {
    orderDetailId.value = orderId
    showOrderDetail.value = true
  }

  const showAuditTrail = ref(false)
  const auditTrailLot = ref<LotSummaryResponse | null>(null)

  function openAuditTrail(lot: LotSummaryResponse): void {
    auditTrailLot.value = lot
    showAuditTrail.value = true
  }

  const requiredDeliveryDialogRef = ref<LotRequiredDeliveryDateDialogApi>()

  function openSetRequiredDelivery(lot: LotSummaryResponse): void {
    requiredDeliveryDialogRef.value?.open(lot)
  }

  function onRequiredDeliverySaved(): void {
    lotsStore.triggerRefresh()
  }

  const scrapDialogRef = ref<ScrapPiecesDialogApi>()

  function openScrapPieces(lot: LotSummaryResponse): void {
    void scrapDialogRef.value?.open({ kind: 'lot', lotId: lot.id })
  }

  function onPiecesScrapped(): void {
    lotsStore.triggerRefresh()
  }

  return {
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
  }
}
