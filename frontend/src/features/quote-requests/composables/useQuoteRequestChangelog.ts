import { ref } from 'vue'

import { getQuoteRequestChangelog } from '../api/getQuoteRequestChangelog'
import type { ChangelogEntry } from '@/shared/utils/changelog'

/**
 * One quote request's changelog. The detail view reloads it whenever the
 * request changes, so a write or a live refresh shows its new lines. The
 * entries already shown stay while a reload runs, and a failed load is
 * shown as an error instead of an empty log.
 */
export function useQuoteRequestChangelog(id: number) {
  const entries = ref<ChangelogEntry[]>([])
  const loading = ref(false)
  const error = ref(false)

  async function reload(): Promise<void> {
    loading.value = true
    try {
      entries.value = await getQuoteRequestChangelog(id)
      error.value = false
    } catch {
      error.value = true
    } finally {
      loading.value = false
    }
  }

  return { entries, loading, error, reload }
}
