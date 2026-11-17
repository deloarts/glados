import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useAdminSettingsStore } from '../../stores/adminSettingsStore'

import type { AdminFeatureSettings, AllAdminSettings } from '../../types/adminSettingsTypes'

// Mount/user-fixture pattern mirrors AdminSettingsTabNotifications.webhookTimeout.spec.ts.

const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi.fn<(url: string) => Promise<unknown>>(),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import AdminSettingsTabFeatures from '../AdminSettingsTabFeatures.vue'

function makeFeatures(overrides: Partial<AdminFeatureSettings> = {}): AdminFeatureSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    enable_email_notifications: true,
    enable_production_planning: true,
    allow_private_webhooks: true,
    enable_calculations: true,
    enable_checklists: true,
    enable_devices: true,
    enable_sequences: true,
    enable_todos: true,
    ...overrides,
  }
}

async function mountTab(permissions: string[], features: AdminFeatureSettings) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  useAdminSettingsStore().settings = { features } as unknown as AllAdminSettings

  const wrapper = mountWithApp(AdminSettingsTabFeatures, { pinia, attachTo: document.body })
  await flushPromises()
  return wrapper
}

function privateWebhooksToggle(wrapper: ReturnType<typeof mount>) {
  const label = i18n.global.t('adminSettings.features.allowPrivateWebhooks') as string
  return wrapper
    .findAll('.field-row')
    .find((r) => r.text().includes(label))!
    .findComponent({ name: 'ToggleSwitch' })
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

describe('AdminSettingsTabFeatures, private webhook targets', () => {
  beforeEach(() => {
    putMock.mockReset()
  })

  it('reflects settings.features.allow_private_webhooks', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeFeatures({ allow_private_webhooks: false }),
    )

    expect(privateWebhooksToggle(wrapper).props('modelValue')).toBe(false)

    wrapper.unmount()
  })

  it('PUTs allow_private_webhooks with the other flags on Save', async () => {
    putMock.mockResolvedValue({ data: makeFeatures({ allow_private_webhooks: false }) })
    const wrapper = await mountTab(['write:settings'], makeFeatures())

    await privateWebhooksToggle(wrapper).vm.$emit('update:modelValue', false)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/features',
      expect.objectContaining({ allow_private_webhooks: false }),
    )

    wrapper.unmount()
  })

  it('is disabled without write:settings', async () => {
    const wrapper = await mountTab(['read:settings'], makeFeatures())

    expect(privateWebhooksToggle(wrapper).props('disabled')).toBe(true)

    wrapper.unmount()
  })
})

function moduleToggle(wrapper: ReturnType<typeof mount>, key: string) {
  return wrapper.find(`[data-testid="feature-${key}"]`).findComponent({ name: 'ToggleSwitch' })
}

describe('AdminSettingsTabFeatures, modules', () => {
  beforeEach(() => {
    putMock.mockReset()
  })

  it('PUTs the module switches and applies them to the host flags', async () => {
    putMock.mockResolvedValue({
      data: makeFeatures({ enable_calculations: false, enable_devices: false }),
    })
    const wrapper = await mountTab(['write:settings'], makeFeatures())

    await moduleToggle(wrapper, 'enable_calculations').vm.$emit('update:modelValue', false)
    await moduleToggle(wrapper, 'enable_devices').vm.$emit('update:modelValue', false)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/features',
      expect.objectContaining({ enable_calculations: false, enable_devices: false }),
    )
    const host = useHostStore()
    expect(host.calculationsEnabled).toBe(false)
    expect(host.devicesEnabled).toBe(false)
    // Sequences go with the devices they are built from.
    expect(host.sequencesEnabled).toBe(false)
    expect(host.checklistsEnabled).toBe(true)

    wrapper.unmount()
  })

  it('disables the sequences switch while devices are off', async () => {
    const wrapper = await mountTab(['write:settings'], makeFeatures({ enable_devices: false }))

    expect(moduleToggle(wrapper, 'enable_sequences').props('disabled')).toBe(true)
    expect(moduleToggle(wrapper, 'enable_todos').props('disabled')).toBe(false)

    wrapper.unmount()
  })
})
