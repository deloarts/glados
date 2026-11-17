/**
 * Opening the Manage Orders panel narrows the demand list to rows that
 * panel can act on (`not_fully_allocated`), and closing it restores the
 * full list.
 *
 * The filter is derived from the panel state inside buildFilterParams()
 * rather than stored as its own filter ref, so the only place it is
 * observable is the query string the table sends, hence asserting on the
 * api.get params rather than on store state.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import ConfirmationService from 'openvue/confirmationservice'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'

const get =
  vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<unknown>>()
const post = vi.fn<() => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => get(url, config),
    post: () => post(),
    put: vi.fn<() => Promise<unknown>>(),
    patch: vi.fn<() => Promise<unknown>>(),
    delete: vi.fn<() => Promise<unknown>>(),
  },
}))

import BoughtItemsDemandsTable from '../BoughtItemsDemandsTable.vue'
import { useBoughtItemsDemandsFiltersStore } from '../../stores/boughtItemsDemandsFiltersStore'

/** Params of every request the table made to the demands list endpoint. */
function demandRequestParams(): Record<string, unknown>[] {
  return get.mock.calls
    .filter(([url]) => url === '/bought-items-demands')
    .map(([, config]) => config?.params ?? {})
}

function mountTable() {
  return mount(BoughtItemsDemandsTable, {
    global: {
      plugins: [[OpenVue, { theme: { preset: Aura } }], ToastService, ConfirmationService, i18n],
    },
  })
}

describe('BoughtItemsDemandsTable manage-order filter', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
    post.mockReset()
    get.mockResolvedValue({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    post.mockResolvedValue({ data: {} })
  })

  it('does not narrow the list while the panel is closed', async () => {
    mountTable()
    await flushPromises()

    const params = demandRequestParams()
    expect(params.length).toBeGreaterThan(0)
    expect(params.every((p) => p.not_fully_allocated === undefined)).toBe(true)
  })

  it('requests only not-fully-allocated demands once the panel opens', async () => {
    mountTable()
    await flushPromises()

    const filtersStore = useBoughtItemsDemandsFiltersStore()
    const before = demandRequestParams().length
    filtersStore.showManageOrderPanel = true
    await flushPromises()

    const params = demandRequestParams()
    expect(params.length).toBeGreaterThan(before)
    expect(params.at(-1)).toMatchObject({ not_fully_allocated: true })
  })

  it('restores the full list when the panel closes again', async () => {
    mountTable()
    await flushPromises()

    const filtersStore = useBoughtItemsDemandsFiltersStore()
    filtersStore.showManageOrderPanel = true
    await flushPromises()
    filtersStore.showManageOrderPanel = false
    await flushPromises()

    expect(demandRequestParams().at(-1)?.not_fully_allocated).toBeUndefined()
  })

  it('leaves the user-facing status filter untouched', async () => {
    /**
     * The narrowing is quantity-derived and must not masquerade as a
     * status filter, `status` cannot express "partially allocated".
     */
    mountTable()
    await flushPromises()

    const filtersStore = useBoughtItemsDemandsFiltersStore()
    filtersStore.showManageOrderPanel = true
    await flushPromises()

    expect(filtersStore.statusFilter).toBeNull()
    expect(demandRequestParams().at(-1)?.status).toBeUndefined()
  })

  it('counts as an active filter so Clear is not left greyed out', async () => {
    mountTable()
    await flushPromises()

    const filtersStore = useBoughtItemsDemandsFiltersStore()
    expect(filtersStore.hasActiveFilters).toBe(false)

    filtersStore.showManageOrderPanel = true
    await flushPromises()

    expect(filtersStore.hasActiveFilters).toBe(true)
  })

  it('Clear widens the list again without closing the panel', async () => {
    mountTable()
    await flushPromises()

    const filtersStore = useBoughtItemsDemandsFiltersStore()
    filtersStore.showManageOrderPanel = true
    await flushPromises()
    filtersStore.clearAll()
    await flushPromises()

    expect(demandRequestParams().at(-1)?.not_fully_allocated).toBeUndefined()
    expect(filtersStore.showManageOrderPanel).toBe(true)
    expect(filtersStore.hasActiveFilters).toBe(false)
  })

  it('re-arms the narrowing when the panel is reopened after a Clear', async () => {
    mountTable()
    await flushPromises()

    const filtersStore = useBoughtItemsDemandsFiltersStore()
    filtersStore.showManageOrderPanel = true
    await flushPromises()
    filtersStore.clearAll()
    await flushPromises()
    filtersStore.showManageOrderPanel = false
    await flushPromises()
    filtersStore.showManageOrderPanel = true
    await flushPromises()

    expect(demandRequestParams().at(-1)).toMatchObject({ not_fully_allocated: true })
  })
})
