import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { nextTick } from 'vue'
import { flushPromises, RouterLinkStub, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import draggable from 'vuedraggable'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeProductionOrderResponse } from '@/test-utils/factories'

import type { ProductionMachineResponse } from '@/features/production-machines'
import type { MachinePoolResponse } from '@/features/production-machines'
import type { ProductionOrderResponse } from '../../../types/productionOrdersResponse'

const getMock = vi.fn<(url: string) => Promise<unknown>>()
const putMock = vi
  .fn<(url: string, payload: unknown) => Promise<unknown>>()
  .mockResolvedValue({ data: [] })
const postMock = vi
  .fn<(url: string, payload?: unknown) => Promise<unknown>>()
  .mockResolvedValue({ data: {} })

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    put: (url: string, payload: unknown) => putMock(url, payload),
    post: (url: string, payload?: unknown) => postMock(url, payload),
    patch: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import ProductionQueueBoard from '../ProductionQueueBoard.vue'
import ProductionOrderCard from '../ProductionOrderCard.vue'
import { useProductionQueueStore } from '../../../stores/productionQueueStore'

// The component exposes no internals. Its column routing and reorder payload
// building live in separately-tested pure modules
// (utils/queueColumnRouting.spec.ts, utils/queueReorderPayload.spec.ts), and
// every test below drives the real `<draggable>`/`<DatePicker>` child
// components' own props/events, exercising genuine behaviour rather than an
// internals reach-in.

function makeMachine(id: number): ProductionMachineResponse {
  return {
    id,
    public_id: `00000000-0000-0000-0000-${String(id).padStart(12, '0')}`,
    archived: false,
    created: '2026-07-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    internal_name: `Machine ${id}`,
    vendor: 'Acme',
    model: 'X1',
    fabrication_method_ids: [],
    fabrication_methods: [],
    max_part_dimension: null,
    is_qa_machine: false,
    note: null,
    creator_id: 1,
    creator_full_name: 'Tester',
    changes: [],
    active_orders: [],
    live_order_count: 0,
    open_downtime: null,
    status: 'down',
  }
}

function makePool(overrides: Partial<MachinePoolResponse> & { id: number }): MachinePoolResponse {
  return {
    public_id: `10000000-0000-0000-0000-${String(overrides.id).padStart(12, '0')}`,
    archived: false,
    created: '2026-07-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    name: `Pool ${overrides.id}`,
    machine_ids: [],
    machines: [],
    note: null,
    creator_id: 1,
    creator_full_name: 'Tester',
    changes: [],
    ...overrides,
  }
}

function makeOrder(
  overrides: Partial<ProductionOrderResponse> & { id: number },
): ProductionOrderResponse {
  return makeProductionOrderResponse({
    public_id: `33333333-3333-3333-3333-${String(overrides.id).padStart(12, '0')}`,
    production_order_number: `PO-${overrides.id}`,
    queue_sequence: overrides.id,
    ...overrides,
  })
}

interface DraggableChangeEvent {
  added?: { element: ProductionOrderResponse; newIndex: number }
  removed?: { element: ProductionOrderResponse; oldIndex: number }
  moved?: { element: ProductionOrderResponse; newIndex: number; oldIndex: number }
}

/**
 * The `.board-column` whose rendered text contains the given header. Each
 * column's title/subtitle is unique per fixture in every test below.
 */
function findColumn(wrapper: VueWrapper, headerText: string) {
  const column = wrapper.findAll('.board-column').find((c) => c.text().includes(headerText))
  if (!column) throw new Error(`No .board-column found containing "${headerText}"`)
  return column
}

/**
 * Simulates a completed vuedraggable drag on a column's (single, day-0 by
 * default) draggable list by driving the real child component's own events,
 * in the same order the real library fires them: `alterList` emits
 * `update:modelValue` with the already-spliced array synchronously, then
 * `emitChanges` emits `change` with the moved/added/removed descriptor (see
 * vuedraggable's own source). This is not a script-internal reach-in; it is
 * exactly what SortableJS driving the real component would produce.
 */
