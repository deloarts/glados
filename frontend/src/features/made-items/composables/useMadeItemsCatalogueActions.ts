import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useConfirm } from 'openvue/useconfirm'

import type { MenuItem } from 'openvue/menuitem'

import { useAppToast } from '@/core/composables/useAppToast'
import { useClipboard } from '@/core/composables/useClipboard'
import { usePermissions } from '@/core/composables/usePermissions'
import { Permission } from '@/core/auth/permissions'
import { useHostStore } from '@/core/host/stores/hostStore'
import { extractApiError } from '@/core/utils/errors'
import { usePrint } from '@/shared/print'
import { useDialogTarget } from '@/shared/composables/useDialogTarget'
import { useMissingPermission } from '@/shared/composables/useMissingPermission'
import { useMadeItemsStore } from '../stores/madeItemsStore'
import { useMadeItemsCatalogueEditStore } from '../stores/madeItemsCatalogueEditStore'

import type { MadeItemResponse } from '../types/madeItemsResponse'

/**
 * Row actions of the made items catalogue, shared by the row action buttons
 * and the context menu: the dialogs each action opens, archive and restore,
 * label printing, and the context menu model itself.
 */
export function useMadeItemsCatalogueActions() {
  const { t } = useI18n()
  const confirm = useConfirm()
  const toast = useAppToast()
  const printService = usePrint()
  const { copyToClipboard } = useClipboard()
  const { hasPermission } = usePermissions()
  const { missing } = useMissingPermission()
  const hostStore = useHostStore()
  const madeItemsStore = useMadeItemsStore()
  const editStore = useMadeItemsCatalogueEditStore()

  const canWrite = computed(() => hasPermission(Permission.WRITE_MADE_ITEMS))
  const canDelete = computed(() => hasPermission(Permission.DELETE_MADE_ITEMS))
  const canWriteDemands = computed(() => hasPermission(Permission.WRITE_DEMAND_ITEMS))
  const canPrint = computed(() => hasPermission(Permission.PRINT_DOCUMENTS))

  // A row click navigates to the detail page; this dialog only serves the
  // context menu's Edit entry, which opens it in edit mode.
  const detailItem = ref<MadeItemResponse | null>(null)
  const showDetail = ref(false)
  const detailEditOnOpen = ref(false)

  function openDetailForEdit(item: MadeItemResponse): void {
    detailItem.value = item
    detailEditOnOpen.value = true
    showDetail.value = true
  }

  const { target: copyFromItem, visible: showCopyForm, open: copyItem } =
    useDialogTarget<MadeItemResponse>()
  const { target: revisionOfItem, visible: showRevisionForm, open: openRevisionForm } =
    useDialogTarget<MadeItemResponse>()
  const { target: changelogItem, visible: showChangelogDialog, open: showChangelogFor } =
    useDialogTarget<MadeItemResponse>()
  const { target: mergeSourceItem, visible: showMergeDialog, open: mergeItem } =
    useDialogTarget<MadeItemResponse>()
  const { target: demandForItem, visible: showDemandForm, open: addToDemand } =
    useDialogTarget<MadeItemResponse>()
  const { target: historyItem, visible: showHistoryDialog, open: showHistoryFor } =
    useDialogTarget<MadeItemResponse>()

  function editItem(item: MadeItemResponse): void {
    editStore.editMode = true
    editStore.selectedItems = [item]
  }

  function onArchiveItem(item: MadeItemResponse): void {
    async function onAccept(): Promise<void> {
      try {
        await madeItemsStore.archive(item.id)
        toast.success(item.article_name, t('common.archive'))
      } catch (e) {
        toast.error(item.article_name, extractApiError(e) ?? t('madeItems.catalogue.errors.unknown'))
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

  async function onRestoreItem(item: MadeItemResponse): Promise<void> {
    try {
      await madeItemsStore.restore(item.id)
      toast.success(item.article_name, t('common.restore'))
    } catch (e) {
      toast.error(item.article_name, extractApiError(e) ?? t('madeItems.catalogue.errors.unknown'))
    }
  }

  const printingItemId = ref<number | null>(null)

  async function onPrintLabel(item: MadeItemResponse): Promise<void> {
    printingItemId.value = item.id
    try {
      const [job] = await printService.print({
        root_type: 'made_item',
        root_id: item.id,
        items: [{ classifier: 'made_item_label' }],
      })
      if (job?.status === 'sent') {
        toast.success(item.article_name, t('madeItems.catalogue.contextMenu.printLabelSent'))
      } else {
        toast.error(
          item.article_name,
          job?.error_message ?? t('madeItems.catalogue.contextMenu.printLabelFailed'),
        )
      }
    } catch (e) {
      toast.error(
        item.article_name,
        extractApiError(e) ?? t('madeItems.catalogue.contextMenu.printLabelFailed'),
      )
    } finally {
      printingItemId.value = null
    }
  }

  // Copy and New revision both create a made item, so they are hidden
  // entirely when web creation is off, like the toolbar's Create button.
  const canCreate = computed(() => hostStore.madeItemPartNumbers.web_creation_allowed)

  const contextMenuItem = ref<MadeItemResponse | null>(null)

  const contextMenuItems = computed<MenuItem[]>(() => {
    const item = contextMenuItem.value
    if (!item) return []
    const isCadItem = item.data_source === 'CAD'

    const items: MenuItem[] = [
      {
        label: t('madeItems.catalogue.controls.edit'),
        icon: 'mdi mdi-pencil',
        disabled: !canWrite.value,
        title: missing(Permission.WRITE_MADE_ITEMS) || undefined,
        command: () => openDetailForEdit(item),
      },
    ]

    if (canCreate.value) {
      items.push({
        label: t('madeItems.catalogue.controls.copy'),
        icon: 'mdi mdi-content-copy',
        disabled: !canWrite.value,
        title: missing(Permission.WRITE_MADE_ITEMS) || undefined,
        command: () => copyItem(item),
      })
      // CAD revisions come only from PDM. The entry is disabled with a hint
      // rather than hidden so the reason stays discoverable.
      items.push({
        label: t('madeItems.catalogue.contextMenu.newRevision'),
        icon: 'mdi mdi-source-branch-plus',
        disabled: !canWrite.value || isCadItem,
        title: isCadItem
          ? t('madeItems.catalogue.contextMenu.newRevisionManagedByPdm')
          : missing(Permission.WRITE_MADE_ITEMS) || undefined,
        command: () => openRevisionForm(item),
      })
    }

    items.push(
      {
        label: t('madeItems.catalogue.controls.merge'),
        icon: 'mdi mdi-source-merge',
        disabled: !canDelete.value,
        title: missing(Permission.DELETE_MADE_ITEMS) || undefined,
        command: () => mergeItem(item),
      },
      item.archived
        ? {
            label: t('common.restore'),
            icon: 'mdi mdi-archive-arrow-up-outline',
            disabled: !canDelete.value,
            title: missing(Permission.DELETE_MADE_ITEMS) || undefined,
            command: () => void onRestoreItem(item),
          }
        : {
            label: t('common.archive'),
            icon: 'mdi mdi-archive-outline',
            disabled: !canDelete.value,
            title: missing(Permission.DELETE_MADE_ITEMS) || undefined,
            command: () => onArchiveItem(item),
          },
      { separator: true },
      {
        label: t('madeItems.catalogue.contextMenu.addToDemand'),
        icon: 'mdi mdi-clipboard-plus-outline',
        disabled: !canWriteDemands.value,
        title: missing(Permission.WRITE_DEMAND_ITEMS) || undefined,
        command: () => addToDemand(item),
      },
      {
        label: t('madeItems.catalogue.contextMenu.showHistory'),
        icon: 'mdi mdi-timeline-text-outline',
        command: () => showHistoryFor(item),
      },
      {
        label: t('madeItems.catalogue.contextMenu.printLabel'),
        icon: 'mdi mdi-tag-outline',
        disabled: !canPrint.value || printingItemId.value === item.id,
        title: missing(Permission.PRINT_DOCUMENTS) || undefined,
        command: () => void onPrintLabel(item),
      },
      { separator: true },
      {
        label: t('madeItems.catalogue.contextMenu.showChangelog'),
        icon: 'mdi mdi-history',
        command: () => showChangelogFor(item),
      },
      { separator: true },
      {
        label: t('common.copyUuid'),
        icon: 'mdi mdi-content-copy',
        command: () => void copyToClipboard(item.public_id),
      },
    )

    return items
  })

  return {
    canWrite,
    canDelete,
    detailItem,
    showDetail,
    detailEditOnOpen,
    copyFromItem,
    showCopyForm,
    copyItem,
    revisionOfItem,
    showRevisionForm,
    changelogItem,
    showChangelogDialog,
    showChangelogFor,
    mergeSourceItem,
    showMergeDialog,
    mergeItem,
    demandForItem,
    showDemandForm,
    historyItem,
    showHistoryDialog,
    editItem,
    contextMenuItem,
    contextMenuItems,
  }
}
