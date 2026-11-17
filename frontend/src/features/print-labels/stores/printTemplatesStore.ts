import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { getPrintTemplates } from '../api/getPrintTemplates'
import { resetPrintTemplate } from '../api/resetPrintTemplate'
import { updatePrintTemplate } from '../api/updatePrintTemplate'

import type { PrintTemplateUpdateRequest } from '../types/printTemplateRequest'
import type { PrintTemplateResponse } from '../types/printTemplateResponse'

/**
 * One row per classifier, which the backend ensures at startup as an
 * unconfigured slot and which is never created or deleted here, so the small
 * set is fetched once and filtered client-side.
 */
export const usePrintTemplatesStore = defineStore('printTemplates', () => {
  const { loading, error, run } = useSequencedFetch(getPrintTemplates)
  const mutating = ref(false)
  const items = ref<PrintTemplateResponse[]>([])
  const search = ref('')
  const showActions = ref(false)

  const hasActiveFilters = computed<boolean>(() => search.value !== '')

  const labelTemplates = computed(() => items.value.filter((t) => t.output_kind === 'zpl'))
  const docketTemplates = computed(() => items.value.filter((t) => t.output_kind === 'pdf_docket'))

  async function refresh(): Promise<void> {
    const result = await run()
    if (result) items.value = result
  }

  async function update(
    classifier: string,
    payload: PrintTemplateUpdateRequest,
  ): Promise<PrintTemplateResponse> {
    mutating.value = true
    try {
      const updated = await updatePrintTemplate(classifier, payload)
      const index = items.value.findIndex((t) => t.classifier === classifier)
      if (index !== -1) items.value[index] = updated
      return updated
    } finally {
      mutating.value = false
    }
  }

  async function reset(classifier: string): Promise<PrintTemplateResponse> {
    mutating.value = true
    try {
      const updated = await resetPrintTemplate(classifier)
      const index = items.value.findIndex((t) => t.classifier === classifier)
      if (index !== -1) items.value[index] = updated
      return updated
    } finally {
      mutating.value = false
    }
  }

  function toggleShowActions(): void {
    showActions.value = !showActions.value
  }

  function clearAll(): void {
    search.value = ''
  }

  return {
    loading,
    error,
    mutating,
    items,
    search,
    showActions,
    hasActiveFilters,
    labelTemplates,
    docketTemplates,
    refresh,
    // Satisfies ManagementCrudShellStore; there is no separate silent refresh.
    triggerRefresh: refresh,
    update,
    reset,
    toggleShowActions,
    clearAll,
  }
})
