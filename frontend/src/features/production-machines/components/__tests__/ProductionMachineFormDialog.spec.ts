import { describe, it, expect, vi } from 'vitest'
import { flushPromises, DOMWrapper } from '@vue/test-utils'


const postMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>().mockResolvedValue({
  data: {},
})

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: {
        items: [
          {
            id: 1,
            created: '2026-01-01',
            changed: null,
            archived: false,
            name: 'Machining',
            description: '',
            label_color: '#6366f1',
            label_font_color: '#ffffff',
            creator_id: 1,
            creator: null,
            parent_id: null,
            has_children: true,
            children: [
              {
                id: 2,
                created: '2026-01-01',
                changed: null,
                archived: false,
                name: 'Milling',
                description: '',
                label_color: '#6366f1',
                label_font_color: '#ffffff',
                creator_id: 1,
                creator: null,
                parent_id: 1,
                has_children: false,
                children: [],
              },
            ],
          },
        ],
        total: 1,
        limit: 1000,
        skip: 0,
      },
    }),
    post: (url: string, payload: unknown) => postMock(url, payload),
    patch: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import ProductionMachineFormDialog from '../ProductionMachineFormDialog.vue'
import type { ProductionMachineResponse } from '../../types/productionMachinesResponse'
import { mountWithApp } from '@/test-utils/mountWithApp'

const machine: ProductionMachineResponse = {
  id: 1,
  public_id: '11111111-1111-1111-1111-111111111111',
  archived: false,
  created: '2026-07-01',
  changed: null,
  changed_by_id: null,
  changed_by_full_name: '',
  internal_name: 'CNC-01',
  vendor: 'Contoso',
  model: 'VF-2',
  fabrication_method_ids: [2],
  fabrication_methods: [],
  max_part_dimension: '400x400x300mm',
  is_qa_machine: false,
  note: null,
  creator_id: 1,
  creator_full_name: 'Creator',
  changes: [],
  active_orders: [],
  live_order_count: 0,
  open_downtime: null,
  status: 'down',
}

describe('ProductionMachineFormDialog', () => {
  it('renders in create mode without errors when opened', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(ProductionMachineFormDialog, {
      attachTo: document.body,
      props: { visible: true, machine: null },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    wrapper.unmount()
  })

  it('renders in edit mode pre-filled with the machine without errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(ProductionMachineFormDialog, {
      attachTo: document.body,
      // Mount closed first, then open, the dialog only populates its form
      // from `watch(visible, ...)`, which fires on a false -> true
      // transition, not on an initial `visible: true` mount (matching
      // FabricationMethodFormDialog.vue's/LotPositionAssignDialog.vue's
      // established pattern).
      props: { visible: false, machine },
    })

    await flushPromises()

    await wrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])
    // Dialog content is teleported to document.body, outside the wrapper's
    // own root element, so query the document directly rather than
    // wrapper.find().
    const nameInput = document.body.querySelector<HTMLInputElement>('#pm-internal-name')
    expect(nameInput?.value).toBe('CNC-01')

    wrapper.unmount()
  })

  // A QA/measuring machine never does fabrication work, so ticking the box
  // must clear and disable the capabilities select rather than just
  // leaving a stale, hidden selection.
  it('disables and clears capabilities when is_qa_machine is ticked', async () => {
    const wrapper = mountWithApp(ProductionMachineFormDialog, {
      attachTo: document.body,
      props: { visible: false, machine },
    })

    await flushPromises()
    await wrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()

    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })
    expect(multiSelect.props('modelValue')).toEqual([2])
    expect(multiSelect.props('disabled')).toBe(false)

    const qaCheckbox = document.body.querySelector<HTMLInputElement>('#pm-is-qa-machine')
    await new DOMWrapper(qaCheckbox!).setValue(true)
    await flushPromises()

    expect(multiSelect.props('disabled')).toBe(true)
    expect(multiSelect.props('modelValue')).toEqual([])

    wrapper.unmount()
  })

  it('sends an empty fabrication_method_ids when saving a QA machine', async () => {
    postMock.mockClear()

    const wrapper = mountWithApp(ProductionMachineFormDialog, {
      attachTo: document.body,
      props: { visible: true, machine: null },
    })

    await flushPromises()
    await flushPromises()

    await new DOMWrapper(document.body.querySelector('#pm-internal-name')!).setValue('CMM-99')
    await new DOMWrapper(document.body.querySelector('#pm-vendor')!).setValue('Fabrikam')
    await new DOMWrapper(document.body.querySelector('#pm-model')!).setValue('CMM-500')

    const multiSelect = wrapper.findComponent({ name: 'MultiSelect' })
    await multiSelect.vm.$emit('update:modelValue', [2])
    await flushPromises()

    await new DOMWrapper(document.body.querySelector('#pm-is-qa-machine')!).setValue(true)
    await flushPromises()

    await new DOMWrapper(document.body.querySelector('form.machine-form')!).trigger('submit')
    await flushPromises()

    expect(postMock).toHaveBeenCalledTimes(1)
    const [, payload] = postMock.mock.calls[0]!
    expect((payload as { fabrication_method_ids: number[] }).fabrication_method_ids).toEqual([])

    wrapper.unmount()
  })
})
