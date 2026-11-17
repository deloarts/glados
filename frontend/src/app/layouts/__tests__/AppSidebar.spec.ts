import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import Toast from 'openvue/toast'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'
import { localeEndonym } from '@/core/i18n/localeMessages'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useLayoutStore } from '@/core/stores/layoutStore'
import type { UserResponse } from '@/core/types/userResponse'

const updateUserMock = vi.fn<(...args: unknown[]) => Promise<unknown>>()

vi.mock('@/core/api/users/updateUser', () => ({
  updateUser: (...args: unknown[]) => updateUserMock(...args),
}))

import AppSidebar from '../AppSidebar.vue'

// updateUser calls from setLocale/onToggleDarkMode are awaited so a failed
// save surfaces as a toast to the user, instead of failing silently as an
// unhandled rejection.
describe('AppSidebar, preference save failures', () => {
  let router: ReturnType<typeof createRouter>

  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    // OpenVue's ToastService is a module-level singleton whose teleported
    // DOM lives in document.body, which outlives one test's wrapper.unmount(),
    // so a toast from the previous case would otherwise leak into this one.
    document.body.innerHTML = ''
    useCurrentUserStore().user = {
      id: 1,
      is_systemuser: false,
      permissions: [],
    } as unknown as UserResponse

    router = createRouter({
      history: createMemoryHistory(),
      // The sidebar's route-navigating items are `<router-link>`s, which
      // resolve their `href` against this router on every render, so a
      // catch-all keeps that resolution quiet instead of warning "No match
      // found" for every nav item that isn't literally "/".
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
      ],
    })
    await router.push('/')
  })

  function mountSidebar() {
    return mount(
      {
        components: { AppSidebar, Toast },
        template: '<div><AppSidebar :collapsed="false" /><Toast /></div>',
      },
      {
        global: {
          plugins: [router, [OpenVue, { theme: { preset: Aura } }], ToastService, i18n],
        },
      },
    )
  }

  it('shows an error toast when saving the dark-mode toggle fails', async () => {
    updateUserMock.mockRejectedValue(new Error('network error'))
    const wrapper = mountSidebar()

    await wrapper.find('[data-testid="dark-mode-toggle"]').trigger('click')
    await flushPromises()

    expect(updateUserMock).toHaveBeenCalledWith(1, { theme_dark_mode: expect.any(Boolean) })
    // OpenVue's <Toast> teleports its content to document.body by default,
    // so it never shows up under the mounted wrapper's own subtree.
    expect(document.body.textContent).toContain('Could not save your preference. Please try again.')
  })

  it('does not show a toast when the save succeeds', async () => {
    updateUserMock.mockResolvedValue({})
    const wrapper = mountSidebar()

    await wrapper.find('[data-testid="dark-mode-toggle"]').trigger('click')
    await flushPromises()

    expect(document.body.textContent).not.toContain('Could not save your preference')
  })

  it('hides the Settings link for a non-admin user', () => {
    const wrapper = mountSidebar()
    expect(wrapper.find('a[href="/settings"]').exists()).toBe(false)
  })
})

