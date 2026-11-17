import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { makeProductionOrderResponse, userWithPermissions } from '@/test-utils/factories'
import { useProductionQueueStore } from '../../../stores/productionQueueStore'

import type { ProductionOrderResponse } from '../../../types/productionOrdersResponse'
import type { ProductionMachineResponse, MachinePoolResponse } from '@/features/production-machines'
import type { MadeItemResponse } from '@/features/made-items'
import type { SourceItemResponse } from '@/features/source-items'

// MachineDetailContent's own composition (useProductionQueueStore's
// fetchMachines/fetchMachinePools/fetchOrders/fetchOperators, getLot,
// getMadeItems) all end up calling the same underlying axios instance,
// mocked at that one boundary rather than per api-module, same pattern as
// ProductionQueueBoard.spec.ts and LotDetailContent.spec.ts.
const getMock =
  vi.fn<(url: string, config?: { params?: Record<string, unknown> }) => Promise<{ data: unknown }>>()
// The Print split button's onPrint (mirrors ProductionOrderCard.vue's own)
// posts to /print, named so tests can assert on its payload/mock its reply.
const postMock = vi.fn<(url: string, body?: unknown) => Promise<{ data: unknown }>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string, config?: { params?: Record<string, unknown> }) => getMock(url, config),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    post: (url: string, body?: unknown) => postMock(url, body),
    patch: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    delete: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

// No live SSE stream in a unit test: useLiveRefresh's real implementation
// just registers a subscriber on the live store, which is harmless, but
// stubbing it out entirely keeps this spec from depending on that module at
// all (per the machine-view test-writing brief).
vi.mock('@/core/realtime/useLiveRefresh', () => ({
  useLiveRefresh: vi.fn<() => void>(),
}))

import MachineDetailContent from '../MachineDetailContent.vue'

// ── Fixtures ──────────────────────────────────────────────────────────

function makeMachine(overrides: Partial<ProductionMachineResponse> = {}): ProductionMachineResponse {
  return {
    id: 1,
    public_id: `00000000-0000-0000-0000-${String(overrides.id ?? 1).padStart(12, '0')}`,
    archived: false,
    created: '2026-07-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    internal_name: 'Machine 1',
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
    ...overrides,
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
    machine_id: null,
    machine_internal_name: '',
    lot_id: overrides.id,
    lot_number: `LOT-${overrides.id}`,
    ...overrides,
  })
}

// Loose on purpose (see LotDetailContent.spec.ts's own lot fixture); only
// the fields ProductionOrderCard/MachineDetailContent actually read.
function makeLot(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    id: 1,
    positions: [],
    steps: [],
    source_label: '',
    source_sublabel: '',
    source_item_id: null,
    project_id: 1,
    project_number: 'PRJ-1',
    ...overrides,
  }
}

function makeMadeItem(overrides: Partial<MadeItemResponse> = {}): MadeItemResponse {
  return {
    id: 900,
    public_id: 'bbbbbbbb-0000-0000-0000-000000000900',
    part_number: 'PN-900',
    status: 'active',
    created: '2026-02-01',
    changed: null,
    deleted: false,
    revision: 'A',
    revision_date: null,
    revision_note: null,
    article_name: 'Bracket 900',
    article_groups: [],
    data_source: 'WEB',
    material: '1.0037',
    mass: 1.25,
    base_size: '100x50',
    note: null,
    weblink: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    bought_item_id: null,
    bought_item: null,
    source_item_id: null,
    source_item: null,
    source_label: '',
    source_sublabel: '',
    processes: [],
    ...overrides,
  } as MadeItemResponse
}

// Loose on purpose, same reasoning as makeMadeItem above; only the fields
// SourceItemDetailFields/SourceItemDetailDialog actually read.
function makeSourceItem(overrides: Partial<SourceItemResponse> & { id: number }): SourceItemResponse {
  return {
    public_id: `cccccccc-0000-0000-0000-${String(overrides.id).padStart(12, '0')}`,
    status: 'active',
    created: '2026-01-01',
    changed: null,
    deleted: false,
    type_id: 1,
    type_name: 'Round Bar',
    dimension: 'Ø20',
    material: '1.4301',
    mass: 2.5,
    note: null,
    order_code_1: null,
    order_code_2: null,
    successor_item_id: null,
    creator_id: 1,
    creator: null,
    approver_id: null,
    manufacturer_id: null,
    manufacturer_name: '',
    ...overrides,
  } as SourceItemResponse
}

