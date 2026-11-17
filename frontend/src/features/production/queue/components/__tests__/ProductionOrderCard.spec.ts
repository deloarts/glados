import { describe, it, expect, afterEach } from 'vitest'
import { RouterLinkStub } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { Permission } from '@/core/auth/permissions'
import { makeProductionOrderResponse, userWithPermissions } from '@/test-utils/factories'

import ProductionOrderCard from '../ProductionOrderCard.vue'

import type { ProductionOrderResponse } from '../../../types/productionOrdersResponse'
import type { LotResponse, LotStepResponse } from '../../../types/productionLotsResponse'
import type { LifecycleAction } from '@/core/utils/lifecycleActions'

// What the backend offers on a production order in each status, from the
// production order intent table (start and resume also need the lot, the
// machine and upstream input, which can_start reports).
const ORDER_ACTIONS: Record<string, LifecycleAction[]> = {
  queued: ['start', 'cancel', 'split', 'merge'],
  in_progress: ['pause', 'cancel', 'record_completion', 'scrap'],
  paused: ['resume', 'cancel'],
  completed: [],
  canceled: [],
}

function makeOrder(overrides: Partial<ProductionOrderResponse> = {}): ProductionOrderResponse {
  return makeProductionOrderResponse({
    actions: ORDER_ACTIONS[overrides.status ?? 'queued'],
    lot_number: 'LOT-2026-0027',
    ...overrides,
  })
}

function mountCard(
  order: ProductionOrderResponse,
  lot: LotResponse | null = null,
  permissions: string[] = [Permission.WRITE_PRODUCTION_ORDERS],
  rights: { canWrite: boolean; canManage: boolean } = { canWrite: true, canManage: true },
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  return mountWithApp(ProductionOrderCard, {
    pinia,
    props: { order, ...rights, lot },
    global: {
      stubs: { RouterLink: RouterLinkStub },
    },
  })
}

function tooltipOf(button: { element: Element }): string | undefined {
  return (button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null)
    ?.$_ptooltipValue
}

// An inspection position: machine-less, so the no-machine gate can't mask
// the permission gate under test.
function makeInspectionLot(positionId: number): LotResponse {
  return {
    positions: [
      {
        id: positionId,
        steps: [
          {
            id: 1,
            sequence: 1,
            role: 'inspection',
            fabrication_method_id: null,
            fabrication_method_name: '',
            fabrication_method_requires_machine: false,
            inspection_method_id: 1,
            inspection_method_name: 'Visual Inspection',
            inspection_method_requires_evidence: false,
          } as unknown as LotStepResponse,
        ],
      },
    ],
    source_label: '',
    source_sublabel: '',
    source_item_id: null,
  } as unknown as LotResponse
}

// Only the fields the card actually reads from the lot are populated.
function makeLotWithSteps(positionId: number, requiresMachine: boolean[]): LotResponse {
  const steps = requiresMachine.map(
    (req, i) =>
      ({
        id: i + 1,
        sequence: i + 1,
        fabrication_method_id: i + 1,
        fabrication_method_name: req ? 'Milling' : 'Cutting',
        fabrication_method_requires_machine: req,
      }) as unknown as LotStepResponse,
  )
  return {
    positions: [{ id: positionId, steps }],
    source_label: '',
    source_sublabel: '',
    source_item_id: null,
  } as unknown as LotResponse
}

