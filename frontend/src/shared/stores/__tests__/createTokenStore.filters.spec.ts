import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { createTokenStore } from '../createTokenStore'
import type { TokenApi } from '../../api/createTokenApi'
import type { TokenFilterParams, TokenSummary } from '../../types/tokenTypes'
import type { PageResponse } from '@/core/api/types'

function makeApi(): TokenApi {
  return {
    list: vi
      .fn<(params?: TokenFilterParams) => Promise<PageResponse<TokenSummary>>>()
      .mockResolvedValue({ items: [], total: 0, limit: 25, skip: 0 }),
    create: vi.fn<() => Promise<never>>(),
    revoke: vi.fn<() => Promise<never>>(),
    revokeAll: vi.fn<() => Promise<never>>(),
    getUsageLog: vi.fn<() => Promise<never>>(),
  }
}

describe('createTokenStore row filters', () => {
  let api: TokenApi

  beforeEach(() => {
    setActivePinia(createPinia())
    api = makeApi()
  })

  it('maps every row filter to its request param', async () => {
    const store = createTokenStore(`tokenFilters-${Math.random()}`, api)()
    store.nameFilter = ' deploy '
    store.prefixFilter = 'ab12'
    store.createdFrom = new Date(2026, 8, 1)
    store.createdTo = new Date(2026, 8, 30)
    store.expiryFilter = 'expired'

    await store.refresh({ skip: 0, limit: 25 })

    expect(api.list).toHaveBeenCalledWith({
      skip: 0,
      limit: 25,
      search: 'deploy',
      token_prefix: 'ab12',
      created_from: '2026-09-01',
      created_to: '2026-09-30',
      expiry: 'expired',
    })
  })

  it('reports and clears active filters', () => {
    const store = createTokenStore(`tokenFilters-${Math.random()}`, api)()
    expect(store.hasActiveFilters).toBe(false)

    store.expiryFilter = 'never'
    expect(store.hasActiveFilters).toBe(true)

    store.clearFilters()
    expect(store.hasActiveFilters).toBe(false)
    expect(store.expiryFilter).toBeNull()
  })

  it('still omits the params object while nothing is set', async () => {
    const store = createTokenStore(`tokenFilters-${Math.random()}`, api)()

    await store.refresh()

    expect(api.list).toHaveBeenCalledWith(undefined)
  })
})
