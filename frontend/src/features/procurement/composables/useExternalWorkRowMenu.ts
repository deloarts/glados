import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { useProductionLotDetailStore } from '@/features/production'
import type { LotPositionResponse } from '@/features/production'
import { Permission } from '@/core/auth/permissions'
import { useAppToast } from '@/core/composables/useAppToast'
import { extractApiError } from '@/core/utils/errors'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useExternalWorkActions } from './useExternalWorkActions'

import type { MenuItem } from 'openvue/menuitem'
import type { ExternalWorkRow } from '../types/externalWork'

/**
 * The context menu of an external work row and the dialogs it opens: open
 * the lot, take the suggested supplier, choose another, take the part off
 * its order again, and record the pieces handed to the supplier. A disabled
 * entry names why. `refresh` reloads the list after a change.
 */
export function useExternalWorkRowMenu(refresh: () => Promise<void>) {
  const { t } = useI18n()
  const router = useRouter()
  const toast = useAppToast()
  const { openLotDetail } = useLotDetail()
  const { missing } = useMissingPermission()
  const lotDetailStore = useProductionLotDetailStore()
  const actions = useExternalWorkActions()

  const menuRow = ref<ExternalWorkRow | null>(null)

  async function runAction(
    row: ExternalWorkRow,
    action: () => Promise<void>,
    doneKey: 'takeSuggestionDone' | 'removedFromOrder',
  ): Promise<void> {
    try {
      await action()
      toast.success(
        row.lot_number,
        t(`procurement.externalWork.menu.${doneKey}`, { supplier: row.suggested_supplier_name }),
      )
    } catch (e) {
      toast.error(row.lot_number, extractApiError(e) ?? t('procurement.externalWork.menu.failed'))
    }
    await refresh()
  }

  // The assign and provision dialogs of the lot detail work on the lot that
  // store holds, so the row's lot is loaded into it first.
  const dialogLotId = ref(0)
  const dialogPosition = ref<LotPositionResponse | null>(null)
  const showAssign = ref(false)
  const showProvision = ref(false)

  async function loadPosition(row: ExternalWorkRow): Promise<boolean> {
    try {
      await lotDetailStore.fetch(row.lot_id)
    } catch (e) {
      toast.error(row.lot_number, extractApiError(e) ?? t('procurement.externalWork.menu.failed'))
      return false
    }
    dialogLotId.value = row.lot_id
    dialogPosition.value =
      lotDetailStore.lot?.positions.find((position) => position.id === row.position_id) ?? null
    return dialogPosition.value !== null
  }

  async function openAssign(row: ExternalWorkRow): Promise<void> {
    if (await loadPosition(row)) showAssign.value = true
  }

  async function openProvision(row: ExternalWorkRow): Promise<void> {
    if (await loadPosition(row)) showProvision.value = true
  }

  // The provision dialog stays open while pieces are recorded, so the list
  // catches up once it closes.
  watch(showProvision, (open) => {
    if (!open) void refresh()
  })

  const items = computed<MenuItem[]>(() => {
    const row = menuRow.value
    if (!row) return []
    const onOrder = row.order_item_id !== null
    const handedOver = row.handed_over_quantity > 0
    const ordersReason = missing(Permission.WRITE_ORDERS)
    const lotsReason = missing(Permission.WRITE_LOTS)
    return [
      {
        label: t('procurement.externalWork.menu.openLot'),
        icon: 'mdi mdi-open-in-app',
        command: () => openLotDetail(row.lot_id),
      },
      {
        label: t('procurement.externalWork.menu.openLotInNewTab'),
        icon: 'mdi mdi-open-in-new',
        command: () =>
          window.open(router.resolve(`/production/lots/${row.lot_id}`).href, '_blank', 'noopener'),
      },
      { separator: true },
      {
        label: row.suggested_supplier_name
          ? t('procurement.externalWork.menu.takeSuggestion', {
              supplier: row.suggested_supplier_name,
            })
          : t('procurement.externalWork.menu.takeSuggestionNone'),
        icon: 'mdi mdi-truck-check-outline',
        disabled: onOrder || row.suggested_supplier_id === null || ordersReason !== '',
        title:
          ordersReason ||
          (onOrder
            ? t('procurement.externalWork.menu.reason.onOrder')
            : t('procurement.externalWork.menu.reason.noSuggestion')),
        command: () => void runAction(row, () => actions.takeSuggestion(row), 'takeSuggestionDone'),
      },
      {
        label: t('procurement.externalWork.menu.chooseSupplier'),
        icon: 'mdi mdi-truck-outline',
        disabled: onOrder || ordersReason !== '',
        title: ordersReason || t('procurement.externalWork.menu.reason.onOrder'),
        command: () => void openAssign(row),
      },
      {
        label: t('procurement.externalWork.menu.removeFromOrder'),
        icon: 'mdi mdi-truck-remove-outline',
        disabled: !onOrder || handedOver || ordersReason !== '',
        title:
          ordersReason ||
          (handedOver
            ? t('procurement.externalWork.menu.reason.handedOver')
            : t('procurement.externalWork.menu.reason.notOnOrder')),
        command: () => void runAction(row, () => actions.removeFromOrder(row), 'removedFromOrder'),
      },
      { separator: true },
      {
        label: t('procurement.externalWork.menu.recordProvision'),
        icon: 'mdi mdi-package-variant-closed-check',
        disabled: !onOrder || lotsReason !== '',
        title: lotsReason || t('procurement.externalWork.menu.reason.notOnOrder'),
        command: () => void openProvision(row),
      },
    ]
  })

  return { menuRow, items, dialogLotId, dialogPosition, showAssign, showProvision }
}
