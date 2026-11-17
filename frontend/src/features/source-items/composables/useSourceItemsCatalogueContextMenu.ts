import { computed, type Ref } from 'vue'
import { useI18n } from 'vue-i18n'

import { Permission } from '@/core/auth/permissions'
import { useClipboard } from '@/core/composables/useClipboard'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'

import type { MenuItem } from 'openvue/menuitem'
import type { SourceItemResponse } from '../types/sourceItemsResponse'

export interface SourceItemsCatalogueContextMenuActions {
  contextMenuItem: Ref<SourceItemResponse | null>
  canWrite: Ref<boolean>
  canDelete: Ref<boolean>
  canPrint: Ref<boolean>
  printingItemId: Ref<number | null>
  openDetailForEdit: (item: SourceItemResponse) => void
  onPrintLabel: (item: SourceItemResponse) => Promise<void>
  onRestoreItem: (item: SourceItemResponse) => Promise<void>
  onArchiveItem: (item: SourceItemResponse) => void
}

/**
 * The entries of the source item catalogue's row context menu, for the item
 * it was opened on. An entry the user lacks the permission for stays in the
 * menu disabled, and its title names the permission for a menu bound to
 * disabledItemTooltipPt.
 */
export function useSourceItemsCatalogueContextMenu(actions: SourceItemsCatalogueContextMenuActions) {
  const { t } = useI18n()
  const { copyToClipboard } = useClipboard()
  const { missing } = useMissingPermission()

  const contextMenuItems = computed<MenuItem[]>(() => {
    const item = actions.contextMenuItem.value
    if (!item) return []
    const deleteBlocked = missing(Permission.DELETE_SOURCE_ITEMS) || undefined

    return [
      {
        label: t('sourceItems.catalogue.controls.edit'),
        icon: 'mdi mdi-pencil',
        disabled: !actions.canWrite.value,
        title: missing(Permission.WRITE_SOURCE_ITEMS) || undefined,
        command: () => actions.openDetailForEdit(item),
      },
      { separator: true },
      {
        label: t('sourceItems.edit.contextMenu.printLabel'),
        icon: 'mdi mdi-tag-outline',
        disabled: !actions.canPrint.value || actions.printingItemId.value === item.id,
        title: missing(Permission.PRINT_DOCUMENTS) || undefined,
        command: () => void actions.onPrintLabel(item),
      },
      { separator: true },
      item.archived
        ? {
            label: t('common.restore'),
            icon: 'mdi mdi-archive-arrow-up-outline',
            disabled: !actions.canDelete.value,
            title: deleteBlocked,
            command: () => void actions.onRestoreItem(item),
          }
        : {
            label: t('common.archive'),
            icon: 'mdi mdi-archive-outline',
            disabled: !actions.canDelete.value,
            title: deleteBlocked,
            command: () => actions.onArchiveItem(item),
          },
      { separator: true },
      {
        label: t('common.copyUuid'),
        icon: 'mdi mdi-content-copy',
        command: () => void copyToClipboard(item.public_id),
      },
    ]
  })

  return { contextMenuItems }
}
