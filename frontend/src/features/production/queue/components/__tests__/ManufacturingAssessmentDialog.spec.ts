import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { makeProductionOrderResponse } from '@/test-utils/factories'

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: [] }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
    patch: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import ManufacturingAssessmentDialog from '../ManufacturingAssessmentDialog.vue'
import type { ProductionOrderResponse } from '../../../types/productionOrdersResponse'

function makeOrder(): ProductionOrderResponse {
  return makeProductionOrderResponse({ status: 'completed', quantity_completed: 10 })
}

describe('ManufacturingAssessmentDialog', () => {
  it('renders without errors when opened', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(ManufacturingAssessmentDialog, {
      attachTo: document.body,
      props: { visible: true, order: makeOrder() },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    wrapper.unmount()
  })

  it('defaults to normal complexity and requires actual minutes per piece', async () => {
    const wrapper = mountWithApp(ManufacturingAssessmentDialog, {
      attachTo: document.body,
      props: { visible: true, order: makeOrder() },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      complexity: string
      actualMinutesPerPiece: number | null
      isValid: boolean
    }

    expect(vm.complexity).toBe('normal')
    expect(vm.isValid).toBe(false)

    vm.actualMinutesPerPiece = 4.5
    await flushPromises()
    expect(vm.isValid).toBe(true)

    wrapper.unmount()
  })

  it('sends minutes per piece with two decimals', async () => {
    const wrapper = mountWithApp(ManufacturingAssessmentDialog, {
      attachTo: document.body,
      props: { visible: true, order: makeOrder() },
    })
    await flushPromises()

    const api = (await import('@/core/api')).default
    const postSpy = vi.mocked(api.post)
    postSpy.mockClear()

    const [minutesInput] = wrapper.findAllComponents({ name: 'InputNumber' })
    expect(minutesInput!.props('maxFractionDigits')).toBe(2)
    minutesInput!.vm.$emit('update:modelValue', 6.75)
    await flushPromises()
    const save = Array.from(document.body.querySelectorAll('button')).find(
      (b) => b.textContent?.trim() === 'Save Assessment',
    )
    save!.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    await flushPromises()

    const [, payload] = postSpy.mock.calls.find(([url]) => String(url).endsWith('/assessment'))!
    expect(payload).toMatchObject({ actual_minutes_per_piece: 6.75 })

    wrapper.unmount()
  })

  it('skip closes the dialog without an API call', async () => {
    const wrapper = mountWithApp(ManufacturingAssessmentDialog, {
      attachTo: document.body,
      props: { visible: true, order: makeOrder() },
    })

    await flushPromises()

    const api = (await import('@/core/api')).default
    const postSpy = vi.mocked(api.post)
    postSpy.mockClear()

    const vm = wrapper.vm as unknown as { onSkip: () => void }
    vm.onSkip()
    await flushPromises()

    expect(postSpy).not.toHaveBeenCalled()
    expect(wrapper.emitted('update:visible')).toEqual([[false]])

    wrapper.unmount()
  })
})
