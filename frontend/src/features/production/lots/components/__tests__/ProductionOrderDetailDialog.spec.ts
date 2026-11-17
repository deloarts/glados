import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeProductionOrderResponse } from '@/test-utils/factories'

import ProductionOrderDetailDialog from '../ProductionOrderDetailDialog.vue'
import type {
  ManufacturingAssessmentResponse,
  ProductionOrderResponse,
} from '../../../types/productionOrdersResponse'

function makeOrder(overrides: Partial<ProductionOrderResponse> = {}): ProductionOrderResponse {
  return makeProductionOrderResponse({
    production_order_number: 'PO-0001',
    status: 'completed',
    quantity: 5,
    quantity_completed: 5,
    planned_start: '2026-07-10T07:00:00',
    planned_end: '2026-07-10T09:00:00',
    actual_start: '2026-07-10T08:00:00',
    actual_end: '2026-07-10T10:30:00',
    machine_id: 3,
    machine_internal_name: 'Mill 3',
    machine_pool_id: 5,
    machine_pool_name: '3-Axis Pool',
    lot_number: 'LOT-0001',
    lot_position_count: 2,
    ...overrides,
  })
}

// Dialog teleports its content to <body>, so (matching AutoPlanDialog.spec.ts's
// established pattern) assertions read document.body rather than wrapper.text(),
// and mounting is awaited so the teleported content is actually in the DOM yet.
async function mountDialog(props: {
  order: ProductionOrderResponse | null
  startedBy?: string | null
  endedBy?: string | null
  duration?: string | null
  assessment?: ManufacturingAssessmentResponse | null
}) {
  const wrapper = mountWithApp(ProductionOrderDetailDialog, {
    attachTo: document.body,
    props: {
      order: props.order,
      startedBy: props.startedBy ?? null,
      endedBy: props.endedBy ?? null,
      duration: props.duration ?? null,
      assessment: props.assessment ?? null,
      visible: true,
    },
  })
  await flushPromises()
  return wrapper
}

describe('ProductionOrderDetailDialog', () => {
  it('renders order identity, position context, machine and pool together', async () => {
    const wrapper = await mountDialog({ order: makeOrder() })

    const text = document.body.textContent
    expect(text).toContain('PO-0001')
    expect(text).toContain('LOT-0001')
    expect(text).toContain('PN-1:A')
    expect(text).toContain('Mill 3')
    expect(text).toContain('3-Axis Pool')

    wrapper.unmount()
  })

  it('shows started-by, ended-by and duration when provided', async () => {
    const wrapper = await mountDialog({
      order: makeOrder(),
      startedBy: 'mhughes',
      endedBy: 'A. Green',
      duration: '2 h 30 min',
    })

    const text = document.body.textContent
    expect(text).toContain('mhughes')
    expect(text).toContain('A. Green')
    expect(text).toContain('2 h 30 min')

    wrapper.unmount()
  })

  it('omits started-by/ended-by/duration fields entirely when null', async () => {
    const wrapper = await mountDialog({
      order: makeOrder({ actual_start: null, actual_end: null }),
    })

    const text = document.body.textContent
    expect(text).not.toContain('Started by')
    expect(text).not.toContain('Ended by')
    expect(text).not.toContain('Duration')

    wrapper.unmount()
  })

  it('lists conflicts as tags', async () => {
    const wrapper = await mountDialog({
      order: makeOrder({ conflicts: ['no_machine_assigned', 'past_target_date'] }),
    })

    const tags = wrapper.findAllComponents({ name: 'Tag' }).map((t) => t.props('value'))
    expect(tags).toContain('No machine assigned')
    expect(tags).toContain('Past target date')

    wrapper.unmount()
  })

  it('renders nothing but the empty dialog shell when order is null', async () => {
    const wrapper = await mountDialog({ order: null })
    expect(document.body.querySelector('.po-detail')).toBeNull()
    wrapper.unmount()
  })
})
