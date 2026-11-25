import { describe, expect, it } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeLotResponse } from '@/test-utils/factories'

import LotRecordSourceDemand from '../lot-detail/LotRecordSourceDemand.vue'
import type { LotResponse } from '../../../types/productionLotsResponse'

function mountDemand(lot: LotResponse, manageMode = false) {
  return mountWithApp(LotRecordSourceDemand, {
    attachTo: document.body,
    props: {
      lot,
      sourceItemDemand: null,
      sourceItemDemandArrived: 0,
      summary: null,
      allocations: [],
      sourceOrder: null,
      manageMode,
      canWrite: true,
      canApprove: true,
    },
  })
}

function lot(status: LotResponse['source_approval_status']): LotResponse {
  return makeLotResponse({
    status: 'planned',
    source_item_id: 5,
    input_demand_id: null,
    source_approval_status: status,
  })
}

describe('LotRecordSourceDemand supplier material', () => {
  it('explains that a lot awaiting its first step needs no demand', () => {
    const wrapper = mountDemand(lot('awaiting_first_step'))

    expect(wrapper.get('[data-testid="supplier-material-tag"]').text()).toBe('Awaiting First Step')
    expect(wrapper.text()).toContain('A demand is created only if it is made in house.')
    expect(wrapper.find('[data-testid="source-approve"]').exists()).toBe(false)
  })

  it('explains that a supplier sourced lot gets its material from the supplier', () => {
    const wrapper = mountDemand(lot('supplier_sourced'))

    expect(wrapper.get('[data-testid="supplier-material-tag"]').text()).toBe('Supplier Material')
    expect(wrapper.text()).toContain('brings the material, so no demand is needed.')
  })

  it('keeps the demand button for material sent to the supplier by hand', () => {
    const wrapper = mountDemand(lot('supplier_sourced'), true)

    const button = wrapper
      .findAllComponents({ name: 'Button' })
      .find((b) => b.props('label') === 'Demand Source Item')
    expect(button).toBeDefined()
    expect(button!.attributes('disabled')).toBeUndefined()
  })
})
