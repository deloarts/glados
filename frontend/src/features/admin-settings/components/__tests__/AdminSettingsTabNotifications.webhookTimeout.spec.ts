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

// Mount/user-fixture pattern mirrors AdminSettingsTabNotifications.webhookAdd.spec.ts.

const getMock = vi.fn<(url: string) => Promise<unknown>>()
const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import AdminSettingsTabNotifications from '../AdminSettingsTabNotifications.vue'

function makeNotifications(
  overrides: Partial<AdminNotificationSettings> = {},
): AdminNotificationSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    webhook_timeout_seconds: 10,
    ...overrides,
  }
}

async function mountTab(permissions: string[], notifications: AdminNotificationSettings) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  useAdminSettingsStore().settings = { notifications } as unknown as AllAdminSettings

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

function fieldRow(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('.field-row').find((r) => r.text().includes(label))!
}

function timeoutInput(wrapper: ReturnType<typeof mount>) {
  const label = i18n.global.t('adminSettings.notifications.webhooks.timeoutSeconds') as string
  return fieldRow(wrapper, label).findComponent({ name: 'InputNumber' })
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

describe('AdminSettingsTabNotifications, webhook delivery timeout', () => {
  beforeEach(() => {
    getMock.mockReset()
    putMock.mockReset()
    // Both panel fetches on mount (subscriptions, event types) return empty.
    getMock.mockResolvedValue({ data: [] })
  })

  it('reflects settings.notifications.webhook_timeout_seconds', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeNotifications({ webhook_timeout_seconds: 45 }),
    )

    expect(timeoutInput(wrapper).props('modelValue')).toBe(45)

    wrapper.unmount()
  })

  it('is bounded 1-120', async () => {
    const wrapper = await mountTab(['write:settings'], makeNotifications())

    expect(timeoutInput(wrapper).props('min')).toBe(1)
    expect(timeoutInput(wrapper).props('max')).toBe(120)

    wrapper.unmount()
  })

  it('PUTs webhook_timeout_seconds with the rest of the notifications form on Save', async () => {
    putMock.mockResolvedValue({ data: makeNotifications({ webhook_timeout_seconds: 30 }) })
    const wrapper = await mountTab(['write:settings'], makeNotifications())

    await timeoutInput(wrapper).vm.$emit('update:modelValue', 30)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/notifications',
      expect.objectContaining({ webhook_timeout_seconds: 30 }),
    )

    wrapper.unmount()
  })
})
