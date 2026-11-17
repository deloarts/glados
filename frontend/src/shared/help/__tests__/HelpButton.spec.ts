import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import Tooltip from 'openvue/tooltip'


import HelpButton from '../HelpButton.vue'
import { mountWithApp } from '@/test-utils/mountWithApp'

Element.prototype.scrollIntoView = vi.fn<() => void>()

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    // Stands in for a page that declares its doc, the way real routes do.
    {
      path: '/documented',
      name: 'Documented',
      component: { template: '<div />' },
      meta: { handbook: 'production/auto-plan' },
    },
    { path: '/undocumented', name: 'Undocumented', component: { template: '<div />' } },
    // Declares no doc: its path alone has to resolve to account/access-tokens.
    { path: '/account/:tab?', name: 'Account', component: { template: '<div />' } },
    { path: '/handbook/:section/:page', name: 'HandbookPage', component: { template: '<div />' } },
  ],
})

let wrapper: ReturnType<typeof mount> | null = null

async function mountButton(path: string, props: Record<string, unknown> = {}) {
  await router.push(path)
  await router.isReady()

  wrapper = mountWithApp(HelpButton, {
    props,
    global: {
      plugins: [router],
      directives: { tooltip: Tooltip },
    },
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
})

describe('HelpButton', () => {
  it('takes its doc from the current route', async () => {
    const button = await mountButton('/documented')

    const primeButton = button.findComponent({ name: 'Button' })
    expect(primeButton.exists()).toBe(true)
    expect(primeButton.props('icon')).toBe('mdi mdi-help-circle-outline')
  })

  it('renders nothing on a page that has no doc yet', async () => {
    const button = await mountButton('/undocumented')

    // Dropping the button into a toolbar before its content is written must
    // not leave a control that opens an empty drawer.
    expect(button.findComponent({ name: 'Button' }).exists()).toBe(false)
  })

  it('prefers an explicit slug over the route', async () => {
    const button = await mountButton('/undocumented', { slug: 'production/auto-plan' })

    expect(button.findComponent({ name: 'Button' }).exists()).toBe(true)
  })

  it('falls back to the route path when nothing declares a doc', async () => {
    // This is what makes the shared controls bar work with no per-view wiring:
    // /account/access-tokens is documented at account/access-tokens.
    const button = await mountButton('/account/access-tokens')

    expect(button.findComponent({ name: 'Button' }).exists()).toBe(true)
    await button.findComponent({ name: 'Button' }).trigger('click')
    await vi.waitFor(() => {
      expect(document.querySelector('.handbook-prose')).not.toBeNull()
    })
    expect(document.body.textContent).toContain('Access Tokens')
  })

  it('ignores route paths deeper than a section and page', async () => {
    // /account alone is a section, not a doc, so nothing should appear.
    const button = await mountButton('/account')

    expect(button.findComponent({ name: 'Button' }).exists()).toBe(false)
  })

  it('opens the drawer with the doc rendered', async () => {
    const button = await mountButton('/documented')
    await button.findComponent({ name: 'Button' }).trigger('click')

    await vi.waitFor(() => {
      expect(document.querySelector('.handbook-prose')).not.toBeNull()
    })
    expect(document.body.textContent).toContain('Reading the result')
  })
})
