/**
 * Params mapping of the id and order column filters in the bought demands
 * table: `idFilter` is sent as a one-element `ids` list, `orderIds` as
 * `order_id`, and both stay out of the query while unset. buildFilterParams
 * is private to the table, so the observable surface is the query string
 * sent to the demands list endpoint, hence asserting on the api.get params.
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

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => get(url, config),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
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

function lastDemandRequestParams(): Record<string, unknown> {
  return demandRequestParams().at(-1) ?? {}
}

/** Params of every request the order column's lookup made to the orders list. */
function orderRequestParams(): Record<string, unknown>[] {
  return get.mock.calls
    .filter(([url]) => url === '/orders/')
    .map(([, config]) => config?.params ?? {})
}

function mountTable() {
  return mount(BoughtItemsDemandsTable, {
    global: {
      plugins: [[OpenVue, { theme: { preset: Aura } }], ToastService, ConfirmationService, i18n],
      stubs: { RouterLink: true },
    },
  })
}

describe('BoughtItemsDemandsTable column filters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
    get.mockResolvedValue({ data: { items: [], total: 0, limit: 25, skip: 0 } })
  })

  it('leaves ids and order_id out while the filters are unset', async () => {
    mountTable()
    await flushPromises()

    const params = demandRequestParams()
    expect(params.length).toBeGreaterThan(0)
    expect(params.every((p) => p.ids === undefined && p.order_id === undefined)).toBe(true)
  })

  it('sends idFilter as a one-element ids list', async () => {
    mountTable()
    await flushPromises()

    const filtersStore = useBoughtItemsDemandsFiltersStore()
    const before = demandRequestParams().length
    filtersStore.idFilter = 42
    await flushPromises()

    expect(demandRequestParams().length).toBeGreaterThan(before)
    expect(lastDemandRequestParams()).toMatchObject({ ids: [42] })

    filtersStore.idFilter = null
    await flushPromises()
    expect(lastDemandRequestParams().ids).toBeUndefined()
  })

  it('sends orderIds as order_id and drops it again when emptied', async () => {
    mountTable()
    await flushPromises()

    const filtersStore = useBoughtItemsDemandsFiltersStore()
    const before = demandRequestParams().length
    filtersStore.orderIds = [3, 5]
    await flushPromises()

    expect(demandRequestParams().length).toBeGreaterThan(before)
    expect(lastDemandRequestParams()).toMatchObject({ order_id: [3, 5] })

    filtersStore.orderIds = []
    await flushPromises()
    expect(lastDemandRequestParams().order_id).toBeUndefined()
  })

  it('clearAll drops both params from the next request', async () => {
    mountTable()
    await flushPromises()

    const filtersStore = useBoughtItemsDemandsFiltersStore()
    filtersStore.idFilter = 42
    filtersStore.orderIds = [3]
    await flushPromises()
    expect(lastDemandRequestParams()).toMatchObject({ ids: [42], order_id: [3] })

    filtersStore.clearAll()
    await flushPromises()

    const params = lastDemandRequestParams()
    expect(params.ids).toBeUndefined()
    expect(params.order_id).toBeUndefined()
  })

  it('loads the order lookup options with the pinned page size', async () => {
    mountTable()
    await flushPromises()

    const params = orderRequestParams()
    expect(params.length).toBeGreaterThan(0)
    expect(params[0]).toMatchObject({ limit: 15 })
    expect(params[0]?.search).toBeUndefined()
  })
})
