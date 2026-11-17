import { afterEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { ProductResponse } from '../../types/productResponse'
import type { ProductRenumberImpact } from '../../api/getRenumberImpact'

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

const impactMock = vi.fn<(productId: number, newNumber: string) => Promise<ProductRenumberImpact>>()
vi.mock('../../api/getRenumberImpact', () => ({
  getRenumberImpact: (productId: number, newNumber: string) => impactMock(productId, newNumber),
}))

import ProductFormDialog from '../ProductFormDialog.vue'

const product: ProductResponse = {
  edit_version: 0,
  id: 4,
  public_id: '11111111-1111-1111-1111-111111111111',
  product_number: 'M26001',
  customer_id: null,
  customer: null,
  description: null,
  is_active: true,
  archived: false,
  designated_user_id: 1,
  created: '2026-01-01T00:00:00Z',
  creator_id: 1,
  creator: null,
  designation: null,
  machine_type: null,
  installation_site: null,
  installation_location: null,
  planned_placing_on_market: null,
  legal_basis: null,
  plc_environment_id: null,
  contains_pneumatics: false,
  contains_hydraulics: false,
  contains_electrics: false,
  contains_robotics: false,
}

const impact: ProductRenumberImpact = {
  device_count: 4,
  device_examples: [
    {
      old_name: 'M26001_B01_Push_Cylinder_P1',
      new_name: 'M26002_B01_Push_Cylinder_P1',
    },
  ],
  released_document_count: 0,
  export_count: 0,
}

async function changeNumberAndSubmit() {
  const wrapper = mountWithApp(ProductFormDialog, {
    attachTo: document.body,
    props: { visible: false, product },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  await new DOMWrapper(document.body.querySelector('#p-number')!).setValue('M26002')
  await new DOMWrapper(document.body.querySelector('form.product-form')!).trigger('submit')
  await flushPromises()
  return wrapper
}

afterEach(() => {
  put.mockReset()
  impactMock.mockReset()
  document.body.innerHTML = ''
})

describe('ProductFormDialog renumbering', () => {
  it('shows what a new number affects before saving', async () => {
    impactMock.mockResolvedValue(impact)
    const wrapper = await changeNumberAndSubmit()

    expect(impactMock).toHaveBeenCalledWith(4, 'M26002')
    expect(put).not.toHaveBeenCalled()
    const dialog = document.body.querySelector('[data-testid="product-renumber-dialog"]')
    expect(dialog?.textContent).toContain('M26002_B01_Push_Cylinder_P1')
    expect(dialog?.textContent).toContain('and 3 more')
    expect(document.body.querySelector('[data-testid="renumber-documents"]')).toBeNull()
    expect(document.body.querySelector('[data-testid="renumber-external"]')).not.toBeNull()
    wrapper.unmount()
  })

  it('saves once the change is confirmed', async () => {
    impactMock.mockResolvedValue(impact)
    put.mockResolvedValue({ data: { ...product, product_number: 'M26002' } })
    const wrapper = await changeNumberAndSubmit()

    await new DOMWrapper(document.body.querySelector('[data-testid="renumber-confirm"]')!).trigger(
      'click',
    )
    await flushPromises()

    expect(put).toHaveBeenCalledTimes(1)
    expect(put.mock.calls[0]![1]).toMatchObject({ product_number: 'M26002' })
    wrapper.unmount()
  })
})
