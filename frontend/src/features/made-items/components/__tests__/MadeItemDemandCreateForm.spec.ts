import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'


vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
    post: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import MadeItemDemandCreateForm from '../MadeItemDemandCreateForm.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

describe('MadeItemDemandCreateForm', () => {
  it('renders without errors when opened', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(MadeItemDemandCreateForm, {
      attachTo: document.body,
      props: { visible: true },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(wrapper.exists()).toBe(true)
    expect(logs).toEqual([])

    wrapper.unmount()
  })
})
