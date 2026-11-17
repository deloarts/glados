import { describe, it, expect, vi, beforeEach } from 'vitest'
import { effectScope, reactive, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'

import type { LiveSignal } from '@/core/realtime/types'
import type { OrderItemResponse, OrderResponse } from '@/features/orders'

// Mirrors useAutoPlanRunLiveSync.spec.ts's fake liveStore: a reactive
// wrapper so `() => liveStore.reconnectCount` stays reactive under Pinia's
// ref-auto-unwrap behaviour, and a subscriber map standing in for
// liveStore.on()/its returned unsubscribe.
const fakeReconnectCount = ref(0)
const subscribers = new Map<string, (signal: LiveSignal) => void>()

const fakeLiveStore = reactive({
  reconnectCount: fakeReconnectCount,
  on: (resource: string, handler: (signal: LiveSignal) => void) => {
    subscribers.set(resource, handler)
    return () => subscribers.delete(resource)
  },
})

vi.mock('@/core/realtime/liveStore', () => ({
  useLiveStore: () => fakeLiveStore,
}))

const listMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/source-items/api/sourceItemsApi', () => ({
  sourceItemsApi: { list: (...args: unknown[]) => listMock(...args) },
}))

const getSourceItemDemandsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/source-items/api/sourceItemDemandsApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/source-items/api/sourceItemDemandsApi')>()),
  getSourceItemDemands: (...args: unknown[]) => getSourceItemDemandsMock(...args),
}))

const getSourceItemChangelogMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/source-items/api/getSourceItemChangelog', () => ({
  getSourceItemChangelog: (...args: unknown[]) => getSourceItemChangelogMock(...args),
}))

const getOrdersMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/orders', () => ({
  getOrders: (...args: unknown[]) => getOrdersMock(...args),
}))

const getProjectsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/projects/api/getProjects', () => ({
  getProjects: (...args: unknown[]) => getProjectsMock(...args),
}))

import { useSourceItemDetailPage } from '../useSourceItemDetailPage'
import { makeSourceItemDemandResponse } from '@/test-utils/factories'
import type { SourceItemDemandResponse, SourceItemResponse } from '@/features/source-items'

function makeItem(overrides: Partial<SourceItemResponse> = {}): SourceItemResponse {
  return {
    edit_version: 0,
    over_delivery_tolerance_percent: null,
    under_delivery_tolerance_percent: null,
    id: 5,
    public_id: '11111111-1111-1111-1111-111111111111',
    status: 'active',
    created: '2026-03-01',
    changed: '2026-03-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    type_id: 1,
    type_name: { enGB: 'Rod' },
    dimension: 'D20x100',
    material: 'Steel',
    mass: 1,
    note: null,
    order_code_1: null,
    order_code_2: null,
    successor_item_id: null,
    creator_id: 1,
    creator: { id: 1, full_name: 'Jane Doe' } as SourceItemResponse['creator'],
    approver_id: null,
    manufacturer_id: null,
    manufacturer_name: '',
    ...overrides,
  }
}

function makeDemand(overrides: Partial<SourceItemDemandResponse> = {}): SourceItemDemandResponse {
  return makeSourceItemDemandResponse({
    public_id: 'd1',
    created: '2026-03-01',
    quantity: 10,
    unit: 'pcs',
    creator: { id: 1, full_name: 'Jane Doe' } as SourceItemDemandResponse['creator'],
    source_item_id: 5,
    source_item: null,
    lot_number: 'L-2026-001',
    project_id: 100,
    project_number: 'P-100',
    project_customer: 'ACME',
    project_description: 'Widget',
    ...overrides,
  })
}

function makeOrder(id: number, items: Partial<OrderItemResponse>[]): OrderResponse {
  return {
    id,
    order_number: `ORD-${id}`,
    status: 'ordered',
    supplier_name: 'Supplier',
    items: items.map((i, index) => ({
      id: id * 100 + index,
      status: 'ordered',
      quantity: 1,
      unit: 'pcs',
      source_item_id: 5,
      project_id: 100,
      project_number: 'P-100',
      project_customer: 'ACME',
      project_description: 'Widget',
      project_status: 'active',
      ...i,
    })) as OrderItemResponse[],
  } as OrderResponse
}

function emit(resource: string, signal: LiveSignal): void {
  subscribers.get(resource)?.(signal)
}

