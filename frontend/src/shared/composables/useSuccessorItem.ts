import { ref } from 'vue'
import type { Ref } from 'vue'

/**
 * The list query the successor lookups send, a subset of every item kind's
 * own list params.
 */
export interface SuccessorItemQuery {
  id?: number
  search?: string
  limit?: number
}

const SUGGESTION_LIMIT = 20

/**
 * The successor item picker of an item form: resolves the stored successor
 * id to an item for the AutoComplete, from the store cache first and else
 * by a fetch by id, and loads the suggestions for a typed query.
 *
 * Only the latest resolve is applied, so a slow fetch for an earlier id
 * cannot replace the item of a newer one. A failed fetch leaves the same
 * state as an empty answer, no item and no suggestions, instead of an
 * unhandled rejection.
 */
export function useSuccessorItem<TItem extends { id: number }>(options: {
  getById: (id: number) => TItem | undefined
  list: (params: SuccessorItemQuery) => Promise<{ items: TItem[] }>
}) {
  const successorItem = ref(null) as Ref<TItem | null>
  const successorSuggestions = ref([]) as Ref<TItem[]>
  let latestResolveId = 0

  function resolveSuccessorItem(id: number | null): void {
    const resolveId = ++latestResolveId
    if (id === null) {
      successorItem.value = null
      return
    }
    const cached = options.getById(id)
    if (cached) {
      successorItem.value = cached
      return
    }
    successorItem.value = null
    options
      .list({ id, limit: 1 })
      .then((result) => {
        if (resolveId === latestResolveId) successorItem.value = result.items[0] ?? null
      })
      .catch(() => {
        if (resolveId === latestResolveId) successorItem.value = null
      })
  }

  async function searchSuccessorItems(event: { query: string }): Promise<void> {
    try {
      const result = await options.list({ search: event.query, limit: SUGGESTION_LIMIT })
      successorSuggestions.value = result.items
    } catch {
      successorSuggestions.value = []
    }
  }

  return { successorItem, successorSuggestions, resolveSuccessorItem, searchSuccessorItems }
}
