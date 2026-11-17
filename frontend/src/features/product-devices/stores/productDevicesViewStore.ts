import { ref } from 'vue'
import { defineStore } from 'pinia'

/**
 * How the Devices tab of a product is shown. The switches live in the
 * product page's controls bar and the table reads them, so they meet here.
 * `createRequests` counts presses of the New Device button; the tab opens
 * the dialog on each change.
 */
export const useProductDevicesViewStore = defineStore('productDevicesView', () => {
  const mode = ref<'list' | 'overview' | 'tags' | 'completeness'>('list')
  // The completeness matrix shows only devices with something left to do.
  const onlyIncomplete = ref(false)
  const showArchived = ref(false)
  const showFullNames = ref(false)
  // The overview shows a card per device unless switched off.
  const hideDetails = ref(false)
  const createRequests = ref(0)
  // Presses of Export and Add Tag in the tag list mode.
  const exportRequests = ref(0)
  const addTagRequests = ref(0)

  function requestCreate(): void {
    createRequests.value++
  }

  function requestExport(): void {
    exportRequests.value++
  }

  function requestAddTag(): void {
    addTagRequests.value++
  }

  return { mode, onlyIncomplete, showArchived, showFullNames, hideDetails, createRequests, requestCreate, exportRequests, requestExport, addTagRequests, requestAddTag }
})