// ── Fixture-backed HTTP mock ─────────────────────────────────────────

let machinesFixture: ProductionMachineResponse[] = []
let poolsFixture: MachinePoolResponse[] = []
let ordersFixture: ProductionOrderResponse[] = []
let madeItemsFixture: MadeItemResponse[] = []
let sourceItemsFixture: SourceItemResponse[] = []
let lotsFixture = new Map<number, Record<string, unknown>>()
let failingLotIds = new Set<number>()

function setupApiMock(): void {
  getMock.mockReset()
  postMock.mockReset()
  postMock.mockResolvedValue({ data: [{ status: 'sent' }] })
  getMock.mockImplementation((url, config) => {
    if (url === '/production-machines/') {
      return Promise.resolve({
        data: { items: machinesFixture, total: machinesFixture.length, limit: 500, skip: 0 },
      })
    }
    if (url === '/production-machine-pools/') {
      return Promise.resolve({
        data: { items: poolsFixture, total: poolsFixture.length, limit: 500, skip: 0 },
      })
    }
    if (url === '/production-orders/') {
      return Promise.resolve({
        data: { items: ordersFixture, total: ordersFixture.length, limit: 500, skip: 0 },
      })
    }
    if (url === '/production-operators/') {
      return Promise.resolve({ data: [] })
    }
    if (url === '/made-items/') {
      const id = config?.params?.id as number | undefined
      const item = madeItemsFixture.find((i) => i.id === id) ?? null
      return Promise.resolve({
        data: { items: item ? [item] : [], total: item ? 1 : 0, limit: 1, skip: 0 },
      })
    }
    if (/^\/made-items\/\d+\/files$/.test(url)) {
      // ProductionOrderCard renders a MadeItemThumbnailCell per order.
      return Promise.resolve({ data: [] })
    }
    if (/^\/made-items\/\d+\/revisions$/.test(url)) {
      // MadeItemDetailDialog fetches its own revisions list the moment it
      // opens (both this page's new Open Item dialog and
      // MachineCurrentOrderCard's own "view item details" one); a bare
      // `{}` fallback leaves `revisionsResponse.items` undefined, which
      // crashes its header Select's `v-if`.
      return Promise.resolve({
        data: { items: [], next_revision: null, next_revision_error: null, can_create: false, reason: null },
      })
    }
    if (url === '/source-items') {
      const id = config?.params?.id as number | undefined
      const item = sourceItemsFixture.find((i) => i.id === id) ?? null
      return Promise.resolve({
        data: { items: item ? [item] : [], total: item ? 1 : 0, limit: 1, skip: 0 },
      })
    }
    const lotMatch = url.match(/^\/production-lots\/(\d+)$/)
    if (lotMatch) {
      const id = Number(lotMatch[1])
      if (failingLotIds.has(id)) return Promise.reject(new Error(`lot ${id} failed`))
      const lot = lotsFixture.get(id)
      return lot ? Promise.resolve({ data: lot }) : Promise.reject(new Error(`lot ${id} not found`))
    }
    return Promise.resolve({ data: {} })
  })
}

const mounted: VueWrapper[] = []

async function mountContent(
  machineId: number,
  permissions: string[] = [Permission.WRITE_PRODUCTION_ORDERS, Permission.MANAGE_PRODUCTION_ORDERS],
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)

  const wrapper = mountWithApp(MachineDetailContent, {
    pinia,
    attachTo: document.body,
    props: { machineId },
    global: {
      plugins: [ConfirmationService],
      stubs: { RouterLink: true },
    },
  })
  mounted.push(wrapper)

  // The mount chains several rounds of awaited work: store.fetchAll() (4
  // parallel fetches) flips `ready`, which lets the visibleOrders watcher's
  // own Promise.all(getLot) and the current-order watcher's getMadeItems
  // run; flushPromises (a macrotask boundary) drains the whole chain in
  // one call since nothing in it schedules a further macrotask, but this
  // mirrors the repeated-call idiom used by the other content-level specs
  // (LotDetailContent.spec.ts, ProductionQueueBoard.spec.ts) for safety.
  await flushPromises()
  await flushPromises()
  await flushPromises()

  return wrapper
}

