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

vi.mock('../../api/patsApi', () => ({
  patsApi: {
    list: (params?: TokenFilterParams) => listMock(params),
    create: (cmd: CreateTokenCommand) => createMock(cmd),
    revoke: (id: number) => revokeMock(id),
    revokeAll: () => revokeAllMock(),
  },
}))

import { usePatsStore } from '../patsStore'

// patsStore is a thin createTokenStore('pats', patsApi) instantiation: the
// generic pagination/sort/refreshTrigger behaviour is already covered by
// createTokenStore.spec.ts. These tests pin down its own wiring: it talks to
// patsApi (not apiKeysApi), and the create-secret contract PATs depend on.
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

function page(items: TokenSummary[], total = items.length): PageResponse<TokenSummary> {
  return { items, total, limit: 25, skip: 0 }
}

describe('usePatsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    listMock.mockReset()
    createMock.mockReset()
    revokeMock.mockReset()
    revokeAllMock.mockReset()
  })

  it('starts with an empty list and no sort applied', () => {
    const store = usePatsStore()
    expect(store.loading).toBe(false)
    expect(store.tokens).toEqual([])
    expect(store.total).toBe(0)
    expect(store.refreshTrigger).toBe(0)
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })

  it('refresh populates tokens/total via patsApi.list', async () => {
    listMock.mockResolvedValue(page([makeToken()], 1))
    const store = usePatsStore()

    await store.refresh()

    expect(listMock).toHaveBeenCalledWith(undefined)
    expect(store.tokens).toEqual([makeToken()])
    expect(store.total).toBe(1)
  })

  it('refresh resets loading and leaves tokens empty when the request fails', async () => {
    listMock.mockRejectedValueOnce(new Error('network error'))
    const store = usePatsStore()

    await expect(store.refresh()).rejects.toThrow('network error')

    expect(store.loading).toBe(false)
    expect(store.tokens).toEqual([])
  })

  it('create returns the raw secret (shown once) without caching it on any token row', async () => {
    createMock.mockResolvedValue({ ...makeToken(), secret: 'raw-secret-value' })
    const store = usePatsStore()

    const created = await store.create({ name: 'New token', permissions: [] })

    expect(createMock).toHaveBeenCalledWith({ name: 'New token', permissions: [] })
    expect(created.secret).toBe('raw-secret-value')
    // create() never pushes into the cached list itself. Only a later
    // refresh() (triggered via refreshTrigger) repopulates tokens, and the
    // secret never appears on a TokenSummary row.
    expect(store.tokens).toEqual([])
    expect(store.refreshTrigger).toBe(1)
  })

  it('create bumps refreshTrigger without eagerly refetching', async () => {
    createMock.mockResolvedValue({ ...makeToken(), secret: 'x' })
    const store = usePatsStore()

    await store.create({ name: 'New token', permissions: [] })

    expect(listMock).not.toHaveBeenCalled()
  })

  it('create leaves refreshTrigger unchanged when patsApi.create rejects', async () => {
    createMock.mockRejectedValueOnce(new Error('422'))
    const store = usePatsStore()

    await expect(store.create({ name: 'x', permissions: [] })).rejects.toThrow('422')

    expect(store.refreshTrigger).toBe(0)
  })

  it('revoke calls patsApi.revoke and bumps refreshTrigger', async () => {
    revokeMock.mockResolvedValue(makeToken({ revoked_at: '2026-01-02' }))
    const store = usePatsStore()

    await store.revoke(1)

    expect(revokeMock).toHaveBeenCalledWith(1)
    expect(store.refreshTrigger).toBe(1)
  })

  it('revoke leaves refreshTrigger unchanged when patsApi.revoke rejects', async () => {
    revokeMock.mockRejectedValueOnce(new Error('404'))
    const store = usePatsStore()

    await expect(store.revoke(99)).rejects.toThrow('404')

    expect(store.refreshTrigger).toBe(0)
  })

  it('revokeAll returns the revoked count and bumps refreshTrigger', async () => {
    revokeAllMock.mockResolvedValue({ revoked_count: 4 })
    const store = usePatsStore()

    const count = await store.revokeAll()

    expect(count).toBe(4)
    expect(store.refreshTrigger).toBe(1)
  })

  it('revokeAll leaves refreshTrigger unchanged when patsApi.revokeAll rejects', async () => {
    revokeAllMock.mockRejectedValueOnce(new Error('500'))
    const store = usePatsStore()

    await expect(store.revokeAll()).rejects.toThrow('500')

    expect(store.refreshTrigger).toBe(0)
  })

  it('setSort/clearSort update sortBy/sortDir (no dedicated reset action beyond this)', () => {
    const store = usePatsStore()

    store.setSort('created', 'desc')
    expect(store.sortBy).toBe('created')
    expect(store.sortDir).toBe('desc')

    store.clearSort()
    expect(store.sortBy).toBeNull()
    expect(store.sortDir).toBe('asc')
  })
})
