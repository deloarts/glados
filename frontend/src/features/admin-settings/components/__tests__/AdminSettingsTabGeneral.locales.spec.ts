import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { userWithPermissions } from '@/test-utils/factories'
import { useAdminSettingsStore } from '../../stores/adminSettingsStore'

import type { AdminGeneralSettings, AllAdminSettings } from '../../types/adminSettingsTypes'

// Mirrors AdminSettingsTabProduction.sourceApproval.spec.ts's mount/
// userWithPermissions/store-seeding pattern; the General tab has no spec of its own
// yet either, so this establishes one scoped to just the new Locales
// section rather than covering the whole tab.

const putMock = vi.fn<(url: string, payload: unknown) => Promise<unknown>>()

vi.mock('@/core/api', () => ({
  default: {
    get: vi
      .fn<() => Promise<unknown>>()
      .mockResolvedValue({ data: { items: [], total: 0, limit: 1000, skip: 0 } }),
    put: (url: string, payload: unknown) => putMock(url, payload),
  },
}))

import AdminSettingsTabGeneral from '../AdminSettingsTabGeneral.vue'

function makeGeneralSettings(overrides: Partial<AdminGeneralSettings> = {}): AdminGeneralSettings {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    company_name: null,
    company_legal_name: null,
    has_company_logo: false,
    contact_email: null,
    imprint_url: null,
    privacy_url: null,
    support_url: null,
    product_number_pattern: '',
    project_number_pattern: '',
    allow_headless_projects: true,
    empty_value_placeholder: '-',
    office_launcher_enabled: false,
    office_sharepoint_url: '',
    default_language: 'enGB',
    default_timezone: 'Europe/Vienna',
    default_date_format: 'iso',
    currency: 'EUR',
    ...overrides,
  }
}

async function mountTab(permissions: string[], general: AdminGeneralSettings) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = userWithPermissions(permissions)
  // Seeded directly rather than driven through fetch(): only `general` is
  // under test, so the rest of AllAdminSettings would be dead weight.
  useAdminSettingsStore().settings = { general } as unknown as AllAdminSettings

  const hostStore = useHostStore()
  hostStore.languages = ['enGB', 'deAT']
  hostStore.timezones = ['Europe/Vienna', 'Europe/London']
  hostStore.dateFormats = ['iso', 'dmy_dot']
  hostStore.loaded = true

  const wrapper = mountWithApp(AdminSettingsTabGeneral, {
    pinia,
    attachTo: document.body,
  })
  await flushPromises()
  return wrapper
}

function fieldRowByLabel(wrapper: ReturnType<typeof mount>, label: string) {
  return wrapper.findAll('.field-row').find((r) => r.text().includes(label))!
}

function selectFor(wrapper: ReturnType<typeof mount>, label: string) {
  return fieldRowByLabel(wrapper, label).findComponent({ name: 'Select' })
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

const LANGUAGE_LABEL = i18n.global.t('adminSettings.general.defaultLanguage') as string
const TIMEZONE_LABEL = i18n.global.t('adminSettings.general.defaultTimezone') as string
const DATE_FORMAT_LABEL = i18n.global.t('adminSettings.general.defaultDateFormat') as string

describe('AdminSettingsTabGeneral locales section', () => {
  beforeEach(() => {
    putMock.mockReset()
  })

  it('reflects settings.general.default_language/timezone/date_format', async () => {
    const wrapper = await mountTab(
      ['write:settings'],
      makeGeneralSettings({
        default_language: 'deAT',
        default_timezone: 'Europe/London',
        default_date_format: 'dmy_dot',
      }),
    )

    expect(selectFor(wrapper, LANGUAGE_LABEL).props('modelValue')).toBe('deAT')
    expect(selectFor(wrapper, TIMEZONE_LABEL).props('modelValue')).toBe('Europe/London')
    expect(selectFor(wrapper, DATE_FORMAT_LABEL).props('modelValue')).toBe('dmy_dot')

    wrapper.unmount()
  })

  it('PUTs /admin/settings/general with the three fields once changed and saved', async () => {
    putMock.mockResolvedValue({
      data: makeGeneralSettings({
        default_language: 'deAT',
        default_timezone: 'Europe/London',
        default_date_format: 'dmy_dot',
      }),
    })
    const wrapper = await mountTab(['write:settings'], makeGeneralSettings())

    await selectFor(wrapper, LANGUAGE_LABEL).vm.$emit('update:modelValue', 'deAT')
    await selectFor(wrapper, TIMEZONE_LABEL).vm.$emit('update:modelValue', 'Europe/London')
    await selectFor(wrapper, DATE_FORMAT_LABEL).vm.$emit('update:modelValue', 'dmy_dot')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/general',
      expect.objectContaining({
        default_language: 'deAT',
        default_timezone: 'Europe/London',
        default_date_format: 'dmy_dot',
      }),
    )

    wrapper.unmount()
  })

  it('updates hostStore defaults from the PUT response', async () => {
    putMock.mockResolvedValue({
      data: makeGeneralSettings({
        default_language: 'deAT',
        default_timezone: 'Europe/London',
        default_date_format: 'dmy_dot',
      }),
    })
    const wrapper = await mountTab(['write:settings'], makeGeneralSettings())
    const hostStore = useHostStore()

    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(hostStore.defaultLanguage).toBe('deAT')
    expect(hostStore.defaultTimezone).toBe('Europe/London')
    expect(hostStore.defaultDateFormat).toBe('dmy_dot')

    wrapper.unmount()
  })

  it('disables the three Selects without write:settings', async () => {
    const wrapper = await mountTab([], makeGeneralSettings())

    expect(selectFor(wrapper, LANGUAGE_LABEL).props('disabled')).toBe(true)
    expect(selectFor(wrapper, TIMEZONE_LABEL).props('disabled')).toBe(true)
    expect(selectFor(wrapper, DATE_FORMAT_LABEL).props('disabled')).toBe(true)

    wrapper.unmount()
  })
})
