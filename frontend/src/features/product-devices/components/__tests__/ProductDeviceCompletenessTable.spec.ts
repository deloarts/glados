import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { ProductDevice, ProductDeviceCompleteness } from '../../types/productDevice'

const setCheckMock = vi.fn<(deviceId: number, plan: string, checked: boolean) => Promise<void>>()
vi.mock('../../api/deviceCompletenessApi', () => ({
  setDeviceCheck: (deviceId: number, plan: string, checked: boolean) => setCheckMock(deviceId, plan, checked),
}))

import ProductDeviceCompletenessTable from '../ProductDeviceCompletenessTable.vue'
import { useProductDevicesViewStore } from '../../stores/productDevicesViewStore'

function device(id: number, name: string): ProductDevice {
  return { id, name_utf8: name, archived: false } as ProductDevice
}

const COMPLETENESS: ProductDeviceCompleteness[] = [
  {
    device_id: 1,
    checks: [
      { plan: 'cad_assembly', checked_by_name: 'Ada', checked_at: '2026-10-24T10:00:00Z' },
      { plan: 'eplan', checked_by_name: 'Ada', checked_at: '2026-10-24T10:00:00Z' },
    ],
    sequence_coverage: 'released',
  },
  { device_id: 2, checks: [], sequence_coverage: 'none' },
]

async function mountTable(canEdit = true) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(ProductDeviceCompletenessTable, {
    pinia,
    props: {
      devices: [device(1, 'B01 Zylinder P1'), device(2, 'B01 Greifer P1')],
      completeness: COMPLETENESS,
      disciplines: { pneumatics: false, hydraulics: false, electrics: true, robotics: false },
      canEdit,
    },
  })
  await flushPromises()
  return wrapper
}

afterEach(() => setCheckMock.mockReset())

describe('ProductDeviceCompletenessTable', () => {
  it('shows one column per plan of the disciplines and ticks a plan', async () => {
    setCheckMock.mockResolvedValue()
    const wrapper = await mountTable()
    expect(wrapper.text()).toContain('CAD assembly')
    expect(wrapper.text()).toContain('EPLAN')
    expect(wrapper.text()).not.toContain('Pneumatics plan')
    expect(wrapper.find('[data-testid="coverage-2"]').text()).toBe('In none')

    await wrapper.find('[data-testid="check-eplan-2"] input').setValue(true)
    await flushPromises()
    expect(setCheckMock).toHaveBeenCalledWith(2, 'eplan', true)
    expect(wrapper.emitted('changed')).toHaveLength(1)
  })

  it('hides complete devices with Only Incomplete', async () => {
    const wrapper = await mountTable()
    useProductDevicesViewStore().onlyIncomplete = true
    await flushPromises()
    expect(wrapper.text()).not.toContain('B01 Zylinder P1')
    expect(wrapper.text()).toContain('B01 Greifer P1')
  })

  it('shows the ticks disabled without the rights to edit the product', async () => {
    const wrapper = await mountTable(false)
    expect(wrapper.find('[data-testid="check-eplan-2"] input').attributes('disabled')).toBeDefined()
  })
})
