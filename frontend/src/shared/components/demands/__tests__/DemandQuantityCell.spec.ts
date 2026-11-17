import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'

import DemandQuantityCell from '../DemandQuantityCell.vue'

describe('DemandQuantityCell', () => {
  it('renders the quantity and unit separated by a space', () => {
    const wrapper = mountWithApp(DemandQuantityCell, {
      props: { quantity: 5, unit: 'PCS' },
    })

    expect(wrapper.text()).toBe('5 PCS')
  })

  it('renders whatever unit label the caller resolved, formatted or raw', () => {
    const wrapper = mountWithApp(DemandQuantityCell, {
      props: { quantity: 12, unit: 'mm' },
    })

    expect(wrapper.text()).toBe('12 mm')
  })
})
