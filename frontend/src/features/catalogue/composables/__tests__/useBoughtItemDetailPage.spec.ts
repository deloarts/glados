import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { effectScope, nextTick, reactive, ref } from 'vue'
import type { EffectScope, Ref } from 'vue'

import type { LiveSignal } from '@/core/realtime/types'

// Mirrors useAutoPlanRunLiveSync.spec.ts / useLiveRows.spec.ts's fake
// liveStore: a reactive wrapper so `() => liveStore.reconnectCount` stays
// reactive, and a subscriber map standing in for liveStore.on()/its
// returned unsubscribe. Only one handler per resource, which is fine here
// since the composable subscribes to two distinct resources.
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

function emit(resource: string, signal: LiveSignal): void {
  subscribers.get(resource)?.(signal)
}

const getBoughtItemsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/bought-items/api/getBoughtItems', () => ({
  getBoughtItems: (...args: unknown[]) => getBoughtItemsMock(...args),
}))

const getDemandsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/bought-items/api/boughtItemDemandsApi', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/features/bought-items/api/boughtItemDemandsApi')>()),
  getDemands: (...args: unknown[]) => getDemandsMock(...args),
}))

const getBoughtItemChangelogMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/bought-items/api/getBoughtItemChangelog', () => ({
  getBoughtItemChangelog: (...args: unknown[]) => getBoughtItemChangelogMock(...args),
}))

const getOrdersMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/orders', () => ({
  getOrders: (...args: unknown[]) => getOrdersMock(...args),
}))

const getProjectsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/projects/api/getProjects', () => ({
  getProjects: (...args: unknown[]) => getProjectsMock(...args),
}))

import { useBoughtItemDetailPage } from '../useBoughtItemDetailPage'

function makeItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    public_id: 'a',
    part_number: 'PN-1',
    status: 'active',
    created: '2026-01-01',
    changed: null,
    deleted: false,
    order_code_1: 'OC-1',
    order_code_2: null,
    gtin: null,
    ean: null,
    tariff_number: null,
    article_name: 'Bolt',
    article_groups: [],
    data_source: 'WEB',
    mass: null,
    note: null,
    weblink: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    manufacturer_id: 1,
    manufacturer_name: 'ACME',
    ...overrides,
  }
}

function makeDemand(overrides: Record<string, unknown> = {}) {
  return {
    id: 10,
    public_id: 'd',
    status: 'open',
    created: '2026-01-01',
    changed: null,
    quantity: 5,
    unit: 'PCS',
    items_per_unit: 1,
    high_priority: false,
    notify_on_delivery: false,
    note: null,
    desired_delivery_date: null,
    creator_id: 1,
    creator: { id: 1, public_id: 'u', username: 'jd', full_name: 'Jane Doe', email: 'j@x.com', has_avatar: false },
    item_id: 1,
    item_order_code_1: 'OC-1',
    item_article_name: 'Bolt',
    project_id: 100,
    project_number: 'P-100',
    project_customer: 'ACME',
    project_description: 'Widget line',
    project_status: 'active',
    bucket_id: null,
    ...overrides,
  }
}

function makeOrder(id: number, items: unknown[]) {
  return {
    id,
    public_id: `order-${id}`,
    order_number: `ORD-${id}`,
    status: 'ordered',
    created: '2026-01-01T00:00:00Z',
    changed: null,
    total: null,
    note: null,
    ordered_date: null,
    expected_delivery_date: null,
    delivery_date: null,
    storage_place: null,
    creator_id: 1,
    creator: null,
    supplier_id: 1,
    supplier_name: 'Supplier Co',
    supplier_vat_id: '',
    items,
  }
}

function makeOrderItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 20,
    public_id: 'oi',
    status: 'delivered',
    created: '2026-01-01T00:00:00Z',
    changed: null,
    position: 1,
    quantity: 3,
    quantity_delivered: 3,
    unit: 'PCS',
    items_per_unit: 1,
    price: null,
    note: null,
    ordered_date: null,
    expected_delivery_date: null,
    delivery_date: null,
    storage_place: null,
    expected_pickup_date: null,
    ready_for_pickup_date: null,
    creator_id: 1,
    creator: null,
    orderer_id: null,
    orderer: null,
    receiver_id: null,
    receiver: null,
    bought_item_id: 1,
    source_item_id: null,
    virtual_name: null,
    item_order_code_1: 'OC-1',
    item_order_code_2: null,
    item_specification: '',
    item_article_name: 'Bolt',
    item_part_number: 'PN-1',
    item_material: null,
    item_dimension: null,
    item_type_name: null,
    item_revision: null,
    item_base_size: null,
    item_mass: null,
    item_manufacturer: null,
    made_item_id: null,
    order_id: 1,
    supplier_id: 1,
    supplier_name: 'Supplier Co',
    project_id: 100,
    project_number: 'P-100',
    project_customer: 'ACME',
    project_description: 'Widget line',
    project_status: 'active',
    line_type: 'bought',
    lot_position_id: null,
    lot_id: null,
    lot_number: '',
    fabrication_method: '',
    ...overrides,
  }
}

function defaultMocks(): void {
  getBoughtItemsMock.mockResolvedValue({ items: [makeItem()], total: 1 })
  getDemandsMock.mockResolvedValue({ items: [], total: 0 })
  getBoughtItemChangelogMock.mockResolvedValue([])
  getOrdersMock.mockResolvedValue({ items: [], total: 0 })
  getProjectsMock.mockResolvedValue({ items: [], total: 0 })
}

// Tracks every effectScope a test creates so afterEach can stop them all,
// even one whose test threw before reaching its own scope.stop(): an
// un-stopped scope's live-signal watchers (reconnectCount, demands, orders)
// stay active and can fire extra reloads during a LATER test that shares
// this file's module-level fakeReconnectCount/subscribers, corrupting call
// counts there instead of just failing its own test.
const activeScopes: EffectScope[] = []

function mountPage(id: number | Ref<number>) {
  const scope = effectScope()
  activeScopes.push(scope)
  const idRef = typeof id === 'number' ? ref(id) : id
  return { scope, page: scope.run(() => useBoughtItemDetailPage(idRef))! }
}

