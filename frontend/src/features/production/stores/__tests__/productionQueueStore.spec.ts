import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { PageResponse } from '@/core/api/types'
import type {
  MergeProductionOrdersRequest,
  ProductionOrderFilterParams,
  PauseProductionOrderRequest,
  ReassignProductionOrderMachineRequest,
  RecordManufacturingAssessmentRequest,
  RecordProductionOrderCompletionRequest,
  SplitProductionOrderRequest,
  StartProductionOrderRequest,
} from '../../types/productionOrdersRequest'
import type {
  ManufacturingAssessmentResponse,
  ProductionOrderResponse,
} from '../../types/productionOrdersResponse'

const reassignMock = vi.fn<
  (id: number, payload: ReassignProductionOrderMachineRequest) => Promise<ProductionOrderResponse>
>()
const getProductionOrdersMock = vi.fn<
  (params?: ProductionOrderFilterParams) => Promise<PageResponse<ProductionOrderResponse>>
>()
const startMock = vi.fn<
  (id: number, payload: StartProductionOrderRequest) => Promise<ProductionOrderResponse>
>()
const pauseMock = vi.fn<
  (id: number, payload: PauseProductionOrderRequest) => Promise<ProductionOrderResponse>
>()
const cancelMock = vi.fn<
  (id: number, payload: { reason?: string | null }) => Promise<ProductionOrderResponse>
>()
const recordCompletionMock = vi.fn<
  (
    id: number,
    payload: RecordProductionOrderCompletionRequest,
  ) => Promise<ProductionOrderResponse>
>()
const splitMock = vi.fn<
  (id: number, payload: SplitProductionOrderRequest) => Promise<ProductionOrderResponse[]>
>()
const mergeMock = vi.fn<
  (payload: MergeProductionOrdersRequest) => Promise<ProductionOrderResponse>
>()
const reorderMock = vi.fn<
  (machineId: number | null, orderedIds: number[]) => Promise<ProductionOrderResponse[]>
>()
const reorderPoolMock = vi.fn<
  (poolId: number, orderedIds: number[]) => Promise<ProductionOrderResponse[]>
>()
const recordAssessmentMock = vi.fn<
  (
    id: number,
    payload: RecordManufacturingAssessmentRequest,
  ) => Promise<ManufacturingAssessmentResponse>
>()

vi.mock('../../api/reassignProductionOrderMachine', () => ({
  reassignProductionOrderMachine: (id: number, payload: ReassignProductionOrderMachineRequest) =>
    reassignMock(id, payload),
}))
vi.mock('../../api/getProductionOrders', () => ({
  getProductionOrders: (params?: ProductionOrderFilterParams) => getProductionOrdersMock(params),
}))
vi.mock('../../api/startProductionOrder', () => ({
  startProductionOrder: (id: number, payload: StartProductionOrderRequest) =>
    startMock(id, payload),
}))
vi.mock('../../api/pauseProductionOrder', () => ({
  pauseProductionOrder: (id: number, payload: PauseProductionOrderRequest) =>
    pauseMock(id, payload),
}))
vi.mock('../../api/cancelProductionOrder', () => ({
  cancelProductionOrder: (id: number, payload: { reason?: string | null }) =>
    cancelMock(id, payload),
}))
vi.mock('../../api/recordProductionOrderCompletion', () => ({
  recordProductionOrderCompletion: (
    id: number,
    payload: RecordProductionOrderCompletionRequest,
  ) => recordCompletionMock(id, payload),
}))
vi.mock('../../api/splitProductionOrder', () => ({
  splitProductionOrder: (id: number, payload: SplitProductionOrderRequest) =>
    splitMock(id, payload),
}))
vi.mock('../../api/mergeProductionOrders', () => ({
  mergeProductionOrders: (payload: MergeProductionOrdersRequest) => mergeMock(payload),
}))
vi.mock('../../api/reorderProductionOrders', () => ({
  reorderProductionOrders: (machineId: number | null, orderedIds: number[]) =>
    reorderMock(machineId, orderedIds),
}))
vi.mock('../../api/reorderProductionOrdersByPool', () => ({
  reorderProductionOrdersByPool: (poolId: number, orderedIds: number[]) =>
    reorderPoolMock(poolId, orderedIds),
}))
vi.mock('../../api/recordManufacturingAssessment', () => ({
  recordManufacturingAssessment: (
    id: number,
    payload: RecordManufacturingAssessmentRequest,
  ) => recordAssessmentMock(id, payload),
}))

