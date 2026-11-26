import { describe, it, expect, vi } from 'vitest'
import { flushPromises, DOMWrapper } from '@vue/test-utils'


const postMock = vi
  .fn<(url: string, payload: Record<string, unknown>) => Promise<unknown>>()
  .mockResolvedValue({ data: {} })
const putMock = vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} })
const getMock = vi
  .fn<() => Promise<unknown>>()
  .mockResolvedValue({ data: { items: [], total: 0 } })

vi.mock('@/core/api', () => ({
  default: {
    get: (...args: unknown[]) => getMock(...(args as [])),
    post: (url: string, payload: Record<string, unknown>) => postMock(url, payload),
    put: (...args: unknown[]) => putMock(...(args as [])),
  },
}))

import InspectionMethodFormDialog from '../InspectionMethodFormDialog.vue'
import type { ProductionMachineResponse } from '@/features/production-machines'
import { mountWithApp } from '@/test-utils/mountWithApp'
import type { InspectionMethodResponse } from '@/features/inspection-methods'

function makeMachine(overrides: Partial<ProductionMachineResponse> = {}): ProductionMachineResponse {
  return {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    archived: false,
    created: '2026-01-01',
    changed: null,
    changed_by_id: null,
    changed_by_full_name: '',
    internal_name: 'CMM-01',
    vendor: 'Fabrikam',
    model: 'CMM-500',
    fabrication_method_ids: [],
    fabrication_methods: [],
    max_part_dimension: null,
    is_qa_machine: true,
    note: null,
    creator_id: 1,
    creator_full_name: 'Creator',
    changes: [],
    active_orders: [],
    live_order_count: 0,
    open_downtime: null,
    status: 'down',
    ...overrides,
  }
}

const method: InspectionMethodResponse = {
  id: 1,
  public_id: '11111111-1111-1111-1111-111111111111',
  created: '2026-07-01',
  changed: '2026-07-01T00:00:00Z',
  changed_by: null,
  changed_by_id: null,
  name: { enGB: 'Measurement' },
  description: { enGB: '' },
  label_color: '#999999',
  label_font_color: '#000000',
  default_setup_minutes: 10,
  default_minutes_per_piece: 2.5,
  wait_after_minutes: null,
  requires_evidence: true,
  default_machine_id: null,
  default_machine_name: null,
  archived: true,
  creator_id: 1,
  creator: null,
}

// The name is entered per language; the default language's input is the
// one a create needs, and the test host offers only that language.
const NAME_INPUT = '[data-testid="localized-text-enGB"]'

