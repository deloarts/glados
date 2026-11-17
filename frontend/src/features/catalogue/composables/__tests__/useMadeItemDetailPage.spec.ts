import { describe, it, expect, vi, beforeEach } from 'vitest'
import { effectScope, nextTick, reactive, ref } from 'vue'

import type { LiveSignal } from '@/core/realtime/types'

// Mirrors useBoughtItemDetailPage.spec.ts / useLiveRows.spec.ts's fake
// liveStore: a reactive wrapper so `() => liveStore.reconnectCount` stays
// reactive, and a subscriber map standing in for liveStore.on()/its
// returned unsubscribe. Only one handler per resource is fine here, since
// the composable subscribes to three distinct resources.
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

// Real Pinia store, but faked wholesale (like liveStore above) rather than
// booted through createPinia()/setActivePinia(); the composable only ever
// reads one boolean off it (productionPlanningEnabled, gating the lots
// section), so a fake avoids pulling in the store's own /host/* fetch()
// plumbing for something this suite never exercises.
const fakeProductionPlanningEnabled = ref(true)
const fakeHostStore = reactive({
  productionPlanningEnabled: fakeProductionPlanningEnabled,
  // Only the separator is read (useMadeItemLabel, for the alteration-source
  // label on demand rows). The rest of the numbering policy shape is never
  // touched by this suite.
  madeItemPartNumbers: { revision: { separator: ':' } },
})

vi.mock('@/core/host/stores/hostStore', () => ({
  useHostStore: () => fakeHostStore,
}))

const getMadeItemsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/made-items/api/getMadeItems', () => ({
  getMadeItems: (...args: unknown[]) => getMadeItemsMock(...args),
}))

const getMadeItemDemandsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/made-items/api/madeItemDemandsApi', () => ({
  getMadeItemDemands: (...args: unknown[]) => getMadeItemDemandsMock(...args),
}))

const getMadeItemChangelogMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/made-items/api/getMadeItemChangelog', () => ({
  getMadeItemChangelog: (...args: unknown[]) => getMadeItemChangelogMock(...args),
}))

const getMadeItemRevisionsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/made-items/api/getMadeItemRevisions', () => ({
  getMadeItemRevisions: (...args: unknown[]) => getMadeItemRevisionsMock(...args),
}))

const getOrdersMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/orders', () => ({
  getOrders: (...args: unknown[]) => getOrdersMock(...args),
}))

const getLotsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/production', () => ({
  getLots: (...args: unknown[]) => getLotsMock(...args),
}))

const getProjectsMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()
vi.mock('@/features/projects/api/getProjects', () => ({
  getProjects: (...args: unknown[]) => getProjectsMock(...args),
}))

import { useMadeItemDetailPage } from '../useMadeItemDetailPage'

function makeItem(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    public_id: 'a',
    part_number: 'PN-1',
    status: 'active',
    created: '2026-01-01',
    changed: null,
    deleted: false,
    revision: 'A',
    article_name: 'Bracket',
    article_groups: [],
    data_source: 'WEB',
    material: null,
    mass: null,
    base_size: null,
    note: null,
    weblink: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    bought_item_id: null,
    bought_item: null,
    source_item_id: null,
    source_item: null,
    processes: [],
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
    creator: {
      id: 1,
      public_id: 'u',
      username: 'jd',
      full_name: 'Jane Doe',
      email: 'j@x.com',
      has_avatar: false,
    },
    made_item_id: 1,
    item_part_number: 'PN-1',
    item_article_name: 'Bracket',
    project_id: 100,
    project_number: 'P-100',
    project_customer: 'ACME',
    project_description: 'Widget line',
    project_status: 'active',
    is_alteration: false,
    alteration_of_made_item_part_number: '',
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
    bought_item_id: null,
    source_item_id: null,
    virtual_name: null,
    item_order_code_1: '',
    item_order_code_2: null,
    item_specification: '',
    item_article_name: 'Bracket',
    item_part_number: 'PN-1',
    item_material: null,
    item_dimension: null,
    item_type_name: null,
    item_revision: null,
    item_base_size: null,
    item_mass: null,
    item_manufacturer: null,
    made_item_id: 1,
    order_id: 1,
    supplier_id: 1,
    supplier_name: 'Supplier Co',
    project_id: 100,
    project_number: 'P-100',
    project_customer: 'ACME',
    project_description: 'Widget line',
    project_status: 'active',
    line_type: 'made',
    lot_position_id: 1,
    lot_id: 1,
    lot_number: 'L-1',
    fabrication_method: '',
    ...overrides,
  }
}

