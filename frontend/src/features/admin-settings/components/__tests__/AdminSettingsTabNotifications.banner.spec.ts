import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import OpenVue from 'openvue/config'
import ToastService from 'openvue/toastservice'
import Toast from 'openvue/toast'
import ConfirmationService from 'openvue/confirmationservice'
import Aura from '@openvue/themes/aura'

import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useAdminSettingsStore } from '../../stores/adminSettingsStore'

import type {
  AdminBannerSettings,
  AdminNotificationSettings,
  AllAdminSettings,
} from '../../types/adminSettingsTypes'

// Mirrors AdminSettingsTabNotifications.webhookAdd.spec.ts's mount/user
// fixture and AdminSettingsTabMaintenance.spec.ts's Toast-alongside pattern
// (useToast() needs a real <Toast/> in the tree to assert on toast text).

const getMock = vi.fn<(url: string) => Promise<unknown>>()
const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: (url: string) => getMock(url),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import AdminSettingsTabNotifications from '../AdminSettingsTabNotifications.vue'

const NOTIFICATIONS: AdminNotificationSettings = {
  id: 1,
  public_id: '11111111-1111-1111-1111-111111111111',
  webhook_timeout_seconds: 10,
}

function makeBanner(overrides: Partial<AdminBannerSettings> = {}): AdminBannerSettings {
  return {
    id: 1,
    public_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    enabled: false,
    text: '',
    severity: 'info',
    shows_from: null,
    shows_until: null,
    dismissable: true,
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

async function mountTab(permissions: string[], banner: AdminBannerSettings = makeBanner()) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  useAdminSettingsStore().settings = {
    notifications: NOTIFICATIONS,
    banner,
  } as unknown as AllAdminSettings

  const wrapper = mount(
    {
      components: { AdminSettingsTabNotifications, Toast },
      template: '<div><AdminSettingsTabNotifications /><Toast /></div>',
    },
    {
      attachTo: document.body,
      global: {
        plugins: [
          pinia,
          [OpenVue, { theme: { preset: Aura } }],
          ToastService,
          ConfirmationService,
          i18n,
        ],
      },
    },
  )
  await flushPromises()
  return wrapper
}

function buttonsLabelled(wrapper: ReturnType<typeof mount>, key: string) {
  const label = i18n.global.t(key) as string
  return wrapper.findAllComponents({ name: 'Button' }).filter((b) => b.props('label') === label)
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return buttonsLabelled(wrapper, 'common.save')[0]!
}

describe('AdminSettingsTabNotifications, New Acknowledgement button', () => {
  beforeEach(() => {
    getMock.mockReset()
    putMock.mockReset()
    getMock.mockResolvedValue({ data: [] })
    document.body.innerHTML = ''
  })

  it('renders exactly one New Acknowledgement button in the Toolbar', async () => {
    const wrapper = await mountTab(['write:settings'])

    const buttons = buttonsLabelled(wrapper, 'adminSettings.notifications.acknowledgements.new')
    expect(buttons).toHaveLength(1)
    expect(wrapper.findComponent({ name: 'Toolbar' }).element.contains(buttons[0]!.element)).toBe(
      true,
    )

    wrapper.unmount()
  })

  it('is disabled without write:settings', async () => {
    const wrapper = await mountTab([])

    expect(
      buttonsLabelled(wrapper, 'adminSettings.notifications.acknowledgements.new')[0]!.element.hasAttribute(
        'disabled',
      ),
    ).toBe(true)

    wrapper.unmount()
  })

  it('opens the acknowledgements panel create dialog', async () => {
    const wrapper = await mountTab(['write:settings'])
    const dialog = wrapper.findComponent({ name: 'AcknowledgementFormDialog' })
    expect(dialog.props('visible')).toBe(false)

    await buttonsLabelled(wrapper, 'adminSettings.notifications.acknowledgements.new')[0]!.trigger(
      'click',
    )
    await flushPromises()

    expect(dialog.props('visible')).toBe(true)

    wrapper.unmount()
  })
})

describe('AdminSettingsTabNotifications, Banner section', () => {
  beforeEach(() => {
    getMock.mockReset()
    putMock.mockReset()
    getMock.mockResolvedValue({ data: [] })
    document.body.innerHTML = ''
  })

  it('reflects settings.banner in the form', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeBanner({ enabled: true, text: 'We upgrade at 18:00.', severity: 'warning' }),
    )

    expect(wrapper.findComponent({ name: 'ToggleSwitch' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'Textarea' }).props('modelValue')).toBe(
      'We upgrade at 18:00.',
    )

    wrapper.unmount()
  })

  it('Save PUTs the banner as ISO instants, alongside the webhook settings', async () => {
    putMock.mockImplementation((url: string) => {
      if (url === '/admin/settings/notifications') return Promise.resolve({ data: NOTIFICATIONS })
      return Promise.resolve({ data: makeBanner() })
    })
    const wrapper = await mountTab(['write:settings'], makeBanner())

    await wrapper.findComponent({ name: 'Textarea' }).setValue('We upgrade at 18:00.')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/notifications',
      expect.objectContaining({ webhook_timeout_seconds: 10 }),
    )
    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/banner',
      expect.objectContaining({
        text: 'We upgrade at 18:00.',
        shows_from: null,
        shows_until: null,
      }),
    )

    wrapper.unmount()
  })

  it('saves the "users may dismiss it" toggle, off included', async () => {
    putMock.mockResolvedValue({ data: makeBanner({ dismissable: false }) })
    const wrapper = await mountTab(['write:settings'], makeBanner({ dismissable: true }))

    const label = i18n.global.t('adminSettings.notifications.banner.dismissable') as string
    const row = wrapper.findAll('.field-row--toggle').find((r) => r.text().includes(label))
    const toggle = row!.findComponent({ name: 'ToggleSwitch' })
    expect(toggle.props('modelValue')).toBe(true)

    await toggle.vm.$emit('update:modelValue', false)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/banner',
      expect.objectContaining({ dismissable: false }),
    )

    wrapper.unmount()
  })

  it('serialises the date-picker window as ISO instants (toISOString, not dateToParam)', async () => {
    putMock.mockResolvedValue({ data: makeBanner() })
    const wrapper = await mountTab(
      ['write:settings'],
      makeBanner({
        shows_from: '2026-08-27T10:00:00.000Z',
        shows_until: '2026-08-27T12:00:00.000Z',
      }),
    )

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/banner',
      expect.objectContaining({
        shows_from: '2026-08-27T10:00:00.000Z',
        shows_until: '2026-08-27T12:00:00.000Z',
      }),
    )

    wrapper.unmount()
  })

  it('blocks Save and shows an inline error when Shows Until is before Shows From', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeBanner({
        shows_from: '2026-08-27T12:00:00Z',
        shows_until: '2026-08-27T10:00:00Z',
      }),
    )

    expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
    expect(document.body.textContent).toContain(
      i18n.global.t('adminSettings.notifications.banner.windowInvalid') as string,
    )
    expect(putMock).not.toHaveBeenCalled()

    wrapper.unmount()
  })

  it('toasts a banner-specific error with the 422 detail when the banner save fails', async () => {
    putMock.mockImplementation((url: string) => {
      if (url === '/admin/settings/notifications') return Promise.resolve({ data: NOTIFICATIONS })
      return Promise.reject({
        isAxiosError: true,
        response: { status: 422, data: { detail: 'text: required when enabled' } },
      })
    })
    const wrapper = await mountTab(['write:settings'], makeBanner())

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain(
      i18n.global.t('adminSettings.notifications.banner.saveFailed') as string,
    )
    expect(document.body.textContent).toContain('text: required when enabled')

    wrapper.unmount()
  })

  it('toasts the generic error, not the banner one, when the webhook settings save fails first', async () => {
    putMock.mockImplementation((url: string) => {
      if (url === '/admin/settings/notifications') return Promise.reject(new Error('network down'))
      return Promise.resolve({ data: makeBanner() })
    })
    const wrapper = await mountTab(['write:settings'], makeBanner())

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(document.body.textContent).toContain(
      i18n.global.t('adminSettings.errors.unknown') as string,
    )
    // Notifications failed before the banner PUT was ever attempted.
    expect(putMock).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })
})
