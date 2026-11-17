import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'


vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<() => Promise<unknown>>().mockResolvedValue({
      data: { items: [], total: 0, limit: 1000, skip: 0 },
    }),
    post: vi.fn<() => void>(),
  },
}))

import BoughtItemCreateForm from '../BoughtItemCreateForm.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

describe('BoughtItemCreateForm', () => {
  it('renders all fields without errors when opened', async () => {
    const logs: unknown[][] = []
    const errorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      logs.push(args)
    })
    const warnSpy = vi.spyOn(console, 'warn').mockImplementation((...args) => {
      logs.push(args)
    })

    const wrapper = mountWithApp(BoughtItemCreateForm, {
      attachTo: document.body,
      props: { visible: true },
    })

    await flushPromises()
    await flushPromises()

    errorSpy.mockRestore()
    warnSpy.mockRestore()

    expect(document.querySelector('#bi-article-name')).not.toBeNull()
    expect(document.querySelector('#bi-order-code-1')).not.toBeNull()
    expect(document.querySelector('#bi-manufacturer')).not.toBeNull()
    expect(document.querySelector('#bi-article-groups')).not.toBeNull()
    expect(logs).toEqual([])

    wrapper.unmount()
  })
})
