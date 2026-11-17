import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppToast } from '@/core/composables/useAppToast'
import { useConfirm } from 'openvue/useconfirm'

import { extractApiError } from '@/core/utils/errors'
import { usePrint } from '@/shared/print'
import { useBoughtItemsStore } from '../stores/boughtItemsStore'
import { useBoughtItemsCatalogueEditStore } from '../stores/boughtItemsCatalogueEditStore'

import type { BoughtItemResponse } from '../types/boughtItemsResponse'

// The row-local state changes BoughtItemsCatalogueTable drives directly:
// entering bulk-edit on one item, archive/restore, and label printing.
export function useBoughtItemsCatalogueRowActions() {
  const { t } = useI18n()
  const toast = useAppToast()
  const printService = usePrint()
  const confirm = useConfirm()
  const boughtItemsStore = useBoughtItemsStore()
  const editStore = useBoughtItemsCatalogueEditStore()

  function editItem(item: BoughtItemResponse): void {
    editStore.editMode = true
    editStore.selectedItems = [item]
  }

  function onArchiveItem(item: BoughtItemResponse): void {
    async function onAccept(): Promise<void> {
      try {
        await boughtItemsStore.archive(item.id)
        toast.success(item.article_name, t('common.archive'))
      } catch (e) {
        toast.error(item.article_name, extractApiError(e) ?? t('boughtItems.catalogue.errors.unknown'))
      }
    }

    confirm.require({
      message: t('common.archiveConfirm', { name: item.article_name }),
      header: t('common.archive'),
      icon: 'mdi mdi-archive-outline',
      rejectProps: { label: t('common.cancel'), severity: 'secondary' },
      acceptProps: { label: t('common.archive'), severity: 'warn' },
      accept: () => void onAccept(),
    })
  }

  async function onRestoreItem(item: BoughtItemResponse): Promise<void> {
    try {
      await boughtItemsStore.restore(item.id)
      toast.success(item.article_name, t('common.restore'))
    } catch (e) {
      toast.error(item.article_name, extractApiError(e) ?? t('boughtItems.catalogue.errors.unknown'))
    }
  }

  const printingItemId = ref<number | null>(null)

  async function onPrintLabel(item: BoughtItemResponse): Promise<void> {
    printingItemId.value = item.id
    try {
      const [job] = await printService.print({
        root_type: 'bought_item',
        root_id: item.id,
        items: [{ classifier: 'bought_item_label' }],
      })
      if (job?.status === 'sent') {
        toast.success(item.article_name, t('boughtItems.catalogue.contextMenu.printLabelSent'))
      } else {
        toast.error(
          item.article_name,
          job?.error_message ?? t('boughtItems.catalogue.contextMenu.printLabelFailed'),
        )
      }
    } catch (e) {
      toast.error(
        item.article_name,
        extractApiError(e) ?? t('boughtItems.catalogue.contextMenu.printLabelFailed'),
      )
    } finally {
      printingItemId.value = null
    }
  }

  return { editItem, onArchiveItem, onRestoreItem, printingItemId, onPrintLabel }
}