import { useProductionQueueStore } from '../productionQueueStore'
import { makeProductionOrderResponse } from '@/test-utils/factories'

function page(items: ProductionOrderResponse[] = []): PageResponse<ProductionOrderResponse> {
  return { items, total: items.length, limit: null, skip: 0 }
}

function makeOrder(overrides: Partial<ProductionOrderResponse> = {}): ProductionOrderResponse {
  return makeProductionOrderResponse({
    machine_id: null,
    machine_internal_name: '',
    lot_number: 'LOT-2026-0027',
    ...overrides,
  })
}

// reassignMachine's payload is ReassignProductionOrderMachineRequest, a
// discriminated union (machine_id XOR machine_pool_id). These tests
// assert the store's own branch never sends both fields, whichever target
// shape it receives.
describe('productionQueueStore.reassignMachine, payload shape', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    reassignMock.mockReset()
    getProductionOrdersMock.mockReset()
    getProductionOrdersMock.mockResolvedValue(page())
    reassignMock.mockResolvedValue({} as ProductionOrderResponse)
  })

  it('sends only machine_id for a plain machine target', async () => {
    const store = useProductionQueueStore()

    await store.reassignMachine(1, 5)

    expect(reassignMock).toHaveBeenCalledWith(1, { machine_id: 5 })
    expect(reassignMock.mock.calls[0]![1]).not.toHaveProperty('machine_pool_id')
  })

  it('sends machine_id: null to clear the machine, never alongside machine_pool_id', async () => {
    const store = useProductionQueueStore()

    await store.reassignMachine(1, null)

    expect(reassignMock).toHaveBeenCalledWith(1, { machine_id: null })
    expect(reassignMock.mock.calls[0]![1]).not.toHaveProperty('machine_pool_id')
  })

  it('sends only machine_pool_id for a pool target', async () => {
    const store = useProductionQueueStore()

    await store.reassignMachine(1, { machinePoolId: 9 })

    expect(reassignMock).toHaveBeenCalledWith(1, { machine_pool_id: 9 })
    expect(reassignMock.mock.calls[0]![1]).not.toHaveProperty('machine_id')
  })
})

// machine_pool_id is schema-optional as well as nullable: the backend can
// omit the key entirely for a machine-and-pool-less order rather than send
// an explicit null. ordersByPool's own gate reads `== null` (not `=== null`)
// for exactly that reason: an `=== null` check would leave `undefined`
// treated as "has a pool", routing the order into a bogus Map bucket keyed
// by `undefined` instead of skipping it, which silently drops it off every
// real pool column.
describe('productionQueueStore.ordersByPool, undefined vs null machine_pool_id', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getProductionOrdersMock.mockReset()
  })

  it('excludes an order whose machine_pool_id key is entirely absent, same as an explicit null', async () => {
    getProductionOrdersMock.mockResolvedValue(
      page([makeOrder({ id: 1, machine_id: null, machine_pool_id: undefined })]),
    )
    const store = useProductionQueueStore()
    await store.fetchOrders()

    // No real pools registered: a correctly-skipped order leaves the map
    // empty. A `=== null` check instead of `== null` would instead fall
    // through to grouped.set(order.machine_pool_id, ...),
    // inserting a bogus bucket keyed by `undefined`.
    expect(store.ordersByPool.size).toBe(0)
  })
})

