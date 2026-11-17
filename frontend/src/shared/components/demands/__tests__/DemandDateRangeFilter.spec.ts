import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'

import DemandDateRangeFilter from '../DemandDateRangeFilter.vue'

describe('DemandDateRangeFilter', () => {
  it('passes the placeholder through to the underlying DatePicker', () => {
    const wrapper = mountWithApp(DemandDateRangeFilter, {
      props: { modelValue: null, placeholder: 'Filter by...' },
    })

    const datePicker = wrapper.findComponent({ name: 'DatePicker' })
    expect(datePicker.props('placeholder')).toBe('Filter by...')
    expect(datePicker.props('selectionMode')).toBe('range')
  })

  it('re-emits update:modelValue from the DatePicker', async () => {
    const wrapper = mountWithApp(DemandDateRangeFilter, {
      props: { modelValue: null, placeholder: 'Filter by...' },
    })

    const range: [Date, Date] = [new Date('2026-01-01'), new Date('2026-01-31')]
    await wrapper.findComponent({ name: 'DatePicker' }).vm.$emit('update:modelValue', range)

    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([range])
  })

  it('re-emits clear-click from the DatePicker', async () => {
    const wrapper = mountWithApp(DemandDateRangeFilter, {
      props: { modelValue: null, placeholder: 'Filter by...' },
    })

    await wrapper.findComponent({ name: 'DatePicker' }).vm.$emit('clear-click')

    expect(wrapper.emitted('clear-click')).toHaveLength(1)
  })
})
