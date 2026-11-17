import { describe, it, expect } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useProductFamiliesStore } from '../../stores/productFamiliesStore'
import ProductFamilySelect from '../ProductFamilySelect.vue'

import type { ProductFamilyResponse } from '../../types/productFamilyResponse'

function makeFamily(overrides: Partial<ProductFamilyResponse>): ProductFamilyResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    created: '2026-01-01',
    changed: '2026-01-01T00:00:00Z',
    changed_by_id: null,
    changed_by: null,
    archived: false,
    name: 'Cylinders',
    label_color: '#ffffff',
    label_font_color: '#000000',
    description: '',
    creator_id: 1,
    creator: null,
    ...overrides,
  }
}

async function mountSelect(modelValue: number | null) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useProductFamiliesStore().items = [
    makeFamily({ id: 1, name: 'Cylinders' }),
    makeFamily({ id: 2, name: 'Valves', archived: true }),
    makeFamily({ id: 3, name: 'Sensors', archived: true }),
  ]
  const wrapper = mountWithApp(ProductFamilySelect, { pinia, props: { modelValue } })
  await flushPromises()
  return wrapper
}

function optionNames(wrapper: Awaited<ReturnType<typeof mountSelect>>): string[] {
  const select = wrapper.findComponent({ name: 'Select' })
  return (select.props('options') as ProductFamilyResponse[]).map((f) => f.name)
}

describe('ProductFamilySelect', () => {
  it('offers only live families', async () => {
    const wrapper = await mountSelect(null)

    expect(optionNames(wrapper)).toEqual(['Cylinders'])
  })

  it('keeps an archived family the item already has', async () => {
    const wrapper = await mountSelect(2)

    expect(optionNames(wrapper)).toEqual(['Cylinders', 'Valves'])
  })
})
