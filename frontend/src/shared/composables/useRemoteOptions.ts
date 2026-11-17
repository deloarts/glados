import { onMounted, ref, watch } from 'vue'
import type { Ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { SEARCH_DEBOUNCE_MS } from '@/core/constants/table'

type SearchOutcome<TOption> = { ok: true; options: TOption[] } | { ok: false; error: unknown }

/**
 * The option list of a Select that searches on the server as the user
 * types: `fetch` turns a query into options, the first page loads on mount
 * with an empty query, and `debouncedSearch` is bound to the Select's
 * `@filter` event.
 *
 * Searches run through useSequencedFetch, so a slow answer to an older query
 * never replaces a newer one. A failed search keeps the previous options
 * and, when it is the latest, rethrows its error so the app's error handler
 * reports it; a stale failure is dropped. With `keepSelected`, an item picked into that model is added to
 * the front of the options when they do not contain it, so the Select can
 * still label it.
 */
export function useRemoteOptions<TOption extends { id: number }>(
  fetch: (query: string) => Promise<TOption[]>,
  options: { keepSelected?: Ref<TOption | null> } = {},
) {
  const items = ref([]) as Ref<TOption[]>
  // The fetcher settles with the outcome instead of throwing, so the latest
  // call's own error can be rethrown after the sequencing check.
  const searchFetch = useSequencedFetch(async (query: string): Promise<SearchOutcome<TOption>> => {
    try {
      return { ok: true, options: await fetch(query) }
    } catch (error) {
      return { ok: false, error }
    }
  })
  const { loading } = searchFetch

  async function search(query = ''): Promise<void> {
    const outcome = await searchFetch.run(query)
    if (!outcome) return
    if (!outcome.ok) throw outcome.error
    items.value = outcome.options
  }

  const debouncedSearch = useDebounceFn((query: string) => search(query), SEARCH_DEBOUNCE_MS)

  onMounted(() => search())

  const selected = options.keepSelected
  if (selected) {
    watch(selected, (value) => {
      if (value && !items.value.some((item) => item.id === value.id)) {
        items.value = [value, ...items.value]
      }
    })
  }

  return { items, loading, search, debouncedSearch }
}
