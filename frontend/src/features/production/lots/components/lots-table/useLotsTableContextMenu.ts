import { computed, ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { useClipboard } from '@/core/composables/useClipboard'
import { canDemandSourceItem } from '../../utils/lotSourceEligibility'
import { useMaterialSourceChangeReason } from '../../composables/useMaterialSourceChange'
import { hasInternalPosition } from '../../utils/lotScrapEligibility'
import { Permission } from '@/core/auth/permissions'
import { hasAction } from '@/core/utils/lifecycleActions'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { isTerminalLotStatus } from '../../../utils/lotStatus'
import type { LotPrintClassifier } from './useLotPrinting'

import type { MenuItem } from 'openvue/menuitem'
import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { LotSummaryResponse } from '../../../types/productionLotsResponse'

// The row-level actions the context menu can trigger, one callback per
// LotsTable emit it forwards to, using plain callbacks rather than the emit
// function itself, so this composable doesn't have to match Vue's emit type.
export interface LotsTableContextMenuActions {
  openLot: (lot: LotSummaryResponse) => void
  editSteps: (lot: LotSummaryResponse) => void
  setRequiredDelivery: (lot: LotSummaryResponse) => void
  forceStatus: (lot: LotSummaryResponse, action: 'complete' | 'cancel') => void
  addSourceItem: (lot: LotSummaryResponse) => void
  demandSourceItem: (lot: LotSummaryResponse) => void
  scrapPieces: (lot: LotSummaryResponse) => void
  inspectionReport: (lot: LotSummaryResponse) => void
}

// The row context menu: its item list, the ContextMenu ref it drives, and
// the lot it was opened for.
export function useLotsTableContextMenu(
  lotOf: (data: unknown) => LotSummaryResponse,
  canWrite: Ref<boolean>,
  canManage: Ref<boolean>,
  canPrint: Ref<boolean>,
  canWriteProductionOrders: Ref<boolean>,
  isPrintingLot: (lot: LotSummaryResponse, classifier: LotPrintClassifier) => boolean,
  onPrintLot: (lot: LotSummaryResponse, classifier: LotPrintClassifier) => Promise<void>,
  openAuditTrail: (lot: LotSummaryResponse) => void,
  actions: LotsTableContextMenuActions,
) {
  const { t } = useI18n()
  const { copyToClipboard } = useClipboard()
  const { sourceChangeBlockedReason } = useMaterialSourceChangeReason()
  const { missingForAction } = useMissingPermission()

  const cm = ref()
  const contextMenuItem = ref<unknown>(null)

  function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
    cm.value?.show(event.originalEvent)
  }

  const contextMenuLot = computed<LotSummaryResponse | null>(() =>
    contextMenuItem.value ? lotOf(contextMenuItem.value) : null,
  )

  const contextMenuItems = computed<MenuItem[]>(() => {
    const lot = contextMenuLot.value
    if (!lot) return []
    // The required delivery date is no lifecycle action; a finished lot
    // simply takes no new one.
    const isTerminal = isTerminalLotStatus(lot.status)
    const sourceChangeBlocked = sourceChangeBlockedReason(lot, canWrite.value)
    return [
      {
        label: t('production.lots.contextMenu.show'),
        icon: 'mdi mdi-eye-outline',
        command: () => actions.openLot(lot),
      },
      {
        label: t('production.lots.contextMenu.editSteps'),
        icon: 'mdi mdi-format-list-numbered',
        command: () => actions.editSteps(lot),
      },
      {
        label: t('production.lots.contextMenu.setRequiredDelivery'),
        icon: 'mdi mdi-calendar-edit-outline',
        disabled: !canWrite.value || isTerminal,
        command: () => actions.setRequiredDelivery(lot),
      },
      {
        label: t('production.lots.contextMenu.auditTrail'),
        icon: 'mdi mdi-shield-check-outline',
        command: () => openAuditTrail(lot),
      },
      {
        label: t('production.lots.contextMenu.scrapPieces'),
        icon: 'mdi mdi-delete-alert-outline',
        disabled:
          !canWriteProductionOrders.value || !hasAction(lot, 'scrap') || !hasInternalPosition(lot),
        command: () => actions.scrapPieces(lot),
      },
      {
        label: t('production.lots.contextMenu.print'),
        icon: 'mdi mdi-printer-outline',
        items: [
          {
            label: t('production.lots.contextMenu.printLotLabel'),
            icon: 'mdi mdi-tag-outline',
            disabled: !canPrint.value || isPrintingLot(lot, 'lot_label'),
            command: () => void onPrintLot(lot, 'lot_label'),
          },
          {
            label: t('production.lots.contextMenu.printLotDocket'),
            icon: 'mdi mdi-file-document-outline',
            disabled: !canPrint.value || isPrintingLot(lot, 'lot_docket'),
            command: () => void onPrintLot(lot, 'lot_docket'),
          },
          {
            label: t('production.lots.contextMenu.printScrapTag'),
            icon: 'mdi mdi-alert-octagon-outline',
            disabled:
              !canPrint.value ||
              isPrintingLot(lot, 'scrap_tag') ||
              !((lot.quantity_scrapped ?? 0) > 0),
            command: () => void onPrintLot(lot, 'scrap_tag'),
          },
          { separator: true },
          {
            label: t('production.lots.report.print'),
            icon: 'mdi mdi-file-certificate-outline',
            command: () => actions.inspectionReport(lot),
          },
        ],
      },
      { separator: true },
      {
        label: t('production.lots.contextMenu.addSourceItem'),
        icon: 'mdi mdi-database-import-outline',
        disabled: sourceChangeBlocked !== '',
        title: sourceChangeBlocked || undefined,
        command: () => actions.addSourceItem(lot),
      },
      {
        label: t('production.lots.contextMenu.demandSourceItem'),
        icon: 'mdi mdi-cart-plus',
        disabled: !canWrite.value || !canDemandSourceItem(lot),
        command: () => actions.demandSourceItem(lot),
      },
      { separator: true },
      {
        label: t('production.lots.contextMenu.setCompleted'),
        icon: 'mdi mdi-check-circle-outline',
        disabled: !canWrite.value || !canManage.value || !hasAction(lot, 'force_complete'),
        title: missingForAction(lot, 'force_complete', Permission.WRITE_LOTS) || undefined,
        command: () => actions.forceStatus(lot, 'complete'),
      },
      {
        label: t('production.lots.contextMenu.setCanceled'),
        icon: 'mdi mdi-close-circle-outline',
        disabled: !canWrite.value || !canManage.value || !hasAction(lot, 'cancel'),
        title: missingForAction(lot, 'cancel', Permission.WRITE_LOTS) || undefined,
        command: () => actions.forceStatus(lot, 'cancel'),
      },
      { separator: true },
      {
        label: t('common.copyUuid'),
        icon: 'mdi mdi-content-copy',
        command: () => void copyToClipboard(lot.public_id),
      },
    ]
  })

  return { cm, contextMenuItem, onRowContextMenu, contextMenuItems }
}
