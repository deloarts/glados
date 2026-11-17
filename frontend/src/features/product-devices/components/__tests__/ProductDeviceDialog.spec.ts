import { afterEach, describe, expect, it, vi } from 'vitest'
import { DOMWrapper, flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'

// Renaming asks first; the stub accepts at once and keeps what was asked.
const confirmMock = vi.fn<(options: { message?: string; accept?: () => void }) => void>((options) =>
  options.accept?.(),
)
vi.mock('openvue/useconfirm', () => ({ useConfirm: () => ({ require: confirmMock }) }))
import type {
  ProductDevice,
  ProductDeviceKind,
  ProductDeviceNamePreview,
  ProductDeviceOption,
  ProductDeviceSaveRequest,
} from '../../types/productDevice'

const previewMock =
  vi.fn<(productId: number, body: Record<string, unknown>) => Promise<ProductDeviceNamePreview>>()
const updateMock =
  vi.fn<(id: number, version: number, body: ProductDeviceSaveRequest) => Promise<ProductDevice>>()
const createMock =
  vi.fn<(productId: number, body: ProductDeviceSaveRequest) => Promise<ProductDevice>>()

vi.mock('../../api/productDevicesApi', () => ({
  previewProductDeviceName: (productId: number, body: Record<string, unknown>) =>
    previewMock(productId, body),
  updateProductDevice: (id: number, version: number, body: ProductDeviceSaveRequest) =>
    updateMock(id, version, body),
  createProductDevice: (productId: number, body: ProductDeviceSaveRequest) =>
    createMock(productId, body),
}))

vi.mock('../../api/productDeviceResourcesApi', () => ({
  getProductDeviceOptions: (): Promise<ProductDeviceOption[]> => Promise.resolve([medium]),
  getProductDeviceKinds: (): Promise<ProductDeviceKind[]> => Promise.resolve([kind]),
}))

// The catalogue item picker of a component loads the bought items itself.
vi.mock('@/features/bought-items/api/getBoughtItems', () => ({
  getBoughtItems: async () => ({ items: [], total: 0, skip: 0, limit: 50 }),
}))
vi.mock('../../api/deviceImagesApi', () => ({
  getDeviceSlotFiles: () => Promise.resolve([]),
  uploadDeviceSlotFile: vi.fn<() => Promise<void>>(),
  removeDeviceSlotFile: vi.fn<() => Promise<void>>(),
  getDeviceImageFiles: () => Promise.resolve([]),
  getDeviceImageBlob: () => Promise.resolve(new Blob()),
  uploadDeviceRendering: vi.fn<() => Promise<void>>(),
}))

import ProductDeviceDialog from '../ProductDeviceDialog.vue'

const medium: ProductDeviceOption = {
  id: 7,
  public_id: 'm',
  created: '2026-10-22T00:00:00Z',
  changed: '2026-10-22T00:00:00Z',
  changed_by: null,
  changed_by_id: null,
  category: 'driving_medium',
  label: { enGB: 'Pneumatics' },
  letter: 'P',
  sort_order: 0,
  archived: false,
  creator_id: 1,
  creator: null,
}

const kind: ProductDeviceKind = {
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
  positions: [],
  parameters: [],
  signals: [],
}

const device: ProductDevice = {
  edit_version: 0,
  id: 5,
  public_id: 'd',
  created: '2026-10-22T00:00:00Z',
  changed: '2026-10-22T00:00:00Z',
  changed_by: null,
  changed_by_id: null,
  archived: false,
  product_id: 3,
  product_number: 'M26001',
  location: 'B01-W4-L',
  name: 'Hubzylinder Einförderung',
  driving_medium_id: 7,
  driving_medium_letter: 'P',
  number: 1,
  name_utf8: 'B01-W4-L Hubzylinder Einförderung P1',
  name_ascii: 'B01_W4_L_Hubzylinder_Einfoerderung_P1',
  full_name_utf8: 'M26001 B01-W4-L Hubzylinder Einförderung P1',
  full_name_ascii: 'M26001_B01_W4_L_Hubzylinder_Einfoerderung_P1',
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

function preview(overrides: Partial<ProductDeviceNamePreview> = {}): ProductDeviceNamePreview {
  return {
    number: 1,
    name_utf8: device.name_utf8,
    name_ascii: device.name_ascii,
    full_name_utf8: device.full_name_utf8,
    full_name_ascii: device.full_name_ascii,
    invalid_characters: [],
    taken: false,
    longest_tag_length: null,
    max_tag_length: null,
    ...overrides,
  }
}

async function openDialog(props: Record<string, unknown>) {
  vi.useFakeTimers()
  const wrapper = mountWithApp(ProductDeviceDialog, {
    attachTo: document.body,
    props: { visible: false, productId: 3, ...props },
    global: { stubs: { ConfirmDialog: true } },
  })
  await flushPromises()
  await wrapper.setProps({ visible: true })
  await flushPromises()
  // The preview is debounced, so run its timer instead of waiting it out.
  await vi.runAllTimersAsync()
  await flushPromises()
  return wrapper
}

afterEach(() => {
  vi.useRealTimers()
  previewMock.mockReset()
  updateMock.mockReset()
  createMock.mockReset()
  confirmMock.mockClear()
  document.body.innerHTML = ''
})

describe('ProductDeviceDialog', () => {
  it('shows the name preview in UTF-8 and ASCII with the product number', async () => {
    previewMock.mockResolvedValue(preview())
    const wrapper = await openDialog({ device })

    expect(previewMock).toHaveBeenCalledWith(3, {
      location: 'B01-W4-L',
      name: 'Hubzylinder Einförderung',
      driving_medium_id: 7,
      number: 1,
      device_id: 5,
      kind_id: device.kind_id,
    })
    const box = document.body.querySelector('[data-testid="device-name-preview"]')
    expect(box?.textContent).toContain('M26001 B01-W4-L Hubzylinder Einförderung P1')
    expect(box?.textContent).toContain('M26001_B01_W4_L_Hubzylinder_Einfoerderung_P1')
    wrapper.unmount()
  })

  it('warns when the longest PLC tag of the name is too long', async () => {
    previewMock.mockResolvedValue(preview({ longest_tag_length: 131, max_tag_length: 128 }))
    const wrapper = await openDialog({ device })
    const warning = document.body.querySelector('[data-testid="device-tag-too-long"]')
    expect(warning?.textContent).toContain('131')
    expect(warning?.textContent).toContain('128')
    wrapper.unmount()
  })

  it('reports invalid characters from the preview', async () => {
    previewMock.mockResolvedValue(preview({ invalid_characters: [':'] }))
    const wrapper = await openDialog({ device })

    const box = document.body.querySelector('[data-testid="device-name-preview"]')
    expect(box?.textContent).toContain(':')
    wrapper.unmount()
  })

  it('saves an edited device through the update route', async () => {
    previewMock.mockResolvedValue(preview())
    updateMock.mockResolvedValue(device)
    const wrapper = await openDialog({
      device,
      disciplines: { pneumatics: true, hydraulics: false, electrics: true, robotics: false },
    })

    await new DOMWrapper(document.body.querySelector('#pd-location')!).setValue('B02')
    await new DOMWrapper(document.body.querySelector('form.device-form')!).trigger('submit')
    await flushPromises()

    // The rename names the plans of the machine's disciplines and the CAD assembly.
    const message = confirmMock.mock.calls[0]![0].message ?? ''
    expect(message).toContain('the EPLAN plan')
    expect(message).toContain('the pneumatics plan')
    expect(message).not.toContain('hydraulics')
    expect(message).toContain('the CAD assembly name')
    expect(updateMock).toHaveBeenCalledTimes(1)
    const [id, version, body] = updateMock.mock.calls[0]!
    expect(version).toBe(device.edit_version)
    expect(id).toBe(5)
    expect(body).toMatchObject({ location: 'B02', name: 'Hubzylinder Einförderung', kind_id: 1 })
    expect(wrapper.emitted('saved')).toHaveLength(1)
    wrapper.unmount()
  })

  it('refuses to save without a name', async () => {
    previewMock.mockResolvedValue(preview())
    const wrapper = await openDialog({})

    await new DOMWrapper(document.body.querySelector('form.device-form')!).trigger('submit')
    await flushPromises()

    expect(createMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('The device needs a name.')
    wrapper.unmount()
  })

  it('refuses to save a signal without a meaning instead of dropping it', async () => {
    previewMock.mockResolvedValue(preview())
    const withSignal: ProductDevice = {
      ...device,
      components: [
        {
          id: 1,
          role_id: 1,
          bought_item_id: null,
          eplan_tag: null,
          b10d_cycles: null,
          mttfd_years: null,
          note: null,
          signals: [
            {
              signal_type: 'di',
              meaning: '',
              confirms_position_id: null,
              drives_position_id: null,
              safety: false,
              address: null,
              tag_suffix: null,
              tag_name: null,
              kind_signal_id: null,
            },
          ],
        },
      ] as ProductDevice['components'],
    }
    const wrapper = await openDialog({ device: withSignal })

    await new DOMWrapper(document.body.querySelector('form.device-form')!).trigger('submit')
    await flushPromises()

    expect(updateMock).not.toHaveBeenCalled()
    expect(document.body.textContent).toContain('A signal without a position or a signal of its kind needs a meaning.')
    wrapper.unmount()
  })
})
