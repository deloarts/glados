import { describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

vi.mock('../../api/deviceImagesApi', () => ({
  getDeviceImageFiles: () => Promise.resolve([]),
  getDeviceImageBlob: () => Promise.resolve(new Blob(['png'], { type: 'image/png' })),
  uploadDeviceOverview: vi.fn<() => Promise<void>>(),
}))
vi.mock('../../api/productDeviceResourcesApi', () => ({
  getProductDeviceOptions: () => Promise.resolve([]),
  getProductDeviceKinds: () => Promise.resolve([]),
}))

import ProductDeviceOverview from '../ProductDeviceOverview.vue'

async function mountOverview(canEdit: boolean) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(ProductDeviceOverview, {
    pinia,
    props: { productId: 3, devices: [], canEdit },
    global: { stubs: { DeviceOverviewCanvas: true, ProductDeviceOverviewList: true } },
  })
  await flushPromises()
  return wrapper
}

function tooltipOf(button: { element: Element }): string | undefined {
  return (button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null)
    ?.$_ptooltipValue
}

describe('ProductDeviceOverview', () => {
  it('offers the upload to a user who may edit the product', async () => {
    const wrapper = await mountOverview(true)

    expect(wrapper.get('[data-testid="device-overview-upload"]').attributes('disabled')).toBeUndefined()
  })

  it('shows its buttons disabled with the reason to a user who may not edit the product', async () => {
    const wrapper = await mountOverview(false)

    for (const testId of ['device-overview-upload', 'device-overview-clear-marker']) {
      const button = wrapper.get(`[data-testid="${testId}"]`)
      expect(button.attributes('disabled')).toBeDefined()
      expect(tooltipOf(button)).toBe(i18n.global.t('productDevices.tags.noRights'))
    }
  })
})
