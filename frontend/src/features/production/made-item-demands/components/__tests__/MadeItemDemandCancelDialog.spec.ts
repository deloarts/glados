import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'


const getCancelImpact = vi.fn<(id: number) => Promise<MadeItemDemandCancelImpact>>()
const cancelDemand = vi.fn<(id: number) => Promise<MadeItemDemandResponse>>()

vi.mock('@/features/made-items/api/getMadeItemDemandCancelImpact', () => ({
  getMadeItemDemandCancelImpact: (id: number) => getCancelImpact(id),
}))
vi.mock('@/features/made-items/api/madeItemDemandsApi', () => ({
  cancelMadeItemDemand: (id: number) => cancelDemand(id),
  updateMadeItemDemandStatus: vi.fn<() => Promise<unknown>>(),
  getMadeItemDemands: vi.fn<() => Promise<unknown>>(),
  createMadeItemDemand: vi.fn<() => Promise<unknown>>(),
  updateMadeItemDemand: vi.fn<() => Promise<unknown>>(),
}))
vi.mock('@/features/made-items/api/deleteMadeItemDemand', () => ({
  deleteMadeItemDemand: vi.fn<() => Promise<unknown>>(),
}))

import MadeItemDemandCancelDialog from '../MadeItemDemandCancelDialog.vue'
import type { MadeItemDemandCancelImpact, MadeItemDemandResponse } from '@/features/made-items'

const demand = { id: 9, item_article_name: 'Bracket' } as MadeItemDemandResponse

function makeImpact(
  overrides: Partial<MadeItemDemandCancelImpact> = {},
): MadeItemDemandCancelImpact {
  return {
    demand_item_id: 9,
    status: 'ordered',
    quantity: 10,
    unit: 'pcs',
    item_part_number: 'PN-1',
    item_revision: 'A',
    item_article_name: 'Bracket',
    project_number: 'P-001',
    can_cancel_lots: true,
    lots: [
      {
        lot_id: 3,
        lot_number: 'LOT-0003',
        status: 'in_progress',
        quantity: 10,
        quantity_completed: 0,
        allocated_quantity: 10,
        will_cancel: true,
        cancel_refused: false,
        keep_reason: null,
        other_demand_ids: [],
        source_item_demand: {
          demand_id: 50,
          status: 'ordered',
          quantity: 10,
          unit: 'pcs',
          item_article_name: 'Round bar 20mm',
          will_cancel: true,
          keep_reason: null,
          order_items: [
            {
              order_item_id: 4,
              order_id: 1,
              order_number: 'ORD-1',
              position: 2,
              status: 'ordered',
              quantity: 10,
              quantity_delivered: 0,
              unit: 'pcs',
              supplier_name: 'Steel Ltd',
              item_article_name: 'Round bar 20mm',
              lot_position_sequence: null,
              will_cancel: false,
              keep_reason: 'raw material already on order with the supplier',
            },
          ],
        },
        production_orders: [
          {
            production_order_id: 7,
            production_order_number: 'PO-0007',
            status: 'in_progress',
            quantity: 10,
            quantity_completed: 2,
            machine_id: 1,
            machine_name: 'Mill-01',
            lot_position_sequence: 1,
            will_cancel: true,
            keep_reason: null,
          },
        ],
        order_items: [
          {
            order_item_id: 8,
            order_id: 2,
            order_number: 'ORD-2',
            position: 5,
            status: 'ordered',
            quantity: 10,
            quantity_delivered: 0,
            unit: 'pcs',
            supplier_name: 'Coating Ltd',
            item_article_name: 'Bracket coating',
            lot_position_sequence: 2,
            will_cancel: true,
            keep_reason: null,
          },
        ],
      },
    ],
    ...overrides,
  }
}

let wrapper: ReturnType<typeof mountDialog> | null = null

function mountDialog() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mountWithApp(MadeItemDemandCancelDialog, {
    pinia,
    props: { demand, visible: true },
    attachTo: document.body,
  })
}

