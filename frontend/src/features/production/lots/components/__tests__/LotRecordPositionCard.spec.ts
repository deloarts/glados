import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import ConfirmationService from 'openvue/confirmationservice'

import { createPinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeProductionOrderResponse, userWithPermissions } from '@/test-utils/factories'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import LotRecordPositionCard from '../lot-detail/LotRecordPositionCard.vue'
import type {
  LotEventResponse,
  LotPositionProvisionResponse,
  LotPositionResponse,
  LotStepResponse,
} from '../../../types/productionLotsResponse'
import type {
  ManufacturingAssessmentResponse,
  ProductionOrderFile,
  ProductionOrderResponse,
} from '../../../types/productionOrdersResponse'
import type { OrderItemResponse, OrderResponse } from '@/features/orders'

const step: LotStepResponse = {
  id: 1,
  public_id: '11111111-1111-1111-1111-111111111111',
  created: '2026-07-01',
  note: null,
  estimated_setup_minutes: 10,
  estimated_minutes_per_piece: 2,
  time_budget_per_piece: null,
  sequence: 1,
  creator_id: 1,
  fabrication_method_id: 1,
  role: 'fabrication' as const,
  inspection_method_id: null,
  inspection_method_name: null,
  inspection_method_requires_evidence: null,
  fabrication_method_name: { enGB: 'Milling' },
  fabrication_method_requires_machine: true,
  fabrication_method_required_external: false,
  fabrication_method_default_supplier_id: null,
  lot_id: 1,
  position_id: 1,
  source_process_id: null,
}

function makePosition(overrides: Partial<LotPositionResponse> = {}): LotPositionResponse {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    created: '2026-07-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    sequence: 1,
    kind: 'internal',
    status: 'in_progress',
    quantity: 10,
    quantity_completed: 4,
    quantity_remaining: 6,
    note: null,
    creator_id: 1,
    lot_id: 1,
    steps: [step],
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
}

function makeOrder(overrides: Partial<ProductionOrderResponse> = {}): ProductionOrderResponse {
  return makeProductionOrderResponse({
    production_order_number: 'PO-0001',
    quantity: 5,
    machine_internal_name: 'Mill 1',
    lot_number: 'L-0001',
    ...overrides,
  })
}

function makeOrderItem(overrides: Partial<OrderItemResponse> = {}): OrderItemResponse {
  return {
    edit_version: 0,
    id: 1,
    public_id: '33333333-3333-3333-3333-333333333333',
    status: 'ordered',
    created: '2026-07-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    position: 1,
    quantity: 5,
    quantity_delivered: 0,
    unit: 'PCS',
    items_per_unit: 1,
    price: null,
    note: null,
    ordered_date: '2026-07-02',
    expected_delivery_date: '2026-07-20',
    delivery_date: null,
    storage_place: null,
    expected_pickup_date: null,
    ready_for_pickup_date: null,
    creator_id: 1,
    creator: {
      id: 1,
      public_id: '22222222-2222-2222-2222-222222222222',
      username: 'phil',
      full_name: 'Sam',
      has_avatar: false,
    },
    orderer_id: null,
    orderer: null,
    receiver_id: null,
    receiver: null,
    bought_item_id: 1,
    source_item_id: null,
    virtual_name: null,
    quote_request_line_id: null,
    quote_request_id: null,
    quote_request_number: '',
    item_order_code_1: 'ORD-CODE-1',
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
    made_item_id: null,
    order_id: 1,
    supplier_id: 1,
    supplier_name: 'Acme Supplies',
    project_id: 42,
    project_number: 'P-001',
    project_customer: 'Acme',
    project_description: '',
    project_status: 'active',
    demand_substitutions: [],
    delivery_records: [],
    line_type: 'MADE',
    lot_position_id: 1,
    lot_id: 1,
    lot_number: 'L-0001',
    fabrication_method: '',
    actions: [],
    blocked_actions: {},
    canceled_at: null,
    requested_at: null,
    closed_short_at: null,
    closed_short_from: null,
    ...overrides,
  }
}

