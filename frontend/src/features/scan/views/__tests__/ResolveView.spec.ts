import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'

const resolvePublicId = vi.fn<(publicId: string) => Promise<{ id: number; public_id: string; resource: string }>>()
vi.mock('../../api/resolvePublicId', () => ({ resolvePublicId: (id: string) => resolvePublicId(id) }))

import ResolveView from '../ResolveView.vue'

const PUBLIC_ID = '7c1e0d2a-0000-4000-8000-000000000042'

async function mountAt(path: string) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/resolve/:publicId', name: 'Resolve', component: ResolveView },
      { path: '/checklists/:id', name: 'ChecklistDetail', component: { template: '<div>checklist</div>' } },
    ],
  })
  router.push(path)
  await router.isReady()
  const wrapper = mountWithApp(ResolveView, { global: { plugins: [router] } })
  return { router, wrapper }
}

describe('ResolveView', () => {
  beforeEach(() => {
    resolvePublicId.mockReset()
  })

  it('replaces itself with the page of the record the public id belongs to', async () => {
    resolvePublicId.mockResolvedValue({ id: 31, public_id: PUBLIC_ID, resource: 'checklists' })
    const { router } = await mountAt(`/resolve/${PUBLIC_ID}`)

    await vi.waitFor(() => expect(router.currentRoute.value.fullPath).toBe('/checklists/31'))
    expect(resolvePublicId).toHaveBeenCalledWith(PUBLIC_ID)
  })

  it('says so when no record carries the public id', async () => {
    resolvePublicId.mockRejectedValue(new Error('404'))
    const { wrapper } = await mountAt(`/resolve/${PUBLIC_ID}`)

    await vi.waitFor(() => expect(wrapper.find('[data-testid="resolve-not-found"]').exists()).toBe(true))
  })

  it('says so when the record has no page to open', async () => {
    resolvePublicId.mockResolvedValue({ id: 3, public_id: PUBLIC_ID, resource: 'something-else' })
    const { wrapper } = await mountAt(`/resolve/${PUBLIC_ID}`)

    await vi.waitFor(() => expect(wrapper.find('[data-testid="resolve-no-route"]').exists()).toBe(true))
  })
})
