/**
 * Params mapping of useOrdersTableFilters' buildFilterParams: each text
 * column filter in the orders filters store is sent under its query param
 * name only while non-empty. buildFilterParams is private to the
 * composable, so the observable surface is the query string the composable
 * sends to the orders list endpoint, hence asserting on the api.get params.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { i18n } from '@/core/i18n'
import { TABLE_DEBOUNCE_MS } from '@/core/constants/table'

const get =
  vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => get(url, config),
    post: vi.fn<() => Promise<unknown>>(),
    put: vi.fn<() => Promise<unknown>>(),
    patch: vi.fn<() => Promise<unknown>>(),
    delete: vi.fn<() => Promise<unknown>>(),
  },
}))

import { useOrdersTableFilters } from '../useOrdersTableFilters'
import { useOrdersFiltersStore } from '../../stores/ordersFiltersStore'

/** Params of every request made to the orders list endpoint. */
function orderRequestParams(): Record<string, unknown>[] {
  return get.mock.calls
    .filter(([url]) => url === '/orders/')
    .map(([, config]) => config?.params ?? {})
}

function lastOrderRequestParams(): Record<string, unknown> {
  const params = orderRequestParams()
  return params[params.length - 1] ?? {}
}

const Host = defineComponent({
  setup() {
    useOrdersTableFilters(ref<Record<string, boolean>>({}))
    return () => h('div')
  },
})

function mountHost() {
  return mount(Host, { global: { plugins: [i18n] } })
}

describe('useOrdersTableFilters buildFilterParams', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
    get.mockResolvedValue({ data: { items: [], total: 0, limit: 25, skip: 0 } })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('leaves note and storage_place out while their filters are empty', async () => {
    mountHost()
    await flushPromises()

    const params = lastOrderRequestParams()
    expect(params.note).toBeUndefined()
    expect(params.storage_place).toBeUndefined()
    expect(params.order_number).toBeUndefined()
  })

  it('sends noteFilter as note', async () => {
    useOrdersFiltersStore().noteFilter = 'urgent'
    mountHost()
    await flushPromises()

    expect(lastOrderRequestParams()).toMatchObject({ note: 'urgent' })
    expect(lastOrderRequestParams().storage_place).toBeUndefined()
  })

  it('sends storagePlaceFilter as storage_place', async () => {
    useOrdersFiltersStore().storagePlaceFilter = 'Shelf A'
    mountHost()
    await flushPromises()

    expect(lastOrderRequestParams()).toMatchObject({ storage_place: 'Shelf A' })
    expect(lastOrderRequestParams().note).toBeUndefined()
  })

  it('sends orderNumberFilter as order_number alongside the two new params', async () => {
    const store = useOrdersFiltersStore()
    store.orderNumberFilter = 'O-1'
    store.noteFilter = 'urgent'
    store.storagePlaceFilter = 'Shelf A'
    mountHost()
    await flushPromises()

    expect(lastOrderRequestParams()).toMatchObject({
      order_number: 'O-1',
      note: 'urgent',
      storage_place: 'Shelf A',
    })
  })

  it('refetches on the debounce after noteFilter or storagePlaceFilter changes', async () => {
    vi.useFakeTimers()
    mountHost()
    await flushPromises()
    const before = orderRequestParams().length

    const store = useOrdersFiltersStore()
    store.noteFilter = 'urgent'
    await flushPromises()
    expect(orderRequestParams().length).toBe(before)

    await vi.advanceTimersByTimeAsync(TABLE_DEBOUNCE_MS + 10)
    await flushPromises()
    expect(orderRequestParams().length).toBe(before + 1)
    expect(lastOrderRequestParams()).toMatchObject({ note: 'urgent' })

    store.storagePlaceFilter = 'Shelf A'
    await vi.advanceTimersByTimeAsync(TABLE_DEBOUNCE_MS + 10)
    await flushPromises()
    expect(orderRequestParams().length).toBe(before + 2)
    expect(lastOrderRequestParams()).toMatchObject({ note: 'urgent', storage_place: 'Shelf A' })
  })
})
