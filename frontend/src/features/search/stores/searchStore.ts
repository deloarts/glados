import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { useSequencedFetch } from '@/core/composables/useSequencedFetch'
import { globalSearch } from '../api/globalSearch'

import type { GlobalSearchGroup } from '../types/globalSearchResponse'

export const useSearchStore = defineStore('search', () => {
  // Responses that are no longer the latest request are ignored.
  const searchFetch = useSequencedFetch(globalSearch)
  const { loading } = searchFetch

  const query = ref('')
  const groups = ref<GlobalSearchGroup[]>([])
  const error = ref(false)
  const durationMs = ref<number | null>(null)

  const visibleGroups = computed<GlobalSearchGroup[]>(() =>
    groups.value.filter((group) => group.total > 0),
  )

  const totalHits = computed<number>(() =>
    groups.value.reduce((sum, group) => sum + group.total, 0),
  )

  async function search(q: string): Promise<void> {
    const trimmed = q.trim()
    query.value = trimmed

    if (!trimmed) {
      // Invalidates any request in flight.
      searchFetch.invalidate()
      groups.value = []
      error.value = false
      durationMs.value = null
      return
    }

    const startedAt = performance.now()
    const response = await searchFetch.run(trimmed)
    if (response) {
      groups.value = response.groups
      error.value = false
      durationMs.value = performance.now() - startedAt
    } else if (searchFetch.failed.value) {
      error.value = true
      durationMs.value = null
    }
  }

  async function retry(): Promise<void> {
    await search(query.value)
  }

  return {
    query,
    groups,
    loading,
    error,
    durationMs,

    visibleGroups,
    totalHits,

    search,
    retry,
  }
})
