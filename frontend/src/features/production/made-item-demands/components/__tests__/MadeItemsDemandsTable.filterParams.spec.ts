/**
 * Params mapping of MadeItemsDemandsTable's buildFilterParams for the id,
 * steps and lots column filters. buildFilterParams is private to the
 * component, so the observable surface is the query the table sends to the
 * demands list endpoint, hence asserting on the api.get params.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'


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

import MadeItemsDemandsTable from '../MadeItemsDemandsTable.vue'
import { useMadeItemsDemandsFiltersStore } from '../../stores/madeItemsDemandsFiltersStore'
import { mountWithApp } from '@/test-utils/mountWithApp'

function lastDemandsRequestParams(): Record<string, unknown> {
  const calls = get.mock.calls.filter(([url]) => url === '/made-items-demands')
  const last = calls[calls.length - 1]
  return last?.[1]?.params ?? {}
}

function mountTable() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mountWithApp(MadeItemsDemandsTable, {
    pinia,
    global: {
      stubs: { RouterLink: true },
    },
  })
}

describe('MadeItemsDemandsTable buildFilterParams', () => {
  beforeEach(() => {
    get.mockReset()
    get.mockImplementation((url: string) => {
      if (url === '/made-items-allocations/summary') return Promise.resolve({ data: {} })
      return Promise.resolve({ data: { items: [], total: 0, limit: 25, skip: 0 } })
    })
  })

  it('sends none of the new params while the filters are at their defaults', async () => {
    mountTable()
    await flushPromises()

    const params = lastDemandsRequestParams()
    expect(params).not.toHaveProperty('ids')
    expect(params).not.toHaveProperty('lot_id')
    expect(params).not.toHaveProperty('process_fabrication_method_id')
    expect(params).not.toHaveProperty('process_inspection_method_id')
  })

  it('sends idFilter as a one-element ids list', async () => {
    mountTable()
    await flushPromises()

    useMadeItemsDemandsFiltersStore().idFilter = 42
    await flushPromises()

    expect(lastDemandsRequestParams()).toMatchObject({ ids: [42] })
  })

  it('decodes stepMethods into the fabrication and inspection method lists', async () => {
    mountTable()
    await flushPromises()

    useMadeItemsDemandsFiltersStore().stepMethods = ['fabrication:3', 'inspection:7', 'fabrication:9']
    await flushPromises()

    expect(lastDemandsRequestParams()).toMatchObject({
      process_fabrication_method_id: [3, 9],
      process_inspection_method_id: [7],
    })
  })

  it('sends only the list a step method kind was picked for', async () => {
    mountTable()
    await flushPromises()

    useMadeItemsDemandsFiltersStore().stepMethods = ['inspection:7']
    await flushPromises()

    const params = lastDemandsRequestParams()
    expect(params).toMatchObject({ process_inspection_method_id: [7] })
    expect(params).not.toHaveProperty('process_fabrication_method_id')
  })

  it('sends lotIds as lot_id', async () => {
    mountTable()
    await flushPromises()

    useMadeItemsDemandsFiltersStore().lotIds = [5, 6]
    await flushPromises()

    expect(lastDemandsRequestParams()).toMatchObject({ lot_id: [5, 6] })
  })
})
