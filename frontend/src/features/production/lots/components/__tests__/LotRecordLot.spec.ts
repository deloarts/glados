import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeLotResponse } from '@/test-utils/factories'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
  },
}))

import LotRecordLot from '../lot-detail/LotRecordLot.vue'
import { useLotDetail } from '@/shared/composables/useLotDetail'
import type { LotResponse } from '../../../types/productionLotsResponse'
import type { LotChangelogEntry } from '../../types/lotChangelogResponse'

function makeLot(overrides: Partial<LotResponse> = {}): LotResponse {
  return makeLotResponse({
    public_id: '3f2504e0-4f89-11d3-9a0c-0305e82c3301',
    created: '2026-07-01T09:00:00',
    creator: {
      id: 1,
      public_id: '22222222-2222-2222-2222-222222222222',
      username: 'phil',
      full_name: 'Sam',
      has_avatar: false,
    },
    ...overrides,
  })
}

// LotRecordLot injects the router (see switchTo's 'page' variant), so
// every mount needs one installed even when the test never navigates.
function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
}

function mountCard(
  lot: LotResponse,
  changelog: LotChangelogEntry[] = [],
  options: { variant?: 'dialog' | 'page'; router?: ReturnType<typeof createTestRouter> } = {},
) {
  const router = options.router ?? createTestRouter()
  return mountWithApp(LotRecordLot, {
    attachTo: document.body,
    props: { lot, changelog, variant: options.variant },
    global: {
      plugins: [router],
    },
  })
}

