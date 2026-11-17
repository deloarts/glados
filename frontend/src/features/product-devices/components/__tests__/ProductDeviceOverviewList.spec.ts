import { describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useProductDevicesViewStore } from '../../stores/productDevicesViewStore'
import type { ProductDevice } from '../../types/productDevice'
import ProductDeviceOverviewList from '../ProductDeviceOverviewList.vue'

function device(id: number, name: string, placed: boolean, renderingId: number | null): ProductDevice {
  return {
    id,
    name_utf8: name,
    marker_x: placed ? 0.5 : null,
    marker_y: placed ? 0.5 : null,
    rendering_file_id: renderingId,
  } as ProductDevice
}

function mountList(selectedId: number | null = null, hiddenIds: Set<number> = new Set()) {
  const pinia = createPinia()
  setActivePinia(pinia)
  return mountWithApp(ProductDeviceOverviewList, {
    pinia,
    props: {
      devices: [device(1, 'B01 Hubzylinder P1', true, 40), device(2, 'B02 Greifer P1', false, null)],
      imageUrl: (fileId: number | null) => (fileId === null ? null : `blob:${fileId}`),
      typeLabel: (d: ProductDevice) => (d.id === 1 ? 'Linear drive | Pneumatics' : ''),
      selectedId,
      hoveredId: null,
      hiddenIds,
    },
  })
}

describe('ProductDeviceOverviewList', () => {
  it('lists every device with its image and name, marking unplaced ones', () => {
    const wrapper = mountList()
    const rows = wrapper.findAll('[data-testid="device-overview-list-row"]')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.text()).toContain('B01 Hubzylinder P1')
    expect(rows[0]!.get('img').attributes('src')).toBe('blob:40')
    expect(rows[1]!.find('img').exists()).toBe(false)
    expect(rows[1]!.classes()).toContain('unplaced')
  })

  it('numbers the devices in list order', () => {
    const wrapper = mountList()
    const numbers = wrapper.findAll('[data-testid="device-overview-list-number"]')
    expect(numbers.map((n) => n.text())).toEqual(['1', '2'])
  })

  it('shows the kind and medium under the name', () => {
    const wrapper = mountList()
    const rows = wrapper.findAll('[data-testid="device-overview-list-row"]')
    expect(rows[0]!.get('.device-type').text()).toBe('Linear drive | Pneumatics')
    expect(rows[1]!.find('.device-type').exists()).toBe(false)
  })

  it('toggles a marker without picking the device', async () => {
    const wrapper = mountList(null, new Set([2]))
    const toggles = wrapper.findAll('[data-testid="device-overview-toggle-hidden"]')
    await toggles[0]!.trigger('click')
    expect(wrapper.emitted('toggle-hidden')).toEqual([[1]])
    expect(wrapper.emitted('select')).toBeUndefined()
    const rows = wrapper.findAll('[data-testid="device-overview-list-row"]')
    expect(rows[1]!.classes()).toContain('concealed')
    expect(rows[0]!.classes()).not.toContain('concealed')
  })

  it('hides and shows every marker at once', async () => {
    const wrapper = mountList(null, new Set([2]))
    await wrapper.get('[data-testid="device-overview-hide-all"]').trigger('click')
    await wrapper.get('[data-testid="device-overview-show-all"]').trigger('click')
    expect(wrapper.emitted('hide-all')).toHaveLength(1)
    expect(wrapper.emitted('show-all')).toHaveLength(1)
  })

  it('hides the device cards when Hide detailed is pressed', async () => {
    const wrapper = mountList()
    const view = useProductDevicesViewStore()
    expect(view.hideDetails).toBe(false)
    await wrapper.get('[data-testid="product-devices-hide-details"]').trigger('click')
    expect(view.hideDetails).toBe(true)
  })

  it('disables show all while nothing is hidden', () => {
    const wrapper = mountList()
    expect(wrapper.get('[data-testid="device-overview-show-all"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="device-overview-hide-all"]').attributes('disabled')).toBeUndefined()
  })

  it('reports hovering and picking a device', async () => {
    const wrapper = mountList()
    const row = wrapper.findAll('[data-testid="device-overview-list-row"]')[0]!
    await row.trigger('mouseenter')
    await row.trigger('click')
    expect(wrapper.emitted('hover')).toEqual([[1]])
    expect(wrapper.emitted('select')).toEqual([[1]])
    await wrapper.get('ul').trigger('mouseleave')
    expect(wrapper.emitted('hover')?.at(-1)).toEqual([null])
  })

  it('marks the picked device', () => {
    const wrapper = mountList(2)
    const rows = wrapper.findAll('[data-testid="device-overview-list-row"]')
    expect(rows[1]!.attributes('aria-pressed')).toBe('true')
    expect(rows[0]!.attributes('aria-pressed')).toBe('false')
  })
})