function mountCard(props: {
  position: LotPositionResponse
  orders?: ProductionOrderResponse[]
  provisions?: LotPositionProvisionResponse[]
  orderItem?: OrderItemResponse | null
  order?: OrderResponse | null
  events?: LotEventResponse[]
  assessments?: Record<number, ManufacturingAssessmentResponse>
  files?: Record<number, ProductionOrderFile[]>
  // Reading QA evidence needs write:inspections, so the card holds it by
  // default and a test of the blocked case passes an empty list.
  permissions?: string[]
}) {
  const assessments = props.assessments ?? {}
  const files = props.files ?? {}
  const pinia = createPinia()
  useCurrentUserStore(pinia).user = userWithPermissions(props.permissions ?? [Permission.WRITE_INSPECTIONS])
  return mountWithApp(LotRecordPositionCard, {
    attachTo: document.body,
    pinia,
    props: {
      position: props.position,
      orders: props.orders ?? [],
      provisions: props.provisions ?? [],
      orderItem: props.orderItem ?? null,
      order: props.order ?? null,
      events: props.events ?? [],
      assessmentForOrder: (orderId: number) => assessments[orderId] ?? null,
      filesForOrder: (orderId: number) => files[orderId] ?? [],
    },
    global: {
      plugins: [// The nested OrderDetailDialog calls useConfirm() unconditionally in
        // its own setup() for its remove-item confirm.
        ConfirmationService, // The nested OrderDetailDialog links through to the order's own page.
        createRouter({
          history: createMemoryHistory(),
          routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
        }),],
    },
  })
}