describe('ProductionOrderCard', () => {
  it('shows the step sequence next to the part number for a multi-step lot', () => {
    const wrapper = mountCard(makeOrder({ lot_position_sequence: 2, lot_position_count: 3 }))
    expect(wrapper.find('.lot-link').text()).toBe('LOT-2026-0027')
    expect(wrapper.find('.position-suffix').text()).toBe('· Pos 2/3')
  })

  it('omits the step sequence for a single-step lot', () => {
    const wrapper = mountCard(makeOrder({ lot_position_sequence: 1, lot_position_count: 1 }))
    expect(wrapper.find('.lot-link').text()).toBe('LOT-2026-0027')
    expect(wrapper.find('.position-suffix').exists()).toBe(false)
  })

  // Regression: a machine-less order on a pure-manual position (every step's
  // method has requires_machine=false) sits in the Manual Work column and can
  // never be given a machine, its Start button must not be gated on one.
  it('enables Start for a machine-less order on a pure-manual position', () => {
    const wrapper = mountCard(
      makeOrder({ machine_id: null, machine_pool_id: null }),
      makeLotWithSteps(1, [false]),
    )
    const start = wrapper.findAll('button').find((b) => b.text().includes('Start'))
    expect(start).toBeDefined()
    expect(start!.attributes('disabled')).toBeUndefined()
  })

  it('keeps Start disabled for a machine-less order with a machine-requiring step', () => {
    const wrapper = mountCard(
      makeOrder({ machine_id: null, machine_pool_id: null }),
      makeLotWithSteps(1, [false, true]),
    )
    const start = wrapper.findAll('button').find((b) => b.text().includes('Start'))
    expect(start).toBeDefined()
    expect(start!.attributes('disabled')).toBeDefined()
  })

  // Regression: needsMachineOrPool reads `machine_pool_id == null` (not
  // `=== null`) precisely because the field is schema-optional as well as
  // nullable; the backend can omit the key entirely rather than send an
  // explicit null. An `undefined` order.machine_pool_id must gate Start the
  // same way an explicit null does; a stray `=== null` here would silently
  // let this order start unassigned.
  it('keeps Start disabled when machine_pool_id is undefined (omitted key), same as null', () => {
    const wrapper = mountCard(
      makeOrder({ machine_id: null, machine_pool_id: undefined }),
      makeLotWithSteps(1, [false, true]),
    )
    const start = wrapper.findAll('button').find((b) => b.text().includes('Start'))
    expect(start).toBeDefined()
    expect(start!.attributes('disabled')).toBeDefined()
  })

  // Starting an inspection position IS the QA work; the backend gates it
  // on write:inspections (StartProductionOrder._assert_can_operate_inspection),
  // so the card must not offer an action that would just 403.
  it("disables Cancel in the menu on another user's order without Manage Production Orders", () => {
    const wrapper = mountCard(makeOrder({ creator_id: 99 }))
    const cancel = (
      wrapper.findComponent({ name: 'Menu' }).props('model') as {
        label?: string
        disabled?: boolean
        title?: string
      }[]
    ).find((item) => item.label === 'Cancel')
    expect(cancel?.disabled).toBe(true)
    expect(cancel?.title).toBe(
      'Another user created this order, so canceling it needs the permission Manage Production Orders.',
    )
  })

  it('enables Cancel in the menu on an order the user created', () => {
    const wrapper = mountCard(makeOrder({ creator_id: 1 }))
    const cancel = (
      wrapper.findComponent({ name: 'Menu' }).props('model') as { label?: string; disabled?: boolean }[]
    ).find((item) => item.label === 'Cancel')
    expect(cancel?.disabled).toBe(false)
  })

  it('shows the actions disabled with the missing permission without write and manage rights', () => {
    const wrapper = mountCard(makeOrder({ status: 'in_progress' }), null, [], {
      canWrite: false,
      canManage: false,
    })

    for (const testId of ['order-card-pause', 'order-card-complete', 'order-card-more']) {
      const button = wrapper.get(`[data-testid="${testId}"]`)
      expect(button.attributes('disabled')).toBeDefined()
      expect(tooltipOf(button)).toBe('This needs the permission Write Production Orders.')
    }
    const pin = wrapper.get('[data-testid="order-card-pin"]')
    expect(pin.attributes('disabled')).toBeDefined()
    expect(tooltipOf(pin)).toBe('This needs the permission Manage Production Orders.')
  })

  it('shows Complete on an inspection position disabled without write:inspections', () => {
    const wrapper = mountCard(makeOrder({ status: 'in_progress' }), makeInspectionLot(1), [
      Permission.WRITE_PRODUCTION_ORDERS,
    ])

    const complete = wrapper.get('[data-testid="order-card-complete"]')
    expect(complete.attributes('disabled')).toBeDefined()
    expect(tooltipOf(complete)).toBe(
      i18n.global.t('productionQueue.card.inspectionPermissionTooltip'),
    )
  })

  it('disables Start on an inspection position without write:inspections', () => {
    const wrapper = mountCard(
      makeOrder({ machine_id: null, machine_pool_id: null }),
      makeInspectionLot(1),
      [Permission.WRITE_PRODUCTION_ORDERS],
    )
    const start = wrapper.findAll('button').find((b) => b.text().includes('Start'))
    expect(start).toBeDefined()
    expect(start!.attributes('disabled')).toBeDefined()
  })

  it('enables Start on an inspection position with write:inspections', () => {
    const wrapper = mountCard(
      makeOrder({ machine_id: null, machine_pool_id: null }),
      makeInspectionLot(1),
      [Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_INSPECTIONS],
    )
    const start = wrapper.findAll('button').find((b) => b.text().includes('Start'))
    expect(start).toBeDefined()
    expect(start!.attributes('disabled')).toBeUndefined()
  })

  it('disables Resume on a paused inspection position without write:inspections', () => {
    const wrapper = mountCard(
      makeOrder({ status: 'paused', machine_id: null, machine_pool_id: null }),
      makeInspectionLot(1),
      [Permission.WRITE_PRODUCTION_ORDERS],
    )
    const resume = wrapper.findAll('button').find((b) => b.text().includes('Resume'))
    expect(resume).toBeDefined()
    expect(resume!.attributes('disabled')).toBeDefined()
  })

  it('leaves Start alone on an ordinary fabrication position', () => {
    const wrapper = mountCard(
      makeOrder({ machine_id: null, machine_pool_id: null }),
      makeLotWithSteps(1, [false]),
      [Permission.WRITE_PRODUCTION_ORDERS],
    )
    const start = wrapper.findAll('button').find((b) => b.text().includes('Start'))
    expect(start).toBeDefined()
    expect(start!.attributes('disabled')).toBeUndefined()
  })

  // can_start is the backend's own verdict on the state preconditions
  // (upstream input, lot hold, status); see _resolve_can_start. Without it
  // the board offered a Start that would just 422 because the predecessor
  // step hadn't produced anything yet.
  it('disables Start when the backend says the order cannot start', () => {
    const wrapper = mountCard(makeOrder({ can_start: false }), makeLotWithSteps(1, [true]))
    const start = wrapper.findAll('button').find((b) => b.text().includes('Start'))
    expect(start).toBeDefined()
    expect(start!.attributes('disabled')).toBeDefined()
  })

  it('enables Start when the backend says the order can start', () => {
    const wrapper = mountCard(makeOrder({ can_start: true }), makeLotWithSteps(1, [true]))
    const start = wrapper.findAll('button').find((b) => b.text().includes('Start'))
    expect(start).toBeDefined()
    expect(start!.attributes('disabled')).toBeUndefined()
  })

  it('disables Resume on a paused order the backend says cannot start', () => {
    const wrapper = mountCard(
      makeOrder({ status: 'paused', can_start: false }),
      makeLotWithSteps(1, [true]),
    )
    const resume = wrapper.findAll('button').find((b) => b.text().includes('Resume'))
    expect(resume).toBeDefined()
    expect(resume!.attributes('disabled')).toBeDefined()
  })

  it('keeps Start disabled for a machine-less order when the lot is not loaded', () => {
    const wrapper = mountCard(makeOrder({ machine_id: null, machine_pool_id: null }), null)
    const start = wrapper.findAll('button').find((b) => b.text().includes('Start'))
    expect(start).toBeDefined()
    expect(start!.attributes('disabled')).toBeDefined()
  })

  describe('mass display', () => {
    afterEach(() => {
      i18n.global.locale.value = 'enGB'
    })

    it('renders the mass with a period decimal separator for en-GB', () => {
      const wrapper = mountCard(makeOrder({ made_item_mass: 1500 }))
      expect(wrapper.text()).toContain('1.50 kg')
    })

    // The mass must not go through a bare `.toFixed(2)`, which always reads
    // as English-formatted regardless of the active UI language. Switching
    // to de-AT here proves it goes through the locale-aware formatter.
    it('renders the mass with a comma decimal separator for de-AT', () => {
      i18n.global.locale.value = 'deAT'
      const wrapper = mountCard(makeOrder({ made_item_mass: 1500 }))
      expect(wrapper.text()).toContain('1,50 kg')
    })
  })
})
