import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const getMock = vi.fn<(url: string) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
  },
}))

import { useProductionLotsSelectionStore } from '../productionLotsSelectionStore'

import type { LotPositionResponse, LotResponse } from '../../../types/productionLotsResponse'
import { positionActions } from '../../__tests__/fixtures'
import { makeLotResponse } from '@/test-utils/factories'

function makePosition(overrides: Partial<LotPositionResponse> = {}): LotPositionResponse {
  const position: LotPositionResponse = {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    created: '2026-07-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    sequence: 1,
    kind: 'unassigned',
    status: 'pending',
    quantity: 5,
    quantity_completed: 0,
    quantity_remaining: 5,
    note: null,
    creator_id: 1,
    lot_id: 1,
    steps: [],
    order_item_id: null,
    order_id: null,
    order_number: '',
    supplier_name: '',
    order_item_status: '',
    order_item_closed_short: false,
    earlier_order_lines: [],
    expected_delivery_date: null,
    production_orders: [],
    actions: [],
    planned_delivery_date: null,
    planned_pickup_date: null,
    ...overrides,
  }
  return { ...position, actions: overrides.actions ?? positionActions(position) }
}

function makeLot(lotId: number, positions: LotPositionResponse[]): LotResponse {
  return makeLotResponse({
    id: lotId,
    public_id: `00000000-0000-0000-0000-00000000000${lotId}`,
    lot_number: `LOT-${lotId}`,
    quantity_completed: 0,
    status: 'draft',
    made_item_part_number: `PN-${lotId}`,
    project_id: lotId * 100,
    positions,
  })
}