describe('InspectionMethodFormDialog', () => {
  it('renders in create mode without errors when opened', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(InspectionMethodFormDialog, {
      attachTo: document.body,
      props: { visible: true, method: undefined },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    wrapper.unmount()
  })

  it('renders in edit mode pre-filled with the method without errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(InspectionMethodFormDialog, {
      attachTo: document.body,
      // Mount closed first, then open. The dialog only populates its form
      // from `watch(visible, ...)`, which fires on a false -> true
      // transition, not on an initial `visible: true` mount.
      props: { visible: false, method },
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
    const nameInput = document.body.querySelector<HTMLInputElement>(NAME_INPUT)
    expect(nameInput?.value).toBe('Measurement')

    const requiresEvidenceCheckbox =
      document.body.querySelector<HTMLInputElement>('#im-requires-evidence')
    expect(requiresEvidenceCheckbox?.checked).toBe(true)

    // Archiving is action-driven (Archive/Restore), not settable from this
    // form, so the form has no archived checkbox.
    expect(document.body.querySelector('#im-archived')).toBeNull()

    const setupInput = document.body.querySelector<HTMLInputElement>('#im-setup-minutes')
    expect(setupInput?.value).toBe('10')
    const perPieceInput = document.body.querySelector<HTMLInputElement>('#im-per-piece-minutes')
    expect(perPieceInput?.value).toBe('2.5')

    wrapper.unmount()
  })

  it('submits requires_evidence on create', async () => {
    postMock.mockClear()

    const wrapper = mountWithApp(InspectionMethodFormDialog, {
      attachTo: document.body,
      props: { visible: true, method: undefined },
    })

    await flushPromises()
    await flushPromises()

    await new DOMWrapper(document.body.querySelector(NAME_INPUT)!).setValue('Visual Inspection')
    await new DOMWrapper(document.body.querySelector('#im-requires-evidence')!).setValue(true)
    await flushPromises()

    await new DOMWrapper(document.body.querySelector('form.method-form')!).trigger('submit')
    await flushPromises()

    expect(postMock).toHaveBeenCalledTimes(1)
    const [, payload] = postMock.mock.calls[0]!
    expect(payload.name).toEqual({ enGB: 'Visual Inspection' })
    expect(payload.requires_evidence).toBe(true)
    expect(payload.archived).toBeUndefined()

    wrapper.unmount()
  })

  // Both durations are optional, and "no default" has to survive the round
  // trip as null rather than being coerced to 0. A method with a 0 setup
  // default seeds a real 0, one with none seeds nothing at all.
  it('submits null durations when the fields are left empty', async () => {
    postMock.mockClear()

    const wrapper = mountWithApp(InspectionMethodFormDialog, {
      attachTo: document.body,
      props: { visible: true, method: undefined },
    })

    await flushPromises()
    await flushPromises()

    await new DOMWrapper(document.body.querySelector(NAME_INPUT)!).setValue('Visual Inspection')
    await flushPromises()

    await new DOMWrapper(document.body.querySelector('form.method-form')!).trigger('submit')
    await flushPromises()

    const [, payload] = postMock.mock.calls[0]!
    expect(payload.default_setup_minutes).toBeNull()
    expect(payload.default_minutes_per_piece).toBeNull()

    wrapper.unmount()
  })

  it('submits the entered default durations on create', async () => {
    postMock.mockClear()

    const wrapper = mountWithApp(InspectionMethodFormDialog, {
      attachTo: document.body,
      props: { visible: true, method: undefined },
    })

    await flushPromises()
    await flushPromises()

    await new DOMWrapper(document.body.querySelector(NAME_INPUT)!).setValue('Measurement')
    const setup = new DOMWrapper(document.body.querySelector('#im-setup-minutes')!)
    await setup.setValue('15')
    await setup.trigger('blur')
    const perPiece = new DOMWrapper(document.body.querySelector('#im-per-piece-minutes')!)
    await perPiece.setValue('3.5')
    await perPiece.trigger('blur')
    await flushPromises()

    await new DOMWrapper(document.body.querySelector('form.method-form')!).trigger('submit')
    await flushPromises()

    const [, payload] = postMock.mock.calls[0]!
    expect(payload.default_setup_minutes).toBe(15)
    expect(payload.default_minutes_per_piece).toBe(3.5)

    wrapper.unmount()
  })

  it('sends the wait after the check', async () => {
    postMock.mockClear()
    const wrapper = mountWithApp(InspectionMethodFormDialog, {
      attachTo: document.body,
      props: { visible: true, method: undefined },
    })

    await flushPromises()
    await flushPromises()

    await new DOMWrapper(document.body.querySelector(NAME_INPUT)!).setValue('Lab result')
    const wait = new DOMWrapper(document.body.querySelector('#im-wait-after-minutes')!)
    await wait.setValue('240')
    await wait.trigger('blur')
    await flushPromises()

    await new DOMWrapper(document.body.querySelector('form.method-form')!).trigger('submit')
    await flushPromises()

    const [, payload] = postMock.mock.calls[0]!
    expect(payload.wait_after_minutes).toBe(240)

    wrapper.unmount()
  })

  it('submits default_machine_id: null by default on create', async () => {
    postMock.mockClear()

    const wrapper = mountWithApp(InspectionMethodFormDialog, {
      attachTo: document.body,
      props: { visible: true, method: undefined },
    })

    await flushPromises()
    await flushPromises()

    await new DOMWrapper(document.body.querySelector(NAME_INPUT)!).setValue('Visual Inspection')
    await flushPromises()

    await new DOMWrapper(document.body.querySelector('form.method-form')!).trigger('submit')
    await flushPromises()

    const [, payload] = postMock.mock.calls[0]!
    expect(payload.default_machine_id).toBeNull()

    wrapper.unmount()
  })

  it('selecting a QA machine puts its id in the create payload', async () => {
    postMock.mockClear()
    getMock.mockResolvedValueOnce({
      data: { items: [makeMachine({ id: 7, internal_name: 'CMM-07', is_qa_machine: true })], total: 1 },
    })

    const wrapper = mountWithApp(InspectionMethodFormDialog, {
      attachTo: document.body,
      props: { visible: true, method: undefined },
    })

    await flushPromises()
    await flushPromises()

    await new DOMWrapper(document.body.querySelector(NAME_INPUT)!).setValue('Visual Inspection')
    await wrapper.findComponent({ name: 'Select' }).vm.$emit('update:modelValue', 7)
    await flushPromises()

    await new DOMWrapper(document.body.querySelector('form.method-form')!).trigger('submit')
    await flushPromises()

    const [, payload] = postMock.mock.calls[0]!
    expect(payload.default_machine_id).toBe(7)

    wrapper.unmount()
  })

  it('lists only QA machines in the default-machine dropdown', async () => {
    getMock.mockResolvedValueOnce({
      data: {
        items: [
          makeMachine({ id: 1, internal_name: 'CMM-01', is_qa_machine: true }),
          makeMachine({ id: 2, internal_name: 'Mill-02', is_qa_machine: false }),
        ],
        total: 2,
      },
    })

    const wrapper = mountWithApp(InspectionMethodFormDialog, {
      attachTo: document.body,
      props: { visible: true, method: undefined },
    })

    await flushPromises()
    await flushPromises()

    const select = wrapper.findComponent({ name: 'Select' })
    const options = select.props('options') as { id: number; internal_name: string }[]
    expect(options).toHaveLength(1)
    expect(options[0]?.internal_name).toBe('CMM-01')

    wrapper.unmount()
  })
})
