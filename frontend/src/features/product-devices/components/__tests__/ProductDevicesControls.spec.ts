import { describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import ProductDevicesControls from '../ProductDevicesControls.vue'

function mountControls(canEdit: boolean) {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mountWithApp(ProductDevicesControls, { pinia, props: { canEdit } })
}

describe('ProductDevicesControls', () => {
  it('offers New Device to a user who may edit the product', () => {
    const wrapper = mountControls(true)

    expect(wrapper.get('[data-testid="product-device-create"]').attributes('disabled')).toBeUndefined()
  })

  it('shows New Device disabled with the reason to a user who may not edit the product', () => {
    const wrapper = mountControls(false)

    const create = wrapper.get('[data-testid="product-device-create"]')
    expect(create.attributes('disabled')).toBeDefined()
    const span = create.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe(i18n.global.t('productDevices.tags.noRights'))
  })
})
