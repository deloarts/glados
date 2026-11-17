import { describe, it, expect, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import Tooltip from 'openvue/tooltip'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useHostStore } from '@/core/host/stores/hostStore'

import OfficeLauncher from '../OfficeLauncher.vue'

function mountLauncher() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const hostStore = useHostStore()

  const wrapper = mountWithApp(OfficeLauncher, {
    pinia,
    global: { directives: { tooltip: Tooltip } },
    attachTo: document.body,
  })

  return { wrapper, hostStore }
}

describe('OfficeLauncher', () => {
  afterEach(() => {
    // Popover content teleports to <body> and outlives wrapper.unmount().
    document.body.innerHTML = ''
  })

  it('renders nothing when hostStore.officeLauncherEnabled is false', () => {
    const { wrapper, hostStore } = mountLauncher()
    expect(hostStore.officeLauncherEnabled).toBe(false)

    expect(wrapper.find('.office-launcher-trigger').exists()).toBe(false)
    expect(wrapper.html()).toBe('<!--v-if-->')

    wrapper.unmount()
  })

  it('renders the waffle button when officeLauncherEnabled is true', () => {
    const { wrapper, hostStore } = mountLauncher()
    hostStore.officeLauncherEnabled = true

    return flushPromises().then(() => {
      const button = wrapper.find('.office-launcher-trigger')
      expect(button.exists()).toBe(true)
      expect(button.element.tagName).toBe('BUTTON')
      expect(button.attributes('aria-haspopup')).toBe('dialog')
      expect(button.attributes('aria-expanded')).toBe('false')

      wrapper.unmount()
    })
  })

  it('opens the popover on click', async () => {
    const { wrapper, hostStore } = mountLauncher()
    hostStore.officeLauncherEnabled = true
    await flushPromises()

    expect(document.body.querySelector('.office-launcher-menu')).toBeNull()

    await wrapper.find('.office-launcher-trigger').trigger('click')
    await flushPromises()

    expect(document.body.querySelector('.office-launcher-menu')).not.toBeNull()

    wrapper.unmount()
  })

  it('renders every core tile plus SharePoint with the correct hard-coded hrefs', async () => {
    const { wrapper, hostStore } = mountLauncher()
    hostStore.officeLauncherEnabled = true
    hostStore.officeSharepointUrl = 'https://contoso.sharepoint.com/sites/hub'
    await flushPromises()

    await wrapper.find('.office-launcher-trigger').trigger('click')
    await flushPromises()

    const header = document.body.querySelector<HTMLAnchorElement>('.office-launcher-header')
    expect(header?.getAttribute('href')).toBe('https://m365.cloud.microsoft/')

    const hrefByKey: Record<string, string> = {
      outlook: 'https://outlook.cloud.microsoft/',
      teams: 'https://teams.cloud.microsoft/',
      word: 'https://word.cloud.microsoft/',
      excel: 'https://excel.cloud.microsoft/',
      powerpoint: 'https://powerpoint.cloud.microsoft/',
      oneDrive: 'https://onedrive.cloud.microsoft/',
    }

    const tiles = document.body.querySelectorAll<HTMLAnchorElement>('.office-launcher-tile')
    const hrefs = Array.from(tiles).map((tile) => tile.getAttribute('href'))

    Object.values(hrefByKey).forEach((href) => {
      expect(hrefs).toContain(href)
    })
    expect(hrefs).toContain('https://contoso.sharepoint.com/sites/hub')
    expect(tiles).toHaveLength(7)

    tiles.forEach((tile) => {
      expect(tile.getAttribute('target')).toBe('_blank')
      expect(tile.getAttribute('rel')).toBe('noopener noreferrer')
    })

    wrapper.unmount()
  })

  it('hides the SharePoint tile when officeSharepointUrl is empty', async () => {
    const { wrapper, hostStore } = mountLauncher()
    hostStore.officeLauncherEnabled = true
    hostStore.officeSharepointUrl = ''
    await flushPromises()

    await wrapper.find('.office-launcher-trigger').trigger('click')
    await flushPromises()

    const tiles = document.body.querySelectorAll<HTMLAnchorElement>('.office-launcher-tile')
    expect(tiles).toHaveLength(6)
    const hrefs = Array.from(tiles).map((tile) => tile.getAttribute('href'))
    expect(hrefs.some((href) => href?.includes('sharepoint'))).toBe(false)

    wrapper.unmount()
  })

  it('hides the SharePoint tile when officeSharepointUrl holds a non-http(s) scheme', async () => {
    const { wrapper, hostStore } = mountLauncher()
    hostStore.officeLauncherEnabled = true
    // Defence in depth: the backend should never send this, but a stale or
    // pre-migration row could in theory still hold a bad value.
    hostStore.officeSharepointUrl = 'javascript:alert(1)'
    await flushPromises()

    await wrapper.find('.office-launcher-trigger').trigger('click')
    await flushPromises()

    const tiles = document.body.querySelectorAll<HTMLAnchorElement>('.office-launcher-tile')
    expect(tiles).toHaveLength(6)
    const hrefs = Array.from(tiles).map((tile) => tile.getAttribute('href'))
    expect(hrefs.some((href) => href?.startsWith('javascript:'))).toBe(false)

    wrapper.unmount()
  })
})
