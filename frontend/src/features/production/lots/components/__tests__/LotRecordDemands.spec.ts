import { describe, it, expect, vi } from 'vitest'


vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: [] }),
  },
}))

import LotRecordDemands from '../lot-detail/LotRecordDemands.vue'
import type { LotDemandResponse } from '../../../types/productionLotsResponse'
import { mountWithApp } from '@/test-utils/mountWithApp'

function makeDemand(overrides: Partial<LotDemandResponse> = {}): LotDemandResponse {
  return {
    id: 1,
    public_id: '44444444-4444-4444-4444-444444444444',
    status: 'open',
    created: '2026-07-01',
    changed: null,
    changed_by: null,
    changed_by_id: null,
    quantity: 111,
    unit: 'PCS',
    items_per_unit: 1,
    high_priority: false,
    notify_on_delivery: false,
    note: null,
    desired_delivery_date: '2026-08-01',
    creator_id: 1,
    creator: {
      id: 1,
      public_id: '22222222-2222-2222-2222-222222222222',
      username: 'phil',
      full_name: 'Sam',
      has_avatar: false,
    },
    made_item_id: 1,
    item_part_number: 'PN-1',
    item_revision: 'A',
    item_article_name: 'Bracket',
    // Not read by this card, and building a full MadeItemResponse here
    // would add noise, same idiom as MadeItemsDemandsManageLots.spec.ts.
    item: {} as LotDemandResponse['item'],
    project_id: 42,
    project_number: 'P-001',
    project_customer: 'Acme',
    project_description: '',
    project_status: 'active',
    is_alteration: false,
    alteration_of_made_item_id: null,
    alteration_of_made_item_part_number: '',
    alteration_of_made_item_revision: '',
    alteration_of_made_item_article_name: '',
    allocated_quantity: 91,
    bucket_id: null,
    actions: [],
    canceled_at: null,
    fulfilled_manually_at: null,
    ...overrides,
  }
}

function mountCard(demands: LotDemandResponse[], loading = false) {
  return mountWithApp(LotRecordDemands, {
    attachTo: document.body,
    props: { demands, loading },
  })
}

describe('LotRecordDemands', () => {
  it('lays each demand out as stacked label/value fields, like the Lot card', () => {
    const wrapper = mountCard([makeDemand()])

    // Same grid + field structure the other record cards use.
    expect(wrapper.find('.detail-grid').exists()).toBe(true)
    const labels = wrapper.findAll('.field-label').map((l) => l.text())
    expect(labels).toContain('Demand')
    expect(labels).toContain('Status')
    expect(labels).toContain('Qty')
    expect(labels).toContain('Requested by')

    wrapper.unmount()
  })

  it('shows the allocated-of-total quantity and the requester by name', () => {
    const wrapper = mountCard([makeDemand()])

    const text = wrapper.text()
    expect(text).toContain('#1')
    expect(text).toContain('91 / 111 PCS')
    expect(text).toContain('Sam')

    wrapper.unmount()
  })

  it('flags a high-priority demand', () => {
    const wrapper = mountCard([makeDemand({ high_priority: true })])
    expect(wrapper.find('.demand-flag').exists()).toBe(true)
    wrapper.unmount()
  })

  it('separates multiple demands into their own entries', () => {
    const wrapper = mountCard([makeDemand({ id: 1 }), makeDemand({ id: 2 })])
    expect(wrapper.findAll('.demand-entry')).toHaveLength(2)
    wrapper.unmount()
  })

  it('shows an empty state when the lot came from no demand', () => {
    const wrapper = mountCard([])
    expect(wrapper.text()).toContain('This lot is not linked to a made-item demand.')
    wrapper.unmount()
  })
})
