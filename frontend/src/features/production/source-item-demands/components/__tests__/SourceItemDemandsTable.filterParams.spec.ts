/**
 * Params mapping of SourceItemDemandsTable's buildFilterParams: each column
 * filter in the filters store is sent under its query param name only while
 * set, the id filter becomes a one-element `ids` list, and the desired
 * delivery range is sent as two YYYY-MM-DD bounds. buildFilterParams is
 * private to the component, so the observable surface is the query string
 * sent to the demands list endpoint, hence asserting on the api.get params.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import ConfirmationService from 'openvue/confirmationservice'
import Aura from '@openvue/themes/aura'

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

import SourceItemDemandsTable from '../SourceItemDemandsTable.vue'
import { useSourceItemDemandsFiltersStore } from '../../stores/sourceItemDemandsFiltersStore'

function demandRequestParams(): Record<string, unknown>[] {
  return get.mock.calls
    .filter(([url]) => url === '/source-item-demands')
    .map(([, config]) => config?.params ?? {})
}

function lastDemandRequestParams(): Record<string, unknown> {
  const params = demandRequestParams()
  return params[params.length - 1] ?? {}
}

function mountTable() {
  return mount(SourceItemDemandsTable, {
    global: {
      plugins: [[OpenVue, { theme: { preset: Aura } }], ToastService, ConfirmationService, i18n],
      stubs: { RouterLink: true },
    },
  })
}

describe('SourceItemDemandsTable buildFilterParams', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    get.mockReset()
    get.mockResolvedValue({ data: { items: [], total: 0, limit: 25, skip: 0 } })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('leaves every column filter param out while the store is at its defaults', async () => {
    mountTable()
    await flushPromises()

    const params = lastDemandRequestParams()
    const sent = Object.keys(params).filter((key) =>
      [
        'ids',
        'project_id',
        'item_dimension',
        'item_material',
        'item_type',
        'lot_id',
        'order_id',
        'desired_from',
        'desired_to',
      ].includes(key),
    )
    expect(sent).toEqual([])
  })

  it('sends idFilter as a one-element ids list', async () => {
    useSourceItemDemandsFiltersStore().idFilter = 42
    mountTable()
    await flushPromises()

    expect(lastDemandRequestParams()).toMatchObject({ ids: [42] })
  })

  it('sends the project and the three item text filters under their param names', async () => {
    const store = useSourceItemDemandsFiltersStore()
    store.projectId = 5
    store.itemDimension = '10mm'
    store.itemMaterial = 'Steel'
    store.itemType = 'Rod'
    mountTable()
    await flushPromises()

    expect(lastDemandRequestParams()).toMatchObject({
      project_id: 5,
      item_dimension: '10mm',
      item_material: 'Steel',
      item_type: 'Rod',
    })
  })

  it('sends lotIds and orderIds as lot_id and order_id lists', async () => {
    const store = useSourceItemDemandsFiltersStore()
    store.lotIds = [3, 5]
    store.orderIds = [7]
    mountTable()
    await flushPromises()

    expect(lastDemandRequestParams()).toMatchObject({ lot_id: [3, 5], order_id: [7] })
  })

  // The range refetch is driven by the DatePicker's update callback (see
  // setDesiredDateRange in the table), not by a watch on the two refs, so
  // each shape is checked from a fresh mount.
  it('sends only desired_from while the range has no upper bound', async () => {
    useSourceItemDemandsFiltersStore().desiredFrom = new Date(2026, 0, 5)
    mountTable()
    await flushPromises()

    expect(lastDemandRequestParams()).toMatchObject({ desired_from: '2026-01-05' })
    expect(lastDemandRequestParams().desired_to).toBeUndefined()
  })

  it('sends the desired delivery range as two YYYY-MM-DD bounds', async () => {
    const store = useSourceItemDemandsFiltersStore()
    store.desiredFrom = new Date(2026, 0, 5)
    store.desiredTo = new Date(2026, 1, 28)
    mountTable()
    await flushPromises()

    expect(lastDemandRequestParams()).toMatchObject({
      desired_from: '2026-01-05',
      desired_to: '2026-02-28',
    })
  })

  it('refetches with the new bounds when the DatePicker range filter emits an update', async () => {
    const wrapper = mountTable()
    await flushPromises()
    const before = demandRequestParams().length

    const rangeFilter = wrapper.findComponent({ name: 'DemandDateRangeFilter' })
    expect(rangeFilter.exists()).toBe(true)
    rangeFilter.vm.$emit('update:modelValue', [new Date(2026, 2, 1), new Date(2026, 2, 31)])
    await flushPromises()

    expect(demandRequestParams().length).toBe(before + 1)
    expect(lastDemandRequestParams()).toMatchObject({
      desired_from: '2026-03-01',
      desired_to: '2026-03-31',
    })

    rangeFilter.vm.$emit('clear-click')
    await flushPromises()

    expect(demandRequestParams().length).toBe(before + 2)
    expect(lastDemandRequestParams().desired_from).toBeUndefined()
    expect(lastDemandRequestParams().desired_to).toBeUndefined()
  })

  it('refetches immediately when a pick filter changes', async () => {
    mountTable()
    await flushPromises()
    const before = demandRequestParams().length

    const store = useSourceItemDemandsFiltersStore()
    store.idFilter = 9
    await flushPromises()
    expect(demandRequestParams().length).toBe(before + 1)
    expect(lastDemandRequestParams()).toMatchObject({ ids: [9] })

    store.lotIds = [2]
    await flushPromises()
    expect(demandRequestParams().length).toBe(before + 2)
    expect(lastDemandRequestParams()).toMatchObject({ ids: [9], lot_id: [2] })
  })

  it('refetches on the debounce after a text filter changes', async () => {
    vi.useFakeTimers()
    mountTable()
    await flushPromises()
    const before = demandRequestParams().length

    const store = useSourceItemDemandsFiltersStore()
    store.itemMaterial = 'Steel'
    await flushPromises()
    expect(demandRequestParams().length).toBe(before)

    await vi.advanceTimersByTimeAsync(TABLE_DEBOUNCE_MS + 10)
    await flushPromises()
    expect(demandRequestParams().length).toBe(before + 1)
    expect(lastDemandRequestParams()).toMatchObject({ item_material: 'Steel' })
  })

  it('drops the params again after clearAll', async () => {
    const store = useSourceItemDemandsFiltersStore()
    store.idFilter = 42
    store.projectId = 5
    store.lotIds = [3]
    store.desiredFrom = new Date(2026, 0, 5)
    mountTable()
    await flushPromises()
    expect(lastDemandRequestParams()).toMatchObject({ ids: [42], lot_id: [3] })

    store.clearAll()
    await flushPromises()

    const params = lastDemandRequestParams()
    expect(params.ids).toBeUndefined()
    expect(params.project_id).toBeUndefined()
    expect(params.lot_id).toBeUndefined()
    expect(params.desired_from).toBeUndefined()
  })
})
