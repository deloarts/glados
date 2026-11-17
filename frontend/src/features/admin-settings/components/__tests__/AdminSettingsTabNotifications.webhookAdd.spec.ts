import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ConfirmationService from 'openvue/confirmationservice'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useAdminSettingsStore } from '../../stores/adminSettingsStore'

import type { AdminNotificationSettings, AllAdminSettings } from '../../types/adminSettingsTypes'

// The "Add Webhook" button lives in the tab's controls bar (next to Save,
// like every other tab's actions), not in WebhookSubscriptionsPanel. These
// tests pin that the bar button opens the panel's create dialog, and that
// the panel itself renders no such button, so there are never two ways to
// open the same dialog.
//
// Mount/user-fixture pattern mirrors AdminSettingsTabProduction.*.spec.ts.

const getMock = vi.fn<(url: string) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    put: vi.fn<() => Promise<unknown>>().mockResolvedValue({ data: {} }),
  },
}))

import AdminSettingsTabNotifications from '../AdminSettingsTabNotifications.vue'

const NOTIFICATIONS: AdminNotificationSettings = {
  id: 1,
  public_id: '11111111-1111-1111-1111-111111111111',
  webhook_timeout_seconds: 10,
}

async function mountTab(permissions: string[]) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  useAdminSettingsStore().settings = {
    notifications: NOTIFICATIONS,
  } as unknown as AllAdminSettings

  const wrapper = mountWithApp(AdminSettingsTabNotifications, {
    pinia,
    attachTo: document.body,
    global: {
      plugins: [ConfirmationService],
    },
  })
  await flushPromises()
  return wrapper
}

function addButtons(wrapper: ReturnType<typeof mount>) {
  const label = i18n.global.t('adminSettings.notifications.webhooks.add') as string
  return wrapper.findAllComponents({ name: 'Button' }).filter((b) => b.props('label') === label)
}

describe('AdminSettingsTabNotifications, Add Webhook in the controls bar', () => {
  beforeEach(() => {
    getMock.mockReset()
    // Both panel fetches on mount (subscriptions, event types) return empty.
    getMock.mockResolvedValue({ data: [] })
  })

  it('renders exactly one Add Webhook button, in the Toolbar rather than the panel', async () => {
    const wrapper = await mountTab(['write:settings'])

    const buttons = addButtons(wrapper)
    expect(buttons).toHaveLength(1)
    expect(wrapper.findComponent({ name: 'Toolbar' }).element.contains(buttons[0]!.element)).toBe(
      true,
    )
    expect(wrapper.find('.webhooks-panel').element.contains(buttons[0]!.element)).toBe(false)

    wrapper.unmount()
  })

  it('opens the create dialog of the webhook panel', async () => {
    const wrapper = await mountTab(['write:settings'])
    const dialog = wrapper.findComponent({ name: 'WebhookFormDialog' })
    expect(dialog.props('visible')).toBe(false)

    await addButtons(wrapper)[0]!.trigger('click')
    await flushPromises()

    expect(dialog.props('visible')).toBe(true)
    // Create, not edit: no subscription handed to the form.
    expect(dialog.props('subscription')).toBeUndefined()

    wrapper.unmount()
  })

  it('is disabled without write:settings', async () => {
    const wrapper = await mountTab([])

    expect(addButtons(wrapper)[0]!.element.hasAttribute('disabled')).toBe(true)

    wrapper.unmount()
  })
})