async function simulateDrop(
  wrapper: VueWrapper,
  headerText: string,
  newList: ProductionOrderResponse[],
  change: DraggableChangeEvent,
): Promise<void> {
  const column = findColumn(wrapper, headerText)
  const dragList = column.findComponent(draggable)
  expect(dragList.exists()).toBe(true)
  dragList.vm.$emit('update:modelValue', newList)
  await nextTick()
  dragList.vm.$emit('change', change)
  await flushPromises()
}

function mountBoard() {
  return mountWithApp(ProductionQueueBoard, {
    attachTo: document.body,
    global: {
      // A real machine column's title is a RouterLink to its machine
      // detail page. A plain `true` auto-stub renders no default-slot
      // content, which silently drops the machine's internal_name text
      // that every findColumn() lookup below searches for. RouterLinkStub
      // (unlike `true`) does render its default slot.
      // The help button and the dialogs' handbook drawers read the route,
      // and this mount has no router.
      stubs: { RouterLink: RouterLinkStub, HelpButton: true, HelpDrawer: true },
    },
  })
}

// Reset to `[]` (no pools) in beforeEach; individual tests that need a pool
// column reassign it before calling mountBoard().
let poolsFixture: MachinePoolResponse[] = []

function poolsResponse() {
  return Promise.resolve({
    data: { items: poolsFixture, total: poolsFixture.length, limit: 500, skip: 0 },
  })
}

// A Sunday, the one day whose default range is that day alone, so the drag
// tests see one day group per column and every order in it.
const SUNDAY = new Date(2026, 10, 15, 10, 0, 0)
const TUESDAY = new Date(2026, 10, 10, 10, 0, 0)

