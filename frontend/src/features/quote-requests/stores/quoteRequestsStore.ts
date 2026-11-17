import { ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { getQuoteRequests } from '../api/getQuoteRequests'
import type { QuoteRequestFilterParams } from '../types/quoteRequestsRequest'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

/** The list of the Quotes tab. */
export const useQuoteRequestsStore = defineStore('quoteRequests', () => {
  const { loading, error, run } = useSequencedFetch(getQuoteRequests)
  const items = ref<QuoteRequestResponse[]>([])
  const total = ref(0)

  async function refresh(params?: QuoteRequestFilterParams): Promise<void> {
    const response = await run(params)
    if (!response) return
    items.value = response.items
    total.value = response.total
  }

  return { loading, error, items, total, refresh }
})
