import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import KpiRejectedPerSupplierTable from '../KpiRejectedPerSupplierTable.vue'

import type { RejectedPerSupplierRowResult } from '../../types/productionKpiResponse'

function makeRows(): RejectedPerSupplierRowResult[] {
  return [
    {
      supplier_id: 1,
      supplier_name: 'Acme Supplies',
      delivered: 8,
      rejected: 2,
      rejected_ratio: { value: 0.2, numerator: 2, denominator: 10 },
      rejected_lost: 2,
    },
    {
      supplier_id: 2,
      supplier_name: 'Beta Parts',
      delivered: 5,
      rejected: 0,
      rejected_ratio: { value: 0, numerator: 0, denominator: 5 },
      rejected_lost: 0,
    },
  ]
}

describe('KpiRejectedPerSupplierTable', () => {
  it('renders an empty state when there are no rows', () => {
    const wrapper = mountWithApp(KpiRejectedPerSupplierTable, { props: { rows: [] } })
    expect(wrapper.text()).toContain('No deliveries in this period.')
  })

  it('renders delivered, rejected, ratio and lost quantity per supplier', () => {
    const wrapper = mountWithApp(KpiRejectedPerSupplierTable, { props: { rows: makeRows() } })

    expect(wrapper.text()).toContain('Acme Supplies')
    expect(wrapper.text()).toContain('20.0%')
    expect(wrapper.text()).toContain('Beta Parts')
  })

  it('shows a placeholder rather than a value when the rejected ratio has no denominator', () => {
    const wrapper = mountWithApp(KpiRejectedPerSupplierTable, {
      props: {
        rows: [
          {
            supplier_id: 3,
            supplier_name: 'Gamma Co',
            delivered: 0,
            rejected: 0,
            rejected_ratio: { value: null, numerator: 0, denominator: 0 },
            rejected_lost: 0,
          },
        ],
      },
    })

    expect(wrapper.text()).toContain('Gamma Co')
    expect(wrapper.text()).not.toContain('null')
  })
})
