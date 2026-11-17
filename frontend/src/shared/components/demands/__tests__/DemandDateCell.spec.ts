import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'

import DemandDateCell from '../DemandDateCell.vue'

describe('DemandDateCell', () => {
  it('renders the date when one is set', () => {
    const wrapper = mountWithApp(DemandDateCell, {
      props: { value: '2026-01-01' },
    })

    expect(wrapper.text()).toBe('2026-01-01')
  })

  it('falls back to the empty placeholder when the value is null', () => {
    const wrapper = mountWithApp(DemandDateCell, {
      props: { value: null },
    })

    // The fresh Pinia instance mountWithApp sets up has never fetched host
    // capabilities, so getEmptyPlaceholder() reads hostStore's own default.
    expect(wrapper.text()).toBe('-')
  })

  it('falls back to the empty placeholder when the value is undefined', () => {
    const wrapper = mountWithApp(DemandDateCell, {
      props: { value: undefined },
    })

    expect(wrapper.text()).toBe('-')
  })
})
