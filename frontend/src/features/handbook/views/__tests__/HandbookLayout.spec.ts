import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'

import { HANDBOOK_SECTIONS } from '../../utils/handbookSections'

import HandbookLayout from '../HandbookLayout.vue'
import HandbookPageView from '../HandbookPageView.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

const stub = { template: '<div />' }

// The layout is mounted directly by each test, so the route tree uses a plain
// passthrough parent, because registering HandbookLayout here too would
// render it a second time inside itself and double every count.
const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    {
      path: '/handbook',
      component: { template: '<router-view />' },
      children: [
        { path: '', name: 'Handbook', component: stub },
        { path: ':section', name: 'HandbookSection', component: stub },
        // The real page, so the right rail's outline is built from a doc that
        // actually rendered rather than a fixture.
        { path: ':section/:page', name: 'HandbookPage', component: HandbookPageView },
      ],
    },
  ],
})

let wrapper: ReturnType<typeof mount> | null = null

async function mountAt(path: string) {
  await router.push(path)
  await router.isReady()

  wrapper = mountWithApp(HandbookLayout, {
    global: { plugins: [router] },
  })
  // The tree pulls every doc's frontmatter, each its own lazy chunk (a
  // couple dozen of them), so this resolves measurably slower than the single
  // chunk the routed doc itself needs for its own (right-rail) headings.
  // Waiting on the left rail specifically, rather than `.handbook-aside-link`
  // generally, avoids a false-positive on the right rail's heading links
  // resolving first and leaving the left rail's own section list unloaded
  // when the assertions below run.
  await flushPromises()
  await vi.waitFor(() => {
    expect(
      wrapper?.findAll('.handbook-aside')[0]?.find('.handbook-aside-link').exists(),
    ).toBe(true)
  })
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
})

describe('HandbookLayout', () => {
  it('shows every main section as a tab, in the app navigation order', async () => {
    await mountAt('/handbook/production/auto-plan')

    const tabs = wrapper!.findAllComponents({ name: 'Tab' })
    expect(tabs).toHaveLength(HANDBOOK_SECTIONS.length)
    expect(tabs.map((tab) => tab.text())).toEqual([
      'Todo',
      'Workspace',
      'Catalogue',
      'Procurement',
      'Production',
      'Resources',
      'Account',
    ])
  })

  it('lists the open section pages in the left rail', async () => {
    await mountAt('/handbook/production/auto-plan')

    const left = wrapper!.findAll('.handbook-aside')[0]!
    const pages = left.findAll('.handbook-aside-link')
    expect(pages.map((page) => page.text())).toContain('How Auto-Plan works')

    // The page being read is marked in the tree, not just in the content.
    const current = left.findAll('.handbook-aside-link-current')
    expect(current).toHaveLength(1)
    expect(current[0]?.text()).toBe('How Auto-Plan works')

    // The rail is titled with the section it belongs to.
    expect(left.find('.handbook-aside-title').text()).toBe('Production')
  })

  it('keeps three full-height columns either side of the content', async () => {
    await mountAt('/handbook/production/auto-plan')

    // Both rails and the content are cards, so all three run to the bottom.
    expect(wrapper!.findAll('.handbook-columns > .card')).toHaveLength(3)
    expect(wrapper!.find('.handbook-main').exists()).toBe(true)
  })

  it('builds the right rail from the rendered doc headings', async () => {
    await mountAt('/handbook/production/auto-plan')
    const right = wrapper!.findAll('.handbook-aside')[1]!

    await vi.waitFor(() => {
      expect(right.findAll('.handbook-aside-link').length).toBeGreaterThan(0)
    })

    const headings = right.findAll('.handbook-aside-link').map((link) => link.text())
    expect(headings).toContain('Running it')
    expect(headings).toContain('The six algorithms')

    // Anchors point at the doc's stable ids, so they survive translation.
    expect(right.findAll('a').map((a) => a.attributes('href'))).toContain('#run')
  })

  it('says so when a section has nothing written yet', async () => {
    await router.push('/handbook/todo')
    await router.isReady()
    wrapper = mountWithApp(HandbookLayout, {
      global: { plugins: [router] },
    })
    await flushPromises()
    await vi.waitFor(() => {
      expect(wrapper?.find('.handbook-aside-hint').exists()).toBe(true)
    })

    const left = wrapper.findAll('.handbook-aside')[0]!
    expect(left.find('.handbook-aside-hint').text()).toContain('Nothing has been written')
    expect(left.findAll('.handbook-aside-link')).toHaveLength(0)
  })

  it('keeps both rails on the handbook index, pointing the reader at a section', async () => {
    await router.push('/handbook')
    await router.isReady()
    wrapper = mountWithApp(HandbookLayout, {
      global: { plugins: [router] },
    })
    await flushPromises()

    // The columns must not collapse just because nothing is selected yet.
    expect(wrapper.findAll('.handbook-columns > .card')).toHaveLength(3)
    expect(wrapper.findAll('.handbook-aside')[0]!.text()).toContain('Pick a section')
    expect(wrapper.findAllComponents({ name: 'Tab' })).toHaveLength(HANDBOOK_SECTIONS.length)
  })
})
