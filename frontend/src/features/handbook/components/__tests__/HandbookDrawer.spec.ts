import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import Tooltip from 'openvue/tooltip'


import HandbookDrawer from '../HandbookDrawer.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

// jsdom has no layout, so scrollIntoView is not implemented. It is stubbed so
// the anchor test can assert which element the drawer scrolled to.
const scrollIntoView = vi.fn<() => void>()
Element.prototype.scrollIntoView = scrollIntoView

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', name: 'Home', component: { template: '<div />' } },
    { path: '/handbook', name: 'Handbook', component: { template: '<div />' } },
    { path: '/handbook/:section/:page', name: 'HandbookPage', component: { template: '<div />' } },
  ],
})

// The Drawer teleports to <body>, so assertions query the document rather
// than the wrapper, and the mount has to be torn down explicitly or the
// previous test's drawer is still there for the next one to find.
let wrapper: ReturnType<typeof mount> | null = null

async function mountDrawer(props: Record<string, unknown> = {}) {
  await router.push('/')
  await router.isReady()

  wrapper = mountWithApp(HandbookDrawer, {
    props: { visible: true, slug: 'production/auto-plan', ...props },
    global: {
      plugins: [router],
      directives: { tooltip: Tooltip },
    },
    attachTo: document.body,
  })
  // The doc arrives as its own lazily-imported chunk, so waiting a fixed
  // number of ticks is racy. This waits for the skeleton to actually give
  // way instead.
  await flushPromises()
  await vi.waitFor(() => {
    expect(document.querySelector('.handbook-skeleton')).toBeNull()
  })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  scrollIntoView.mockClear()
})

describe('HandbookDrawer', () => {
  it('renders every section of the page as a compiled heading', async () => {
    await mountDrawer()
    const text = document.body.textContent ?? ''

    expect(text).toContain('Running it')
    expect(text).toContain('Reading the result')
    expect(text).toContain('Planning level')
    expect(text).toContain('The six algorithms')

    // Markdown that failed to compile would render the headings as plain text
    // and leave no heading elements behind it.
    expect(document.querySelectorAll('.handbook-prose h2').length).toBeGreaterThanOrEqual(4)
  })

  it('gives every section the stable id the drawer deep-links to', async () => {
    await mountDrawer()

    // Explicit `{#id}` ids, so the same anchor works in both translations.
    const ids = ['run', 'result', 'planning-level', 'algorithms']
    const absent = ids.filter((id) => document.querySelector(`#${id}`) === null)
    expect(absent).toEqual([])
  })

  it('breaks down all six algorithms and marks the one the caller selected', async () => {
    await mountDrawer({ context: { algorithm: 'balanced_load' } })

    const cards = document.querySelectorAll('.algorithm-card')
    expect(cards).toHaveLength(6)
    // ordering / machine choice / best for / watch out, per algorithm.
    expect(document.querySelectorAll('.algorithm-card-facts dd')).toHaveLength(24)

    const current = document.querySelectorAll('.algorithm-card-current')
    expect(current).toHaveLength(1)
    expect(current[0]?.textContent).toContain('Balanced Load')
  })

  it('highlights nothing when the doc is opened without a selected algorithm', async () => {
    await mountDrawer()

    expect(document.querySelectorAll('.algorithm-card')).toHaveLength(6)
    expect(document.querySelectorAll('.algorithm-card-current')).toHaveLength(0)
  })

  it('scrolls to the section a caller deep-links to', async () => {
    await mountDrawer({ anchor: 'planning-level' })

    expect(scrollIntoView).toHaveBeenCalled()
    expect(scrollIntoView.mock.instances[0]).toBe(document.querySelector('#planning-level'))
  })

  it('ignores an anchor ending in a backslash instead of building an invalid selector', async () => {
    await mountDrawer({ anchor: 'planning-level\\' })
    await flushPromises()

    expect(scrollIntoView).not.toHaveBeenCalled()
  })

  it('reports a page that has no doc yet instead of rendering empty', async () => {
    await mountDrawer({ slug: 'not-written-yet' })

    expect(document.body.textContent).toContain('no handbook entry for this page yet')
    expect(document.querySelector('.handbook-prose')).toBeNull()
  })
})
