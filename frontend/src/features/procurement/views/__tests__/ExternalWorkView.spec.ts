import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeExternalWorkRow } from '../../__tests__/externalWorkFixtures'

import type { PageResponse } from '@/core/api/types'
import type { ExternalWorkQuery, ExternalWorkRow } from '../../types/externalWork'

const getExternalWork = vi.fn<(params?: ExternalWorkQuery) => Promise<PageResponse<ExternalWorkRow>>>()

vi.mock('../../api/getExternalWork', () => ({
  getExternalWork: (params?: ExternalWorkQuery) => getExternalWork(params),
}))

import { useExternalWorkStore } from '../../stores/externalWorkStore'
import ExternalWorkView from '../ExternalWorkView.vue'

function page(items: ExternalWorkRow[]): PageResponse<ExternalWorkRow> {
  return { items, total: items.length, limit: 25, skip: 0 }
}

const hardening = { id: 3, name: { deAT: 'Härten', enGB: 'Hardening' } }
const galvanizing = { id: 4, name: { deAT: 'Verzinken', enGB: 'Galvanizing' } }

async function mountView() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(ExternalWorkView, {
    pinia,
    global: {
      // The lookup filters fetch their options on mount, and the dialogs
      // load their records when opened; neither is under test here.
      stubs: {
        OrderDetailDialog: true,
        MadeItemDetailDialog: true,
        SupplierFormDialog: true,
        LotPositionAssignDialog: true,
        LotPositionProvisionDialog: true,
        LookupSelect: true,
        LookupMultiSelect: true,
      },
    },
  })
  await flushPromises()
  return wrapper
}

describe('ExternalWorkView', () => {
  beforeEach(() => {
    getExternalWork.mockResolvedValue(
      page([
        makeExternalWorkRow({
          position_id: 1,
          fabrication_methods: [hardening],
          latest_pickup_date: '2026-11-24',
          alert: 'not_ready_in_time',
          planned_pickup_date: '2026-11-26',
        }),
        makeExternalWorkRow({
          position_id: 2,
          fabrication_methods: [galvanizing],
          latest_pickup_date: '2026-11-27',
          order_item_id: 9,
          order_id: 7,
          order_number: 'ORD-26-0091',
          order_item_status: 'ordered',
          supplier_name: 'Verzinkerei B',
          product_id: 5,
          product_number: 'PRD-0815',
        }),
        makeExternalWorkRow({
          position_id: 3,
          fabrication_methods: [hardening],
          latest_pickup_date: '2026-12-09',
        }),
      ]),
    )
  })

  it('groups the page by method, each header counting its rows', async () => {
    const wrapper = await mountView()

    const groups = wrapper.findAll('[data-testid="external-work-group"]')
    expect(groups).toHaveLength(2)
    // Groups sort by their label, Galvanizing before Hardening.
    expect(groups[0]!.text()).toContain('Galvanizing')
    expect(groups[0]!.text()).toContain('1 position')
    expect(groups[1]!.text()).toContain('Hardening')
    expect(groups[1]!.text()).toContain('2 positions')
    expect(groups[1]!.text()).toContain('1 critical')
    wrapper.unmount()
  })

  it('says why a row is critical and links its order', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('too late to send it out in time')
    expect(wrapper.text()).toContain('ORD-26-0091')
    expect(wrapper.text()).toContain('Not assigned')
    wrapper.unmount()
  })

  it('shows the product number next to the project in the lot column', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('PRJ-26-031 · PRD-0815')
    wrapper.unmount()
  })

  it('names the grouping on the button instead of filling it', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('Group by Method')
    wrapper.unmount()
  })

  it('shows the quantity with its unit', async () => {
    const wrapper = await mountView()

    expect(wrapper.text()).toContain('12 pcs')
    wrapper.unmount()
  })

  it('orders the columns status, quantity, lot, item, method, supplier, dates, note', async () => {
    const wrapper = await mountView()

    const headers = wrapper.findAll('th').map((th) => th.text().trim())
    expect(headers.slice(0, 11)).toEqual([
      '#',
      'Status',
      'Quantity',
      'Lot / Project',
      'Item',
      'Method',
      'Supplier',
      'Ready From',
      'Send By',
      'Back By',
      'Note',
    ])
    wrapper.unmount()
  })

  it('shows the order under its supplier', async () => {
    const wrapper = await mountView()

    const orderLink = wrapper.get('[data-testid="external-work-order-link"]')
    expect(orderLink.text()).toBe('ORD-26-0091')
    expect(orderLink.element.parentElement?.textContent).toContain('Verzinkerei B')
    wrapper.unmount()
  })

  it('sends a column filter to the list', async () => {
    const wrapper = await mountView()

    useExternalWorkStore().stages = ['unassigned']
    await flushPromises()

    expect(getExternalWork).toHaveBeenLastCalledWith({ skip: 0, limit: 25, stages: ['unassigned'] })
    wrapper.unmount()
  })

  it('asks for the critical rows only once the toggle is pressed', async () => {
    const wrapper = await mountView()
    expect(getExternalWork).toHaveBeenLastCalledWith({ skip: 0, limit: 25 })

    await wrapper.get('[data-testid="external-work-only-critical"]').trigger('click')
    await flushPromises()

    expect(getExternalWork).toHaveBeenLastCalledWith({ skip: 0, limit: 25, only_critical: true })
    wrapper.unmount()
  })
})
