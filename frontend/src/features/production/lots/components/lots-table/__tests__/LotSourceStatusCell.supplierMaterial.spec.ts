import { describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeLotSummaryResponse } from '@/test-utils/factories'

import LotSourceStatusCell from '../LotSourceStatusCell.vue'
import type { LotSummaryResponse } from '../../../../types/productionLotsResponse'

function mountCell(lot: LotSummaryResponse) {
  setActivePinia(createPinia())
  return mountWithApp(LotSourceStatusCell, {
    props: { lot, canManage: true, approvingSourceLotId: null },
    global: { directives: { tooltip: Tooltip } },
  })
}

describe('LotSourceStatusCell supplier material', () => {
  it('shows why a lot awaiting its first step has no demand', () => {
    const wrapper = mountCell(
      makeLotSummaryResponse({ source_approval_status: 'awaiting_first_step', demand_status: '' }),
    )

    expect(wrapper.get('[data-testid="supplier-material-tag"]').text()).toBe('Awaiting First Step')
    expect(wrapper.find('[data-testid="source-approve"]').exists()).toBe(false)
  })

  it('shows a supplier sourced lot as supplier material', () => {
    const wrapper = mountCell(
      makeLotSummaryResponse({ source_approval_status: 'supplier_sourced', demand_status: '' }),
    )

    expect(wrapper.get('[data-testid="supplier-material-tag"]').text()).toBe('Supplier Material')
  })

  it('shows a demand created by hand instead', () => {
    const wrapper = mountCell(
      makeLotSummaryResponse({ source_approval_status: 'supplier_sourced', demand_status: 'open' }),
    )

    expect(wrapper.find('[data-testid="supplier-material-tag"]').exists()).toBe(false)
  })
})
