import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { reactive, ref } from 'vue'

import { LiveResource } from '@/core/realtime/resources'
import type { LiveSignal } from '@/core/realtime/types'
import { mountWithApp } from '@/test-utils/mountWithApp'
import type { ProductDevice } from '../../types/productDevice'

const subscribers = new Map<string, (signal: LiveSignal) => void>()
const fakeLiveStore = reactive({
  reconnectCount: ref(0),
  on: (resource: string, handler: (signal: LiveSignal) => void) => {
    subscribers.set(resource, handler)
    return () => subscribers.delete(resource)
  },
})
vi.mock('@/core/realtime/liveStore', () => ({ useLiveStore: () => fakeLiveStore }))

const getDevicesMock = vi.fn<(productId: number, includeArchived: boolean) => Promise<ProductDevice[]>>()
vi.mock('../../api/productDevicesApi', () => ({
  getProductDevices: (productId: number, includeArchived: boolean) =>
    getDevicesMock(productId, includeArchived),
  setProductDeviceArchived: vi.fn<() => Promise<void>>(),
}))
vi.mock('../../api/deviceCompletenessApi', () => ({ getDeviceCompleteness: () => Promise.resolve([]) }))
vi.mock('../../api/deviceImagesApi', () => ({
  getDeviceSlotFiles: () => Promise.resolve([]),
  uploadDeviceSlotFile: vi.fn<() => Promise<void>>(),
  removeDeviceSlotFile: vi.fn<() => Promise<void>>(),
  getDeviceImageBlob: () => Promise.resolve(new Blob(['png'], { type: 'image/png' })),
}))
vi.mock('../../api/productDeviceResourcesApi', () => ({
  getProductDeviceOptions: () => Promise.resolve([]),
  getProductDeviceKinds: () => Promise.resolve([]),
}))

import ProductDevicesTab from '../ProductDevicesTab.vue'
import { useProductDevicesViewStore } from '../../stores/productDevicesViewStore'

function device(id: number, name: string): ProductDevice {
  return {
    edit_version: 0,
    id,
    public_id: `d${id}`,
    created: '2026-10-22T00:00:00Z',
    changed: '2026-10-22T00:00:00Z',
    changed_by: null,
    changed_by_id: null,
    archived: false,
    product_id: 3,
    product_number: 'M26001',
    location: 'B01',
    name,
    driving_medium_id: 7,
    driving_medium_letter: 'P',
    number: 1,
    name_utf8: `B01 ${name} P1`,
    name_ascii: `B01_${name}_P1`,
    full_name_utf8: `M26001 B01 ${name} P1`,
    full_name_ascii: `M26001_B01_${name}_P1`,
    kind_id: 1,
    description: null,
    initial_position_id: null,
    initial_position_value: null,
    energy_loss_behaviour_id: null,
    energy_restoration_behaviour_id: null,
    monitoring_time_ms: null,
    driven_by_id: null,
    driven_position_map: {},
    safety_relevant: false,
    parameters: {},
    position_labels: {},
    travel_times_ms: {},
    rendering_file_id: null,
    assembly_file_id: null,
    marker_x: null,
    marker_y: null,
    creator_id: 1,
    creator: null,
    components: [],
  }
}

function signal(id: number): LiveSignal {
  return { resource: LiveResource.PRODUCT_DEVICES, id, action: 'updated', actor_id: null }
}

async function mountTab() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const wrapper = mountWithApp(ProductDevicesTab, {
    pinia,
    attachTo: document.body,
    props: { productId: 3, canEdit: true },
    global: { stubs: { ProductDeviceDialog: true, ProductDeviceOverview: true } },
  })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  getDevicesMock.mockReset()
  subscribers.clear()
  vi.useRealTimers()
})

describe('ProductDevicesTab', () => {
  it('has no toolbar of its own and lists the devices', async () => {
    getDevicesMock.mockResolvedValue([device(1, 'Hubzylinder')])
    const wrapper = await mountTab()
    expect(wrapper.text()).toContain('B01 Hubzylinder P1')
    expect(wrapper.find('[role="toolbar"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('M26001 B01 Hubzylinder P1')
  })

  it('numbers the rows and shows each device rendering', async () => {
    URL.createObjectURL = vi.fn<(blob: Blob) => string>(() => 'blob:rendering')
    URL.revokeObjectURL = vi.fn<(url: string) => void>()
    getDevicesMock.mockResolvedValue([
      { ...device(1, 'Hubzylinder'), rendering_file_id: 40 },
      device(2, 'Greifer'),
    ])
    const wrapper = await mountTab()
    await flushPromises()
    const rows = wrapper.findAll('tbody tr')
    expect(rows[0]!.find('td').text()).toBe('1')
    expect(rows[1]!.find('td').text()).toBe('2')
    expect(rows[0]!.find('img').attributes('src')).toBe('blob:rendering')
    expect(rows[1]!.find('img').exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows the names with product number when switched on', async () => {
    getDevicesMock.mockResolvedValue([device(1, 'Hubzylinder')])
    const wrapper = await mountTab()
    useProductDevicesViewStore().showFullNames = true
    await flushPromises()
    expect(wrapper.text()).toContain('M26001 B01 Hubzylinder P1')
  })

  it('refetches when a device of this product changes, not of another one', async () => {
    getDevicesMock.mockResolvedValue([device(1, 'Hubzylinder')])
    await mountTab()
    vi.useFakeTimers()
    getDevicesMock.mockResolvedValue([device(1, 'Hubzylinder'), device(2, 'Greifer')])

    subscribers.get(LiveResource.PRODUCT_DEVICES)?.(signal(99))
    await vi.advanceTimersByTimeAsync(400)
    expect(getDevicesMock).toHaveBeenCalledTimes(1)

    subscribers.get(LiveResource.PRODUCT_DEVICES)?.(signal(3))
    await vi.advanceTimersByTimeAsync(400)
    expect(getDevicesMock).toHaveBeenCalledTimes(2)
  })

  it('copies the names from the row context menu', async () => {
    getDevicesMock.mockResolvedValue([device(1, 'Hubzylinder')])
    const writeText = vi.fn<(text: string) => Promise<void>>().mockResolvedValue()
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true })
    const wrapper = await mountTab()

    expect(wrapper.text()).not.toContain('Actions')
    wrapper
      .findComponent({ name: 'DataTable' })
      .vm.$emit('row-contextmenu', { data: device(1, 'Hubzylinder'), originalEvent: new MouseEvent('contextmenu') })
    await flushPromises()

    const item = (label: string) =>
      [...document.body.querySelectorAll('[role="menuitem"]')].find((el) =>
        el.textContent?.includes(label),
      ) as HTMLElement | undefined
    expect(item('Edit Device')).toBeDefined()
    item('Copy ASCII Name')!.querySelector('a, div')!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()
    expect(writeText).toHaveBeenCalledWith('B01_Hubzylinder_P1')
    wrapper.unmount()
  })

  it('reloads with archived devices when they are switched on', async () => {
    getDevicesMock.mockResolvedValue([])
    await mountTab()
    useProductDevicesViewStore().showArchived = true
    await flushPromises()
    expect(getDevicesMock).toHaveBeenLastCalledWith(3, true)
  })
})
