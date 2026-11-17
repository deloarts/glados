import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { dateToParam } from '@/core/utils/dates'

import type { TokenApi } from '../api/createTokenApi'
import type {
  CreatedToken,
  CreateTokenCommand,
  TokenExpiryFilter,
  TokenFilterParams,
  TokenSortBy,
  TokenSortDir,
  TokenSummary,
} from '../types/tokenTypes'

/**
 * Both API keys and PATs need identical list/create/revoke/revoke-all state,
 * so this is a store factory rather than two hand-written, near-identical
 * Pinia stores, call it once per feature with a unique id and its api client.
 *
 * Neither surface has a picker elsewhere reading the full token list (unlike
 * suppliers/products/... items), so there's no items/tableItems split here;
 * `tokens`/`total` are the paginated table's own page, full stop.
 */
export function createTokenStore(id: string, api: TokenApi) {
  return defineStore(id, () => {
    const loading = ref(false)
    const tokens = ref<TokenSummary[]>([])
    const total = ref(0)
    // Bumped after create/revoke/revokeAll so the table can refetch its
    // *current* page rather than jump back to page 1.
    const refreshTrigger = ref(0)
    const sortBy = ref<TokenSortBy | null>(null)
    const sortDir = ref<TokenSortDir>('asc')

    // Row filter state the table binds directly. Each one is sent only while
    // it holds a value.
    const nameFilter = ref('')
    const prefixFilter = ref('')
    const createdFrom = ref<Date | null>(null)
    const createdTo = ref<Date | null>(null)
    const expiryFilter = ref<TokenExpiryFilter | null>(null)

    function filterParams(): TokenFilterParams {
      const params: TokenFilterParams = {}
      const name = nameFilter.value.trim()
      if (name) params.search = name
      const prefix = prefixFilter.value.trim()
      if (prefix) params.token_prefix = prefix
      const from = dateToParam(createdFrom.value)
      if (from) params.created_from = from
      const to = dateToParam(createdTo.value)
      if (to) params.created_to = to
      if (expiryFilter.value) params.expiry = expiryFilter.value
      return params
    }

    const hasActiveFilters = computed(() => Object.keys(filterParams()).length > 0)

    function clearFilters(): void {
      nameFilter.value = ''
      prefixFilter.value = ''
      createdFrom.value = null
      createdTo.value = null
      expiryFilter.value = null
    }

    async function refresh(page?: { skip: number; limit: number }): Promise<void> {
      loading.value = true
      try {
        // Preserves the pre-sort contract of omitting the params object
        // entirely (rather than sending `{}`) when no page, sort or filter
        // is active. See createTokenStore.spec.ts.
        const filters = filterParams()
        const params: TokenFilterParams | undefined =
          page || sortBy.value || Object.keys(filters).length
            ? {
                ...(page ? { skip: page.skip, limit: page.limit } : {}),
                ...(sortBy.value ? { order_by: sortBy.value, order_dir: sortDir.value } : {}),
                ...filters,
              }
            : undefined
        const response = await api.list(params)
        tokens.value = response.items
        total.value = response.total
      } finally {
        loading.value = false
      }
    }

    function triggerRefresh(): void {
      refreshTrigger.value++
    }

    function setSort(field: TokenSortBy, dir: TokenSortDir): void {
      sortBy.value = field
      sortDir.value = dir
    }

    function clearSort(): void {
      sortBy.value = null
      sortDir.value = 'asc'
    }

    async function create(cmd: CreateTokenCommand): Promise<CreatedToken> {
      const created = await api.create(cmd)
      triggerRefresh()
      return created
    }

    async function revoke(tokenId: number): Promise<void> {
      await api.revoke(tokenId)
      triggerRefresh()
    }

    async function revokeAll(): Promise<number> {
      const result = await api.revokeAll()
      triggerRefresh()
      return result.revoked_count
    }

    return {
      requiresPassword: api.requiresPassword ?? false,
      loading,
      tokens,
      total,
      refreshTrigger,
      sortBy,
      sortDir,
      nameFilter,
      prefixFilter,
      createdFrom,
      createdTo,
      expiryFilter,
      hasActiveFilters,
      refresh,
      triggerRefresh,
      setSort,
      clearSort,
      clearFilters,
      create,
      revoke,
      revokeAll,
    }
  })
}

export type TokenStoreHook = ReturnType<typeof createTokenStore>
export type TokenStoreInstance = ReturnType<TokenStoreHook>
