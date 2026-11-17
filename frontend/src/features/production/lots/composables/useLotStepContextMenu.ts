import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'

import type { DataTableRowContextMenuEvent } from 'openvue/datatable'
import type { MenuItem } from 'openvue/menuitem'

import { useClipboard } from '@/core/composables/useClipboard'

import type { LotStepResponse } from '../../types/productionLotsResponse'

/**
 * Row context menu of the lot step list. `cm` binds to the ContextMenu's
 * template ref and `contextMenuItem` to the table's context menu selection.
 */
export function useLotStepContextMenu() {
  const { t } = useI18n()
  const { copyToClipboard } = useClipboard()

  const cm = ref()
  const contextMenuItem = ref<LotStepResponse | null>(null)

  function onRowContextMenu(event: DataTableRowContextMenuEvent): void {
    cm.value?.show(event.originalEvent)
  }

  const contextMenuItems = computed<MenuItem[]>(() => {
    const step = contextMenuItem.value
    if (!step) return []
    return [
      {
        label: t('common.copyUuid'),
        icon: 'mdi mdi-content-copy',
        command: () => void copyToClipboard(step.public_id),
      },
    ]
  })

  return { cm, contextMenuItem, onRowContextMenu, contextMenuItems }
}
