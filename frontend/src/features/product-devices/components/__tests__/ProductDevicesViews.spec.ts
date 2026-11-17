import { describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import ProductDevicesViews from '../ProductDevicesViews.vue'
import { useProductDevicesViewStore } from '../../stores/productDevicesViewStore'

function mountViews() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(ProductDevicesViews, { pinia })
  return { wrapper, view: useProductDevicesViewStore() }
}

describe('ProductDevicesViews', () => {
  it('offers the names with product number in the list only', async () => {
    const { wrapper, view } = mountViews()
    expect(wrapper.find('[data-testid="product-devices-full-names"]').exists()).toBe(true)

    view.mode = 'overview'
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="product-devices-full-names"]').exists()).toBe(false)
  })
})
