import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeLotResponse } from '@/test-utils/factories'
import { i18n } from '@/core/i18n'

import LotRecordSourceDemand from '../lot-detail/LotRecordSourceDemand.vue'
import type { LotResponse } from '../../../types/productionLotsResponse'
import type { SourceItemAllocationResponse } from '@/features/source-items'

function makeLot(overrides: Partial<LotResponse> = {}): LotResponse {
  return makeLotResponse({
    public_id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
    quantity_completed: 0,
    status: 'draft',
    ...overrides,
  })
}

function mountDemand(lot: LotResponse, allocations: SourceItemAllocationResponse[] = []) {
  return mountWithApp(LotRecordSourceDemand, {
    attachTo: document.body,
    props: {
      lot,
      sourceItemDemand: null,
      sourceItemDemandArrived: 0,
      summary: null,
      allocations,
      sourceOrder: null,
      manageMode: true,
      canWrite: true,
    },
  })
}

function makeAllocation(
  overrides: Partial<SourceItemAllocationResponse> = {},
): SourceItemAllocationResponse {
  return {
    demand_item_id: 1,
    order_item_id: null,
    source: 'stock',
    quantity: 5,
    order_number: null,
    order_supplier_name: null,
    item_article_name: null,
    item_order_code_1: null,
    item_specification: null,
    order_item_quantity: null,
    order_item_unit: null,
    demand_unit: null,
    unit_mismatch: false,
    project_number: null,
    substitute_reason: null,
    substitute_source_item_id: null,
    ...overrides,
  }
}

// "Demand Source Item" always 422s (create_source_item_demand.py's
// LotHasNoMaterialSourceError) on a lot whose made item has no bought/source
// item link, e.g. a rework sourced from another made item. The button must
// be disabled whenever canDemandSourceItem(lot) is false, matching
// LotsTable.vue's gate.
describe('LotRecordSourceDemand', () => {
  it('disables "Demand Source Item" when the lot has no material source', () => {
    const wrapper = mountDemand(
      makeLot({ source_bought_item_id: null, source_item_id: null, source_made_item_id: 7 }),
    )

    const button = wrapper.get('button')
    expect(button.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('enables "Demand Source Item" when the lot has a source item source', () => {
    const wrapper = mountDemand(makeLot({ source_item_id: 6 }))

    const button = wrapper.get('button')
    expect(button.attributes('disabled')).toBeUndefined()

    wrapper.unmount()
  })

  it('enables "Demand Source Item" when the lot has a bought item source', () => {
    const wrapper = mountDemand(makeLot({ source_bought_item_id: 5 }))

    const button = wrapper.get('button')
    expect(button.attributes('disabled')).toBeUndefined()

    wrapper.unmount()
  })

  it('stays disabled without write permission even with a valid material source', () => {
    const wrapper = mountWithApp(LotRecordSourceDemand, {
      attachTo: document.body,
      props: {
        lot: makeLot({ source_item_id: 6 }),
        sourceItemDemand: null,
        sourceItemDemandArrived: 0,
        summary: null,
        allocations: [],
        sourceOrder: null,
        manageMode: true,
        canWrite: false,
      },
    })

    const button = wrapper.get('button')
    expect(button.attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })

  it('renders one order card per allocation', () => {
    const wrapper = mountDemand(makeLot({ input_demand_id: 99 }), [
      makeAllocation({ order_number: 'ORD-1', quantity: 3 }),
      makeAllocation({ order_number: 'ORD-2', quantity: 4 }),
    ])

    const cards = wrapper.findAll('.order-card')
    expect(cards).toHaveLength(2)
    expect(cards[0]!.text()).toContain('ORD-1')
    expect(cards[1]!.text()).toContain('ORD-2')

    wrapper.unmount()
  })

  it('removing a middle allocation keeps the remaining rows showing their own data', async () => {
    const lot = makeLot({ input_demand_id: 99 })
    const allocA = makeAllocation({ order_number: 'ORD-A', quantity: 1 })
    const allocB = makeAllocation({ order_number: 'ORD-B', quantity: 2 })
    const allocC = makeAllocation({ order_number: 'ORD-C', quantity: 3 })

    const wrapper = mountDemand(lot, [allocA, allocB, allocC])

    expect(wrapper.findAll('.order-card')).toHaveLength(3)

    // The middle allocation drops out, as if the caller's own list shrank
    // after a re-fetch, leaving A and C, in order.
    await wrapper.setProps({ allocations: [allocA, allocC] })

    const cards = wrapper.findAll('.order-card')
    expect(cards).toHaveLength(2)
    expect(cards[0]!.text()).toContain('ORD-A')
    expect(cards[0]!.text()).not.toContain('ORD-B')
    expect(cards[1]!.text()).toContain('ORD-C')
    expect(cards[1]!.text()).not.toContain('ORD-B')

    wrapper.unmount()
  })

  it.each([
    [{ source_bought_item_id: null, source_item_id: null, source_made_item_id: null }, true],
    [{ source_item_id: 6 }, false],
    [
      { source_bought_item_id: null, source_item_id: null, source_made_item_id: 7, is_alteration: true },
      false,
    ],
  ])('says a lot without material source waits to be planned (%o)', (source, shown) => {
    const wrapper = mountDemand(makeLot(source))

    const hint = i18n.global.t('production.lots.detail.record.sourceDemand.notPlannedWithoutSource')
    expect(wrapper.text().includes(hint)).toBe(shown)

    wrapper.unmount()
  })
})
