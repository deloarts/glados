import { ref } from 'vue'

import { getBoughtItemFileBlob } from '../api/boughtItemFilesApi'

import type { BoughtItemPdfFile, BoughtItemResponse } from '../types/boughtItemsResponse'

// The dialogs the catalogue table opens, each a visibility flag plus its
// target.
export function useBoughtItemsCatalogueDialogs() {
  const orderHistoryItem = ref<BoughtItemResponse | null>(null)
  const showOrderHistory = ref(false)

  function openOrderHistory(item: BoughtItemResponse): void {
    orderHistoryItem.value = item
    showOrderHistory.value = true
  }

  // A row click navigates to the detail page; this dialog only serves the
  // context menu's Edit entry.
  const detailItem = ref<BoughtItemResponse | null>(null)
  const showDetail = ref(false)
  const detailEditOnOpen = ref(false)

  function openDetailForEdit(item: BoughtItemResponse): void {
    detailItem.value = item
    detailEditOnOpen.value = true
    showDetail.value = true
  }

  const copyFromItem = ref<BoughtItemResponse | null>(null)
  const showCopyForm = ref(false)

  function copyItem(item: BoughtItemResponse): void {
    copyFromItem.value = item
    showCopyForm.value = true
  }

  const mergeSourceItem = ref<BoughtItemResponse | null>(null)
  const showMergeDialog = ref(false)

  function mergeItem(item: BoughtItemResponse): void {
    mergeSourceItem.value = item
    showMergeDialog.value = true
  }

  const demandPresetItem = ref<BoughtItemResponse | null>(null)
  const showDemandForm = ref(false)

  function createDemandFor(item: BoughtItemResponse): void {
    demandPresetItem.value = item
    showDemandForm.value = true
  }

  const addToOrderItem = ref<BoughtItemResponse | null>(null)
  const showAddToOrder = ref(false)

  function addItemToOrder(item: BoughtItemResponse): void {
    addToOrderItem.value = item
    showAddToOrder.value = true
  }

  const changelogItem = ref<BoughtItemResponse | null>(null)
  const showChangelogDialog = ref(false)

  function showChangelogFor(item: BoughtItemResponse): void {
    changelogItem.value = item
    showChangelogDialog.value = true
  }

  // PDF preview (files column)
  const previewFile = ref<BoughtItemPdfFile | null>(null)
  const previewItemId = ref<number | null>(null)
  const showFilePreview = ref(false)

  function openPdf(item: BoughtItemResponse, file: BoughtItemPdfFile): void {
    previewFile.value = file
    previewItemId.value = item.id
    showFilePreview.value = true
  }

  function fetchPdfBlob(itemId: number, fileId: number): Promise<Blob> {
    return getBoughtItemFileBlob(itemId, fileId)
  }

  return {
    orderHistoryItem,
    showOrderHistory,
    openOrderHistory,
    detailItem,
    showDetail,
    detailEditOnOpen,
    openDetailForEdit,
    copyFromItem,
    showCopyForm,
    copyItem,
    mergeSourceItem,
    showMergeDialog,
    mergeItem,
    demandPresetItem,
    showDemandForm,
    createDemandFor,
    addToOrderItem,
    showAddToOrder,
    addItemToOrder,
    changelogItem,
    showChangelogDialog,
    showChangelogFor,
    previewFile,
    previewItemId,
    showFilePreview,
    openPdf,
    fetchPdfBlob,
  }
}
