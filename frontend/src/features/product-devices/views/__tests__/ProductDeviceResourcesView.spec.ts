import { describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { Permission } from '@/core/auth/permissions'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { userWithPermissions } from '@/test-utils/factories'
import type { ProductDeviceKind, ProductDeviceOption } from '../../types/productDevice'

// The archive confirmation comes from the shared row actions and is covered
// by their own spec, so the confirm service is stubbed here.
vi.mock('openvue/useconfirm', () => ({
  useConfirm: () => ({ require: vi.fn<() => Promise<void>>() }),
}))

const { placeOption } = vi.hoisted(() => ({
  placeOption: vi.fn<(id: number, target: object) => Promise<ProductDeviceOption[]>>(),
}))

vi.mock('../../api/productDeviceResourcesApi', () => ({
  getProductDeviceOptions: (): Promise<ProductDeviceOption[]> =>
    Promise.resolve([
      option(1, 'driving_medium', 'Pneumatics', 'P'),
      option(2, 'driving_medium', 'Hydraulics', 'H', true),
      option(3, 'component_role', 'Sensor', null),
      option(4, 'driving_medium', 'Electric', 'E'),
    ]),
  getProductDeviceKinds: (): Promise<ProductDeviceKind[]> =>
    Promise.resolve([
      {
        id: 1,
        public_id: 'k',
        created: '2026-10-22T00:00:00Z',
        changed: '2026-10-22T00:00:00Z',
        changed_by: null,
        changed_by_id: null,
        label: { enGB: 'Linear drive' },
        sort_order: 0,
        archived: false,
        creator_id: 1,
        creator: null,
        without_driving_medium: false,
        positions: [
          { id: 10, public_id: 'p', label: { enGB: 'Retracted' }, takes_value: false, unit: null, sort_order: 0, archived: false, plc_state_name: null, plc_command_name: null },
          { id: 11, public_id: 'q', label: { enGB: 'Old' }, takes_value: false, unit: null, sort_order: 1, archived: true, plc_state_name: null, plc_command_name: null },
        ],
        parameters: [],
        signals: [],
      },
    ]),
  setProductDeviceOptionArchived: vi.fn<() => Promise<void>>(),
  setProductDeviceKindArchived: vi.fn<() => Promise<void>>(),
  placeProductDeviceOption: placeOption,
  placeProductDeviceKind: vi.fn<() => Promise<ProductDeviceKind[]>>(),
}))

import ProductDeviceResourcesView from '../ProductDeviceResourcesView.vue'

function option(
  id: number,
  category: ProductDeviceOption['category'],
  label: string,
  letter: string | null,
  archived = false,
): ProductDeviceOption {
  return {
    id,
    public_id: `o${id}`,
    created: '2026-10-22T00:00:00Z',
    changed: '2026-10-22T00:00:00Z',
    changed_by: null,
    changed_by_id: null,
    category,
    label: { enGB: label },
    letter,
    sort_order: id,
    archived,
    creator_id: 1,
    creator: null,
  }
}

async function mountView(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  const wrapper = mountWithApp(ProductDeviceResourcesView, {
    pinia,
    global: { stubs: {
        ProductDeviceOptionDialog: true,
        ProductDeviceKindDialog: true,
        ConfirmDialog: true,
      }, },
  })
  await flushPromises()
  return wrapper
}

describe('ProductDeviceResourcesView', () => {
  it('lists live driving media with their letters', async () => {
    const wrapper = await mountView([Permission.WRITE_PRODUCT_DEVICE_RESOURCES])
    expect(wrapper.text()).toContain('Pneumatics')
    expect(wrapper.text()).toContain('P')
    expect(wrapper.text()).not.toContain('Hydraulics')
    expect(wrapper.text()).not.toContain('Sensor')
  })

  it('shows the kinds with their live positions only', async () => {
    const wrapper = await mountView([])
    const kindsButton = wrapper
      .findAll('[data-testid="device-resource-list"] button')
      .find((b) => b.text().includes('Device Kinds'))
    await kindsButton!.trigger('click')
    expect(wrapper.text()).toContain('Linear drive')
    expect(wrapper.text()).toContain('Retracted')
    expect(wrapper.text()).not.toContain('Old')
  })

  it('disables creating without the write permission', async () => {
    const wrapper = await mountView([])
    for (const list of ['driving_medium', 'kind', 'component_role', 'energy_behaviour']) {
      expect(
        wrapper.get(`[data-testid="device-resource-create-${list}"]`).attributes('disabled'),
      ).toBeDefined()
    }
  })

  it('names the missing write permission in a tooltip on the disabled New buttons', async () => {
    const wrapper = await mountView([])
    const button = wrapper.get('[data-testid="device-resource-create-kind"]')
    expect(tooltipOf(button)).toBe('This needs the permission Write Device Lists.')
  })

  it('drags an entry to a new place and shows it there before the server answers', async () => {
    const wrapper = await mountView([Permission.WRITE_PRODUCT_DEVICE_RESOURCES])
    expect(wrapper.findAll('[data-testid="row-drag-handle"]')).toHaveLength(2)

    let answer: (rows: ProductDeviceOption[]) => void = () => {}
    placeOption.mockReturnValueOnce(new Promise((resolve) => (answer = resolve)))
    wrapper.findComponent({ name: 'DataTable' }).vm.$emit('row-reorder', {
      originalEvent: new Event('drop'),
      dragIndex: 0,
      dropIndex: 1,
      value: [],
    })
    await flushPromises()

    expect(placeOption).toHaveBeenCalledWith(1, { after_id: 4 })
    let text = wrapper.text()
    expect(text.indexOf('Electric')).toBeLessThan(text.indexOf('Pneumatics'))

    answer([
      { ...option(4, 'driving_medium', 'Electric', 'E'), sort_order: 0 },
      { ...option(1, 'driving_medium', 'Pneumatics', 'P'), sort_order: 1 },
      { ...option(2, 'driving_medium', 'Hydraulics', 'H', true), sort_order: 2 },
    ])
    await flushPromises()
    text = wrapper.text()
    expect(text.indexOf('Electric')).toBeLessThan(text.indexOf('Pneumatics'))
  })

  it('shows no drag handle without the write permission', async () => {
    const wrapper = await mountView([])
    expect(wrapper.findAll('[data-testid="row-drag-handle"]')).toHaveLength(0)
  })
})

/** The tooltip of a button, kept by OpenVue's Tooltip directive on the span around it. */
function tooltipOf(button: { element: Element }): string | undefined {
  return (button.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null)?.$_ptooltipValue
}
