import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import { flushPromises } from '@vue/test-utils'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import type { DocumentPageAction } from '../composables/useDocumentPageAction'

const warn = vi.fn<(summary: string, detail?: string) => void>()
vi.mock('@/core/composables/useAppToast', () => ({
  useAppToast: () => ({
    warn,
    success: vi.fn<(summary: string, detail?: string) => void>(),
    info: vi.fn<(summary: string, detail?: string) => void>(),
    error: vi.fn<(summary: string, detail?: string) => void>(),
  }),
}))

import { useDocumentPageAction } from '../composables/useDocumentPageAction'

const ready = ref(false)
const run = vi.fn<(action: DocumentPageAction) => boolean>()

const Page = defineComponent({
  setup() {
    useDocumentPageAction({ ready: () => ready.value, run })
    return () => h('div', 'page')
  },
})

async function mountAt(path: string) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/doc/:id', component: Page }] })
  router.push(path)
  await router.isReady()
  const wrapper = mountWithApp(RouterView, { global: { plugins: [router] } })
  await flushPromises()
  return { router, wrapper }
}

describe('useDocumentPageAction', () => {
  beforeEach(() => {
    ready.value = false
    run.mockReset()
    warn.mockReset()
  })

  it('waits until the page is ready, then runs the action once and takes it off the address', async () => {
    run.mockReturnValue(true)
    const { router } = await mountAt('/doc/7?action=edit&tab=a')
    expect(run).not.toHaveBeenCalled()

    ready.value = true
    await flushPromises()

    expect(run).toHaveBeenCalledExactlyOnceWith('edit')
    expect(router.currentRoute.value.fullPath).toBe('/doc/7?tab=a')
    expect(warn).not.toHaveBeenCalled()
  })

  it('tells the user when the document does not allow the action, or it is unknown', async () => {
    run.mockReturnValue(false)
    ready.value = true
    await mountAt('/doc/7?action=release')
    expect(warn).toHaveBeenCalledOnce()

    await mountAt('/doc/7?action=explode')
    expect(run).toHaveBeenCalledOnce()
    expect(warn).toHaveBeenCalledTimes(2)
  })
})