describe('LotRecordPositionCard', () => {
  it('renders without errors for a mixed position with orders and provisions', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountCard({
      position: makePosition({
        kind: 'mixed',
        order_number: 'ORD-1',
        supplier_name: 'Acme Supplies',
        order_item_status: 'requested',
        order_item_closed_short: false,
        expected_delivery_date: '2026-07-20',
      }),
      orders: [
        makeOrder({
          completions: [
            {
            public_id: '00000110-0000-0000-0000-000000000000',
              id: 1,
              production_order_id: 1,
              quantity: 3,
              quantity_accepted: 3,
              quantity_rejected: 0,
              quantity_rework: 0,
              quantity_scrap: 0,
              completion_date: '2026-07-10',
              note: null,
              operator_id: 2,
              operator: {
                id: 2,
                public_id: '33333333-3333-3333-3333-333333333333',
                username: 'agreen',
                full_name: 'A. Green',
                has_avatar: false,
              },
              recorded_by_id: 2,
              recorded_by: {
                id: 2,
                public_id: '33333333-3333-3333-3333-333333333333',
                username: 'agreen',
                full_name: 'A. Green',
                has_avatar: false,
              },
              created: '2026-07-10',
              reject_reason: null,
              scrap_reason: null,
              reverses_completion_id: null,
              machine_id: null,
            },
          ],
        }),
      ],
      provisions: [
        {
        public_id: '00000109-0000-0000-0000-000000000000',
          id: 1,
          lot_position_id: 1,
          quantity: 5,
          provision_date: '2026-07-05',
          note: 'partial delivery',
          creator_id: 1,
          creator: {
            id: 1,
            public_id: '22222222-2222-2222-2222-222222222222',
            username: 'phil',
            full_name: 'Sam',
            has_avatar: false,
          },
          created: '2026-07-05',
        },
      ],
      events: [
        {
        public_id: '00000108-0000-0000-0000-000000000000',
          id: 1,
          lot_id: 1,
          occurred_at: '2026-07-01T10:00:00',
          actor_id: 1,
          actor_username: 'phil',
          actor_full_name: 'Sam Doe',
          event_type: 'position_assigned_internal',
          entity: 'position',
          entity_id: 1,
          summary: 'Position assigned internally',
          payload: null,
        },
      ],
    })

    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    wrapper.unmount()
  })

  it('renders every contributing order when a position is split across machines', async () => {
    const wrapper = mountCard({
      position: makePosition(),
      orders: [
        makeOrder({
          id: 10,
          production_order_number: 'PO-0010',
          machine_id: 1,
          machine_internal_name: 'Mill 1',
        }),
        makeOrder({
          id: 11,
          production_order_number: 'PO-0011',
          machine_id: null,
          machine_internal_name: '',
          machine_pool_id: 5,
          machine_pool_name: '3-Axis Pool',
        }),
      ],
    })

    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('PO-0010')
    expect(text).toContain('Mill 1')
    expect(text).toContain('PO-0011')
    expect(text).toContain('3-Axis Pool')

    wrapper.unmount()
  })

  it('shows the full order detail for an external position', async () => {
    const wrapper = mountCard({
      position: makePosition({
        kind: 'external',
        order_number: 'ORD-551',
        supplier_name: 'Mason Supply',
        order_item_status: 'ordered',
        order_item_closed_short: false,
        expected_delivery_date: '2026-07-19',
      }),
      orderItem: makeOrderItem({
        creator: {
          id: 1,
          public_id: '44444444-4444-4444-4444-444444444444',
          username: 'mhughes',
          full_name: 'M. Hughes',
          has_avatar: false,
        },
        ordered_date: '2026-07-02',
        expected_delivery_date: '2026-07-19',
        expected_pickup_date: '2026-07-18',
        delivery_date: '2026-07-19',
      }),
    })

    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('ORD-551')
    expect(text).toContain('M. Hughes')
    expect(text).toContain('2026-07-19')
    expect(text).toContain('2026-07-18')

    wrapper.unmount()
  })

  it('shows the completion operator', async () => {
    const wrapper = mountCard({
      position: makePosition(),
      orders: [
        makeOrder({
          completions: [
            {
            public_id: '00000107-0000-0000-0000-000000000000',
              id: 1,
              production_order_id: 1,
              quantity: 3,
              quantity_accepted: 3,
              quantity_rejected: 0,
              quantity_rework: 0,
              quantity_scrap: 0,
              completion_date: '2026-07-10',
              note: null,
              operator_id: 2,
              operator: {
                id: 2,
                public_id: '33333333-3333-3333-3333-333333333333',
                username: 'agreen',
                full_name: 'A. Green',
                has_avatar: false,
              },
              recorded_by_id: 2,
              recorded_by: {
                id: 2,
                public_id: '33333333-3333-3333-3333-333333333333',
                username: 'agreen',
                full_name: 'A. Green',
                has_avatar: false,
              },
              created: '2026-07-10',
              reject_reason: null,
              scrap_reason: null,
              reverses_completion_id: null,
              machine_id: null,
            },
          ],
        }),
      ],
    })

    await flushPromises()

    expect(wrapper.text()).toContain('A. Green')

    wrapper.unmount()
  })

  it('history table shows only events for this position/its steps/its orders', async () => {
    const wrapper = mountCard({
      position: makePosition(),
      orders: [makeOrder({ id: 10 })],
      events: [
        {
        public_id: '00000106-0000-0000-0000-000000000000',
          id: 1,
          lot_id: 1,
          occurred_at: '2026-07-01T10:00:00',
          actor_id: 1,
          actor_username: 'phil',
          actor_full_name: 'Sam Doe',
          event_type: 'position_assigned_internal',
          entity: 'position',
          entity_id: 1,
          summary: 'Position assigned internally',
          payload: null,
        },
        // Different entity type ('lot'): must never match, even though the id
        // happens to coincide with this position's id.
        {
        public_id: '00000105-0000-0000-0000-000000000000',
          id: 2,
          lot_id: 1,
          occurred_at: '2026-07-01T11:00:00',
          actor_id: 1,
          actor_username: 'someone-else',
          actor_full_name: 'Someone Else',
          event_type: 'lot_updated',
          entity: 'lot',
          entity_id: 1,
          summary: 'Lot updated',
          payload: null,
        },
      ],
    })

    await flushPromises()

    // Always rendered now (no expand toggle): the history table shows the
    // matching event straight away and never the unrelated 'lot' one.
    expect(wrapper.text()).toContain('Sam Doe')
    expect(wrapper.text()).not.toContain('phil')
    expect(wrapper.text()).not.toContain('Someone Else')

    wrapper.unmount()
  })

  it('shows both pool and machine when an order was resolved from a pool', async () => {
    const wrapper = mountCard({
      position: makePosition(),
      orders: [
        makeOrder({
          machine_id: 3,
          machine_internal_name: 'Mill 3',
          machine_pool_id: 5,
          machine_pool_name: '3-Axis Pool',
        }),
      ],
    })

    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Mill 3')
    expect(text).toContain('3-Axis Pool')

    wrapper.unmount()
  })

  it('shows who started and ended a completed order, and how long it took', async () => {
    const wrapper = mountCard({
      position: makePosition(),
      orders: [
        makeOrder({
          id: 20,
          status: 'completed',
          actual_start: '2026-07-10T08:00:00',
          actual_end: '2026-07-10T10:30:00',
          completions: [
            {
            public_id: '00000104-0000-0000-0000-000000000000',
              id: 1,
              production_order_id: 20,
              quantity: 5,
              quantity_accepted: 5,
              quantity_rejected: 0,
              quantity_rework: 0,
              quantity_scrap: 0,
              completion_date: '2026-07-10',
              note: null,
              operator_id: 2,
              operator: {
                id: 2,
                public_id: '33333333-3333-3333-3333-333333333333',
                username: 'agreen',
                full_name: 'A. Green',
                has_avatar: false,
              },
              recorded_by_id: 2,
              recorded_by: {
                id: 2,
                public_id: '33333333-3333-3333-3333-333333333333',
                username: 'agreen',
                full_name: 'A. Green',
                has_avatar: false,
              },
              created: '2026-07-10',
              reject_reason: null,
              scrap_reason: null,
              reverses_completion_id: null,
              machine_id: null,
            },
          ],
        }),
      ],
      events: [
        {
        public_id: '00000103-0000-0000-0000-000000000000',
          id: 1,
          lot_id: 1,
          occurred_at: '2026-07-10T08:00:00',
          actor_id: 3,
          actor_username: 'mhughes',
          actor_full_name: 'Max Hughes',
          event_type: 'order_started',
          entity: 'order',
          entity_id: 20,
          summary: 'Production order #20 started.',
          payload: null,
        },
      ],
    })

    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Max Hughes')
    expect(text).not.toContain('mhughes')
    expect(text).toContain('A. Green')
    expect(text).toContain('2 h 30 min')

    wrapper.unmount()
  })

  it('compares estimated against measured time with a minute and percent diff', async () => {
    const wrapper = mountCard({
      position: makePosition({
        quantity: 5,
        steps: [{ ...step, id: 1, estimated_setup_minutes: 10, estimated_minutes_per_piece: 2 }],
      }),
      // 10 setup + 5 x 2 = 20 estimated
      orders: [makeOrder({ id: 42, quantity: 5, estimated_duration_minutes: 20 })],
      assessments: {
        42: {
        public_id: '00000102-0000-0000-0000-000000000000',
          id: 1,
          production_order_id: 42,
          operator_id: 2,
          operator: null,
          // 15 setup + 5 x 3 = 30 actual, i.e. +10 min / +50%
          actual_minutes_per_piece: 3,
          actual_setup_minutes: 15,
          complexity: 'normal',
          note: null,
          created: '2026-07-11',
        },
      },
    })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('+10 min (+50%)')
    expect(text).toContain('+5 min (+50%)')
    expect(wrapper.findAll('.diff-over').length).toBeGreaterThan(0)

    wrapper.unmount()
  })

  it('shows decimal minutes with two decimals and the assessment time formatted', async () => {
    const wrapper = mountCard({
      position: makePosition({
        quantity: 3,
        steps: [{ ...step, id: 1, estimated_setup_minutes: 0, estimated_minutes_per_piece: 5 }],
      }),
      orders: [makeOrder({ id: 42, quantity: 3, estimated_duration_minutes: 15 })],
      assessments: {
        42: {
          public_id: '00000103-0000-0000-0000-000000000000',
          id: 1,
          production_order_id: 42,
          operator_id: 2,
          operator: null,
          // 3 x 6.75 = 20.25 actual against 15 estimated.
          actual_minutes_per_piece: 6.75,
          actual_setup_minutes: null,
          complexity: 'normal',
          note: null,
          created: '2026-11-27T12:28:10.804229Z',
        },
      },
    })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('6.75 min')
    expect(text).toContain('20.25 min')
    expect(text).toContain('+5.25 min (+35%)')
    expect(text).not.toContain('T12:28:10')

    wrapper.unmount()
  })

  it('shows no comparison table for an order nobody has assessed', async () => {
    const wrapper = mountCard({ position: makePosition(), orders: [makeOrder({ id: 42 })] })
    await flushPromises()

    expect(wrapper.find('.compare-table').exists()).toBe(false)

    wrapper.unmount()
  })

  it('clicking a production order number opens its detail dialog with the right order', async () => {
    const order = makeOrder({ id: 10, production_order_number: 'PO-0010' })
    const wrapper = mountCard({ position: makePosition(), orders: [order] })
    await flushPromises()

    const link = wrapper.find('.order-card .field-link')
    await link.trigger('click')

    const dialog = wrapper.findComponent({ name: 'ProductionOrderDetailDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('order')).toEqual(order)

    wrapper.unmount()
  })

  it("shows each step's setup/per-piece estimate and the computed total", async () => {
    const wrapper = mountCard({
      position: makePosition({
        quantity: 10,
        steps: [
          {
            ...step,
            id: 1,
            sequence: 1,
            estimated_setup_minutes: 15,
            estimated_minutes_per_piece: 3,
          },
        ],
      }),
    })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('15 min')
    expect(text).toContain('3 min')
    // 15 setup + 10 pieces x 3 = 45 min
    expect(text).toContain('45 min')

    wrapper.unmount()
  })

  it('falls back to the project time budget for a step with no measured per-piece estimate', async () => {
    const wrapper = mountCard({
      position: makePosition({
        steps: [
          {
            ...step,
            id: 1,
            estimated_setup_minutes: null,
            estimated_minutes_per_piece: null,
            time_budget_per_piece: 7,
          },
        ],
      }),
    })
    await flushPromises()

    // Rendered, but visibly marked as budget-derived rather than measured.
    expect(wrapper.find('.from-budget').exists()).toBe(true)
    expect(wrapper.text()).toContain('7 min')

    wrapper.unmount()
  })

  it('shows the measured manufacturing assessment for an assessed order', async () => {
    const order = makeOrder({ id: 42 })
    const wrapper = mountCard({
      position: makePosition(),
      orders: [order],
      assessments: {
        42: {
        public_id: '00000101-0000-0000-0000-000000000000',
          id: 1,
          production_order_id: 42,
          operator_id: 2,
          operator: {
            id: 2,
            public_id: '33333333-3333-3333-3333-333333333333',
            username: 'agreen',
            full_name: 'A. Green',
            has_avatar: false,
          },
          actual_minutes_per_piece: 9,
          actual_setup_minutes: 20,
          complexity: 'very',
          note: 'fixture slipped twice',
          created: '2026-07-11',
        },
      },
    })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('9 min')
    expect(text).toContain('20 min')
    expect(text).toContain('Very Complex')
    expect(text).toContain('fixture slipped twice')

    wrapper.unmount()
  })

  it('clicking an external order number opens the orders feature detail dialog', async () => {
    const wrapper = mountCard({
      position: makePosition({
        kind: 'external',
        order_id: 77,
        order_number: 'ORD-77',
        supplier_name: 'Acme',
      }),
    })
    await flushPromises()

    const link = wrapper.find('.order-card .field-link')
    await link.trigger('click')

    const dialog = wrapper.findComponent({ name: 'OrderDetailDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('orderId')).toBe(77)

    wrapper.unmount()
  })

  it('lists the earlier lines closed short below the newest line, each opening its order', async () => {
    const wrapper = mountCard({
      position: makePosition({
        kind: 'mixed',
        order_id: 78,
        order_number: 'ORD-78',
        supplier_name: 'Acme',
        order_item_status: 'ordered',
        earlier_order_lines: [
          {
            order_item_id: 40,
            order_id: 77,
            order_number: 'ORD-77',
            supplier_name: 'Mason Supply',
            quantity: 6,
            quantity_delivered: 6,
            unit: 'pcs',
            closed_short: true,
          },
        ],
      }),
    })
    await flushPromises()

    const text = wrapper.text()
    expect(text.indexOf('ORD-78')).toBeLessThan(text.indexOf('ORD-77'))
    const earlier = wrapper.find('[data-testid="earlier-order-line"]')
    expect(earlier.text()).toContain('Mason Supply')
    expect(earlier.text()).toContain('Closed short')
    expect(earlier.text()).toMatch(/6\s*\/\s*6\s*pcs/)

    await earlier.find('.field-link').trigger('click')
    const dialog = wrapper.findComponent({ name: 'OrderDetailDialog' })
    expect(dialog.props('visible')).toBe(true)
    expect(dialog.props('orderId')).toBe(77)

    wrapper.unmount()
  })

  it('spells out the QA split and scrap reason of a completion that rejected pieces', async () => {
    const operator = {
      id: 2,
      public_id: '33333333-3333-3333-3333-333333333333',
      username: 'agreen',
      full_name: 'A. Green',
      email: 'a@x.com',
      has_avatar: false,
    }
    const wrapper = mountCard({
      position: makePosition({ kind: 'internal' }),
      orders: [
        makeOrder({
          status: 'completed',
          completions: [
            {
              public_id: '00000120-0000-0000-0000-000000000000',
              id: 1,
              production_order_id: 1,
              quantity: 5,
              quantity_accepted: 3,
              quantity_rejected: 2,
              quantity_rework: 1,
              quantity_scrap: 1,
              scrap_reason: 'tool_breakage',
              completion_date: '2026-07-10',
              note: null,
              operator_id: 2,
              operator,
              recorded_by_id: 2,
              recorded_by: operator,
              created: '2026-07-10',
              reject_reason: null,
              reverses_completion_id: null,
              machine_id: null,
            },
          ],
        }),
      ],
    })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('3 accepted')
    expect(text).toContain('2 rejected')
    expect(text).toContain('1 rework')
    expect(text).toContain('1 scrap (Tool Breakage)')

    wrapper.unmount()
  })

  it('lists every pause of an order, marking one that has not resumed yet', async () => {
    const wrapper = mountCard({
      position: makePosition({ kind: 'internal' }),
      orders: [
        makeOrder({
          status: 'paused',
          interruptions: [
            { paused_at: '2026-07-10T08:00:00', resumed_at: '2026-07-10T09:30:00', reason: null, paused_operator_id: null, pause_cause: null },
            { paused_at: '2026-07-10T11:00:00', resumed_at: null, reason: null, paused_operator_id: null, pause_cause: null },
          ],
        }),
      ],
    })
    await flushPromises()

    const text = wrapper.text()
    expect(text).toContain('Interruptions (2)')
    expect(text).toContain('resumed')
    expect(text).toContain('still paused')

    wrapper.unmount()
  })

  it('names the cause an operator picked for a pause', async () => {
    const wrapper = mountCard({
      position: makePosition({ kind: 'internal' }),
      orders: [
        makeOrder({
          status: 'paused',
          interruptions: [
            { paused_at: '2026-07-10T11:00:00', resumed_at: null, reason: 'manual', paused_operator_id: null, pause_cause: 'waiting_for_material' },
          ],
        }),
      ],
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Waiting for Material')

    wrapper.unmount()
  })

  it('shows the evidence files of an inspection position and flags a missing required one', async () => {
    const inspectionStep: LotStepResponse = {
      ...step,
      id: 9,
      role: 'inspection',
      fabrication_method_id: null,
      fabrication_method_name: { enGB: '' },
      fabrication_method_requires_machine: false,
      inspection_method_id: 1,
      inspection_method_name: { enGB: 'Visual Inspection' },
      inspection_method_requires_evidence: true,
    }
    const file: ProductionOrderFile = {
      id: 5,
      public_id: '00000130-0000-0000-0000-000000000000',
      production_order_id: 1,
      category: 'measurement_report',
      file_name: 'report.pdf',
      mime_type: 'application/pdf',
      size_bytes: 2048,
      sha256: 'abc',
      storage_path: 'x',
      stored_name: 'x',
      uploaded_by_user_id: 1,
      url: null,
      created: '2026-07-10',
    }

    const withFile = mountCard({
      position: makePosition({ kind: 'internal', steps: [inspectionStep] }),
      orders: [makeOrder()],
      files: { 1: [file] },
    })
    await flushPromises()
    expect(withFile.text()).toContain('Visual Inspection')
    expect(withFile.text()).toContain('Evidence (1)')
    expect(withFile.text()).toContain('report.pdf')
    withFile.unmount()

    const without = mountCard({
      position: makePosition({ kind: 'internal', steps: [inspectionStep] }),
      orders: [makeOrder()],
    })
    await flushPromises()
    expect(without.text()).toContain('No evidence uploaded yet.')
    without.unmount()
  })

  it('names the missing permission instead of claiming no evidence was uploaded', async () => {
    const inspectionStep: LotStepResponse = {
      ...step,
      id: 9,
      role: 'inspection',
      fabrication_method_id: null,
      fabrication_method_name: { enGB: '' },
      fabrication_method_requires_machine: false,
      inspection_method_id: 1,
      inspection_method_name: { enGB: 'Visual Inspection' },
      inspection_method_requires_evidence: true,
    }

    const wrapper = mountCard({
      position: makePosition({ kind: 'internal', steps: [inspectionStep] }),
      orders: [makeOrder()],
      permissions: [],
    })
    await flushPromises()

    expect(wrapper.text()).toContain('This needs the permission')
    expect(wrapper.text()).not.toContain('No evidence uploaded yet.')
    expect(wrapper.text()).not.toContain('Evidence (')

    wrapper.unmount()
  })

  it('never shows an evidence section on a plain fabrication position', async () => {
    const wrapper = mountCard({
      position: makePosition({ kind: 'internal' }),
      orders: [makeOrder()],
    })
    await flushPromises()

    expect(wrapper.text()).not.toContain('Evidence (')

    wrapper.unmount()
  })
})
