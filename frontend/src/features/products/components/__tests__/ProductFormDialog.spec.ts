import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { ProductResponse } from '../../types/productResponse'

const put = vi.fn<(url: string, body: unknown) => Promise<{ data: unknown }>>()
vi.mock('@/features/product-devices/api/plcEnvironmentsApi', () => ({
  getPlcEnvironments: () => Promise.resolve([]),
}))
vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: (url: string, body: unknown) => put(url, body),
  },
}))

import ProductFormDialog from '../ProductFormDialog.vue'

const product: ProductResponse = {
  edit_version: 0,
  id: 4,
  public_id: '11111111-1111-1111-1111-111111111111',
  product_number: 'PN-0004',
  customer_id: null,
  customer: null,
  description: null,
  is_active: true,
  archived: false,
  designated_user_id: 1,
  created: '2026-01-01T00:00:00Z',
  creator_id: 1,
  creator: null,
  designation: 'Press 12',
  machine_type: null,
  installation_site: null,
  installation_location: null,
  planned_placing_on_market: '2026-11-01',
  legal_basis: 'directive',
  plc_environment_id: null,
  contains_pneumatics: false,
  contains_hydraulics: false,
  contains_electrics: false,
  contains_robotics: false,
}

// Opened after mounting, the way a page opens it, so the form is filled from the product.
async function mountDialog() {
  const wrapper = mountWithApp(ProductFormDialog, { attachTo: document.body, props: { visible: false, product } })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

type Wrapper = Awaited<ReturnType<typeof mountDialog>>

function legalBasisSelect(wrapper: Wrapper) {
  const select = wrapper
    .findAllComponents({ name: 'SelectButton' })
    .find((c) => c.attributes('data-testid') === 'p-legal-basis')
  if (!select) throw new Error('no legal basis select')
  return select
}

const warning = () => document.body.querySelector('[data-testid="p-legal-basis-warning"]')

describe('ProductFormDialog', () => {
  it('preselects the legal basis from the planned date and warns about the Directive after the switch', async () => {
    const wrapper = await mountDialog()
    expect(legalBasisSelect(wrapper).props('modelValue')).toBe('directive')
    expect(warning()).toBeNull()

    wrapper.findComponent({ name: 'DatePicker' }).vm.$emit('update:modelValue', new Date(2027, 2, 1))
    await flushPromises()
    expect(legalBasisSelect(wrapper).props('modelValue')).toBe('regulation')
    expect(warning()).toBeNull()

    legalBasisSelect(wrapper).vm.$emit('update:modelValue', 'directive')
    await flushPromises()
    expect(warning()).not.toBeNull()

    wrapper.unmount()
  })

  it('saves the machine data with the product', async () => {
    put.mockResolvedValue({ data: product })
    const wrapper = await mountDialog()

    const location = document.body.querySelector<HTMLInputElement>('[data-testid="p-installation_location"]')
    if (!location) throw new Error('no installation location input')
    location.value = 'Hall 3'
    location.dispatchEvent(new Event('input'))
    document.body.querySelector('form')?.dispatchEvent(new Event('submit'))
    await flushPromises()

    expect(put).toHaveBeenCalledWith(
      '/products/4',
      expect.objectContaining({
        designation: 'Press 12',
        machine_type: null,
        installation_location: 'Hall 3',
        planned_placing_on_market: '2026-11-01',
        legal_basis: 'directive',
        plc_environment_id: null,
        contains_pneumatics: false,
        contains_hydraulics: false,
        contains_electrics: false,
        contains_robotics: false,
      }),
    )

    wrapper.unmount()
  })
})
