import { describe, it, expect, vi } from 'vitest'
import { flushPromises, DOMWrapper } from '@vue/test-utils'


const postMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>().mockResolvedValue({
  data: {
    id: 1,
    public_id: '22222222-2222-2222-2222-222222222222',
    created: '2026-01-01T08:00:00Z',
    changed: '2026-01-01T08:00:00Z',
    machine_id: 1,
    machine_internal_name: 'CNC-01',
    started_at: '2026-01-01T08:00:00Z',
    ended_at: null,
    reason: 'breakdown',
    note: null,
    reported_by_id: 1,
    reported_by_full_name: 'Tester',
    ended_by_id: null,
    ended_by_full_name: null,
    changes: [],
  },
})

vi.mock('@/core/api', () => ({
  default: {
    post: (url: string, payload: unknown) => postMock(url, payload),
  },
}))

import MachineDowntimeFormDialog from '../MachineDowntimeFormDialog.vue'
import type { ProductionMachineResponse } from '../../types/productionMachinesResponse'
import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeTestRouter } from '@/test-utils/factories/router'

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
  fabrication_method_ids: [],
  fabrication_methods: [],
  max_part_dimension: null,
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

describe('MachineDowntimeFormDialog', () => {
  it('renders with the machine shown read-only, without errors', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(MachineDowntimeFormDialog, {
      attachTo: document.body,
      // Mount closed first, then open: the dialog only resets its form
      // from `watch(visible, ...)`, which fires on a false -> true
      // transition (same idiom as ProductionMachineFormDialog.spec.ts).
      props: { visible: false, machine },
      global: { plugins: [makeTestRouter()] },
    })

    await flushPromises()
    await wrapper.setProps({ visible: true })
    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    const machineInput = document.body.querySelector<HTMLInputElement>('.downtime-form input')
    expect(machineInput?.value).toBe('CNC-01')
    expect(machineInput?.disabled).toBe(true)

    wrapper.unmount()
  })

  it('requires a reason before submitting', async () => {
    const wrapper = mountWithApp(MachineDowntimeFormDialog, {
      attachTo: document.body,
      props: { visible: true, machine },
      global: { plugins: [makeTestRouter()] },
    })

    await flushPromises()
    await flushPromises()

    await new DOMWrapper(document.body.querySelector('form.downtime-form')!).trigger('submit')
    await flushPromises()

    expect(document.body.textContent).toContain('Please fill in all required fields.')
    expect(postMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('submits the reason and note, with no end date for an ongoing downtime', async () => {
    postMock.mockClear()

    const wrapper = mountWithApp(MachineDowntimeFormDialog, {
      attachTo: document.body,
      props: { visible: true, machine },
      global: { plugins: [makeTestRouter()] },
    })

    await flushPromises()
    await flushPromises()

    const select = wrapper.findComponent({ name: 'Select' })
    await select.vm.$emit('update:modelValue', 'breakdown')
    await new DOMWrapper(document.body.querySelector('#dt-note')!).setValue('Spindle fault')
    await flushPromises()

    await new DOMWrapper(document.body.querySelector('form.downtime-form')!).trigger('submit')
    await flushPromises()

    expect(postMock).toHaveBeenCalledTimes(1)
    const [url, payload] = postMock.mock.calls[0]!
    expect(url).toBe('/production-machines/downtimes')
    expect(payload).toMatchObject({
      machine_id: 1,
      reason: 'breakdown',
      note: 'Spindle fault',
      ended_at: null,
    })
    expect(typeof (payload as { started_at: string }).started_at).toBe('string')

    wrapper.unmount()
  })

  it('opens the downtimes handbook section from the header help button', async () => {
    const wrapper = mountWithApp(MachineDowntimeFormDialog, {
      attachTo: document.body,
      props: { visible: true, machine },
      // The drawer itself is the handbook's; the spec checks only which
      // page and section the button opens.
      global: { plugins: [makeTestRouter()], stubs: { HelpDrawer: true } },
    })
    await flushPromises()

    document.body.querySelector<HTMLButtonElement>('[data-testid="downtime-form-dialog-explain"]')!.click()
    await flushPromises()

    const drawer = wrapper.findComponent({ name: 'HelpDrawer' })
    expect(drawer.props('slug')).toBe('resources/machines')
    expect(drawer.props('anchor')).toBe('downtimes')
    expect(drawer.props('visible')).toBe(true)

    wrapper.unmount()
  })
})
