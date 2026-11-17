import { describe, it, expect } from 'vitest'

import { mountWithApp } from '@/test-utils/mountWithApp'
import TextFieldsFilter from '../TextFieldsFilter.vue'

const FIELDS = [
  { key: 'dimension', label: 'Dimension' },
  { key: 'material', label: 'Material' },
]

function mountFilter(values: Record<string, string>) {
  return mountWithApp(TextFieldsFilter, {
    props: { column: 'Item', fields: FIELDS, placeholder: 'Any', modelValue: values },
    global: { stubs: { Popover: { template: '<div><slot /></div>', methods: { toggle() {} } } } },
  })
}

describe('TextFieldsFilter', () => {
  it('sums up the set fields in its one field', () => {
    const wrapper = mountFilter({ dimension: '10mm', material: '' })

    const field = wrapper.find('[data-testid="text-fields-filter-field"]')
    expect((field.element as HTMLInputElement).value).toBe('Dimension: 10mm')
  })

  it('emits the values with the edited field, and clears them all', async () => {
    const wrapper = mountFilter({ dimension: '10mm', material: '' })

    await wrapper.find('[data-testid="text-fields-filter-material"]').setValue('Steel')
    await wrapper.find('[data-testid="text-fields-filter-clear"]').trigger('click')

    const emitted = wrapper.emitted('update:modelValue') as Record<string, string>[][]
    expect(emitted[0]?.[0]).toEqual({ dimension: '10mm', material: 'Steel' })
    expect(emitted.at(-1)?.[0]).toEqual({ dimension: '', material: '' })
  })
})
