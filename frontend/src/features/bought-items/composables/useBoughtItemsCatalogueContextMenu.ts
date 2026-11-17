import { computed, ref, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { useClipboard } from '@/core/composables/useClipboard'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { disabledItemTooltipPt } from '@/shared/utils/menuItemTooltip'

import type { MenuItem } from 'openvue/menuitem'
import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { BoughtItemResponse } from '../types/boughtItemsResponse'

export interface BoughtItemsCatalogueContextMenuActions {
  canWrite: Ref<boolean>
  canDelete: Ref<boolean>
  canCreateDemand: Ref<boolean>
  canWriteOrders: Ref<boolean>
  canPrint: Ref<boolean>
  printingItemId: Ref<number | null>
  openDetailForEdit: (item: BoughtItemResponse) => void
  copyItem: (item: BoughtItemResponse) => void
  mergeItem: (item: BoughtItemResponse) => void
  onRestoreItem: (item: BoughtItemResponse) => Promise<void>
  onArchiveItem: (item: BoughtItemResponse) => void
  createDemandFor: (item: BoughtItemResponse) => void
  addItemToOrder: (item: BoughtItemResponse) => void
  openOrderHistory: (item: BoughtItemResponse) => void
  showChangelogFor: (item: BoughtItemResponse) => void
  onPrintLabel: (item: BoughtItemResponse) => Promise<void>
}

// The row context menu: its item list, the ContextMenu ref it drives, and
// the item it was opened for.
export function useBoughtItemsCatalogueContextMenu(actions: BoughtItemsCatalogueContextMenuActions) {
  const { t } = useI18n()
  const { copyToClipboard } = useClipboard()
  const { missing } = useMissingPermission()

  const cm = ref()
  const contextMenuItem = ref<BoughtItemResponse | null>(null)

  function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
    cm.value?.show(event.originalEvent)
  }

  const contextMenuItems = computed<MenuItem[]>(() => {
    const item = contextMenuItem.value
    if (!item) return []

    return [
      {
        label: t('boughtItems.catalogue.controls.edit'),
        icon: 'mdi mdi-pencil',
        disabled: !actions.canWrite.value,
        title: missing(Permission.WRITE_BOUGHT_ITEMS) || undefined,
        command: () => actions.openDetailForEdit(item),
      },
      {
        label: t('boughtItems.catalogue.controls.copy'),
        icon: 'mdi mdi-content-copy',
        disabled: !actions.canWrite.value,
        title: missing(Permission.WRITE_BOUGHT_ITEMS) || undefined,
        command: () => actions.copyItem(item),
      },
      {
        label: t('boughtItems.catalogue.controls.merge'),
        icon: 'mdi mdi-source-merge',
        disabled: !actions.canDelete.value,
        title: missing(Permission.DELETE_BOUGHT_ITEMS) || undefined,
        command: () => actions.mergeItem(item),
      },
      item.archived
        ? {
            label: t('common.restore'),
            icon: 'mdi mdi-archive-arrow-up-outline',
            disabled: !actions.canDelete.value,
            title: missing(Permission.DELETE_BOUGHT_ITEMS) || undefined,
            command: () => void actions.onRestoreItem(item),
          }
        : {
            label: t('common.archive'),
            icon: 'mdi mdi-archive-outline',
            disabled: !actions.canDelete.value,
            title: missing(Permission.DELETE_BOUGHT_ITEMS) || undefined,
            command: () => actions.onArchiveItem(item),
          },
      { separator: true },
      {
        label: t('boughtItems.catalogue.contextMenu.createDemand'),
        icon: 'mdi mdi-cart-plus',
        disabled: !actions.canCreateDemand.value,
        title: missing(Permission.WRITE_DEMAND_ITEMS) || undefined,
        command: () => actions.createDemandFor(item),
      },
      {
        label: t('boughtItems.catalogue.contextMenu.addToOrder'),
        icon: 'mdi mdi-cart-arrow-right',
        disabled: !actions.canWriteOrders.value,
        title: missing(Permission.WRITE_ORDERS) || undefined,
        command: () => actions.addItemToOrder(item),
      },
      { separator: true },
      {
        label: t('boughtItems.catalogue.orderHistory.viewOrders'),
        icon: 'mdi mdi-receipt-text-outline',
        command: () => actions.openOrderHistory(item),
      },
      {
        label: t('boughtItems.catalogue.contextMenu.showChangelog'),
        icon: 'mdi mdi-history',
        command: () => actions.showChangelogFor(item),
      },
      {
        label: t('boughtItems.catalogue.contextMenu.printLabel'),
        icon: 'mdi mdi-tag-outline',
        disabled: !actions.canPrint.value || actions.printingItemId.value === item.id,
        title: missing(Permission.PRINT_DOCUMENTS) || undefined,
        command: () => void actions.onPrintLabel(item),
      },
      { separator: true },
      {
        label: t('common.copyUuid'),
        icon: 'mdi mdi-content-copy',
        command: () => void copyToClipboard(item.public_id),
      },
    ]
  })

  return { cm, contextMenuItem, onRowContextMenu, contextMenuItems, disabledItemTooltipPt }
}