describe('useBoughtItemDetailPage', () => {
  beforeEach(() => {
    fakeReconnectCount.value = 0
    subscribers.clear()
    getBoughtItemsMock.mockReset()
    getDemandsMock.mockReset()
    getBoughtItemChangelogMock.mockReset()
    getOrdersMock.mockReset()
    getProjectsMock.mockReset()
    defaultMocks()
  })

  afterEach(() => {
    activeScopes.splice(0).forEach((scope) => scope.stop())
  })

  it('loads the item and every section on initial mount', async () => {
    getDemandsMock.mockResolvedValue({ items: [makeDemand()], total: 1 })

    const { page } = mountPage(1)
    await flushAll()

    expect(page.item.value?.id).toBe(1)
    expect(page.loading.value).toBe(false)
    expect(page.notFound.value).toBe(false)
    expect(page.loadError.value).toBe(false)
    expect(page.demandRows.value).toHaveLength(1)
  })

  it('flags not-found when the item list comes back empty', async () => {
    getBoughtItemsMock.mockResolvedValue({ items: [], total: 0 })

    const { page } = mountPage(999)
    await flushAll()

    expect(page.notFound.value).toBe(true)
    expect(page.item.value).toBeNull()
    expect(page.loadError.value).toBe(false)
  })

  it('flags a load error on any failed item request, distinct from not-found', async () => {
    getBoughtItemsMock.mockRejectedValue(new Error('network down'))

    const { page } = mountPage(1)
    await flushAll()

    expect(page.loadError.value).toBe(true)
    expect(page.notFound.value).toBe(false)
  })

  it('isolates a failing section - the item and other sections still load', async () => {
    getDemandsMock.mockRejectedValue(new Error('demands down'))
    getOrdersMock.mockResolvedValue({
      items: [makeOrder(1, [makeOrderItem()])],
      total: 1,
    })

    const { page } = mountPage(1)
    await flushAll()

    expect(page.item.value).not.toBeNull()
    expect(page.loadError.value).toBe(false)
    expect(page.demands.error).toBe(true)
    expect(page.orders.error).toBe(false)
    expect(page.orders.data).toHaveLength(1)
  })

  it('flags the demands section truncated once it reaches the 200-row limit', async () => {
    getDemandsMock.mockResolvedValue({
      items: Array.from({ length: 200 }, (_, i) => makeDemand({ id: i })),
      total: 200,
    })

    const { page } = mountPage(1)
    await flushAll()

    expect(page.demands.truncated).toBe(true)
  })

  it('does not flag the demands section truncated below the limit', async () => {
    getDemandsMock.mockResolvedValue({ items: [makeDemand()], total: 1 })

    const { page } = mountPage(1)
    await flushAll()

    expect(page.demands.truncated).toBe(false)
  })

  it('flags the orders section truncated from the raw order-page size, not the flattened row count', async () => {
    // 200 orders, each with a line for a DIFFERENT item: the flattened,
    // filtered row count is 0, but the underlying order page still hit its
    // 200 limit, so there may be more of this item's orders beyond page 1.
    getOrdersMock.mockResolvedValue({
      items: Array.from({ length: 200 }, (_, i) =>
        makeOrder(i, [makeOrderItem({ bought_item_id: 999 })]),
      ),
      total: 200,
    })

    const { page } = mountPage(1)
    await flushAll()

    expect(page.orders.data).toHaveLength(0)
    expect(page.orders.truncated).toBe(true)
  })

  it('chunks the projects request at 200 ids and unions demand + order project ids', async () => {
    const demands = Array.from({ length: 150 }, (_, i) =>
      makeDemand({ id: i, project_id: i, project_number: `P-${i}` }),
    )
    const orderItems = Array.from({ length: 150 }, (_, i) =>
      makeOrderItem({ id: 1000 + i, project_id: 150 + i, project_number: `P-${150 + i}` }),
    )
    getDemandsMock.mockResolvedValue({ items: demands, total: demands.length })
    getOrdersMock.mockResolvedValue({
      items: [makeOrder(1, orderItems)],
      total: 1,
    })
    getProjectsMock.mockResolvedValue({ items: [], total: 0 })

    mountPage(1)

    // loadProjects awaits its two chunk requests sequentially (not
    // Promise.all, see the composable), so this needs more microtask hops
    // than a fixed flushAll() reliably provides; poll instead of guessing a
    // hop count.
    await vi.waitFor(() => {
      expect(getProjectsMock).toHaveBeenCalledTimes(2)
    })

    // 300 distinct project ids (0..149 from demands, 150..299 from orders)
    // chunked at 200 each -> two calls.
    const chunkSizes = getProjectsMock.mock.calls.map(
      (call) => (call[0] as { ids: number[] }).ids.length,
    )
    expect(chunkSizes.reduce((a, b) => a + b, 0)).toBe(300)
    expect(chunkSizes.every((size) => size <= 200)).toBe(true)
  })

  it('reloads demands quietly on a created signal, without flipping loading', async () => {
    const { page } = mountPage(1)
    await flushAll()

    getDemandsMock.mockClear()
    getDemandsMock.mockResolvedValue({ items: [makeDemand({ id: 55 })], total: 1 })

    emit('bought-items-demands', { resource: 'bought-items-demands', id: 55, action: 'created', actor_id: null })
    // The demands loader is async even for a quiet call: loading itself
    // must never flip true, but the fetch is still in flight for a tick.
    expect(page.demands.loading).toBe(false)
    await flushAll()

    expect(getDemandsMock).toHaveBeenCalledTimes(1)
    expect(page.demands.data).toHaveLength(1)
    expect(page.demands.loading).toBe(false)
  })

  it('reloads demands quietly on a bulk signal, the same as a created signal', async () => {
    const { page } = mountPage(1)
    await flushAll()

    getDemandsMock.mockClear()
    getDemandsMock.mockResolvedValue({ items: [makeDemand({ id: 66 })], total: 1 })

    emit('bought-items-demands', { resource: 'bought-items-demands', id: 999, action: 'bulk', actor_id: null })
    expect(page.demands.loading).toBe(false)
    await flushAll()

    expect(getDemandsMock).toHaveBeenCalledTimes(1)
    expect(page.demands.data).toHaveLength(1)
  })

  it('reloads demands on an updated signal only when the row is already in the section', async () => {
    getDemandsMock.mockResolvedValue({ items: [makeDemand({ id: 55 })], total: 1 })

    mountPage(1)
    await flushAll()
    getDemandsMock.mockClear()

    emit('bought-items-demands', { resource: 'bought-items-demands', id: 999, action: 'updated', actor_id: null })
    await flushAll()
    expect(getDemandsMock).not.toHaveBeenCalled()

    emit('bought-items-demands', { resource: 'bought-items-demands', id: 55, action: 'updated', actor_id: null })
    await flushAll()
    expect(getDemandsMock).toHaveBeenCalledTimes(1)
  })

  it('reloads orders (and refreshes projects) on an orders signal', async () => {
    getOrdersMock.mockResolvedValue({ items: [makeOrder(1, [makeOrderItem({ id: 77 })])], total: 1 })

    mountPage(1)
    await flushAll()
    getOrdersMock.mockClear()
    getProjectsMock.mockClear()

    emit('orders', { resource: 'orders', id: 1, action: 'updated', actor_id: null })
    await flushAll()

    expect(getOrdersMock).toHaveBeenCalledTimes(1)
    expect(getProjectsMock).toHaveBeenCalledTimes(1)
  })

  it('reloads everything quietly on a reconnectCount bump', async () => {
    mountPage(1)
    await flushAll()
    getBoughtItemsMock.mockClear()
    getDemandsMock.mockClear()
    getOrdersMock.mockClear()
    getBoughtItemChangelogMock.mockClear()

    fakeReconnectCount.value++
    await flushAll()

    expect(getBoughtItemsMock).toHaveBeenCalledTimes(1)
    expect(getDemandsMock).toHaveBeenCalledTimes(1)
    expect(getOrdersMock).toHaveBeenCalledTimes(1)
    expect(getBoughtItemChangelogMock).toHaveBeenCalledTimes(1)
  })

  it('re-runs everything when itemId changes (same-route navigation)', async () => {
    const id = ref(1)
    mountPage(id)
    await flushAll()

    getBoughtItemsMock.mockClear()
    getBoughtItemsMock.mockResolvedValue({ items: [makeItem({ id: 2 })], total: 1 })

    id.value = 2
    await flushAll()

    expect(getBoughtItemsMock).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }))
  })

  it("changing itemId clears the previous item's sections immediately", async () => {
    getDemandsMock.mockResolvedValue({ items: [makeDemand()], total: 1 })

    const id = ref(1)
    const { page } = mountPage(id)
    await flushAll()

    expect(page.item.value).not.toBeNull()
    expect(page.demands.data.length).toBeGreaterThan(0)

    id.value = 2
    // No await here: `flush: 'sync'` runs the reset in the same tick as
    // the id mutation, before the new id's requests have even resolved.
    expect(page.item.value).toBeNull()
    expect(page.demands.data).toEqual([])

    await flushAll()
  })

  it('a response for a previous id is discarded', async () => {
    let resolveFirst: (value: unknown) => void = () => {}
    let resolveSecond: (value: unknown) => void = () => {}
    getBoughtItemsMock
      .mockImplementationOnce(() => new Promise((resolve) => (resolveFirst = resolve)))
      .mockImplementationOnce(() => new Promise((resolve) => (resolveSecond = resolve)))

    const id = ref(1)
    const { page } = mountPage(id)
    id.value = 2
    await flushAll()

    // Resolve the NEW id's request first, then the stale OLD one settles
    // after it: the late arrival must not overwrite the newer item.
    resolveSecond({ items: [makeItem({ id: 2 })], total: 1 })
    await flushAll()
    resolveFirst({ items: [makeItem({ id: 1 })], total: 1 })
    await flushAll()

    expect(page.item.value?.id).toBe(2)
  })

  it('unsubscribes from live signals on scope dispose', async () => {
    const { scope } = mountPage(1)
    await flushAll()
    scope.stop()

    getDemandsMock.mockClear()
    emit('bought-items-demands', { resource: 'bought-items-demands', id: 1, action: 'created', actor_id: null })
    await flushAll()

    expect(getDemandsMock).not.toHaveBeenCalled()
  })
})

async function flushAll(): Promise<void> {
  await nextTick()
  await Promise.resolve()
  await Promise.resolve()
  await nextTick()
}
