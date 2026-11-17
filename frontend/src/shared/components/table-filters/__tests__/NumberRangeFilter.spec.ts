import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import NumberRangeFilter from '../NumberRangeFilter.vue'
import NumberRangeRowFilter from '../NumberRangeRowFilter.vue'

function mountFilter(modelValue: [number | null, number | null] | null, unit?: string) {
  return mountWithApp(NumberRangeFilter, {
    props: { column: 'Quantity', placeholder: 'Any', modelValue, unit },
    global: { stubs: { Popover: { template: '<div><slot /></div>', methods: { toggle() {} } } } },
  })
}

function summary(wrapper: ReturnType<typeof mountFilter>): string {
  return (wrapper.find('[data-testid="number-range-filter-field"]').element as HTMLInputElement)
    .value
}

describe('NumberRangeFilter', () => {
  it.each([
    [[5, 10], '5 to 10'],
    [[5, null], 'from 5'],
    [[null, 10], 'up to 10'],
    [[7, 7], '7'],
    [null, ''],
  ] as const)('sums up %j as "%s"', (value, text) => {
    const wrapper = mountFilter(value as [number | null, number | null] | null)
    expect(summary(wrapper)).toBe(text)
  })

  it('puts the unit after each number', () => {
    expect(summary(mountFilter([5, 30], 'min'))).toBe('5 min to 30 min')
  })

  it('passes the range inputs through, and clears to null', async () => {
    const wrapper = mountFilter([5, null])

    wrapper.findComponent(NumberRangeRowFilter).vm.$emit('update:modelValue', [5, 9])
    await wrapper.find('[data-testid="number-range-filter-clear"]').trigger('click')

    const emitted = wrapper.emitted('update:modelValue') as unknown[][]
    expect(emitted[0]?.[0]).toEqual([5, 9])
    expect(emitted.at(-1)?.[0]).toBeNull()
  })
})