describe('LotRecordLot', () => {
  it("shows the lot's own note", () => {
    const wrapper = mountCard(makeLot({ note: 'second run, first scrapped' }))
    expect(wrapper.text()).toContain('second run, first scrapped')
    wrapper.unmount()
  })

  it('says the approval is pending rather than that no material is needed', () => {
    const wrapper = mountCard(makeLot({ demand_status: '', source_approval_status: 'pending' }))
    expect(wrapper.text()).toContain('Approval pending')
    expect(wrapper.text()).not.toContain('No demand')
  })

  it('shows quantity with how much is still outstanding', () => {
    const wrapper = mountCard(makeLot({ quantity: 10, quantity_completed: 4 }))
    const text = wrapper.text()
    expect(text).toContain('4 / 10')
    expect(text).toContain('6 left')
    wrapper.unmount()
  })

  it('shows the creator and truncates the ISO created timestamp to a date', () => {
    const wrapper = mountCard(makeLot())
    const text = wrapper.text()
    expect(text).toContain('Sam')
    expect(text).toContain('2026-07-01')
    expect(text).not.toContain('T09:00:00')
    wrapper.unmount()
  })

  it('resolves the changed-by name from the last changelog entry', () => {
    const wrapper = mountCard(makeLot({ changed: '2026-08-06T11:00:00' }), [
      { timestamp: '2026-08-01 10:00:00', username: 'Someone Earlier', message: 'Lot updated.' },
      { timestamp: '2026-08-06 11:00:00', username: 'Sam', message: 'Lot updated.' },
    ])
    expect(wrapper.text()).toContain('Sam')
    expect(wrapper.text()).toContain('2026-08-06')
    wrapper.unmount()
  })

  it('renders the demand status as a tag only when the lot has a demand', () => {
    const withDemand = mountCard(makeLot({ input_demand_id: 7, demand_status: 'ordered' }))
    expect(withDemand.text()).toContain('Ordered')
    withDemand.unmount()

    const without = mountCard(makeLot({ demand_status: '' }))
    expect(without.text()).toContain('No demand')
    without.unmount()
  })

  it('states the alteration flag explicitly either way', () => {
    const plain = mountCard(makeLot({ is_alteration: false }))
    expect(plain.text()).toContain('No')
    plain.unmount()

    const rework = mountCard(makeLot({ is_alteration: true }))
    expect(rework.text()).toContain('rework of an existing item')
    rework.unmount()
  })

  it('carries the status and priority tags that used to sit in the dialog header', () => {
    const wrapper = mountCard(makeLot({ status: 'in_progress', priority: 'high' }))

    const tags = wrapper.findAllComponents({ name: 'Tag' }).map((tag) => tag.props('value'))
    expect(tags).toContain('In Progress')
    expect(tags).toContain('High')

    wrapper.unmount()
  })

  it('scrolls its fields together with the creator/changed footer', () => {
    // .record-card sets overflow: hidden and the row height is flex-derived,
    // so a card without a scroll body silently clips its lower fields. The
    // footer scrolls with them so it never reserves card height of its own.
    const wrapper = mountCard(makeLot())

    const scrollBody = wrapper.find('.card-scroll-body')
    expect(scrollBody.exists()).toBe(true)
    expect(scrollBody.find('.record-meta').exists()).toBe(true)

    wrapper.unmount()
  })

  it('shows the public id', () => {
    const wrapper = mountCard(makeLot())
    expect(wrapper.text()).toContain('3f2504e0-4f89-11d3-9a0c-0305e82c3301')
    wrapper.unmount()
  })

  it('shows no lineage line for an ordinary lot with no origin and no follow-ups', () => {
    const wrapper = mountCard(makeLot())
    expect(wrapper.find('.follow-up-line').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Created from failed QA')
    wrapper.unmount()
  })

  it('shows a clickable origin line naming the failed-QA lot and disposition', () => {
    const wrapper = mountCard(
      makeLot({
        origin_lot_id: 7,
        origin_lot_number: 'LOT-0007',
        origin_disposition: 'rework',
      }),
    )
    expect(wrapper.text()).toContain('Created from failed QA in lot LOT-0007 (rework)')
    wrapper.unmount()
  })

  it('shows one clickable line per follow-up lot, phrased by disposition', () => {
    const wrapper = mountCard(
      makeLot({
        follow_up_lots: [
          { id: 8, lot_number: 'LOT-0008', disposition: 'rework', quantity: 2 },
          { id: 9, lot_number: 'LOT-0009', disposition: 'replacement', quantity: 3 },
        ],
      }),
    )
    const text = wrapper.text()
    expect(text).toContain('Rework lot: LOT-0008 (2)')
    expect(text).toContain('Replacement lot: LOT-0009 (3)')
    wrapper.unmount()
  })

  it('clicking the origin line opens that lot in the shared lot detail dialog', () => {
    const wrapper = mountCard(
      makeLot({ origin_lot_id: 7, origin_lot_number: 'LOT-0007', origin_disposition: 'rework' }),
    )
    wrapper.find('.field-link').trigger('click')
    const { lotId, visible } = useLotDetail()
    expect(lotId.value).toBe(7)
    expect(visible.value).toBe(true)
    wrapper.unmount()
  })

  it('clicking a follow-up line opens that follow-up lot in the shared lot detail dialog', () => {
    const wrapper = mountCard(
      makeLot({
        follow_up_lots: [{ id: 9, lot_number: 'LOT-0009', disposition: 'replacement', quantity: 3 }],
      }),
    )
    wrapper.find('.follow-up-line').trigger('click')
    const { lotId, visible } = useLotDetail()
    expect(lotId.value).toBe(9)
    expect(visible.value).toBe(true)
    wrapper.unmount()
  })

  it('default variant: clicking the origin-lot link goes through the shared lot detail singleton', () => {
    const wrapper = mountCard(
      makeLot({ origin_lot_id: 7, origin_lot_number: 'LOT-0007', origin_disposition: 'rework' }),
    )
    wrapper.find('.field-link').trigger('click')
    const { lotId, visible } = useLotDetail()
    expect(lotId.value).toBe(7)
    expect(visible.value).toBe(true)
    wrapper.unmount()
  })

  it("variant 'page': clicking the origin-lot link navigates the page instead of the singleton", async () => {
    const router = createTestRouter()
    await router.push('/production/lots/1')
    await router.isReady()

    const { lotId, visible } = useLotDetail()
    const lotIdBeforeClick = lotId.value
    const visibleBeforeClick = visible.value

    const wrapper = mountCard(
      makeLot({ origin_lot_id: 7, origin_lot_number: 'LOT-0007', origin_disposition: 'rework' }),
      [],
      { variant: 'page', router },
    )
    await wrapper.find('.field-link').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/production/lots/7')
    expect(lotId.value).toBe(lotIdBeforeClick)
    expect(visible.value).toBe(visibleBeforeClick)
    wrapper.unmount()
  })
})
