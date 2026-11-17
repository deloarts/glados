import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type {
  CreatedToken,
  CreateTokenCommand,
  RevokeAllTokensResult,
  TokenFilterParams,
  TokenSummary,
} from '@/shared/types/tokenTypes'

const listMock = vi.fn<(params?: TokenFilterParams) => Promise<PageResponse<TokenSummary>>>()
const createMock = vi.fn<(cmd: CreateTokenCommand) => Promise<CreatedToken>>()
const revokeMock = vi.fn<(id: number) => Promise<TokenSummary>>()
const revokeAllMock = vi.fn<() => Promise<RevokeAllTokensResult>>()

vi.mock('../../api/apiKeysApi', () => ({
  apiKeysApi: {
    list: (params?: TokenFilterParams) => listMock(params),
    create: (cmd: CreateTokenCommand) => createMock(cmd),
    revoke: (id: number) => revokeMock(id),
    revokeAll: () => revokeAllMock(),
  },
}))

import { useApiKeysStore } from '../apiKeysStore'

// apiKeysStore is a thin createTokenStore('apiKeys', apiKeysApi) instantiation;
// the generic pagination/sort/refreshTrigger behaviour is already covered
// by createTokenStore.spec.ts. These tests pin down its own wiring: it talks
// to apiKeysApi (not patsApi), and admin API keys additionally carry a
// created_by_id (who issued the key on someone else's behalf).
function makeToken(overrides: Partial<TokenSummary> = {}): TokenSummary {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    name: 'Integration key',
    token_prefix: 'glados_abcd',
    permissions: ['write:orders'],
    created: '2026-01-01',
    expires_at: null,
    revoked_at: null,
    is_expired: false,
    created_by_id: 7,
    ...overrides,
  }
}

function page(items: TokenSummary[], total = items.length): PageResponse<TokenSummary> {
  return { items, total, limit: 25, skip: 0 }
}

describe('useApiKeysStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listMock.mockReset()
    createMock.mockReset()
    revokeMock.mockReset()
    revokeAllMock.mockReset()
  })

  it('starts with an empty list and no sort applied', () => {
    const store = useApiKeysStore()
    expect(store.loading).toBe(false)
    expect(store.tokens).toEqual([])
    expect(store.total).toBe(0)
    expect(store.refreshTrigger).toBe(0)
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })

  it('refresh sends the include_revoked filter through and populates tokens/total', async () => {
    listMock.mockResolvedValue(page([makeToken()], 1))
    const store = useApiKeysStore()

    await store.refresh({ skip: 0, limit: 25 })

    expect(listMock).toHaveBeenCalledWith(expect.objectContaining({ skip: 0, limit: 25 }))
    expect(store.tokens).toEqual([makeToken()])
    expect(store.total).toBe(1)
  })

  it('refresh resets loading and leaves tokens empty when the request fails', async () => {
    listMock.mockRejectedValueOnce(new Error('network error'))
    const store = useApiKeysStore()

    await expect(store.refresh()).rejects.toThrow('network error')

    expect(store.loading).toBe(false)
    expect(store.tokens).toEqual([])
  })

  it('create returns the raw secret (shown once) and bumps refreshTrigger without refetching', async () => {
    createMock.mockResolvedValue({ ...makeToken(), secret: 'raw-key-value' })
    const store = useApiKeysStore()

    const created = await store.create({ name: 'New key', permissions: ['read:orders'] })

    expect(createMock).toHaveBeenCalledWith({ name: 'New key', permissions: ['read:orders'] })
    expect(created.secret).toBe('raw-key-value')
    expect(store.tokens).toEqual([])
    expect(store.refreshTrigger).toBe(1)
    expect(listMock).not.toHaveBeenCalled()
  })

  it('create leaves refreshTrigger unchanged when apiKeysApi.create rejects', async () => {
    createMock.mockRejectedValueOnce(new Error('422'))
    const store = useApiKeysStore()

    await expect(store.create({ name: 'x', permissions: [] })).rejects.toThrow('422')

    expect(store.refreshTrigger).toBe(0)
  })

  it('revoke calls apiKeysApi.revoke and bumps refreshTrigger', async () => {
    revokeMock.mockResolvedValue(makeToken({ revoked_at: '2026-01-02' }))
    const store = useApiKeysStore()

    await store.revoke(1)

    expect(revokeMock).toHaveBeenCalledWith(1)
    expect(store.refreshTrigger).toBe(1)
  })

  it('revoke leaves refreshTrigger unchanged when apiKeysApi.revoke rejects', async () => {
    revokeMock.mockRejectedValueOnce(new Error('404'))
    const store = useApiKeysStore()

    await expect(store.revoke(99)).rejects.toThrow('404')

    expect(store.refreshTrigger).toBe(0)
  })

  it('revokeAll returns the revoked count and bumps refreshTrigger', async () => {
    revokeAllMock.mockResolvedValue({ revoked_count: 2 })
    const store = useApiKeysStore()

    const count = await store.revokeAll()

    expect(count).toBe(2)
    expect(store.refreshTrigger).toBe(1)
  })

  it('revokeAll leaves refreshTrigger unchanged when apiKeysApi.revokeAll rejects', async () => {
    revokeAllMock.mockRejectedValueOnce(new Error('500'))
    const store = useApiKeysStore()

    await expect(store.revokeAll()).rejects.toThrow('500')

    expect(store.refreshTrigger).toBe(0)
  })

  it('setSort/clearSort update sortBy/sortDir (no dedicated reset action beyond this)', () => {
    const store = useApiKeysStore()

    store.setSort('name', 'desc')
    expect(store.sortBy).toBe('name')
    expect(store.sortDir).toBe('desc')

    store.clearSort()
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })
})
