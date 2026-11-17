import { describe, it, expect, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import ConfirmationService from 'openvue/confirmationservice'
import { defineComponent, h } from 'vue'

import { asyncTabModule } from '@/test-utils/asyncTabStub'
import { mountWithApp } from '@/test-utils/mountWithApp'

// Tabs that publish a fixed state, so the info bar shows which one it holds.
function publishingTab(name: string, description: string) {
  return async () => {
    const { publishToolState } = await import('@/features/tools/composables/useToolState')
    return asyncTabModule(
      defineComponent({
        name,
        setup() {
          publishToolState(() => ({ inputs: {}, results: {}, title: description, description }))
          return () => h('div', name)
        },
      }),
    )
  }
}
vi.mock('@/features/tools/components/DriveSizingTab.vue', publishingTab('DriveSizingTab', 'New drive sizing'))
vi.mock('@/features/tools/components/SafetyDistanceTab.vue', publishingTab('SafetyDistanceTab', 'New safety distance'))

import ToolsView from '../ToolsView.vue'

// jsdom does not implement ResizeObserver; OpenVue's TabList binds one.
vi.stubGlobal(
  'ResizeObserver',
  class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  },
)

describe('ToolsView tab switching', () => {
  it('keeps the state of a tab opened a second time, which mounts before the previous tab unmounts', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/tools/:tab?/:calc?', name: 'Tools', component: ToolsView }],
    })
    router.push('/tools/drive-sizing')
    await router.isReady()
    const wrapper = mountWithApp(ToolsView, { global: { plugins: [router, ConfirmationService] } })
    const description = () => wrapper.find('[data-testid="calc-description"]')

    await vi.waitFor(() => expect(description().text()).toBe('New drive sizing'), { timeout: 2000, interval: 25 })
    await router.replace('/tools/safety-distance')
    await vi.waitFor(() => expect(description().text()).toBe('New safety distance'), { timeout: 2000, interval: 25 })

    // Drive sizing is loaded by now, so it mounts at once.
    await router.replace('/tools/drive-sizing')
    await flushPromises()

    expect(description().exists() && description().text()).toBe('New drive sizing')
    wrapper.unmount()
  })
})
