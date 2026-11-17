import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { createTokenStore } from '../createTokenStore'
import type { TokenApi, UsageLogParams } from '../../api/createTokenApi'
import type {
  CreatedToken,
  CreateTokenCommand,
  RevokeAllTokensResult,
  TokenFilterParams,
  TokenSummary,
  TokenUsageLogEntry,
} from '../../types/tokenTypes'
import type { PageResponse } from '@/core/api/types'

function makeToken(overrides: Partial<TokenSummary> = {}): TokenSummary {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    name: 'CI token',
    token_prefix: 'glados_abcd',
    permissions: ['read:orders'],
    created: '2026-01-01',
    expires_at: null,
    revoked_at: null,
    is_expired: false,
    ...overrides,
  }
}

function makeApi(): TokenApi {
  return {
    list: vi.fn<(params?: TokenFilterParams) => Promise<PageResponse<TokenSummary>>>(),
    create: vi.fn<(cmd: CreateTokenCommand) => Promise<CreatedToken>>(),
    revoke: vi.fn<(id: number) => Promise<TokenSummary>>(),
    revokeAll: vi.fn<() => Promise<RevokeAllTokensResult>>(),
    getUsageLog:
      vi.fn<
        (id: number, params?: UsageLogParams) => Promise<PageResponse<TokenUsageLogEntry>>
      >(),
  }
}

describe('createTokenStore pagination', () => {
  let api: TokenApi

  beforeEach(() => {
    setActivePinia(createPinia())
    api = makeApi()
  })

  it('refresh sends skip/limit and populates tokens/total from the envelope', async () => {
    vi.mocked(api.list).mockResolvedValue({ items: [makeToken()], total: 42, limit: 25, skip: 25 })
    const store = createTokenStore('testTokens1', api)()

    await store.refresh({ skip: 25, limit: 25 })

    expect(api.list).toHaveBeenCalledWith(expect.objectContaining({ skip: 25, limit: 25 }))
    expect(store.tokens).toHaveLength(1)
    expect(store.total).toBe(42)
  })

  it('refresh with no page argument omits skip/limit', async () => {
    vi.mocked(api.list).mockResolvedValue({ items: [], total: 0, limit: 50, skip: 0 })
    const store = createTokenStore('testTokens2', api)()

    await store.refresh()

    expect(api.list).toHaveBeenCalledWith(undefined)
  })

  it('threads order_by/order_dir into refresh once setSort is called, and clearSort drops them again', async () => {
    vi.mocked(api.list).mockResolvedValue({ items: [], total: 0, limit: 25, skip: 0 })
    const store = createTokenStore('testTokens4', api)()

    store.setSort('created', 'desc')
    await store.refresh({ skip: 0, limit: 25 })
    expect(api.list).toHaveBeenCalledWith({
      skip: 0,
      limit: 25,
      order_by: 'created',
      order_dir: 'desc',
    })

    vi.mocked(api.list).mockClear()
    store.clearSort()
    await store.refresh()
    expect(api.list).toHaveBeenCalledWith(undefined)
  })

  it('bumps refreshTrigger instead of eagerly refetching after create/revoke/revokeAll', async () => {
    vi.mocked(api.create).mockResolvedValue({ ...makeToken(), secret: 'raw-secret' })
    vi.mocked(api.revoke).mockResolvedValue(makeToken({ revoked_at: '2026-01-02' }))
    vi.mocked(api.revokeAll).mockResolvedValue({ revoked_count: 3 })
    const store = createTokenStore('testTokens3', api)()

    expect(store.refreshTrigger).toBe(0)

    await store.create({ name: 'New token', permissions: [] })
    expect(store.refreshTrigger).toBe(1)
    expect(api.list).not.toHaveBeenCalled()

    await store.revoke(1)
    expect(store.refreshTrigger).toBe(2)

    const revokedCount = await store.revokeAll()
    expect(revokedCount).toBe(3)
    expect(store.refreshTrigger).toBe(3)
    expect(api.list).not.toHaveBeenCalled()
  })
})
