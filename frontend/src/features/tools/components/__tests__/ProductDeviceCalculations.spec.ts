import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import type { ProductDevice } from '@/features/product-devices'

interface Row {
  id: number
  document_number: string
  title: string
  tool: string
  revision: string
  released_at: string | null
  product_device_id: number | null
}

const getCalculations = vi.fn<(params: Record<string, unknown>) => Promise<{ total: number; items: Row[] }>>()
const setCalculationDevice = vi.fn<(id: number, deviceId: number | null) => Promise<void>>()

vi.mock('@/features/tools/api/getCalculations', () => ({
  getCalculations: (params: Record<string, unknown>) => getCalculations(params),
}))
vi.mock('@/features/tools/api/setCalculationDevice', () => ({
  setCalculationDevice: (id: number, deviceId: number | null) => setCalculationDevice(id, deviceId),
}))

import ProductDeviceCalculations from '../ProductDeviceCalculations.vue'

const device = { id: 5, product_id: 3, product_number: 'M26001' } as ProductDevice

function row(overrides: Partial<Row>): Row {
  return {
    id: 1,
    document_number: 'CALC-26-0001',
    title: 'Axis sizing',
    tool: 'drive_sizing',
    revision: 'A',
    released_at: null,
    product_device_id: 5,
    ...overrides,
  }
}

async function mountSection(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = { id: 1, permissions, is_systemuser: false } as never
  const wrapper = mountWithApp(ProductDeviceCalculations, { pinia, props: { device } })
  await flushPromises()
  return wrapper
}

describe('ProductDeviceCalculations', () => {
  beforeEach(() => {
    setCalculationDevice.mockReset()
    setCalculationDevice.mockResolvedValue(undefined)
    getCalculations.mockReset()
    getCalculations.mockImplementation(async (params) => {
      if (params.product_device_id === 5) {
        return {
          total: 2,
          items: [row({}), row({ id: 2, document_number: 'CALC-26-0002', released_at: '2026-10-24T00:00:00Z' })],
        }
      }
      // The product's drafts: one without a device can be linked.
      return { total: 2, items: [row({ id: 3, document_number: 'CALC-26-0003', product_device_id: null }), row({})] }
    })
  })

  it('lists the linked calculations and lets only a draft be unlinked', async () => {
    const wrapper = await mountSection(['write:calculations'])
    const rows = wrapper.findAll('[data-testid="device-calculation"]')
    expect(rows).toHaveLength(2)
    expect(rows[0]!.text()).toContain('CALC-26-0001')
    const unlinks = wrapper.findAll('[data-testid="device-calculation-unlink"]')
    expect(unlinks[0]!.attributes('disabled')).toBeUndefined()
    expect(unlinks[1]!.attributes('disabled')).toBeDefined()

    await unlinks[0]!.trigger('click')
    await flushPromises()
    expect(setCalculationDevice).toHaveBeenCalledWith(1, null)
  })

  it('offers only the product drafts without a device for linking', async () => {
    const wrapper = await mountSection(['write:calculations'])
    expect(getCalculations).toHaveBeenCalledWith({ related_product_id: 3, released: false, limit: 200 })
    const picker = wrapper.findComponent({ name: 'Select' })
    expect((picker.props('options') as Array<{ value: number }>).map((o) => o.value)).toEqual([3])

    picker.vm.$emit('update:modelValue', 3)
    await flushPromises()
    expect(setCalculationDevice).toHaveBeenCalledWith(3, 5)
  })

  it('shows the actions disabled without write:calculations', async () => {
    const wrapper = await mountSection([])
    expect(wrapper.find('[data-testid="device-calculation-unlink"]').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-testid="calc-new"]').attributes('disabled')).toBeDefined()
  })
})
