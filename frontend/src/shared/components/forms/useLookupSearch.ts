import { onMounted, ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { SEARCH_DEBOUNCE_MS } from '@/core/constants/table'

import type { LookupFetch, LookupOption } from './lookupMultiSelect'

/**
 * The server-side search behind the lookup filters: the first page loads on
 * mount, typing narrows it after a debounce, and hiding the panel goes back
 * to the unfiltered page. Searches run through useSequencedFetch, so an
 * answer to an older query is ignored when a newer one is already out. A
 * failed search keeps the previous page and, when it is the latest,
 * rethrows its error so the app's error handler reports it.
 */
export function useLookupSearch(fetch: LookupFetch) {
  const fetched = ref<LookupOption[]>([])
  // The fetcher settles with the outcome instead of throwing, so the latest
  // call's own error can be rethrown after the sequencing check.
  const searchFetch = useSequencedFetch(
    async (query: string): Promise<{ ok: true; options: LookupOption[] } | { ok: false; error: unknown }> => {
      try {
        return { ok: true, options: await fetch(query) }
      } catch (error) {
        return { ok: false, error }
      }
    },
  )
  const { loading } = searchFetch
  // The query the user last typed. The debounced callback checks it so a
  // keystroke that was superseded (or cleared by hiding the panel) is dropped.
  let pendingQuery = ''

  async function search(query: string): Promise<void> {
    const outcome = await searchFetch.run(query)
    if (!outcome) return
    if (!outcome.ok) throw outcome.error
    fetched.value = outcome.options
  }

  const debouncedSearch = useDebounceFn((query: string) => {
    if (query !== pendingQuery) return
    return search(query)
  }, SEARCH_DEBOUNCE_MS)

  function onFilter(query: string): void {
    pendingQuery = query
    void debouncedSearch(query)
  }

  // The panel resets its filter text on hide, so the list behind it goes back
  // to the unfiltered page as well, ready for the next open.
  function onHide(): void {
    if (pendingQuery === '') return
    pendingQuery = ''
    void search('')
  }

  onMounted(() => search(''))

  return { fetched, loading, onFilter, onHide }
}
