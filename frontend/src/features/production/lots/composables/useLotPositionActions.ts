import { ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useErrorToast } from '@/core/composables/useErrorToast'
import { useDialogTarget } from '@/shared/composables/useDialogTarget'
import { useProductionLotDetailStore } from '../stores/productionLotDetailStore'

import type { LotPositionResponse } from '../../types/productionLotsResponse'

/**
 * Position actions on an open lot. The assign, provision and append dialogs
 * make their own API calls, so this only tracks which position each is open
 * for. Unassign has no dialog and is a plain action.
 */
export function useLotPositionActions(lotId: Ref<number>) {
  const { t } = useI18n()
  const { withErrorToast } = useErrorToast()
  const detailStore = useProductionLotDetailStore()

  const {
    target: assignTarget,
    visible: showAssign,
    open: openAssign,
  } = useDialogTarget<LotPositionResponse>()
  const {
    target: assignInternalTarget,
    visible: showAssignInternal,
    open: openAssignInternal,
  } = useDialogTarget<LotPositionResponse>()
  const {
    target: provisionsTarget,
    visible: showProvisions,
    open: openProvisions,
  } = useDialogTarget<LotPositionResponse>()

  const showAppendPosition = ref(false)

  function openAppendPosition(): void {
    showAppendPosition.value = true
  }

  async function unassign(position: LotPositionResponse): Promise<void> {
    await withErrorToast(() => detailStore.unassignPosition(lotId.value, position.id), {
      summary: t('production.lots.detail.assign.unassignError'),
    })
  }

  return {
    assignTarget,
    showAssign,
    openAssign,
    assignInternalTarget,
    showAssignInternal,
    openAssignInternal,
    provisionsTarget,
    showProvisions,
    openProvisions,
    showAppendPosition,
    openAppendPosition,
    unassign,
  }
}