// Every mutation below must update `orders` straight from its own response
// instead of triggering a GET /production-orders refetch; that's the whole
// point of the withMutation/applyOrders rework. getProductionOrdersMock
// asserts on call count (`fetchOrders` is still used for the *initial*
// load in these tests, so the assertion is "no *additional* call after the
// mutation resolves", not "never called at all").
describe('productionQueueStore mutations apply their own response, no refetch', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    for (const m of [
      reassignMock,
      getProductionOrdersMock,
      startMock,
      pauseMock,
      cancelMock,
      recordCompletionMock,
      splitMock,
      mergeMock,
      reorderMock,
      reorderPoolMock,
      recordAssessmentMock,
    ]) {
      m.mockReset()
    }
  })

  async function seededStore(orders: ProductionOrderResponse[]) {
    getProductionOrdersMock.mockResolvedValue(page(orders))
    const store = useProductionQueueStore()
    await store.fetchOrders()
    getProductionOrdersMock.mockClear()
    return store
  }

  it('start replaces the matching order by id and issues no refetch', async () => {
    const store = await seededStore([makeOrder({ id: 1, status: 'queued' })])
    const updated = makeOrder({ id: 1, status: 'in_progress', actual_start: '2026-09-02T08:00:00' })
    startMock.mockResolvedValue(updated)

    await store.start(1, { operator_id: 7 })

    expect(store.orders).toEqual([updated])
    expect(getProductionOrdersMock).not.toHaveBeenCalled()
  })

  it('pause replaces the matching order by id and issues no refetch', async () => {
    const store = await seededStore([makeOrder({ id: 1, status: 'in_progress' })])
    const updated = makeOrder({ id: 1, status: 'paused' })
    pauseMock.mockResolvedValue(updated)

    await store.pause(1, {})

    expect(store.orders).toEqual([updated])
    expect(getProductionOrdersMock).not.toHaveBeenCalled()
  })

  it('cancel replaces the matching order by id and issues no refetch', async () => {
    const store = await seededStore([makeOrder({ id: 1, status: 'queued' })])
    const updated = makeOrder({ id: 1, status: 'canceled' })
    cancelMock.mockResolvedValue(updated)

    await store.cancel(1, 3, 'no longer needed')

    expect(cancelMock).toHaveBeenCalledWith(1, {
      reason: 'no longer needed',
      expected_edit_version: 3,
    })
    expect(store.orders).toEqual([updated])
    expect(getProductionOrdersMock).not.toHaveBeenCalled()
  })

  it('recordCompletion replaces the matching order by id (incl. created_lots) and issues no refetch', async () => {
    const store = await seededStore([makeOrder({ id: 1, status: 'in_progress' })])
    const updated = makeOrder({
      id: 1,
      status: 'completed',
      quantity_completed: 10,
      created_lots: [{ id: 2, lot_number: 'LOT-2026-0099', disposition: 'rework' }],
    })
    recordCompletionMock.mockResolvedValue(updated)

    const result = await store.recordCompletion(1, {
      quantity: 10,
      completion_date: '2026-09-02',
    })

    expect(result).toBe(updated)
    expect(store.orders).toEqual([updated])
    expect(getProductionOrdersMock).not.toHaveBeenCalled()
  })

  it('reassignMachine replaces the matching order by id and issues no refetch', async () => {
    const store = await seededStore([makeOrder({ id: 1, machine_id: null })])
    const updated = makeOrder({ id: 1, machine_id: 5 })
    reassignMock.mockResolvedValue(updated)

    await store.reassignMachine(1, 5)

    expect(store.orders).toEqual([updated])
    expect(getProductionOrdersMock).not.toHaveBeenCalled()
  })

  it('split replaces the reduced original and appends the new parts, no refetch', async () => {
    const store = await seededStore([makeOrder({ id: 1, quantity: 10 })])
    const reduced = makeOrder({ id: 1, quantity: 4 })
    const part = makeOrder({ id: 99, quantity: 6, queue_sequence: 2 })
    splitMock.mockResolvedValue([reduced, part])

    await store.split(1, { quantities: [4, 6] })

    expect(store.orders).toEqual(
      expect.arrayContaining([reduced, part]),
    )
    expect(store.orders).toHaveLength(2)
    expect(getProductionOrdersMock).not.toHaveBeenCalled()
  })

  it('merge replaces the keeper and marks every other requested id canceled/zeroed, no refetch', async () => {
    const store = await seededStore([
      makeOrder({ id: 1, quantity: 5, status: 'queued', queue_sequence: 1 }),
      makeOrder({ id: 2, quantity: 3, status: 'queued', queue_sequence: 2 }),
      makeOrder({ id: 3, quantity: 100, status: 'queued', queue_sequence: 99 }),
    ])
    // The backend picks the keeper by lowest queue_sequence, which need not
    // be the first id in the request payload. Order #1 merges into #2 here
    // to make sure the store derives "absorbed" from the response, not from
    // payload order/position.
    const keeper = makeOrder({ id: 2, quantity: 8, status: 'queued', queue_sequence: 2 })
    mergeMock.mockResolvedValue(keeper)

    await store.merge({ production_order_ids: [1, 2], expected_edit_versions: { 1: 0, 2: 0 } })

    const byId = new Map(store.orders.map((o) => [o.id, o]))
    // Pinia's setup-store state is deeply reactive, so an object read back
    // out of `store.orders` is a reactive proxy wrapping what was assigned,
    // never the exact same object reference, so toEqual (content), not toBe
    // (identity), is the correct comparison here and below.
    expect(byId.get(2)).toEqual(keeper)
    expect(byId.get(1)).toMatchObject({ status: 'canceled', quantity: 0 })
    // Order #3 was never part of the merge request: it stays untouched.
    expect(byId.get(3)).toMatchObject({ status: 'queued', quantity: 100 })
    expect(getProductionOrdersMock).not.toHaveBeenCalled()
  })

  it('reorder updates only the ids in the response, leaving an anchor order untouched, no refetch', async () => {
    const pinnedAnchor = makeOrder({ id: 9, machine_id: 1, pinned: true, queue_sequence: 50 })
    const store = await seededStore([
      makeOrder({ id: 1, machine_id: 1, queue_sequence: 1 }),
      makeOrder({ id: 2, machine_id: 1, queue_sequence: 2 }),
      pinnedAnchor,
    ])
    const reordered = [
      makeOrder({ id: 2, machine_id: 1, queue_sequence: 1 }),
      makeOrder({ id: 1, machine_id: 1, queue_sequence: 2 }),
    ]
    reorderMock.mockResolvedValue(reordered)

    await store.reorder(1, [2, 1])

    const byId = new Map(store.orders.map((o) => [o.id, o]))
    expect(byId.get(1)).toEqual(reordered[1])
    expect(byId.get(2)).toEqual(reordered[0])
    // The pinned anchor was left out of the request/response on purpose
    // (the backend rejects pinned ids in the payload); its cached copy is
    // still correct, so it must be untouched.
    expect(byId.get(9)).toEqual(pinnedAnchor)
    expect(getProductionOrdersMock).not.toHaveBeenCalled()
  })

  it('reorderPool behaves the same as reorder for a pool-scoped queue, no refetch', async () => {
    const store = await seededStore([
      makeOrder({ id: 1, machine_id: null, machine_pool_id: 7, queue_sequence: 1 }),
      makeOrder({ id: 2, machine_id: null, machine_pool_id: 7, queue_sequence: 2 }),
    ])
    const reordered = [
      makeOrder({ id: 2, machine_id: null, machine_pool_id: 7, queue_sequence: 1 }),
      makeOrder({ id: 1, machine_id: null, machine_pool_id: 7, queue_sequence: 2 }),
    ]
    reorderPoolMock.mockResolvedValue(reordered)

    await store.reorderPool(7, [2, 1])

    expect(store.orders).toEqual(expect.arrayContaining(reordered))
    expect(getProductionOrdersMock).not.toHaveBeenCalled()
  })

  it('recordAssessment patches only the assessment field of the matching order, no refetch', async () => {
    const store = await seededStore([makeOrder({ id: 1, assessment: null })])
    const assessment: ManufacturingAssessmentResponse = {
      id: 1,
      public_id: '44444444-4444-4444-4444-444444444444',
      production_order_id: 1,
      operator_id: 3,
      operator: null,
      actual_minutes_per_piece: 12.5,
      actual_setup_minutes: 5,
      complexity: 'normal',
      note: null,
      created: '2026-09-02T09:00:00',
    }
    recordAssessmentMock.mockResolvedValue(assessment)

    const result = await store.recordAssessment(1, {
      actual_minutes_per_piece: 12.5,
      complexity: 'normal',
    })

    expect(result).toBe(assessment)
    // Same reactive-proxy-wrapping caveat as the merge/reorder tests above:
    // toEqual, not toBe, for anything read back out of `store.orders`.
    expect(store.orders[0]?.assessment).toEqual(assessment)
    expect(store.orders[0]?.id).toBe(1)
    expect(getProductionOrdersMock).not.toHaveBeenCalled()
  })

  it('a malformed/empty response (no numeric id) is dropped defensively, leaving orders untouched', async () => {
    const original = makeOrder({ id: 1 })
    const store = await seededStore([original])
    // Mirrors this suite's own shared test-double default shape ({} / [])
    // for endpoints that really return a single object or a list.
    startMock.mockResolvedValue({} as ProductionOrderResponse)

    await store.start(1, {})

    expect(store.orders).toEqual([original])
  })

  it('replaces `orders` with a new array reference on every applied mutation (reference-watch safety)', async () => {
    const store = await seededStore([makeOrder({ id: 1, status: 'queued' })])
    const before = store.orders
    startMock.mockResolvedValue(makeOrder({ id: 1, status: 'in_progress' }))

    await store.start(1, {})

    // useProductionSchedule/ProductionQueueBoard both watch `() =>
    // store.orders` with a shallow (non-deep) getter watch, which only
    // fires on a reference change. An in-place `orders.value[i] = x`
    // would silently stop notifying them, so this must always be a new
    // array, never the same one mutated in place.
    expect(store.orders).not.toBe(before)
  })
})

