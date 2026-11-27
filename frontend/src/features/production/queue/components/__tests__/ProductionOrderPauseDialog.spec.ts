import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeProductionOrderResponse } from '@/test-utils/factories'

const postMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>(() =>
  Promise.resolve({ data: {} }),
)

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: [] }),
    post: (url: string, payload: unknown) => postMock(url, payload),
  },
}))

import ProductionOrderPauseDialog from '../ProductionOrderPauseDialog.vue'

function mountDialog() {
  return mountWithApp(ProductionOrderPauseDialog, {
    attachTo: document.body,
    props: { visible: true, order: makeProductionOrderResponse({ status: 'in_progress' }) },
  })
}

function clickPause(): void {
  const button = Array.from(document.body.querySelectorAll('button')).find(
    (b) => b.textContent?.trim() === 'Pause',
  )
  expect(button).toBeTruthy()
  button!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
}

function pausePayload(): Record<string, unknown> {
  const call = postMock.mock.calls.find(([url]) => url.endsWith('/pause'))
  expect(call).toBeTruthy()
  return call![1] as Record<string, unknown>
}

describe('ProductionOrderPauseDialog', () => {
  beforeEach(() => {
    postMock.mockClear()
  })

  it('offers every pause cause by its label', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    const [causeSelect] = wrapper.findAllComponents({ name: 'Select' })
    const options = causeSelect!.props('options') as { label: string; value: string }[]
    expect(options.map((o) => o.value)).toEqual([
      'waiting_for_material',
      'waiting_for_tool',
      'waiting_for_drawing',
      'waiting_for_qa',
      'machine_fault',
      'other_work',
      'end_of_shift',
    ])
    expect(options[0]!.label).toBe('Waiting for Material')

    wrapper.unmount()
  })

  it('sends the picked cause with the reason', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    const [causeSelect] = wrapper.findAllComponents({ name: 'Select' })
    causeSelect!.vm.$emit('update:modelValue', 'machine_fault')
    wrapper.findComponent({ name: 'Textarea' }).vm.$emit('update:modelValue', 'Spindle alarm')
    await flushPromises()
    clickPause()
    await flushPromises()

    expect(pausePayload()).toMatchObject({ pause_cause: 'machine_fault', reason: 'Spindle alarm' })

    wrapper.unmount()
  })

  it('pauses without a cause when none is picked', async () => {
    const wrapper = mountDialog()
    await flushPromises()

    clickPause()
    await flushPromises()

    expect(pausePayload()).not.toHaveProperty('pause_cause')

    wrapper.unmount()
  })
})