function findCardByTitle(wrapper: VueWrapper, title: string) {
  const panel = wrapper.findAllComponents({ name: 'Panel' }).find((p) => p.props('header') === title)
  if (!panel) throw new Error(`No Panel found with header "${title}"`)
  return panel
}

describe('MachineDetailContent', () => {
  afterEach(() => {
    for (const wrapper of mounted) wrapper.unmount()
    mounted.length = 0
  })

  beforeEach(() => {
    machinesFixture = []
    poolsFixture = []
    ordersFixture = []
    madeItemsFixture = []
    sourceItemsFixture = []
    lotsFixture = new Map()
    failingLotIds = new Set()
    setupApiMock()
  })

  it("current card shows only this machine's in-progress/paused orders, queue card shows its queued orders in queue_sequence order, and other machines' orders never appear", async () => {
    machinesFixture = [makeMachine({ id: 1, internal_name: 'Machine 1' }), makeMachine({ id: 2, internal_name: 'Machine 2' })]
    ordersFixture = [
      makeOrder({ id: 10, machine_id: 1, status: 'in_progress', lot_id: 100, lot_number: 'LOT-10' }),
      makeOrder({ id: 11, machine_id: 1, status: 'paused', lot_id: 101, lot_number: 'LOT-11' }),
      makeOrder({ id: 12, machine_id: 1, status: 'queued', queue_sequence: 2, lot_id: 102, lot_number: 'LOT-12' }),
      makeOrder({ id: 13, machine_id: 1, status: 'queued', queue_sequence: 1, lot_id: 103, lot_number: 'LOT-13' }),
      makeOrder({ id: 20, machine_id: 2, status: 'queued', lot_id: 104, lot_number: 'LOT-20' }),
    ]
    lotsFixture.set(100, makeLot({ id: 100 }))
    lotsFixture.set(101, makeLot({ id: 101 }))
    lotsFixture.set(102, makeLot({ id: 102 }))
    lotsFixture.set(103, makeLot({ id: 103 }))

    const wrapper = await mountContent(1)

    // The primary current order (first in the list) gets the full hero
    // treatment including its lot link; the second concurrent order is a
    // compact row (order number + status + qty, no lot link); see
    // MachineCurrentOrderCard.vue.
    const currentCard = findCardByTitle(wrapper, 'Current Order')
    expect(currentCard.text()).toContain('LOT-10')
    expect(currentCard.text()).toContain('PO-11')
    expect(currentCard.text()).not.toContain('LOT-12')

    // The primary order's own lot (fetched into lotsById the same as every
    // other visible order's) is threaded down as the card's new `lot` prop
    // rather than re-fetched; proven here by the project link it feeds.
    // (RouterLink is stubbed with bare `true`, so the stub tag, not the
    // component name, is what's queryable here.)
    const projectLink = currentCard.find('router-link-stub')
    expect(projectLink.attributes('to')).toBe('/workspace/projects/1')

    const queueCard = findCardByTitle(wrapper, 'Queue')
    expect(queueCard.text()).toContain('LOT-12')
    expect(queueCard.text()).toContain('LOT-13')
    // queue_sequence order: 13 (seq 1) before 12 (seq 2).
    expect(queueCard.text().indexOf('LOT-13')).toBeLessThan(queueCard.text().indexOf('LOT-12'))
    expect(queueCard.text()).not.toContain('LOT-10')

    // Machine 2's own order never renders anywhere on machine 1's page.
    expect(wrapper.text()).not.toContain('LOT-20')
  })

  it('pool card shows only pools containing this machine and their machine-unresolved (pool) orders', async () => {
    machinesFixture = [makeMachine({ id: 1 })]
    poolsFixture = [
      makePool({ id: 5, name: 'Pool A', machine_ids: [1] }),
      makePool({ id: 6, name: 'Pool B', machine_ids: [2] }),
    ]
    ordersFixture = [
      makeOrder({ id: 30, machine_id: null, machine_pool_id: 5, status: 'queued', lot_id: 200, lot_number: 'LOT-30' }),
      makeOrder({ id: 31, machine_id: null, machine_pool_id: 6, status: 'queued', lot_id: 201, lot_number: 'LOT-31' }),
    ]
    lotsFixture.set(200, makeLot({ id: 200 }))

    const wrapper = await mountContent(1)

    expect(wrapper.text()).toContain('Pool A')
    expect(wrapper.text()).not.toContain('Pool B')

    const poolCard = findCardByTitle(wrapper, 'Pool A Pool Queue')
    expect(poolCard.text()).toContain('LOT-30')
    expect(wrapper.text()).not.toContain('LOT-31')
  })

  it('shows the no-pool empty state when the machine belongs to no pool', async () => {
    machinesFixture = [makeMachine({ id: 1 })]
    poolsFixture = [makePool({ id: 6, name: 'Pool B', machine_ids: [2] })]

    const wrapper = await mountContent(1)

    expect(wrapper.text()).toContain('This machine is not part of a machine pool.')
    expect(wrapper.text()).not.toContain('Pool B')
  })

  it('idle machine: current/item cards show their empty states, and controlTarget falls back to the head of this machine\'s own queue', async () => {
    machinesFixture = [makeMachine({ id: 1 })]
    ordersFixture = [
      makeOrder({ id: 40, machine_id: 1, status: 'queued', queue_sequence: 2, lot_id: 300, lot_number: 'LOT-40', made_item_id: 940 }),
      makeOrder({ id: 41, machine_id: 1, status: 'queued', queue_sequence: 1, lot_id: 301, lot_number: 'LOT-41', made_item_id: 941 }),
    ]
    lotsFixture.set(300, makeLot({ id: 300 }))
    lotsFixture.set(301, makeLot({ id: 301 }))

    const wrapper = await mountContent(1)

    // The combined current-order/item card has a single empty state, with
    // no separate "no item" copy.
    expect(wrapper.text()).toContain('No order running right now.')

    const vm = wrapper.vm as unknown as { controlTarget: ProductionOrderResponse | null }
    expect(vm.controlTarget?.id).toBe(41)
  })

  it("fetches and renders the current order's made item, and refetches when the current order changes", async () => {
    machinesFixture = [makeMachine({ id: 1 })]
    ordersFixture = [
      makeOrder({ id: 50, machine_id: 1, status: 'in_progress', lot_id: 400, lot_number: 'LOT-50', made_item_id: 950 }),
    ]
    lotsFixture.set(400, makeLot({ id: 400 }))
    madeItemsFixture = [makeMadeItem({ id: 950, article_name: 'Bracket 950' })]

    const wrapper = await mountContent(1)

    expect(getMock).toHaveBeenCalledWith(
      '/made-items/',
      expect.objectContaining({ params: expect.objectContaining({ id: 950, limit: 1 }) }),
    )
    expect(wrapper.findComponent({ name: 'MadeItemDetailFields' }).exists()).toBe(true)
    expect(wrapper.text()).toContain('Bracket 950')

    // Simulate the store re-syncing with a different current order (what a
    // live PRODUCTION_ORDERS refresh would produce); the item card must
    // switch to the new order's made item.
    madeItemsFixture = [
      makeMadeItem({ id: 950, article_name: 'Bracket 950' }),
      makeMadeItem({ id: 951, article_name: 'Widget 951' }),
    ]
    const store = useProductionQueueStore()
    store.orders = [
      makeOrder({ id: 51, machine_id: 1, status: 'in_progress', lot_id: 401, lot_number: 'LOT-51', made_item_id: 951 }),
    ]
    await flushPromises()
    await flushPromises()

    expect(getMock).toHaveBeenCalledWith(
      '/made-items/',
      expect.objectContaining({ params: expect.objectContaining({ id: 951, limit: 1 }) }),
    )
    expect(wrapper.text()).toContain('Widget 951')
    expect(wrapper.text()).not.toContain('Bracket 950')
  })

  it('shows the not-found state when the machine id does not exist', async () => {
    machinesFixture = [makeMachine({ id: 1 })]

    const wrapper = await mountContent(999)

    expect(wrapper.text()).toContain('This machine does not exist.')
  })

  it('fails soft when one lot fetch rejects: the other cards still render, with no unhandled rejection', async () => {
    const unhandled: unknown[] = []
    const onUnhandledRejection = (reason: unknown): void => {
      unhandled.push(reason)
    }
    process.on('unhandledRejection', onUnhandledRejection)

    try {
      machinesFixture = [makeMachine({ id: 1 })]
      ordersFixture = [
        makeOrder({ id: 60, machine_id: 1, status: 'in_progress', lot_id: 500, lot_number: 'LOT-60' }),
        makeOrder({ id: 61, machine_id: 1, status: 'queued', lot_id: 501, lot_number: 'LOT-61' }),
      ]
      lotsFixture.set(500, makeLot({ id: 500 }))
      failingLotIds.add(501)

      const wrapper = await mountContent(1)
      // Give the rejected getLot(501) promise (already caught internally,
      // but scheduled on its own microtask chain) a further tick to settle.
      await flushPromises()

      expect(wrapper.text()).toContain('LOT-60')
      // Order 61's own lot fetch failed, but the order itself (denormalized
      // fields only, lot: null) still renders; one bad lot must not sink
      // the whole page.
      expect(wrapper.text()).toContain('LOT-61')
    } finally {
      process.off('unhandledRejection', onUnhandledRejection)
    }

    expect(unhandled).toEqual([])
  })

  it('controlStartBlocked is true with the cannotStart tooltip when the control target cannot start yet', async () => {
    machinesFixture = [makeMachine({ id: 1 })]
    ordersFixture = [
      makeOrder({ id: 70, machine_id: 1, status: 'queued', lot_id: 600, lot_number: 'LOT-70', can_start: false, lot_position_id: 1 }),
    ]
    lotsFixture.set(600, makeLot({ id: 600, positions: [{ id: 1, steps: [] }] }))

    const wrapper = await mountContent(1, [Permission.WRITE_PRODUCTION_ORDERS])
    const vm = wrapper.vm as unknown as {
      controlStartBlocked: boolean
      controlStartBlockedTooltip: string | undefined
    }

    expect(vm.controlStartBlocked).toBe(true)
    expect(vm.controlStartBlockedTooltip).toBe(
      "This order can't be started yet, because its upstream step hasn't made anything available or its lot is on hold.",
    )
  })

  it('controlCanOperateInspection is false without write:inspections when the position has an inspection step, and blocks start', async () => {
    machinesFixture = [makeMachine({ id: 1 })]
    ordersFixture = [
      makeOrder({ id: 71, machine_id: 1, status: 'queued', lot_id: 601, lot_number: 'LOT-71', lot_position_id: 10, can_start: true }),
    ]
    lotsFixture.set(
      601,
      makeLot({
        id: 601,
        positions: [
          { id: 10, steps: [{ id: 1, role: 'inspection', fabrication_method_requires_machine: false }] },
        ],
      }),
    )

    const wrapper = await mountContent(1, [Permission.WRITE_PRODUCTION_ORDERS])
    const vm = wrapper.vm as unknown as {
      controlCanOperateInspection: boolean
      controlStartBlocked: boolean
      controlStartBlockedTooltip: string | undefined
    }

    expect(vm.controlCanOperateInspection).toBe(false)
    expect(vm.controlStartBlocked).toBe(true)
    expect(vm.controlStartBlockedTooltip).toBe(
      'An inspection step needs the permission Record QA Inspections.',
    )
  })

  it('grants controlCanOperateInspection with write:inspections and unblocks start once nothing else blocks it', async () => {
    machinesFixture = [makeMachine({ id: 1 })]
    ordersFixture = [
      makeOrder({ id: 72, machine_id: 1, status: 'queued', lot_id: 602, lot_number: 'LOT-72', lot_position_id: 10, can_start: true }),
    ]
    lotsFixture.set(
      602,
      makeLot({
        id: 602,
        positions: [
          { id: 10, steps: [{ id: 1, role: 'inspection', fabrication_method_requires_machine: false }] },
        ],
      }),
    )

    const wrapper = await mountContent(1, [Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_INSPECTIONS])
    const vm = wrapper.vm as unknown as {
      controlCanOperateInspection: boolean
      controlStartBlocked: boolean
    }

    expect(vm.controlCanOperateInspection).toBe(true)
    expect(vm.controlStartBlocked).toBe(false)
  })

  it('the machine queue and pool queue only show orders overdue or due today; a date-less order defaults to today and stays', async () => {
    machinesFixture = [makeMachine({ id: 1 })]
    poolsFixture = [makePool({ id: 5, name: 'Pool A', machine_ids: [1] })]
    const past = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString()
    const future = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000).toISOString()
    ordersFixture = [
      makeOrder({ id: 90, machine_id: 1, status: 'queued', lot_id: 900, lot_number: 'LOT-90', planned_start: past }),
      makeOrder({ id: 91, machine_id: 1, status: 'queued', lot_id: 901, lot_number: 'LOT-91', planned_start: future }),
      makeOrder({ id: 92, machine_id: 1, status: 'queued', lot_id: 902, lot_number: 'LOT-92', planned_start: null }),
      makeOrder({
        id: 93,
        machine_id: null,
        machine_pool_id: 5,
        status: 'queued',
        lot_id: 903,
        lot_number: 'LOT-93',
        planned_start: future,
      }),
    ]
    lotsFixture.set(900, makeLot({ id: 900 }))
    lotsFixture.set(901, makeLot({ id: 901 }))
    lotsFixture.set(902, makeLot({ id: 902 }))

    const wrapper = await mountContent(1)

    const queueCard = findCardByTitle(wrapper, 'Queue')
    expect(queueCard.text()).toContain('LOT-90')
    expect(queueCard.text()).not.toContain('LOT-91')
    expect(queueCard.text()).toContain('LOT-92')

    // The pool's own future-dated order is dropped the same way.
    expect(wrapper.text()).not.toContain('LOT-93')
  })

  it('an order whose only date is a future not_before (no planned_start yet) is excluded too', async () => {
    machinesFixture = [makeMachine({ id: 1 })]
    const futureDate = new Date(Date.now() + 5 * 24 * 60 * 60 * 1000)
    const futureParam = `${futureDate.getFullYear()}-${String(futureDate.getMonth() + 1).padStart(2, '0')}-${String(futureDate.getDate()).padStart(2, '0')}`
    ordersFixture = [
      makeOrder({
        id: 94,
        machine_id: 1,
        status: 'queued',
        lot_id: 904,
        lot_number: 'LOT-94',
        planned_start: null,
        not_before: futureParam,
      }),
    ]
    lotsFixture.set(904, makeLot({ id: 904 }))

    const wrapper = await mountContent(1)

    expect(wrapper.text()).not.toContain('LOT-94')
  })

  it('onPrint posts the classifier for the control target and reports success via the toast', async () => {
    machinesFixture = [makeMachine({ id: 1 })]
    ordersFixture = [
      makeOrder({
        id: 80,
        machine_id: 1,
        status: 'in_progress',
        lot_id: 700,
        lot_number: 'LOT-80',
        production_order_number: 'PO-80',
      }),
    ]
    lotsFixture.set(700, makeLot({ id: 700 }))
    postMock.mockResolvedValueOnce({ data: [{ status: 'sent' }] })

    const wrapper = await mountContent(1, [
      Permission.WRITE_PRODUCTION_ORDERS,
      Permission.PRINT_DOCUMENTS,
    ])
    const vm = wrapper.vm as unknown as {
      canPrint: boolean
      printing: string | null
      onPrint: (classifier: 'production_order_label' | 'production_order_docket') => Promise<void>
    }

    expect(vm.canPrint).toBe(true)

    await vm.onPrint('production_order_docket')

    expect(postMock).toHaveBeenCalledWith('/print/', {
      root_type: 'production_order',
      root_id: 80,
      items: [{ classifier: 'production_order_docket' }],
    })
    expect(vm.printing).toBe(null)
  })

  it('canPrint is false without the print:documents permission, and onPrint is a no-op without a control target', async () => {
    machinesFixture = [makeMachine({ id: 1 })]

    const wrapper = await mountContent(1, [Permission.WRITE_PRODUCTION_ORDERS])
    const vm = wrapper.vm as unknown as {
      canPrint: boolean
      onPrint: (classifier: 'production_order_label' | 'production_order_docket') => Promise<void>
    }

    expect(vm.canPrint).toBe(false)

    await vm.onPrint('production_order_docket')
    expect(postMock).not.toHaveBeenCalled()
  })

  it("exposes controlCanOpenItem/controlCanOpenSourceItem, and each opener shows its dialog with the control target's own data", async () => {
    machinesFixture = [makeMachine({ id: 1 })]
    ordersFixture = [
      makeOrder({
        id: 100,
        machine_id: 1,
        status: 'in_progress',
        lot_id: 700,
        lot_number: 'LOT-100',
        made_item_id: 960,
      }),
    ]
    lotsFixture.set(700, makeLot({ id: 700, source_item_id: 777 }))
    madeItemsFixture = [makeMadeItem({ id: 960, article_name: 'Bracket 960' })]
    sourceItemsFixture = [makeSourceItem({ id: 777, material: '1.4301' })]

    const wrapper = await mountContent(1)
    // Let useSourceMaterialCache's own background fetch (fire-and-forget,
    // see that composable) resolve before reading controlCanOpenSourceItem.
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      controlCanOpenItem: boolean
      controlCanOpenSourceItem: boolean
      openItemDialog: () => void
      openSourceItemDialog: () => void
      openOrderDialog: () => void
    }

    expect(vm.controlCanOpenItem).toBe(true)
    expect(vm.controlCanOpenSourceItem).toBe(true)

    // MachineCurrentOrderCard.vue hosts its own separate MadeItemDetailDialog
    // (its "view item details" eye icon) bound to the same `madeItem`; only
    // MachineDetailContent's own instance should flip visible here, so this
    // picks the one that actually opened rather than assuming render order.
    vm.openItemDialog()
    await flushPromises()
    const openItemDialogs = wrapper
      .findAllComponents({ name: 'MadeItemDetailDialog' })
      .filter((c) => c.props('visible') === true)
    expect(openItemDialogs).toHaveLength(1)
    expect((openItemDialogs[0]!.props('item') as MadeItemResponse).id).toBe(960)

    vm.openSourceItemDialog()
    await flushPromises()
    const sourceDialog = wrapper.findComponent({ name: 'SourceItemDetailDialog' })
    expect(sourceDialog.props('visible')).toBe(true)
    expect((sourceDialog.props('item') as SourceItemResponse).id).toBe(777)

    vm.openOrderDialog()
    await flushPromises()
    const orderDialog = wrapper.findComponent({ name: 'ProductionOrderDetailDialog' })
    expect(orderDialog.props('visible')).toBe(true)
    expect((orderDialog.props('order') as ProductionOrderResponse).id).toBe(100)
    // Not fetched here (no lot-event log on this page); left null.
    expect(orderDialog.props('startedBy')).toBe(null)
    // Neither completed nor with completions, so both stay null too.
    expect(orderDialog.props('endedBy')).toBe(null)
    expect(orderDialog.props('duration')).toBe(null)
    expect(orderDialog.props('assessment')).toBe(null)
  })

  it('Open Item/Open Source Material stay closed without their own data even with a control target (idle machine); Open Order still opens', async () => {
    machinesFixture = [makeMachine({ id: 1 })]
    ordersFixture = [
      makeOrder({
        id: 110,
        machine_id: 1,
        status: 'queued',
        lot_id: 800,
        lot_number: 'LOT-110',
        made_item_id: 961,
      }),
    ]
    lotsFixture.set(800, makeLot({ id: 800 })) // no source_item_id

    const wrapper = await mountContent(1)
    await flushPromises()

    const vm = wrapper.vm as unknown as {
      controlCanOpenItem: boolean
      controlCanOpenSourceItem: boolean
      openItemDialog: () => void
      openSourceItemDialog: () => void
      openOrderDialog: () => void
    }

    // Idle machine: controlTarget falls back to the head of this machine's
    // own queue, but `madeItem` stays keyed to the (now nonexistent) primary
    // current order; Open Item is gated on that same ref, so it's disabled
    // here too even though there is a control target.
    expect(vm.controlCanOpenItem).toBe(false)
    expect(vm.controlCanOpenSourceItem).toBe(false)

    vm.openItemDialog()
    vm.openSourceItemDialog()
    await flushPromises()
    expect(
      wrapper
        .findAllComponents({ name: 'MadeItemDetailDialog' })
        .some((c) => c.props('visible') === true),
    ).toBe(false)
    expect(wrapper.findComponent({ name: 'SourceItemDetailDialog' }).props('visible')).toBe(false)

    vm.openOrderDialog()
    await flushPromises()
    const orderDialog = wrapper.findComponent({ name: 'ProductionOrderDetailDialog' })
    expect(orderDialog.props('visible')).toBe(true)
    expect((orderDialog.props('order') as ProductionOrderResponse).id).toBe(110)
  })
})
