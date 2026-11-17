import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'


import HandbookPageView from '../HandbookPageView.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

// Real handbook content is used throughout, the same way
// HandbookIndexView.spec.ts/HandbookLayout.spec.ts do. The compiled markdown
// chunks are cheap to load and exercising the real useHandbookDoc/loadHandbookDoc
// pipeline is more useful here than a fixture.
const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/handbook/:section/:page', name: 'HandbookPage', component: HandbookPageView }],
})

let wrapper: ReturnType<typeof mount> | null = null

async function mountAt(path: string) {
  await router.push(path)
  await router.isReady()

  wrapper = mountWithApp(HandbookPageView, {
    global: { plugins: [router] },
  })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('HandbookPageView', () => {
  it("renders the doc's own title as the page heading, from its frontmatter", async () => {
    await mountAt('/handbook/production/auto-plan')
    await vi.waitFor(() => {
      expect(wrapper?.find('.handbook-page-title').exists()).toBe(true)
    })

    expect(wrapper!.find('.handbook-page-title').text()).toBe('How Auto-Plan works')
  })

  it('renders the summary and a divider once the doc has loaded', async () => {
    await mountAt('/handbook/production/auto-plan')
    await vi.waitFor(() => {
      expect(wrapper?.find('.handbook-page-title').exists()).toBe(true)
    })

    expect(wrapper!.findComponent({ name: 'Divider' }).exists()).toBe(true)
  })

  it('passes the resolved slug down as `production/auto-plan` and renders the content component', async () => {
    await mountAt('/handbook/production/auto-plan')
    await vi.waitFor(() => {
      expect(wrapper?.find('.handbook-page-title').exists()).toBe(true)
    })

    const content = wrapper!.findComponent({ name: 'HandbookContent' })
    expect(content.exists()).toBe(true)
    expect(content.props('doc')?.slug).toBe('production/auto-plan')
    expect(content.props('missing')).toBe(false)
  })

  it('renders no heading and reports the doc as missing for an undocumented page', async () => {
    await mountAt('/handbook/production/not-a-real-page')
    await flushPromises()

    expect(wrapper!.find('.handbook-page-title').exists()).toBe(false)
    const content = wrapper!.findComponent({ name: 'HandbookContent' })
    expect(content.props('missing')).toBe(true)
    expect(content.props('doc')).toBeNull()
  })

  it('re-resolves the doc when the route params change to a different page', async () => {
    await mountAt('/handbook/production/auto-plan')
    await vi.waitFor(() => {
      expect(wrapper?.find('.handbook-page-title').text()).toBe('How Auto-Plan works')
    })

    await router.push('/handbook/production/capacity')
    await flushPromises()
    await vi.waitFor(() => {
      expect(wrapper?.find('.handbook-page-title').text()).toBe('Capacity')
    })
  })
})