describe('AppSidebar, Settings link visibility', () => {
  let router: ReturnType<typeof createRouter>

  beforeEach(async () => {
    setActivePinia(createPinia())
    document.body.innerHTML = ''

    router = createRouter({
      history: createMemoryHistory(),
      // The sidebar's route-navigating items are `<router-link>`s, which
      // resolve their `href` against this router on every render, so a
      // catch-all keeps that resolution quiet instead of warning "No match
      // found" for every nav item that isn't literally "/".
      routes: [
        { path: '/', component: { template: '<div />' } },
        { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
      ],
    })
    await router.push('/')
  })

  function mountSidebar() {
    return mount(
      { components: { AppSidebar }, template: '<AppSidebar :collapsed="false" />' },
      {
        global: {
          plugins: [router, [OpenVue, { theme: { preset: Aura } }], ToastService, i18n],
        },
      },
    )
  }

  it('shows the Settings link for an admin (is_systemuser)', () => {
    useCurrentUserStore().user = {
      id: 1,
      is_systemuser: true,
      permissions: [],
    } as unknown as UserResponse

    const wrapper = mountSidebar()
    expect(wrapper.find('a[href="/settings"]').exists()).toBe(true)
  })

  it('shows the Settings link for a non-system user with read:settings', () => {
    useCurrentUserStore().user = {
      id: 1,
      is_systemuser: false,
      permissions: ['read:settings'],
    } as unknown as UserResponse

    const wrapper = mountSidebar()
    expect(wrapper.find('a[href="/settings"]').exists()).toBe(true)
  })
})

// The 9 nav items that navigate to a route are `<router-link>`s (native
// focus, native Enter, a real href); the 3 that perform an in-place action
// follow the codebase's existing `role="button"` + `@keydown.enter`/`.space`
// pattern (see ClickableOrderNumber.vue). All 12 are reachable by keyboard
// and screen readers.
describe('AppSidebar, keyboard accessibility', () => {
  let router: ReturnType<typeof createRouter>

  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    updateUserMock.mockResolvedValue({})
    document.body.innerHTML = ''
    useCurrentUserStore().user = {
      id: 1,
      is_systemuser: true,
      permissions: [],
    } as unknown as UserResponse

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div />' } },
        // Catches every target the sidebar links to so router-link can
        // resolve an href without the router warning about an unmatched
        // location, since the exact destination component isn't under test here.
        { path: '/:pathMatch(.*)*', component: { template: '<div />' } },
      ],
    })
    await router.push('/')
  })

  function mountSidebar() {
    return mount(
      { components: { AppSidebar }, template: '<AppSidebar :collapsed="false" />' },
      {
        global: {
          plugins: [router, [OpenVue, { theme: { preset: Aura } }], ToastService, i18n],
        },
      },
    )
  }

  // The first column only labels the test name, which predates the lookup
  // by data-testid; the nav item itself is found by its testid.
  /* eslint-disable no-restricted-syntax -- test name labels, not selectors */
  const routeItems: Array<[string, string, string]> = [
    ['.mdi-view-dashboard', '/dashboard', 'nav-dashboard'],
    ['.mdi-checkbox-marked-outline', '/todo', 'nav-todo'],
    ['.mdi-folder', '/workspace', 'nav-workspace'],
    ['.mdi-book-open-page-variant', '/catalogue/bought-items', 'nav-catalogue'],
    ['.mdi-cart', '/procurement/orders', 'nav-procurement'],
    ['.mdi-factory', '/production/lots', 'nav-production'],
    ['.mdi-table-large', '/tables', 'nav-tables'],
    ['.mdi-toolbox', '/tools', 'nav-tools'],
    ['.mdi-bookshelf', '/resources', 'nav-resources'],
    ['.mdi-tune', '/settings', 'nav-settings'],
  ]
  /* eslint-enable no-restricted-syntax */

  it.each(routeItems)(
    'renders the %s nav item as a real <a href="%s"> in the tab order',
    (_iconLabel, href, testId) => {
      const wrapper = mountSidebar()
      const item = wrapper.find(`[data-testid="${testId}"]`)
      expect(item.exists()).toBe(true)

      const link = item.element.closest('a.nav-item')
      expect(link).not.toBeNull()
      expect(link?.getAttribute('href')).toBe(href)
    },
  )

  it('exposes exactly the 3 action items as role="button" with tabindex 0', () => {
    const wrapper = mountSidebar()
    const items = wrapper.findAll('.nav-item[role="button"]')

    // DOM order: Language, Dark mode, Toggle sidebar.
    expect(items).toHaveLength(3)
    items.forEach((item) => {
      expect(item.attributes('tabindex')).toBe('0')
    })
  })

  it('names the active language by its own name, not by its locale code', () => {
    const wrapper = mountSidebar()
    const language = wrapper.findAll('.nav-item[role="button"]')[0]
    if (!language) throw new Error('expected the Language nav item to be in the DOM')

    const label = language.attributes('aria-label') ?? ''
    expect(label).toContain(localeEndonym(i18n.global.locale.value))
    expect(label).not.toContain(i18n.global.locale.value.toUpperCase())
  })

  it('Enter and Space both open the language popover', async () => {
    const wrapper = mountSidebar()
    const language = wrapper.findAll('.nav-item[role="button"]')[0]
    if (!language) throw new Error('expected the Language nav item to be in the DOM')

    await language.trigger('keydown.enter')
    await flushPromises()
    expect(document.body.querySelector('.lang-list')).not.toBeNull()

    // Re-mount for a clean popover instance rather than asserting a second
    // open on top of the first.
    document.body.innerHTML = ''
    const wrapper2 = mountSidebar()
    const language2 = wrapper2.findAll('.nav-item[role="button"]')[0]
    if (!language2) throw new Error('expected the Language nav item to be in the DOM')
    await language2.trigger('keydown.space')
    await flushPromises()
    expect(document.body.querySelector('.lang-list')).not.toBeNull()
  })

  it('Enter and Space both toggle dark mode', async () => {
    const layoutStore = useLayoutStore()
    const wrapper = mountSidebar()
    const darkMode = wrapper.findAll('.nav-item[role="button"]')[1]
    if (!darkMode) throw new Error('expected the Dark mode nav item to be in the DOM')
    const initial = layoutStore.isDarkMode

    await darkMode.trigger('keydown.enter')
    expect(layoutStore.isDarkMode).toBe(!initial)

    await darkMode.trigger('keydown.space')
    expect(layoutStore.isDarkMode).toBe(initial)
  })

  it('Enter and Space both toggle the sidebar width', async () => {
    const layoutStore = useLayoutStore()
    const wrapper = mountSidebar()
    const toggle = wrapper.findAll('.nav-item[role="button"]')[2]
    if (!toggle) throw new Error('expected the Toggle sidebar nav item to be in the DOM')
    const initial = layoutStore.isSidebarWide

    await toggle.trigger('keydown.enter')
    expect(layoutStore.isSidebarWide).toBe(!initial)

    await toggle.trigger('keydown.space')
    expect(layoutStore.isSidebarWide).toBe(initial)
  })
})