describe('MadeItemDemandCancelDialog', () => {
  beforeEach(() => {
    getCancelImpact.mockReset()
    cancelDemand.mockReset()
    getCancelImpact.mockResolvedValue(makeImpact())
    cancelDemand.mockResolvedValue({ ...demand, status: 'canceled' })
  })

  // The dialog teleports its content to document.body, so a leftover
  // wrapper would pollute the next test's body-text assertions.
  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
  })

  it('names every entity the cancelation takes down', async () => {
    wrapper = mountDialog()
    await flushPromises()

    const text = document.body.textContent ?? ''
    expect(text).toContain('LOT-0003')
    expect(text).toContain('PO-0007')
    expect(text).toContain('Mill-01')
    expect(text).toContain('ORD-2')
    expect(text).toContain('Coating Ltd')
    expect(text).toContain('Round bar 20mm')
  })

  it('marks the raw material order as kept rather than canceled', async () => {
    wrapper = mountDialog()
    await flushPromises()

    const text = document.body.textContent ?? ''
    expect(text).toContain('ORD-1')
    expect(text).toContain('stays open')
  })

  it('separates a lot that survives, with its reason', async () => {
    getCancelImpact.mockResolvedValue(
      makeImpact({
        lots: [
          {
            ...makeImpact().lots![0]!,
            will_cancel: false,
            keep_reason: 'lot is also allocated to other open demands',
            other_demand_ids: [11],
          },
        ],
      }),
    )
    wrapper = mountDialog()
    await flushPromises()

    const text = document.body.textContent ?? ''
    expect(text).toContain('Will be kept')
    expect(text).toContain('lot is also allocated to other open demands')
    expect(text).toContain('#11')
    expect(text).not.toContain('Will be canceled')
  })

  it('cancels nothing until the user confirms', async () => {
    wrapper = mountDialog()
    await flushPromises()
    expect(cancelDemand).not.toHaveBeenCalled()
  })

  it('performs the cancelation on confirm', async () => {
    wrapper = mountDialog()
    await flushPromises()

    const confirm = wrapper!
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Cancel Demand')
    expect(confirm!.attributes('disabled')).toBeUndefined()
    await confirm!.trigger('click')
    await flushPromises()

    expect(cancelDemand).toHaveBeenCalledWith(9)
    expect(wrapper.emitted('canceled')).toBeTruthy()
  })

  it('keeps the confirm disabled while the impact is still loading', async () => {
    getCancelImpact.mockReturnValue(new Promise<MadeItemDemandCancelImpact>(() => {}))
    wrapper = mountDialog()
    await flushPromises()

    const confirm = wrapper!
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Cancel Demand')
    expect(confirm!.attributes('disabled')).toBeDefined()
  })

  it('keeps the confirm disabled when the impact could not be loaded', async () => {
    getCancelImpact.mockRejectedValue(new Error('network'))
    wrapper = mountDialog()
    await flushPromises()

    const confirm = wrapper!
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Cancel Demand')
    expect(confirm!.attributes('disabled')).toBeDefined()
    await confirm!.trigger('click')
    await flushPromises()
    expect(cancelDemand).not.toHaveBeenCalled()
  })

  it('blocks confirmation when the user may not cancel lots', async () => {
    getCancelImpact.mockResolvedValue(makeImpact({ can_cancel_lots: false }))
    wrapper = mountDialog()
    await flushPromises()

    const confirm = wrapper!
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Cancel Demand')
    // OpenVue passes `disabled` through to the native button rather than
    // declaring it as a prop, so assert on the rendered attribute.
    expect(confirm!.attributes('disabled')).toBeDefined()
    expect(document.body.textContent).toContain('Canceling it needs the permission Manage Production Lots.')
  })

  it('blocks confirmation while a lot it would cancel made good pieces', async () => {
    getCancelImpact.mockResolvedValue(
      makeImpact({ lots: [{ ...makeImpact().lots![0]!, cancel_refused: true }] }),
    )
    wrapper = mountDialog()
    await flushPromises()

    const confirm = wrapper!
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Cancel Demand')
    expect(confirm!.attributes('disabled')).toBeDefined()
    expect(document.body.textContent).toContain('Lot LOT-0003 already made good pieces')
  })
})