describe('useSourceItemDetailPage', () => {
  beforeEach(() => {
    fakeReconnectCount.value = 0
    subscribers.clear()
    listMock.mockReset().mockResolvedValue({ items: [makeItem()], total: 1, limit: 1, skip: 0 })
    getSourceItemDemandsMock.mockReset().mockResolvedValue({ items: [], total: 0, limit: 200, skip: 0 })
    getSourceItemChangelogMock.mockReset().mockResolvedValue([])
    getOrdersMock.mockReset().mockResolvedValue({ items: [], total: 0 })
    getProjectsMock.mockReset().mockResolvedValue({ items: [], total: 0, limit: 200, skip: 0 })
  })

  it('loads the item and its sections on setup', async () => {
    const scope = effectScope()
    const page = scope.run(() => useSourceItemDetailPage(ref(5)))!
    await flushPromises()

    expect(page.item.value?.id).toBe(5)
    expect(page.notFound.value).toBe(false)
    expect(page.loadError.value).toBe(false)
    expect(listMock).toHaveBeenCalledWith({ id: 5, limit: 1 })
    scope.stop()
  })

  it('sets notFound when the item list comes back empty', async () => {
    listMock.mockReset().mockResolvedValue({ items: [], total: 0, limit: 1, skip: 0 })

    const scope = effectScope()
    const page = scope.run(() => useSourceItemDetailPage(ref(5)))!
    await flushPromises()

    expect(page.item.value).toBeNull()
    expect(page.notFound.value).toBe(true)
    expect(page.loadError.value).toBe(false)
    scope.stop()
  })

  it('sets loadError when the item request throws', async () => {
    listMock.mockReset().mockRejectedValue(new Error('boom'))

    const scope = effectScope()
    const page = scope.run(() => useSourceItemDetailPage(ref(5)))!
    await flushPromises()

    expect(page.loadError.value).toBe(true)
    expect(page.notFound.value).toBe(false)
    scope.stop()
  })

  it('isolates a failing section: demands erroring does not blank orders or the item', async () => {
    getSourceItemDemandsMock.mockReset().mockRejectedValue(new Error('boom'))
    getOrdersMock.mockReset().mockResolvedValue({
      items: [makeOrder(1, [{ id: 101 }])],
      total: 1,
    })

    const scope = effectScope()
    const page = scope.run(() => useSourceItemDetailPage(ref(5)))!
    await flushPromises()

    expect(page.demands.error).toBe(true)
    expect(page.item.value).not.toBeNull()
    expect(page.orders.data).toHaveLength(1)
    expect(page.orders.error).toBe(false)
    scope.stop()
  })

  it('flags the demands section as truncated when the response fills the page limit', async () => {
    const items = Array.from({ length: 200 }, (_, i) => makeDemand({ id: i + 1 }))
    getSourceItemDemandsMock.mockReset().mockResolvedValue({ items, total: 500, limit: 200, skip: 0 })

    const scope = effectScope()
    const page = scope.run(() => useSourceItemDetailPage(ref(5)))!
    await flushPromises()

    expect(page.demands.truncated).toBe(true)
    expect(page.demandRows.value).toHaveLength(200)
    scope.stop()
  })

  it('maps demand rows with creator name and lot number as the extra field', async () => {
    getSourceItemDemandsMock.mockReset().mockResolvedValue({
      items: [makeDemand({ id: 9, lot_number: 'L-2026-042', creator: { full_name: 'John Smith' } as never })],
      total: 1,
      limit: 200,
      skip: 0,
    })

    const scope = effectScope()
    const page = scope.run(() => useSourceItemDetailPage(ref(5)))!
    await flushPromises()

    expect(page.demandRows.value).toEqual([
      expect.objectContaining({ id: 9, creatorName: 'John Smith', extra: 'L-2026-042' }),
    ])
    scope.stop()
  })

  it('chunks project id lookups at 200 per request', async () => {
    const manyDemands = Array.from({ length: 250 }, (_, i) =>
      makeDemand({ id: i + 1, project_id: i + 1, project_number: `P-${i + 1}` }),
    )
    getSourceItemDemandsMock
      .mockReset()
      .mockResolvedValue({ items: manyDemands, total: 250, limit: 200, skip: 0 })

    const scope = effectScope()
    scope.run(() => useSourceItemDetailPage(ref(5)))
    await flushPromises()

    // 250 distinct project ids from demands ∪ 0 from orders -> two chunks (200 + 50).
    expect(getProjectsMock).toHaveBeenCalledTimes(2)
    const chunkSizes = getProjectsMock.mock.calls.map((call) => (call[0] as { ids: number[] }).ids.length)
    expect(chunkSizes.sort((a, b) => b - a)).toEqual([200, 50])
    scope.stop()
  })

  it('quiet-reloads demands on a matching live signal without flipping the loading flag', async () => {
    const scope = effectScope()
    const page = scope.run(() => useSourceItemDetailPage(ref(5)))!
    await flushPromises()
    getSourceItemDemandsMock.mockClear()

    emit('source-item-demands', { resource: 'source-item-demands', id: 1, action: 'created', actor_id: null })
    await flushPromises()

    expect(getSourceItemDemandsMock).toHaveBeenCalledTimes(1)
    expect(page.loading.value).toBe(false)
    scope.stop()
  })

  it('quiet-reloads demands on a bulk signal, the same as a created signal', async () => {
    const scope = effectScope()
    const page = scope.run(() => useSourceItemDetailPage(ref(5)))!
    await flushPromises()
    getSourceItemDemandsMock.mockClear()

    emit('source-item-demands', { resource: 'source-item-demands', id: 999, action: 'bulk', actor_id: null })
    await flushPromises()

    expect(getSourceItemDemandsMock).toHaveBeenCalledTimes(1)
    expect(page.loading.value).toBe(false)
    scope.stop()
  })

  it('ignores a demand signal for an id the section does not contain and was not a create', async () => {
    const scope = effectScope()
    scope.run(() => useSourceItemDetailPage(ref(5)))
    await flushPromises()
    getSourceItemDemandsMock.mockClear()

    emit('source-item-demands', { resource: 'source-item-demands', id: 999, action: 'updated', actor_id: null })
    await flushPromises()

    expect(getSourceItemDemandsMock).not.toHaveBeenCalled()
    scope.stop()
  })

  it('quiet-reloads orders (and re-derives projects) on a matching orders signal', async () => {
    getOrdersMock.mockResolvedValue({ items: [makeOrder(1, [{ id: 101 }])], total: 1 })

    const scope = effectScope()
    scope.run(() => useSourceItemDetailPage(ref(5)))
    await flushPromises()
    getOrdersMock.mockClear()
    getProjectsMock.mockClear()

    emit('orders', { resource: 'orders', id: 1, action: 'updated', actor_id: null })
    await flushPromises()

    expect(getOrdersMock).toHaveBeenCalledTimes(1)
    expect(getProjectsMock).toHaveBeenCalled()
    scope.stop()
  })

  it('reloads everything quietly on a reconnectCount bump', async () => {
    const scope = effectScope()
    scope.run(() => useSourceItemDetailPage(ref(5)))
    await flushPromises()
    listMock.mockClear()
    getSourceItemDemandsMock.mockClear()
    getOrdersMock.mockClear()
    getSourceItemChangelogMock.mockClear()

    fakeReconnectCount.value++
    await flushPromises()

    expect(listMock).toHaveBeenCalledTimes(1)
    expect(getSourceItemDemandsMock).toHaveBeenCalledTimes(1)
    expect(getOrdersMock).toHaveBeenCalledTimes(1)
    expect(getSourceItemChangelogMock).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('unsubscribes from live signals on scope dispose', async () => {
    const scope = effectScope()
    scope.run(() => useSourceItemDetailPage(ref(5)))
    await flushPromises()
    scope.stop()
    getSourceItemDemandsMock.mockClear()

    emit('source-item-demands', { resource: 'source-item-demands', id: 1, action: 'created', actor_id: null })
    await flushPromises()

    expect(getSourceItemDemandsMock).not.toHaveBeenCalled()
  })

  it('re-runs the full load when itemId changes', async () => {
    const id = ref(5)
    const scope = effectScope()
    const page = scope.run(() => useSourceItemDetailPage(id))!
    await flushPromises()

    listMock.mockReset().mockResolvedValue({ items: [makeItem({ id: 6 })], total: 1, limit: 1, skip: 0 })
    id.value = 6
    await flushPromises()

    expect(listMock).toHaveBeenCalledWith({ id: 6, limit: 1 })
    expect(page.item.value?.id).toBe(6)
    scope.stop()
  })

  it("changing itemId clears the previous item's sections immediately", async () => {
    getSourceItemDemandsMock
      .mockReset()
      .mockResolvedValue({ items: [makeDemand()], total: 1, limit: 200, skip: 0 })

    const id = ref(5)
    const scope = effectScope()
    const page = scope.run(() => useSourceItemDetailPage(id))!
    await flushPromises()

    expect(page.item.value).not.toBeNull()
    expect(page.demands.data.length).toBeGreaterThan(0)

    id.value = 6
    // No await here: `flush: 'sync'` runs the reset in the same tick as
    // the id mutation, before the new id's requests have even resolved.
    expect(page.item.value).toBeNull()
    expect(page.demands.data).toEqual([])

    await flushPromises()
    scope.stop()
  })

  it('a response for a previous id is discarded', async () => {
    let resolveFirst: (value: unknown) => void = () => {}
    let resolveSecond: (value: unknown) => void = () => {}
    listMock
      .mockReset()
      .mockImplementationOnce(() => new Promise((resolve) => (resolveFirst = resolve)))
      .mockImplementationOnce(() => new Promise((resolve) => (resolveSecond = resolve)))

    const id = ref(5)
    const scope = effectScope()
    const page = scope.run(() => useSourceItemDetailPage(id))!
    id.value = 6
    await flushPromises()

    // Resolve the NEW id's request first, then the stale OLD one settles
    // after it; the late arrival must not overwrite the newer item.
    resolveSecond({ items: [makeItem({ id: 6 })], total: 1, limit: 1, skip: 0 })
    await flushPromises()
    resolveFirst({ items: [makeItem({ id: 5 })], total: 1, limit: 1, skip: 0 })
    await flushPromises()

    expect(page.item.value?.id).toBe(6)
    scope.stop()
  })
})
