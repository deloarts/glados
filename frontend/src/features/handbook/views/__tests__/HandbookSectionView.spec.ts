import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'

import HandbookSectionView from '../HandbookSectionView.vue'

const stub = { template: '<div />' }

// Real handbook content, same convention as HandbookIndexView.spec.ts and
// HandbookLayout.spec.ts. The section list is built from the actual
// compiled docs rather than a fixture tree. A HandbookPage route is
// registered (as a stub) purely so each card's RouterLink can resolve.
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/handbook/:section', name: 'HandbookSection', component: HandbookSectionView },
    { path: '/handbook/:section/:page', name: 'HandbookPage', component: stub },
  ],
})

let wrapper: ReturnType<typeof mount> | null = null

async function mountAt(path: string) {
  await router.push(path)
  await router.isReady()

  wrapper = mountWithApp(HandbookSectionView, {
    global: { plugins: [router] },
  })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('HandbookSectionView', () => {
  it('renders the section heading from its sidebar label key', async () => {
    await mountAt('/handbook/production')
    await vi.waitFor(() => {
      expect(wrapper?.find('.handbook-section-list').exists()).toBe(true)
    })

    expect(wrapper!.find('.handbook-section-title').text()).toBe(
      i18n.global.t('main.sidebar.production.label'),
    )
  })

  it('lists every documented page in the section, linking to its handbook page route', async () => {
    await mountAt('/handbook/production')
    await vi.waitFor(() => {
      expect(wrapper?.find('.handbook-section-list').exists()).toBe(true)
    })

    const cards = wrapper!.findAll('.handbook-section-card')
    expect(cards.length).toBeGreaterThan(0)
    const autoPlanCard = cards.find((card) => card.text().includes('How Auto-Plan works'))!
    expect(autoPlanCard.attributes('href')).toBe('/handbook/production/auto-plan')
  })

  it('shows the empty-section message for a section with no docs yet, e.g. todo', async () => {
    await mountAt('/handbook/todo')
    await flushPromises()

    expect(wrapper!.find('.handbook-section-list').exists()).toBe(false)
    expect(wrapper!.findComponent({ name: 'Message' }).text()).toBe(
      i18n.global.t('handbook.sectionEmpty'),
    )
  })

  it('renders nothing when the section key does not match any known section', async () => {
    await mountAt('/handbook/not-a-real-section')
    await flushPromises()

    expect(wrapper!.find('.handbook-section-title').exists()).toBe(false)
  })

  it('re-lists pages when the route moves to a different section', async () => {
    await mountAt('/handbook/production')
    await vi.waitFor(() => {
      expect(wrapper?.find('.handbook-section-list').exists()).toBe(true)
    })

    await router.push('/handbook/todo')
    await flushPromises()

    expect(wrapper!.find('.handbook-section-list').exists()).toBe(false)
    expect(wrapper!.find('.handbook-section-title').text()).toBe(
      i18n.global.t('main.sidebar.todo.label'),
    )
  })
})
