import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'

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
import type { LotResponse } from '../../../types/productionLotsResponse'

function mountCard(status: LotResponse['source_approval_status']) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
  })
  return mountWithApp(LotRecordLot, {
    attachTo: document.body,
    props: {
      lot: makeLotResponse({ demand_status: '', source_approval_status: status }),
      changelog: [],
    },
    global: { plugins: [router] },
  })
}

describe('LotRecordLot supplier material', () => {
  it('says a lot awaiting its first step waits for it rather than that it has no demand', () => {
    const wrapper = mountCard('awaiting_first_step')

    expect(wrapper.text()).toContain('Awaiting First Step')
    expect(wrapper.text()).not.toContain('No demand')
    wrapper.unmount()
  })

  it('says the supplier brings the material of a supplier sourced lot', () => {
    const wrapper = mountCard('supplier_sourced')

    expect(wrapper.text()).toContain('Supplier Material')
    wrapper.unmount()
  })
})