describe('productionQueueStore.fetchOrders', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getProductionOrdersMock.mockReset()
  })

  it('pages through every open order instead of stopping at one page', async () => {
    const open = Array.from({ length: 501 }, (_, i) => makeOrder({ id: i + 1, status: 'queued' }))
    getProductionOrdersMock.mockImplementation(async (params) => {
      if (params?.statuses?.includes('completed')) return page()
      const skip = params?.skip ?? 0
      const items = open.slice(skip, skip + (params?.limit ?? 500))
      return { items, total: open.length, limit: params?.limit ?? null, skip }
    })
    const store = useProductionQueueStore()

    await store.fetchOrders()

    expect(store.orders).toHaveLength(501)
  })

  it('asks for finished orders only inside the board window', async () => {
    getProductionOrdersMock.mockResolvedValue(page())
    const store = useProductionQueueStore()

    await store.fetchOrders()

    const finishedCall = getProductionOrdersMock.mock.calls
      .map(([params]) => params)
      .find((params) => params?.statuses?.includes('completed'))
    expect(finishedCall?.statuses).toEqual(['completed', 'canceled'])
    const since = Date.now() - new Date(finishedCall!.changed_from!).getTime()
    expect(since).toBeGreaterThan(6.9 * 24 * 60 * 60 * 1000)
    expect(since).toBeLessThan(7.1 * 24 * 60 * 60 * 1000)
  })

  it('lists an order once when it finished between the open and the finished request', async () => {
    getProductionOrdersMock.mockImplementation(async (params) =>
      params?.statuses?.includes('completed')
        ? page([makeOrder({ id: 1, status: 'completed' })])
        : page([makeOrder({ id: 1, status: 'in_progress' }), makeOrder({ id: 2, status: 'queued' })]),
    )
    const store = useProductionQueueStore()

    await store.fetchOrders()

    expect(store.orders.map((o) => [o.id, o.status])).toEqual([
      [1, 'completed'],
      [2, 'queued'],
    ])
  })

  it('keeps the newer answer when an older fetch resolves last', async () => {
    let releaseOld: (value: PageResponse<ProductionOrderResponse>) => void = () => {}
    getProductionOrdersMock
      .mockImplementationOnce(() => new Promise((resolve) => (releaseOld = resolve)))
      .mockResolvedValue(page([makeOrder({ id: 2, status: 'queued' })]))
    const store = useProductionQueueStore()

    const older = store.fetchOrders()
    await store.fetchOrders()
    releaseOld(page([makeOrder({ id: 1, status: 'queued' })]))
    await older

    expect(store.orders.map((o) => o.id)).toEqual([2])
  })
})