describe('ProductionQueueBoard', () => {
  afterEach(() => {
    vi.useRealTimers()
    localStorage.clear()
  })

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(SUNDAY)
    setActivePinia(createPinia())
    getMock.mockReset()
    putMock.mockClear()
    postMock.mockClear()
    poolsFixture = []

    getMock.mockImplementation((url: string) => {
      if (url === '/production-machines/') {
        return Promise.resolve({
          data: { items: [makeMachine(1)], total: 1, limit: 1000, skip: 0 },
        })
      }
      if (url === '/production-machine-pools/') {
        return poolsResponse()
      }
      if (url === '/production-orders/') {
        return Promise.resolve({
          data: {
            items: [
              makeOrder({ id: 1, queue_sequence: 1 }),
              makeOrder({ id: 2, queue_sequence: 2 }),
              makeOrder({ id: 3, queue_sequence: 3, pinned: true }),
            ],
            total: 3,
            limit: 1000,
            skip: 0,
          },
        })
      }
      if (url === '/production-operators/') {
        return Promise.resolve({ data: [] })
      }
      if (url.startsWith('/production-lots/')) {
        // useProductionSchedule fetches full lot detail for every lot
        // referenced by an active order; empty positions means no lot
        // dependency chain, orders still get a schedule from queue order alone.
        return Promise.resolve({ data: { id: 1, positions: [], steps: [] } })
      }
      if (url.match(/^\/made-items\/\d+\/files$/)) {
        // ProductionOrderCard renders a MadeItemThumbnailCell per order.
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: {} })
    })
  })

  it('renders without errors when loaded', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountBoard()

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    wrapper.unmount()
  })

  it('routes a machine-less inspection order to its own column, not manual or unassigned', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-machines/') {
        return Promise.resolve({
          data: { items: [makeMachine(1)], total: 1, limit: 1000, skip: 0 },
        })
      }
      if (url === '/production-machine-pools/') {
        return poolsResponse()
      }
      if (url === '/production-orders/') {
        return Promise.resolve({
          data: {
            items: [
              // A born-internal QA order: no machine, its
              // position's one step is role='inspection'.
              makeOrder({
                id: 1,
                machine_id: null,
                lot_id: 1,
                lot_position_id: 10,
              }),
              // A genuinely manual (non-inspection) machine-less order,
              // must still land in "manual", not "inspection".
              makeOrder({
                id: 2,
                machine_id: null,
                lot_id: 2,
                lot_position_id: 20,
                queue_sequence: 2,
              }),
            ],
            total: 2,
            limit: 1000,
            skip: 0,
          },
        })
      }
      if (url === '/production-lots/1') {
        return Promise.resolve({
          data: {
            id: 1,
            positions: [
              {
                id: 10,
                kind: 'internal',
                steps: [{ role: 'inspection', fabrication_method_requires_machine: false }],
              },
            ],
            steps: [],
          },
        })
      }
      if (url === '/production-lots/2') {
        return Promise.resolve({
          data: {
            id: 2,
            positions: [
              {
                id: 20,
                kind: 'internal',
                steps: [{ role: 'fabrication', fabrication_method_requires_machine: false }],
              },
            ],
            steps: [],
          },
        })
      }
      if (url === '/production-operators/') {
        return Promise.resolve({ data: [] })
      }
      if (url.match(/^\/made-items\/\d+\/files$/)) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: {} })
    })

    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    const columns = wrapper.findAll('.board-column')
    // Neither fixture order is truly unassigned (one's inspection, the
    // other's manual), so the "no machine assigned" column is absent:
    // manual, inspection, then the one machine.
    const manualColumn = columns[0]!
    const inspectionColumn = columns[1]!
    expect(inspectionColumn.text()).toContain('Inspection')
    expect(inspectionColumn.find('.column-count').text()).toBe('1')
    expect(manualColumn.find('.column-count').text()).toBe('1')

    wrapper.unmount()
  })

  it('blocks the move guard for pinned or in-progress orders', async () => {
    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    const inProgress = makeOrder({ id: 10, status: 'in_progress' })
    const pinned = makeOrder({ id: 11, pinned: true })
    const movable = makeOrder({ id: 12 })

    // `:move="checkMove"` on the real, rendered <draggable>: the actual
    // function SortableJS would call, not a script-internal export.
    const dragList = findColumn(wrapper, 'Machine 1').findComponent(draggable)
    const checkMove = dragList.props('move') as (evt: {
      draggedContext: { element: ProductionOrderResponse; index: number }
      relatedContext: { element?: ProductionOrderResponse; index: number }
    }) => boolean
    expect(checkMove).toBeTypeOf('function')

    // Dragging a locked (in-progress) card is always rejected.
    expect(
      checkMove({
        draggedContext: { element: inProgress, index: 0 },
        relatedContext: { element: movable, index: 1 },
      }),
    ).toBe(false)

    // Dragging a movable card onto a pinned card is rejected.
    expect(
      checkMove({
        draggedContext: { element: movable, index: 0 },
        relatedContext: { element: pinned, index: 1 },
      }),
    ).toBe(false)

    // Dragging a movable card onto another movable card is allowed.
    expect(
      checkMove({
        draggedContext: { element: movable, index: 0 },
        relatedContext: { element: makeOrder({ id: 13 }), index: 1 },
      }),
    ).toBe(true)

    wrapper.unmount()
  })

  it('calls the reorder API with only the non-locked ids on drop', async () => {
    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    // Simulate a completed drag: order 2 moved before order 1, pinned order 3
    // stays present in the column but must be excluded from the payload.
    await simulateDrop(
      wrapper,
      'Machine 1',
      [
        makeOrder({ id: 2, machine_id: 1, queue_sequence: 2 }),
        makeOrder({ id: 1, machine_id: 1, queue_sequence: 1 }),
        makeOrder({ id: 3, machine_id: 1, queue_sequence: 3, pinned: true }),
      ],
      { moved: { element: makeOrder({ id: 2, machine_id: 1 }), oldIndex: 1, newIndex: 0 } },
    )

    expect(putMock).toHaveBeenCalledWith('/production-orders/machines/1/queue', {
      ordered_production_order_ids: [2, 1],
    })

    wrapper.unmount()
  })

  it('reorders the unassigned pool against the "unassigned" queue endpoint', async () => {
    // The unassigned column only renders once a genuinely unassigned order
    // exists; two of them here, so there's something to reorder.
    getMock.mockImplementation((url: string) => {
      if (url === '/production-machines/') {
        return Promise.resolve({
          data: { items: [makeMachine(1)], total: 1, limit: 1000, skip: 0 },
        })
      }
      if (url === '/production-machine-pools/') return poolsResponse()
      if (url === '/production-orders/') {
        return Promise.resolve({
          data: {
            items: [
              makeOrder({ id: 20, machine_id: null, lot_id: 1, lot_position_id: 10, queue_sequence: 1 }),
              makeOrder({ id: 21, machine_id: null, lot_id: 1, lot_position_id: 10, queue_sequence: 2 }),
            ],
            total: 2,
            limit: 1000,
            skip: 0,
          },
        })
      }
      if (url === '/production-lots/1') {
        return Promise.resolve({
          data: {
            id: 1,
            positions: [
              {
                id: 10,
                kind: 'internal',
                steps: [{ role: 'fabrication', fabrication_method_requires_machine: true }],
              },
            ],
            steps: [],
          },
        })
      }
      if (url === '/production-operators/') return Promise.resolve({ data: [] })
      if (url.match(/^\/made-items\/\d+\/files$/)) return Promise.resolve({ data: [] })
      return Promise.resolve({ data: {} })
    })

    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    await simulateDrop(
      wrapper,
      'No Machine Assigned',
      [
        makeOrder({ id: 21, machine_id: null, queue_sequence: 2 }),
        makeOrder({ id: 20, machine_id: null, queue_sequence: 1 }),
      ],
      { moved: { element: makeOrder({ id: 21, machine_id: null }), oldIndex: 1, newIndex: 0 } },
    )

    expect(putMock).toHaveBeenCalledWith('/production-orders/machines/unassigned/queue', {
      ordered_production_order_ids: [21, 20],
    })

    wrapper.unmount()
  })

  it('reassigns then reorders on a cross-column drop', async () => {
    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    const dropped = makeOrder({ id: 2, machine_id: 1, queue_sequence: 2 })
    // The dragged card already landed in machine 1's local column before the
    // change handler fires (vuedraggable mutates v-model synchronously).
    await simulateDrop(
      wrapper,
      'Machine 1',
      [makeOrder({ id: 1, machine_id: 1, queue_sequence: 1 }), dropped],
      { added: { element: dropped, newIndex: 1 } },
    )

    expect(putMock).toHaveBeenCalledWith('/production-orders/2/machine', { machine_id: 1 })
    expect(putMock).toHaveBeenCalledWith('/production-orders/machines/1/queue', {
      ordered_production_order_ids: [1, 2],
    })

    wrapper.unmount()
  })

  it('does nothing on a plain "removed" change (handled by the target column)', async () => {
    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    putMock.mockClear()
    await simulateDrop(wrapper, 'Machine 1', [makeOrder({ id: 1, machine_id: 1 })], {
      removed: { element: makeOrder({ id: 1 }), oldIndex: 0 },
    })

    expect(putMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('keeps the first-load skeleton until the lots of the orders are loaded', async () => {
    const defaultGet = getMock.getMockImplementation()!
    let releaseLot!: () => void
    const lotGate = new Promise<void>((resolve) => {
      releaseLot = resolve
    })
    getMock.mockImplementation(async (url: string) => {
      if (url.startsWith('/production-lots/')) await lotGate
      return defaultGet(url)
    })

    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    // The orders are in, but a card without its lot would sit in the wrong place.
    expect(wrapper.find('.board-loading').exists()).toBe(true)
    expect(wrapper.find('.board-columns').exists()).toBe(false)

    releaseLot()
    await flushPromises()
    await flushPromises()

    expect(wrapper.find('.board-loading').exists()).toBe(false)
    expect(wrapper.find('.board-columns').exists()).toBe(true)

    wrapper.unmount()
  })

  it('keeps the board mounted through a background live refresh', async () => {
    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    const columnsBefore = wrapper.findAll('.board-column').length
    expect(columnsBefore).toBeGreaterThan(0)

    const store = useProductionQueueStore()
    const inFlight = store.refreshLive({ orders: true })
    await nextTick()

    // The whole point: a live re-sync must not trip the first-load skeleton,
    // which would unmount every column and blank the board mid-shift.
    expect(store.loading).toBe(false)
    expect(wrapper.find('.board-loading').exists()).toBe(false)
    expect(wrapper.findAll('.board-column').length).toBe(columnsBefore)

    await inFlight
    await flushPromises()
    expect(wrapper.findAll('.board-column').length).toBe(columnsBefore)

    wrapper.unmount()
  })

  it('renders one draggable day group per day in the selected range', async () => {
    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    // The default fixture's orders are all already machine-resolved, so the
    // "no machine assigned" column stays hidden: the machine
    // column is the third one (manual, inspection, then machines).
    let machineColumn = findColumn(wrapper, 'Machine 1')
    expect(machineColumn.findAll('.column-list-draggable')).toHaveLength(1)

    const from = new Date()
    from.setHours(0, 0, 0, 0)
    const to = new Date(from)
    to.setDate(to.getDate() + 2)

    // Drives the real toolbar DatePicker's own v-model, same as a person
    // picking a range would.
    const picker = wrapper.findComponent({ name: 'DatePicker' })
    expect(picker.exists()).toBe(true)
    picker.vm.$emit('update:modelValue', [from, to])
    await flushPromises()

    machineColumn = findColumn(wrapper, 'Machine 1')
    expect(machineColumn.findAll('.column-list-draggable')).toHaveLength(3)

    wrapper.unmount()
  })

  it('sends the visible queue day by day, in the order the board renders the days', async () => {
    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    const from = new Date()
    from.setHours(0, 0, 0, 0)
    const to = new Date(from)
    to.setDate(to.getDate() + 1)
    const picker = wrapper.findComponent({ name: 'DatePicker' })
    picker.vm.$emit('update:modelValue', [from, to])
    await flushPromises()

    // Two day groups now render for machine 1's column; day 0's own drop
    // fires the mutation, but queueReorderIdsForColumn sweeps every visible
    // day regardless of which one triggered it (see the component's own
    // comment on onGroupChange). Order 3 (pinned) is excluded even though
    // it's still part of the machine's queue on the server (covered in
    // isolation, with the exclusion itself, by
    // utils/queueReorderPayload.spec.ts).
    const machineColumn = findColumn(wrapper, 'Machine 1')
    const dayLists = machineColumn.findAllComponents(draggable)
    expect(dayLists).toHaveLength(2)

    dayLists[0]!.vm.$emit('update:modelValue', [makeOrder({ id: 1, machine_id: 1, queue_sequence: 1 })])
    await nextTick()
    dayLists[1]!.vm.$emit('update:modelValue', [makeOrder({ id: 2, machine_id: 1, queue_sequence: 2 })])
    await nextTick()
    dayLists[1]!.vm.$emit('change', {
      moved: { element: makeOrder({ id: 2, machine_id: 1 }), oldIndex: 0, newIndex: 0 },
    })
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith('/production-orders/machines/1/queue', {
      ordered_production_order_ids: [1, 2],
    })

    wrapper.unmount()
  })

  it('omits the legacy "no machine assigned" column when every order is resolved, manual, or inspection', async () => {
    // Default fixture (see beforeEach): all three orders already carry
    // machine_id: 1, so none of them ever route to 'unassigned'.
    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    expect(wrapper.findAll('.board-column').some((c) => c.text().includes('No Machine Assigned'))).toBe(
      false,
    )

    wrapper.unmount()
  })

  it('renders the legacy "no machine assigned" column once a truly machine-less order exists', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-machines/') {
        return Promise.resolve({
          data: { items: [makeMachine(1)], total: 1, limit: 1000, skip: 0 },
        })
      }
      if (url === '/production-machine-pools/') {
        return poolsResponse()
      }
      if (url === '/production-orders/') {
        return Promise.resolve({
          data: {
            items: [
              makeOrder({
                id: 1,
                machine_id: null,
                machine_pool_id: null,
                lot_id: 1,
                lot_position_id: 10,
              }),
            ],
            total: 1,
            limit: 1000,
            skip: 0,
          },
        })
      }
      if (url === '/production-lots/1') {
        return Promise.resolve({
          data: {
            id: 1,
            positions: [
              {
                id: 10,
                kind: 'internal',
                steps: [{ role: 'fabrication', fabrication_method_requires_machine: true }],
              },
            ],
            steps: [],
          },
        })
      }
      if (url === '/production-operators/') {
        return Promise.resolve({ data: [] })
      }
      if (url.match(/^\/made-items\/\d+\/files$/)) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: {} })
    })

    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    expect(wrapper.findAll('.board-column')[0]!.text()).toContain('No Machine Assigned')

    wrapper.unmount()
  })

  it('assigns a machine pool (not a machine) on a cross-column drop into a pool column', async () => {
    poolsFixture = [makePool({ id: 7, name: 'Pool 7' })]
    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    const dropped = makeOrder({ id: 2, machine_id: null, machine_pool_id: 7, queue_sequence: 2 })
    await simulateDrop(wrapper, 'Pool 7', [dropped], { added: { element: dropped, newIndex: 0 } })

    // A pool target sends machine_pool_id, never machine_id; the
    // backend resolves it to a concrete machine later.
    expect(putMock).toHaveBeenCalledWith('/production-orders/2/machine', { machine_pool_id: 7 })
    expect(putMock).toHaveBeenCalledWith('/production-orders/machines/pools/7/queue', {
      ordered_production_order_ids: [2],
    })

    wrapper.unmount()
  })

  it('reorders within a pool column against the pool-scoped queue endpoint', async () => {
    poolsFixture = [makePool({ id: 7, name: 'Pool 7' })]
    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    await simulateDrop(
      wrapper,
      'Pool 7',
      [
        makeOrder({ id: 31, machine_id: null, machine_pool_id: 7, queue_sequence: 2 }),
        makeOrder({ id: 30, machine_id: null, machine_pool_id: 7, queue_sequence: 1 }),
      ],
      {
        moved: {
          element: makeOrder({ id: 31, machine_id: null, machine_pool_id: 7 }),
          oldIndex: 1,
          newIndex: 0,
        },
      },
    )

    expect(putMock).toHaveBeenCalledWith('/production-orders/machines/pools/7/queue', {
      ordered_production_order_ids: [31, 30],
    })
    // Never the plain machine-reorder endpoint (pool id 7 vs. a
    // same-numbered machine id would silently collide otherwise).
    expect(putMock).not.toHaveBeenCalledWith('/production-orders/machines/7/queue', expect.anything())

    wrapper.unmount()
  })

  // The template's four ProductionOrderCard blocks share one
  // cardBindings(order, kind, isDraggable) factory. This pins down that the
  // per-column values it derives (draggable, hideNoMachineConflict) land on
  // the right cards, a manual/
  // inspection column's read-only card vs. a normal machine column's
  // draggable one.
  it('wires draggable and hideNoMachineConflict per column kind through cardBindings', async () => {
    getMock.mockImplementation((url: string) => {
      if (url === '/production-machines/') {
        return Promise.resolve({
          data: { items: [makeMachine(1)], total: 1, limit: 1000, skip: 0 },
        })
      }
      if (url === '/production-machine-pools/') {
        return poolsResponse()
      }
      if (url === '/production-orders/') {
        return Promise.resolve({
          data: {
            items: [
              // Resolved to a real machine: a normal, draggable column.
              makeOrder({ id: 1, machine_id: 1, lot_id: 1, lot_position_id: 10, queue_sequence: 1 }),
              // No machine, no pool, an inspection step: the static,
              // never-draggable inspection column.
              makeOrder({
                id: 2,
                machine_id: null,
                lot_id: 2,
                lot_position_id: 20,
                queue_sequence: 2,
              }),
            ],
            total: 2,
            limit: 1000,
            skip: 0,
          },
        })
      }
      if (url === '/production-lots/1') {
        return Promise.resolve({
          data: {
            id: 1,
            positions: [
              {
                id: 10,
                kind: 'internal',
                steps: [{ role: 'fabrication', fabrication_method_requires_machine: true }],
              },
            ],
            steps: [],
          },
        })
      }
      if (url === '/production-lots/2') {
        return Promise.resolve({
          data: {
            id: 2,
            positions: [
              {
                id: 20,
                kind: 'internal',
                steps: [{ role: 'inspection', fabrication_method_requires_machine: false }],
              },
            ],
            steps: [],
          },
        })
      }
      if (url === '/production-operators/') {
        return Promise.resolve({ data: [] })
      }
      if (url.match(/^\/made-items\/\d+\/files$/)) {
        return Promise.resolve({ data: [] })
      }
      return Promise.resolve({ data: {} })
    })

    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    const cards = wrapper.findAllComponents(ProductionOrderCard)
    const machineCard = cards.find((c) => c.props('order').id === 1)
    const inspectionCard = cards.find((c) => c.props('order').id === 2)

    expect(machineCard).toBeDefined()
    expect(machineCard!.props('draggable')).toBe(true)
    expect(machineCard!.props('hideNoMachineConflict')).toBe(false)

    expect(inspectionCard).toBeDefined()
    expect(inspectionCard!.props('draggable')).toBe(false)
    expect(inspectionCard!.props('hideNoMachineConflict')).toBe(true)

    wrapper.unmount()
  })

  it('shows the rest of the week by default, today through Sunday', async () => {
    vi.setSystemTime(TUESDAY)
    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    const picker = wrapper.findComponent({ name: 'DatePicker' })
    const [from, to] = picker.props('modelValue') as [Date, Date]
    expect(from.getDay()).toBe(2)
    expect(to.getDay()).toBe(0)
    expect(findColumn(wrapper, 'Machine 1').findAll('.column-list-draggable')).toHaveLength(6)

    wrapper.unmount()
  })

  it('hides the orders that cannot start while Hide Not-Ready is on, and remembers it', async () => {
    // Over a whole week both orders land on the board, whichever day the
    // schedule projects them onto.
    vi.setSystemTime(TUESDAY)
    getMock.mockImplementation((url: string) => {
      if (url === '/production-machines/') {
        return Promise.resolve({ data: { items: [makeMachine(1)], total: 1, limit: 1000, skip: 0 } })
      }
      if (url === '/production-orders/') {
        return Promise.resolve({
          data: {
            items: [
              makeOrder({ id: 1, queue_sequence: 1 }),
              makeOrder({ id: 2, queue_sequence: 2, can_start: false }),
            ],
            total: 2,
            limit: 1000,
            skip: 0,
          },
        })
      }
      if (url === '/production-operators/') return Promise.resolve({ data: [] })
      if (url.startsWith('/production-lots/')) {
        return Promise.resolve({ data: { id: 1, positions: [], steps: [] } })
      }
      if (url === '/production-machine-pools/') return poolsResponse()
      return Promise.resolve({ data: [] })
    })
    const wrapper = mountBoard()
    await flushPromises()
    await flushPromises()

    const visibleIds = (): number[] => {
      const cards: VueWrapper[] = findColumn(wrapper, 'Machine 1').findAllComponents(
        ProductionOrderCard,
      )
      return cards
        .filter((card) => card.isVisible())
        .map((card) => (card.props() as { order: ProductionOrderResponse }).order.id)
    }
    expect(visibleIds()).toEqual([1, 2])

    await wrapper.find('[data-testid="queue-hide-not-ready"]').trigger('click')
    expect(visibleIds()).toEqual([1])
    // The hidden card stays in its group, so a reorder keeps its place.
    expect(findColumn(wrapper, 'Machine 1').findAllComponents(ProductionOrderCard)).toHaveLength(2)
    wrapper.unmount()

    const remounted = mountBoard()
    await flushPromises()
    expect(
      remounted.find('[data-testid="queue-hide-not-ready"]').classes(),
    ).not.toContain('p-button-text')
    remounted.unmount()
  })
})
