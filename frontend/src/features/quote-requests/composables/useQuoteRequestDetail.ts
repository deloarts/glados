import { ref } from 'vue'

import { LiveResource } from '@/core/realtime/resources'
import { useLiveRefresh } from '@/core/realtime/useLiveRefresh'
import { getQuoteRequest } from '../api/getQuoteRequest'
import type { QuoteRequestResponse } from '../types/quoteRequestsResponse'

/** One quote request, loaded by id and kept current while others change it. */
export function useQuoteRequestDetail(id: number) {
  const request = ref<QuoteRequestResponse | null>(null)
  const loading = ref(true)
  const notFound = ref(false)
  const loadError = ref(false)

  async function reload(options: { quiet?: boolean } = {}): Promise<void> {
    if (!options.quiet) loading.value = true
    try {
      request.value = await getQuoteRequest(id)
      notFound.value = false
      loadError.value = false
    } catch (e) {
      const status = (e as { response?: { status?: number } }).response?.status
      notFound.value = status === 404
      loadError.value = status !== 404
    } finally {
      loading.value = false
    }
  }

  /** Shows a request a write answered with, so no reload is needed. */
  function replace(next: QuoteRequestResponse): void {
    request.value = next
  }

  void reload()
  useLiveRefresh([LiveResource.QUOTE_REQUESTS], () => reload({ quiet: true }), {
    filter: (signal) => signal.id === id || signal.action === 'bulk',
  })

  return { request, loading, notFound, loadError, reload, replace }
}
