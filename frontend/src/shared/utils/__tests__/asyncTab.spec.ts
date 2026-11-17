import { describe, it, expect, vi } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'

import { asyncTab } from '../asyncTab'

describe('asyncTab', () => {
  it('shows AsyncChunkLoading while the loader is pending, then the resolved component', async () => {
    let resolveLoader: (component: ReturnType<typeof defineComponent>) => void = () => {}
    const pending = new Promise<ReturnType<typeof defineComponent>>((resolve) => {
      resolveLoader = resolve
    })

    const Target = defineComponent({
      name: 'AsyncTabTarget',
      render: () => h('div', 'loaded'),
    })

    const wrapper = mount(defineComponent({ render: () => h(asyncTab(() => pending)) }))

    // Before the loader resolves, the loading placeholder shows instead of
    // the target component.
    expect(wrapper.findComponent({ name: 'AsyncTabTarget' }).exists()).toBe(false)

    resolveLoader(Target)

    await vi.waitFor(() => expect(wrapper.findComponent({ name: 'AsyncTabTarget' }).exists()).toBe(true), {
      timeout: 2000,
      interval: 25,
    })
    await flushPromises()

    expect(wrapper.text()).toBe('loaded')

    wrapper.unmount()
  })

  it('passes the loader through to defineAsyncComponent unmodified', async () => {
    const loader = vi.fn<() => Promise<ReturnType<typeof defineComponent>>>(() =>
      Promise.resolve(defineComponent({ name: 'DirectLoad', render: () => h('span', 'direct') })),
    )

    const wrapper = mount(defineComponent({ render: () => h(asyncTab(loader)) }))

    expect(loader).toHaveBeenCalledTimes(1)

    await vi.waitFor(() => expect(wrapper.findComponent({ name: 'DirectLoad' }).exists()).toBe(true), {
      timeout: 2000,
      interval: 25,
    })

    wrapper.unmount()
  })
})
