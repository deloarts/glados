import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { useProductionLotsStore } from '../../../stores/productionLotsStore'
import { approveLotSource } from '../../api/approveLotSource'
import { rejectLotSource } from '../../api/rejectLotSource'
import { refreshOnConflict } from '../../utils/refreshOnConflict'

import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

// Approve/reject from the sourceStatus column. Row-local actions, same
// "mutate then lotsStore.triggerRefresh()" refresh this table already uses
// elsewhere. There's no dedicated approve/reject store method (these are
// plain API calls, not productionLotsStore actions), so the trigger has to
// be called explicitly here.
export function useLotSourceApproval() {
  const { t } = useI18n()
  const toast = useAppToast()
  const { withErrorToast } = useErrorToast()
  const lotsStore = useProductionLotsStore()

  const approvingSourceLotId = ref<number | null>(null)
  const rejectingSource = ref(false)
  const rejectSourceLot = ref<LotSummaryResponse | null>(null)
  const showRejectSource = ref(false)

  async function approveSourceRow(lot: LotSummaryResponse): Promise<void> {
    if (approvingSourceLotId.value !== null) return
    approvingSourceLotId.value = lot.id
    const succeeded = await withErrorToast(
      async () => {
        await refreshOnConflict(
          () => approveLotSource(lot.id, lot.edit_version),
          () => lotsStore.triggerRefresh(),
        )
        lotsStore.triggerRefresh()
        return true
      },
      { summary: t('production.lots.detail.record.sourceApproval.title') },
    )
    if (succeeded) {
      toast.success(lot.lot_number, t('production.lots.detail.record.sourceApproval.approveSuccess'))
    }
    approvingSourceLotId.value = null
  }

  function openRejectSourceRow(lot: LotSummaryResponse): void {
    rejectSourceLot.value = lot
    showRejectSource.value = true
  }

  async function confirmRejectSourceRow(reason: string): Promise<void> {
    const lot = rejectSourceLot.value
    if (!lot) return
    rejectingSource.value = true
    const succeeded = await withErrorToast(
      async () => {
        await refreshOnConflict(
          () => rejectLotSource(lot.id, { reason, expected_edit_version: lot.edit_version }),
          () => lotsStore.triggerRefresh(),
        )
        lotsStore.triggerRefresh()
        return true
      },
      { summary: t('production.lots.detail.record.sourceApproval.title') },
    )
    if (succeeded) {
      showRejectSource.value = false
      toast.success(lot.lot_number, t('production.lots.detail.record.sourceApproval.rejectSuccess'))
    }
    rejectingSource.value = false
  }

  return {
    approvingSourceLotId,
    rejectingSource,
    rejectSourceLot,
    showRejectSource,
    approveSourceRow,
    openRejectSourceRow,
    confirmRejectSourceRow,
  }
}