describe('productionQueueStore one-click actions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    startMock.mockReset()
    cancelMock.mockReset()
  })

  it('sends a start only once while the first is still running', async () => {
    let finish: (value: ProductionOrderResponse) => void = () => {}
    startMock.mockImplementation(() => new Promise((resolve) => (finish = resolve)))
    const store = useProductionQueueStore()

    const first = store.start(1)
    const second = store.start(1)
    finish(makeOrder({ id: 1, status: 'in_progress' }))
    await Promise.all([first, second])

    expect(startMock).toHaveBeenCalledTimes(1)
  })

  it('sends a new start once the first has finished', async () => {
    startMock.mockResolvedValue(makeOrder({ id: 1, status: 'in_progress' }))
    const store = useProductionQueueStore()

    await store.start(1)
    await store.start(1)

    expect(startMock).toHaveBeenCalledTimes(2)
  })

  it('guards each order on its own', async () => {
    startMock.mockResolvedValue(makeOrder({ id: 1, status: 'in_progress' }))
    const store = useProductionQueueStore()

    await Promise.all([store.start(1), store.start(2)])

    expect(startMock).toHaveBeenCalledTimes(2)
  })

  it('sends a cancel only once on a double click', async () => {
    cancelMock.mockResolvedValue(makeOrder({ id: 1, status: 'canceled' }))
    const store = useProductionQueueStore()

    await Promise.all([store.cancel(1, 3), store.cancel(1, 3)])

    expect(cancelMock).toHaveBeenCalledTimes(1)
  })
})