function makeLot(overrides: Record<string, unknown> = {}) {
  return {
    id: 30,
    lot_number: 'L-2026-001',
    status: 'in_progress',
    quantity: 10,
    quantity_completed: 4,
    project_number: 'P-100',
    required_delivery_date: '2026-04-01',
    created: '2026-03-01',
    ...overrides,
  }
}

function makeRevisions(overrides: Record<string, unknown> = {}) {
  return {
    items: [],
    next_revision: null,
    next_revision_error: null,
    can_create: true,
    reason: null,
    ...overrides,
  }
}

function defaultMocks(): void {
  getMadeItemsMock.mockResolvedValue({ items: [makeItem()], total: 1 })
  getMadeItemDemandsMock.mockResolvedValue({ items: [], total: 0 })
  getMadeItemChangelogMock.mockResolvedValue([])
  getMadeItemRevisionsMock.mockResolvedValue(makeRevisions())
  getOrdersMock.mockResolvedValue({ items: [], total: 0 })
  getLotsMock.mockResolvedValue({ items: [], total: 0 })
  getProjectsMock.mockResolvedValue({ items: [], total: 0 })
}

describe('useMadeItemDetailPage', () => {
  beforeEach(() => {
    fakeReconnectCount.value = 0
    fakeProductionPlanningEnabled.value = true
    subscribers.clear()
    getMadeItemsMock.mockReset()
    getMadeItemDemandsMock.mockReset()
    getMadeItemChangelogMock.mockReset()
    getMadeItemRevisionsMock.mockReset()
    getOrdersMock.mockReset()
    getLotsMock.mockReset()
    getProjectsMock.mockReset()
    defaultMocks()
  })

  it('loads the item and every section on initial mount', async () => {
    getMadeItemDemandsMock.mockResolvedValue({ items: [makeDemand()], total: 1 })
    getLotsMock.mockResolvedValue({ items: [makeLot()], total: 1 })

    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(ref(1)))!
    await flushAll()

    expect(page.item.value?.id).toBe(1)
    expect(page.loading.value).toBe(false)
    expect(page.notFound.value).toBe(false)
    expect(page.loadError.value).toBe(false)
    expect(page.demandRows.value).toHaveLength(1)
    expect(page.lots.data).toHaveLength(1)
    scope.stop()
  })

  it('loads the revisions GET alongside the other sections', async () => {
    getMadeItemRevisionsMock.mockResolvedValue(
      makeRevisions({
        items: [
          { id: 1, public_id: 'a', revision: 'B', revision_date: null, status: 'active', successor_item_id: null, created: '2026-01-01', is_newest: true },
        ],
      }),
    )

    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(ref(1)))!
    await flushAll()

    expect(getMadeItemRevisionsMock).toHaveBeenCalledWith(1)
    expect(page.revisions.value?.items).toHaveLength(1)
    scope.stop()
  })

  it('flags not-found when the item list comes back empty', async () => {
    getMadeItemsMock.mockResolvedValue({ items: [], total: 0 })

    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(ref(999)))!
    await flushAll()

    expect(page.notFound.value).toBe(true)
    expect(page.item.value).toBeNull()
    expect(page.loadError.value).toBe(false)
    scope.stop()
  })

  it('flags a load error when the item request throws', async () => {
    getMadeItemsMock.mockRejectedValue(new Error('network down'))

    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(ref(1)))!
    await flushAll()

    expect(page.loadError.value).toBe(true)
    expect(page.notFound.value).toBe(false)
    scope.stop()
  })

  it('isolates a failing section - the item and other sections still load', async () => {
    getMadeItemDemandsMock.mockRejectedValue(new Error('demands down'))
    getOrdersMock.mockResolvedValue({
      items: [makeOrder(1, [makeOrderItem()])],
      total: 1,
    })

    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(ref(1)))!
    await flushAll()

    expect(page.item.value).not.toBeNull()
    expect(page.loadError.value).toBe(false)
    expect(page.demands.error).toBe(true)
    expect(page.orders.error).toBe(false)
    expect(page.orders.data).toHaveLength(1)
    scope.stop()
  })

  it('flags the demands section truncated once it reaches the 200-row limit', async () => {
    getMadeItemDemandsMock.mockResolvedValue({
      items: Array.from({ length: 200 }, (_, i) => makeDemand({ id: i })),
      total: 200,
    })

    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(ref(1)))!
    await flushAll()

    expect(page.demands.truncated).toBe(true)
    scope.stop()
  })

  it('does not flag the demands section truncated below the limit', async () => {
    getMadeItemDemandsMock.mockResolvedValue({ items: [makeDemand()], total: 1 })

    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(ref(1)))!
    await flushAll()

    expect(page.demands.truncated).toBe(false)
    scope.stop()
  })

  it('marks a demand row with its alteration source part number, and leaves it undefined otherwise', async () => {
    getMadeItemDemandsMock.mockResolvedValue({
      items: [
        makeDemand({ id: 1, is_alteration: false, alteration_of_made_item_part_number: '' }),
        makeDemand({ id: 2, is_alteration: true, alteration_of_made_item_part_number: 'PN-OLD' }),
      ],
      total: 2,
    })

    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(ref(1)))!
    await flushAll()

    const rows = page.demandRows.value
    expect(rows.find((r) => r.id === 1)?.extra).toBeUndefined()
    expect(rows.find((r) => r.id === 2)?.extra).toBe('PN-OLD')
    scope.stop()
  })

  it('derives usageError from either the demands or orders section erroring', async () => {
    getMadeItemDemandsMock.mockRejectedValue(new Error('demands down'))

    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(ref(1)))!
    await flushAll()

    expect(page.demands.error).toBe(true)
    expect(page.usageError.value).toBe(true)
    scope.stop()
  })

  it('skips the lots request entirely when production planning is disabled', async () => {
    fakeProductionPlanningEnabled.value = false

    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(ref(1)))!
    await flushAll()

    expect(getLotsMock).not.toHaveBeenCalled()
    expect(page.lots.data).toHaveLength(0)
    scope.stop()
  })

  it('flags the lots section truncated once it reaches the 200-row limit', async () => {
    getLotsMock.mockResolvedValue({
      items: Array.from({ length: 200 }, (_, i) => makeLot({ id: i })),
      total: 200,
    })

    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(ref(1)))!
    await flushAll()

    expect(page.lots.truncated).toBe(true)
    scope.stop()
  })

  it('flags the orders section truncated from the raw order-page size, not the flattened row count', async () => {
    // 200 orders, each with a line for a DIFFERENT item. The flattened,
    // filtered row count is 0, but the underlying order page still hit its
    // 200 limit, so there may be more of this item's orders beyond page 1.
    getOrdersMock.mockResolvedValue({
      items: Array.from({ length: 200 }, (_, i) =>
        makeOrder(i, [makeOrderItem({ made_item_id: 999 })]),
      ),
      total: 200,
    })

    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(ref(1)))!
    await flushAll()

    expect(page.orders.data).toHaveLength(0)
    expect(page.orders.truncated).toBe(true)
    scope.stop()
  })

  it('chunks the projects request at 200 ids and unions demand + order project ids', async () => {
    const demands = Array.from({ length: 150 }, (_, i) =>
      makeDemand({ id: i, project_id: i, project_number: `P-${i}` }),
    )
    const orderItems = Array.from({ length: 150 }, (_, i) =>
      makeOrderItem({ id: 1000 + i, project_id: 150 + i, project_number: `P-${150 + i}` }),
    )
    getMadeItemDemandsMock.mockResolvedValue({ items: demands, total: demands.length })
    getOrdersMock.mockResolvedValue({
      items: [makeOrder(1, orderItems)],
      total: 1,
    })
    getProjectsMock.mockResolvedValue({ items: [], total: 0 })

    const scope = effectScope()
    scope.run(() => useMadeItemDetailPage(ref(1)))
    await flushAll()

    // 300 distinct project ids (0..149 from demands, 150..299 from orders)
    // chunked at 200 each -> two calls.
    expect(getProjectsMock).toHaveBeenCalledTimes(2)
    const chunkSizes = getProjectsMock.mock.calls.map(
      (call) => (call[0] as { ids: number[] }).ids.length,
    )
    expect(chunkSizes.reduce((a, b) => a + b, 0)).toBe(300)
    expect(chunkSizes.every((size) => size <= 200)).toBe(true)
    scope.stop()
  })

  it('reloads demands quietly on a created signal, without flipping loading', async () => {
    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(ref(1)))!
    await flushAll()

    getMadeItemDemandsMock.mockClear()
    getMadeItemDemandsMock.mockResolvedValue({ items: [makeDemand({ id: 55 })], total: 1 })

    emit('made-items-demands', {
      resource: 'made-items-demands',
      id: 55,
      action: 'created',
      actor_id: null,
    })
    // The demands loader is async even for a quiet call: loading itself
    // must never flip true, but the fetch is still in flight for a tick.
    expect(page.demands.loading).toBe(false)
    await flushAll()

    expect(getMadeItemDemandsMock).toHaveBeenCalledTimes(1)
    expect(page.demands.data).toHaveLength(1)
    expect(page.demands.loading).toBe(false)
    scope.stop()
  })

  it('reloads demands on an updated signal only when the row is already in the section', async () => {
    getMadeItemDemandsMock.mockResolvedValue({ items: [makeDemand({ id: 55 })], total: 1 })

    const scope = effectScope()
    scope.run(() => useMadeItemDetailPage(ref(1)))
    await flushAll()
    getMadeItemDemandsMock.mockClear()

    emit('made-items-demands', {
      resource: 'made-items-demands',
      id: 999,
      action: 'updated',
      actor_id: null,
    })
    await flushAll()
    expect(getMadeItemDemandsMock).not.toHaveBeenCalled()

    emit('made-items-demands', {
      resource: 'made-items-demands',
      id: 55,
      action: 'updated',
      actor_id: null,
    })
    await flushAll()
    expect(getMadeItemDemandsMock).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('reloads orders (and refreshes projects) on an orders signal', async () => {
    getOrdersMock.mockResolvedValue({ items: [makeOrder(1, [makeOrderItem({ id: 77 })])], total: 1 })

    const scope = effectScope()
    scope.run(() => useMadeItemDetailPage(ref(1)))
    await flushAll()
    getOrdersMock.mockClear()
    getProjectsMock.mockClear()

    emit('orders', { resource: 'orders', id: 1, action: 'updated', actor_id: null })
    await flushAll()

    expect(getOrdersMock).toHaveBeenCalledTimes(1)
    expect(getProjectsMock).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('reloads lots on a production-lots signal, but never when planning is disabled', async () => {
    getLotsMock.mockResolvedValue({ items: [makeLot({ id: 30 })], total: 1 })

    const scope = effectScope()
    scope.run(() => useMadeItemDetailPage(ref(1)))
    await flushAll()
    getLotsMock.mockClear()

    emit('production-lots', { resource: 'production-lots', id: 30, action: 'updated', actor_id: null })
    await flushAll()
    expect(getLotsMock).toHaveBeenCalledTimes(1)

    fakeProductionPlanningEnabled.value = false
    getLotsMock.mockClear()

    emit('production-lots', { resource: 'production-lots', id: 30, action: 'updated', actor_id: null })
    await flushAll()
    expect(getLotsMock).not.toHaveBeenCalled()
    scope.stop()
  })

  it('reloads everything quietly on a reconnectCount bump', async () => {
    const scope = effectScope()
    scope.run(() => useMadeItemDetailPage(ref(1)))
    await flushAll()
    getMadeItemsMock.mockClear()
    getMadeItemDemandsMock.mockClear()
    getOrdersMock.mockClear()
    getLotsMock.mockClear()
    getMadeItemChangelogMock.mockClear()

    fakeReconnectCount.value++
    await flushAll()

    expect(getMadeItemsMock).toHaveBeenCalledTimes(1)
    expect(getMadeItemDemandsMock).toHaveBeenCalledTimes(1)
    expect(getOrdersMock).toHaveBeenCalledTimes(1)
    expect(getLotsMock).toHaveBeenCalledTimes(1)
    expect(getMadeItemChangelogMock).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('re-runs everything when itemId changes (same-route navigation)', async () => {
    const id = ref(1)
    const scope = effectScope()
    scope.run(() => useMadeItemDetailPage(id))
    await flushAll()

    getMadeItemsMock.mockClear()
    getMadeItemsMock.mockResolvedValue({ items: [makeItem({ id: 2 })], total: 1 })

    id.value = 2
    await flushAll()

    expect(getMadeItemsMock).toHaveBeenCalledWith(expect.objectContaining({ id: 2 }))
    scope.stop()
  })

  it("changing itemId clears the previous item's sections immediately", async () => {
    getMadeItemDemandsMock.mockResolvedValue({ items: [makeDemand()], total: 1 })

    const id = ref(1)
    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(id))!
    await flushAll()

    expect(page.item.value).not.toBeNull()
    expect(page.demands.data.length).toBeGreaterThan(0)

    id.value = 2
    // No await here: `flush: 'sync'` runs the reset in the same tick as
    // the id mutation, before the new id's requests have even resolved.
    expect(page.item.value).toBeNull()
    expect(page.demands.data).toEqual([])

    await flushAll()
    scope.stop()
  })

  it('does not load when the id turns NaN on leaving the route', async () => {
    const id = ref(1)
    const scope = effectScope()
    scope.run(() => useMadeItemDetailPage(id))
    await flushAll()

    getMadeItemsMock.mockClear()
    getMadeItemDemandsMock.mockClear()
    getOrdersMock.mockClear()
    getLotsMock.mockClear()
    getMadeItemChangelogMock.mockClear()

    id.value = Number.NaN
    await flushAll()

    expect(getMadeItemsMock).not.toHaveBeenCalled()
    expect(getMadeItemDemandsMock).not.toHaveBeenCalled()
    expect(getOrdersMock).not.toHaveBeenCalled()
    expect(getLotsMock).not.toHaveBeenCalled()
    expect(getMadeItemChangelogMock).not.toHaveBeenCalled()
    scope.stop()
  })

  it('a response for a previous id is discarded', async () => {
    let resolveFirst: (value: unknown) => void = () => {}
    let resolveSecond: (value: unknown) => void = () => {}
    getMadeItemsMock
      .mockImplementationOnce(() => new Promise((resolve) => (resolveFirst = resolve)))
      .mockImplementationOnce(() => new Promise((resolve) => (resolveSecond = resolve)))

    const id = ref(1)
    const scope = effectScope()
    const page = scope.run(() => useMadeItemDetailPage(id))!
    id.value = 2
    await flushAll()

    // Resolve the NEW id's request first, then the stale OLD one settles
    // after it. The late arrival must not overwrite the newer item.
    resolveSecond({ items: [makeItem({ id: 2 })], total: 1 })
    await flushAll()
    resolveFirst({ items: [makeItem({ id: 1 })], total: 1 })
    await flushAll()

    expect(page.item.value?.id).toBe(2)
    scope.stop()
  })

  it('unsubscribes from live signals on scope dispose', async () => {
    const scope = effectScope()
    scope.run(() => useMadeItemDetailPage(ref(1)))
    await flushAll()
    scope.stop()

    getMadeItemDemandsMock.mockClear()
    emit('made-items-demands', {
      resource: 'made-items-demands',
      id: 1,
      action: 'created',
      actor_id: null,
    })
    await flushAll()

    expect(getMadeItemDemandsMock).not.toHaveBeenCalled()
  })
})

async function flushAll(): Promise<void> {
  await nextTick()
  await Promise.resolve()
  await Promise.resolve()
  await nextTick()
}
