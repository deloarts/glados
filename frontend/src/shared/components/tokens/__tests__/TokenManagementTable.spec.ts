import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { createTokenStore } from '../../../stores/createTokenStore'

import type { TokenApi, UsageLogParams } from '../../../api/createTokenApi'
import type {
  CreatedToken,
  CreateTokenCommand,
  RevokeAllTokensResult,
  TokenFilterParams,
  TokenSummary,
  TokenUsageLogEntry,
} from '../../../types/tokenTypes'
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

function mountTable(api: TokenApi) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = createTokenStore('testTokenTable', api)()

  return {
    store,
    wrapper: mountWithApp(TokenManagementTable, {
      pinia,
      props: { store, api, canManage: true, i18nPrefix: 'account.pat' },
      global: { plugins: [ConfirmationService] },
    }),
  }
}

import TokenManagementTable from '../TokenManagementTable.vue'

describe('TokenManagementTable', () => {
  let api: TokenApi

  beforeEach(() => {
    api = makeApi()
  })

  it('mounts, loads tokens via the paginated fetch, and renders columns', async () => {
    vi.mocked(api.list).mockResolvedValue({ items: [makeToken()], total: 1, limit: 25, skip: 0 })

    const { wrapper } = mountTable(api)
    await flushPromises()

    expect(wrapper.text()).toContain('CI token')
    expect(api.list).toHaveBeenCalledWith({ skip: 0, limit: 25 })
  })

  it('is a lazy DataTable whose totalRecords comes from the server total', async () => {
    vi.mocked(api.list).mockResolvedValue({ items: [makeToken()], total: 120, limit: 25, skip: 0 })

    const { wrapper } = mountTable(api)
    await flushPromises()

    const table = wrapper.findComponent({ name: 'DataTable' })
    expect(table.props('lazy')).toBe(true)
    expect(table.props('totalRecords')).toBe(120)
  })

  it('requests the next page with the correct skip on @page', async () => {
    vi.mocked(api.list).mockResolvedValue({ items: [makeToken()], total: 60, limit: 25, skip: 0 })

    const { wrapper } = mountTable(api)
    await flushPromises()

    vi.mocked(api.list).mockClear()
    vi.mocked(api.list).mockResolvedValue({
      items: [makeToken({ id: 2, name: 'Second Page Token' })],
      total: 60,
      limit: 25,
      skip: 25,
    })

    const next = wrapper.find('[aria-label="Next Page"]')
    await next.trigger('click')
    await flushPromises()

    expect(api.list).toHaveBeenCalledWith({ skip: 25, limit: 25 })
  })

  it('bumps refreshTrigger (not a page reset) after revoking a token', async () => {
    vi.mocked(api.list).mockResolvedValue({ items: [makeToken()], total: 1, limit: 25, skip: 0 })
    vi.mocked(api.revoke).mockResolvedValue(makeToken({ revoked_at: '2026-01-02' }))

    const { store } = mountTable(api)
    await flushPromises()

    expect(store.refreshTrigger).toBe(0)
    await store.revoke(1)
    expect(store.refreshTrigger).toBe(1)
  })

  // Under `lazy` OpenVue only emits @sort and fetches nothing itself, so the
  // table must wire the event or a header click would only toggle the icon.
  it('fetches with order_by/order_dir and resets to page 1 on a header sort click', async () => {
    vi.mocked(api.list).mockResolvedValue({ items: [makeToken()], total: 60, limit: 25, skip: 0 })

    const { wrapper } = mountTable(api)
    await flushPromises()

    // Move off page 1 first, so the sort click's reset is observable.
    vi.mocked(api.list).mockClear()
    vi.mocked(api.list).mockResolvedValue({
      items: [makeToken()],
      total: 60,
      limit: 25,
      skip: 25,
    })
    await wrapper.find('[aria-label="Next Page"]').trigger('click')
    await flushPromises()

    vi.mocked(api.list).mockClear()
    vi.mocked(api.list).mockResolvedValue({ items: [makeToken()], total: 60, limit: 25, skip: 0 })
    const dataTable = wrapper.findComponent({ name: 'DataTable' })
    dataTable.vm.$emit('sort', { sortField: 'name', sortOrder: 1 })
    await flushPromises()

    expect(api.list).toHaveBeenCalledWith({ skip: 0, limit: 25, order_by: 'name', order_dir: 'asc' })
  })

  it('does not mark the token prefix column sortable (not in the backend allow-list)', async () => {
    vi.mocked(api.list).mockResolvedValue({ items: [makeToken()], total: 1, limit: 25, skip: 0 })

    const { wrapper } = mountTable(api)
    await flushPromises()

    const column = wrapper
      .findAllComponents({ name: 'Column' })
      .find((c) => c.props('field') === 'token_prefix')
    expect(column?.props('sortable')).toBeFalsy()
  })
})