describe('productionLotsSelectionStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getMock.mockReset()
  })

  it('adds a step after resolving the full lot', async () => {
    getMock.mockResolvedValue({ data: makeLot(1, [makePosition({ id: 1 })]) })
    const store = useProductionLotsSelectionStore()

    const result = await store.toggleStep(1, 1, 'orders')

    expect(result).toBe('added')
    expect(store.items).toHaveLength(1)
    expect(store.items[0]).toMatchObject({ lotId: 1, lotNumber: 'LOT-1', projectId: 100 })
  })

  it('resolves to unavailable instead of throwing when the lot fetch fails', async () => {
    getMock.mockRejectedValueOnce(new Error('network error'))
    const store = useProductionLotsSelectionStore()

    const result = await store.toggleStep(1, 1, 'orders')

    expect(result).toBe('unavailable')
    expect(store.items).toHaveLength(0)
    expect(store.resolvingKeys.size).toBe(0)
  })

  it('removes a step on a second click (toggle off)', async () => {
    getMock.mockResolvedValue({ data: makeLot(1, [makePosition({ id: 1 })]) })
    const store = useProductionLotsSelectionStore()
    await store.toggleStep(1, 1, 'orders')

    const result = await store.toggleStep(1, 1, 'orders')

    expect(result).toBe('removed')
    expect(store.items).toHaveLength(0)
  })

  it('accumulates steps clicked across different lots', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-lots/1')
        return Promise.resolve({ data: makeLot(1, [makePosition({ id: 1 })]) })
      return Promise.resolve({ data: makeLot(2, [makePosition({ id: 2, lot_id: 2 })]) })
    })
    const store = useProductionLotsSelectionStore()

    await store.toggleStep(1, 1, 'orders')
    await store.toggleStep(2, 2, 'orders')

    expect(store.items).toHaveLength(2)
    expect(store.items.map((i) => i.lotId)).toEqual([1, 2])
  })

  it('only fetches a given lot once (per-lot cache)', async () => {
    getMock.mockResolvedValue({
      data: makeLot(1, [makePosition({ id: 1 }), makePosition({ id: 2, sequence: 2 })]),
    })
    const store = useProductionLotsSelectionStore()

    await store.toggleStep(1, 1, 'orders')
    await store.toggleStep(1, 2, 'orders')

    expect(getMock).toHaveBeenCalledTimes(1)
    expect(store.items).toHaveLength(2)
  })

  it('returns unavailable and does not add a fully-routed position (machines mode)', async () => {
    getMock.mockResolvedValue({
      data: makeLot(1, [
        makePosition({
          id: 1,
          kind: 'internal',
          quantity_remaining: 0,
          production_orders: [
            {
              id: 10,
              production_order_number: 'PO-10',
              edit_version: 0,
              status: 'queued',
              priority: 'normal',
              quantity: 5,
              quantity_completed: 0,
              machine_id: 3,
              machine_internal_name: 'Mill A',
              machine_pool_id: null,
              machine_pool_name: '',
              conflicts: [],
            },
          ],
        }),
      ]),
    })
    const store = useProductionLotsSelectionStore()

    const result = await store.toggleStep(1, 1, 'machines')

    expect(result).toBe('unavailable')
    expect(store.items).toHaveLength(0)
  })

  it('returns unavailable for orders mode once a live OrderItem already exists', async () => {
    getMock.mockResolvedValue({
      data: makeLot(1, [makePosition({ id: 1, kind: 'external', order_item_id: 99 })]),
    })
    const store = useProductionLotsSelectionStore()

    const result = await store.toggleStep(1, 1, 'orders')

    expect(result).toBe('unavailable')
    expect(store.items).toHaveLength(0)
  })

  // Regression: order_item_id is schema-optional as well as nullable. The
  // backend can omit the key entirely for a position with no live OrderItem,
  // rather than send an explicit null. isPositionActionable reads
  // `order_item_id == null` (not `=== null`) for exactly that reason; an
  // `=== null` check would leave `undefined` looking like "already has a
  // live OrderItem" and wrongly mark an eligible position unavailable.
  it('adds a position for orders mode when order_item_id is undefined (omitted key), same as null', async () => {
    getMock.mockResolvedValue({
      data: makeLot(1, [makePosition({ id: 1, kind: 'unassigned', order_item_id: undefined })]),
    })
    const store = useProductionLotsSelectionStore()

    const result = await store.toggleStep(1, 1, 'orders')

    expect(result).toBe('added')
    expect(store.items).toHaveLength(1)
  })

  it('respects a capability predicate, returning unavailable when it fails', async () => {
    getMock.mockResolvedValue({ data: makeLot(1, [makePosition({ id: 1 })]) })
    const store = useProductionLotsSelectionStore()

    const result = await store.toggleStep(1, 1, 'orders', () => false)

    expect(result).toBe('unavailable')
    expect(store.items).toHaveLength(0)
  })

  it('removeItem drops a specific item', async () => {
    getMock.mockResolvedValue({ data: makeLot(1, [makePosition({ id: 1 })]) })
    const store = useProductionLotsSelectionStore()
    await store.toggleStep(1, 1, 'orders')

    store.removeItem(1, 1)

    expect(store.items).toHaveLength(0)
  })

  it('clearItems empties the batch but keeps selectedOrder/selectedMachine', async () => {
    getMock.mockResolvedValue({ data: makeLot(1, [makePosition({ id: 1 })]) })
    const store = useProductionLotsSelectionStore()
    await store.toggleStep(1, 1, 'orders')
    store.selectedMachine = {
      id: 1,
      public_id: '11111111-1111-1111-1111-111111111111',
      archived: false,
      created: '2026-07-01',
      changed: null,
      changed_by_id: null,
      changed_by_full_name: '',
      internal_name: 'Mill A',
      vendor: 'Acme',
      model: 'M1',
      fabrication_method_ids: [],
      fabrication_methods: [],
      max_part_dimension: null,
      is_qa_machine: false,
      note: null,
      creator_id: 1,
      creator_full_name: 'Tester',
      changes: [],
      open_downtime: null,
      status: 'idle',
      active_orders: [],
      live_order_count: 0,
    }

    store.clearItems()

    expect(store.items).toHaveLength(0)
    expect(store.selectedMachine).not.toBeNull()
  })

  it('clearSelection resets everything including the lot cache', async () => {
    getMock.mockResolvedValue({ data: makeLot(1, [makePosition({ id: 1 })]) })
    const store = useProductionLotsSelectionStore()
    await store.toggleStep(1, 1, 'orders')

    store.clearSelection()

    expect(store.items).toHaveLength(0)
    expect(store.selectedOrder).toBeNull()
    expect(store.selectedMachine).toBeNull()

    // Cache was cleared -> selecting the same lot again refetches.
    getMock.mockClear()
    await store.toggleStep(1, 1, 'orders')
    expect(getMock).toHaveBeenCalledTimes(1)
  })
})
