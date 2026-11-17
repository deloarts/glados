import { describe, it, expect, afterEach } from 'vitest'
import { flushPromises, DOMWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { i18n } from '@/core/i18n'

import SystemUserWarningDialog from '../SystemUserWarningDialog.vue'

// Dialog teleports to document.body (OpenVue's default `appendTo`), so it
// has to be looked up there rather than within the wrapper, the same
// approach as WebhookFormDialog.spec.ts.
function mountDialog() {
  const pinia = createPinia()
  setActivePinia(pinia)

  const wrapper = mountWithApp(SystemUserWarningDialog, {
    pinia,
    attachTo: document.body,
  })

  return { wrapper, userStore: useCurrentUserStore() }
}

describe('SystemUserWarningDialog', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('is hidden when no warning is pending', async () => {
    const { wrapper } = mountDialog()
    await flushPromises()

    expect(document.body.querySelector('[role="dialog"]')).toBeNull()

    wrapper.unmount()
  })

  it('renders the warning when systemUserWarningPending is true', async () => {
    const { wrapper, userStore } = mountDialog()
    userStore.systemUserWarningPending = true
    await flushPromises()

    expect(document.body.querySelector('[role="dialog"]')).not.toBeNull()
    expect(document.body.textContent).toContain(i18n.global.t('main.systemUserWarning.title'))
    expect(document.body.textContent).toContain(i18n.global.t('main.systemUserWarning.body'))
    expect(document.body.textContent).toContain(i18n.global.t('main.systemUserWarning.countdown'))

    wrapper.unmount()
  })

  it('acknowledges and hides the dialog when the Understood button is clicked', async () => {
    const { wrapper, userStore } = mountDialog()
    userStore.systemUserWarningPending = true
    await flushPromises()

    const button = Array.from(document.body.querySelectorAll('[role="dialog"] button')).find(
      (btn) => btn.textContent?.includes(i18n.global.t('main.systemUserWarning.acknowledge')),
    )
    expect(button).toBeDefined()

    await new DOMWrapper(button!).trigger('click')
    await flushPromises()

    expect(userStore.systemUserWarningPending).toBe(false)
    expect(document.body.querySelector('[role="dialog"]')).toBeNull()

    wrapper.unmount()
  })
})
