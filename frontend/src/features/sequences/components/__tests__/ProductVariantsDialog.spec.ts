import { afterEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { ProductVariant, ProductVariantRequest } from '../../types/sequence'

const getVariantsMock = vi.fn<(productId: number, includeArchived: boolean) => Promise<ProductVariant[]>>()
const saveVariantsMock = vi.fn<(productId: number, variants: ProductVariantRequest[]) => Promise<ProductVariant[]>>()
vi.mock('../../api/productVariantsApi', () => ({
  getProductVariants: (productId: number, includeArchived: boolean) => getVariantsMock(productId, includeArchived),
  saveProductVariants: (productId: number, variants: ProductVariantRequest[]) =>
    saveVariantsMock(productId, variants),
}))

import ProductVariantsDialog from '../ProductVariantsDialog.vue'

function variant(id: number, name: string, archived = false): ProductVariant {
  return { id, public_id: `v${id}`, product_id: 3, name, sort_order: id, archived }
}

async function mountDialog(canEdit = true) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(ProductVariantsDialog, {
    pinia,
    attachTo: document.body,
    props: { productId: 3, canEdit, visible: false },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function body(selector: string): DOMWrapper<Element> {
  return new DOMWrapper(document.body.querySelector(selector)!)
}

function all(selector: string): DOMWrapper<Element>[] {
  return [...document.body.querySelectorAll(selector)].map((el) => new DOMWrapper(el))
}

afterEach(() => {
  getVariantsMock.mockReset()
  saveVariantsMock.mockReset()
  document.body.innerHTML = ''
})

describe('ProductVariantsDialog', () => {
  it('saves the list in its order and brings back an archived variant by name', async () => {
    getVariantsMock.mockResolvedValue([variant(1, 'Clamp 60'), variant(2, 'Clamp 80'), variant(3, 'Clamp 100', true)])
    saveVariantsMock.mockResolvedValue([])
    const wrapper = await mountDialog()

    expect(all('[data-testid="product-variant-name"]').map((input) => (input.element as HTMLInputElement).value)).toEqual([
      'Clamp 60',
      'Clamp 80',
    ])
    await all('[data-testid="product-variant-remove"]')[0]!.trigger('click')
    await body('[data-testid="product-variant-add"]').trigger('click')
    await all('[data-testid="product-variant-name"]')[1]!.setValue('clamp 100')
    await body('[data-testid="product-variants-save"]').trigger('click')
    await flushPromises()

    expect(saveVariantsMock).toHaveBeenCalledWith(3, [
      { id: 2, name: 'Clamp 80' },
      { id: 3, name: 'clamp 100' },
    ])
    wrapper.unmount()
  })

  it('refuses two variants of the same name', async () => {
    getVariantsMock.mockResolvedValue([variant(1, 'Clamp 60')])
    const wrapper = await mountDialog()
    await body('[data-testid="product-variant-add"]').trigger('click')
    await all('[data-testid="product-variant-name"]')[1]!.setValue('CLAMP 60')
    await body('[data-testid="product-variants-save"]').trigger('click')
    await flushPromises()
    expect(saveVariantsMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('This name appears twice.')
    wrapper.unmount()
  })

  it('shows the editing buttons disabled without the rights to edit the product', async () => {
    getVariantsMock.mockResolvedValue([variant(1, 'Clamp 60')])
    const wrapper = await mountDialog(false)
    expect(body('[data-testid="product-variants-no-rights"]').exists()).toBe(true)
    expect(body('[data-testid="product-variant-add"]').attributes('disabled')).toBeDefined()
    expect(body('[data-testid="product-variant-remove"]').attributes('disabled')).toBeDefined()
    expect(body('[data-testid="product-variants-save"]').attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
})
