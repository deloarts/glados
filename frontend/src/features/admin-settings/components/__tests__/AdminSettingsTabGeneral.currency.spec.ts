import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { i18n } from '@/core/i18n'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { useAdminSettingsStore } from '../../stores/adminSettingsStore'
import { getDisplayCurrency, setDisplayCurrency } from '@/core/utils/currency'
import { userWithPermissions } from '@/test-utils/factories'

import type { AdminGeneralSettings, AllAdminSettings } from '../../types/adminSettingsTypes'

// Mirrors AdminSettingsTabGeneral.locales.spec.ts's own mount/userWithPermissions/
// store-seeding scaffold, scoped to just the new Display > Currency control.

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

function currencySelect(wrapper: ReturnType<typeof mount>) {
  return fieldRowByLabel(wrapper, CURRENCY_LABEL).findComponent({ name: 'Select' })
}

function saveButton(wrapper: ReturnType<typeof mount>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

const CURRENCY_LABEL = i18n.global.t('adminSettings.general.currency') as string

describe('AdminSettingsTabGeneral currency', () => {
  beforeEach(() => {
    putMock.mockReset()
  })

  afterEach(() => {
    // Module-level display-currency state, reset so this file's own
    // assertions never leak into another spec file's default-currency case.
    setDisplayCurrency(null)
  })

  it('shows the company logo buttons disabled with the missing permission without write:settings', async () => {
    const wrapper = await mountTab([], makeGeneralSettings())
    useHostStore().storageEnabled = true
    await flushPromises()
    const label = i18n.global.t('adminSettings.general.companyLogo.upload') as string
    const upload = wrapper.findAllComponents({ name: 'Button' }).find((b) => b.props('label') === label)!

    expect(upload.attributes('disabled')).toBeDefined()
    const span = upload.element.parentElement as (HTMLElement & { $_ptooltipValue?: string }) | null
    expect(span?.$_ptooltipValue).toBe('This needs the permission Write Settings.')

    wrapper.unmount()
  })

  it('reflects settings.general.currency in the Select', async () => {
    const wrapper = await mountTab(['write:settings'], makeGeneralSettings({ currency: 'USD' }))

    expect(currencySelect(wrapper).props('modelValue')).toBe('USD')

    wrapper.unmount()
  })

  it('shows a live preview via formatPrice for the selected currency', async () => {
    const wrapper = await mountTab(['write:settings'], makeGeneralSettings({ currency: 'USD' }))

    // en-GB renders USD as "US$" to stay unambiguous next to "£", matching
    // currency.spec.ts's own formatPrice(500, 'enGB', 'USD') case.
    expect(wrapper.text()).toContain('US$1,234.56')

    wrapper.unmount()
  })

  it('uppercase-normalises a hand-typed currency code', async () => {
    const wrapper = await mountTab(['write:settings'], makeGeneralSettings())

    await currencySelect(wrapper).vm.$emit('update:modelValue', 'usd')

    expect(currencySelect(wrapper).props('modelValue')).toBe('USD')

    wrapper.unmount()
  })

  it('disables Save and hides the preview for an invalid (non 3-letter) code', async () => {
    const wrapper = await mountTab(['write:settings'], makeGeneralSettings())

    await currencySelect(wrapper).vm.$emit('update:modelValue', 'US')

    expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
    expect(wrapper.text()).not.toContain('1,234.56')

    wrapper.unmount()
  })

  it('PUTs /admin/settings/general with the new currency on Save', async () => {
    putMock.mockResolvedValue({ data: makeGeneralSettings({ currency: 'USD' }) })
    const wrapper = await mountTab(['write:settings'], makeGeneralSettings())

    await currencySelect(wrapper).vm.$emit('update:modelValue', 'USD')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(putMock).toHaveBeenCalledWith(
      '/admin/settings/general',
      expect.objectContaining({ currency: 'USD' }),
    )

    wrapper.unmount()
  })

  it('pushes the saved currency into hostStore and currency.ts on Save', async () => {
    putMock.mockResolvedValue({ data: makeGeneralSettings({ currency: 'USD' }) })
    const wrapper = await mountTab(['write:settings'], makeGeneralSettings())
    const hostStore = useHostStore()

    await currencySelect(wrapper).vm.$emit('update:modelValue', 'USD')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(hostStore.currency).toBe('USD')
    expect(getDisplayCurrency()).toBe('USD')

    wrapper.unmount()
  })

  it('disables the Select without write:settings', async () => {
    const wrapper = await mountTab([], makeGeneralSettings())

    expect(currencySelect(wrapper).props('disabled')).toBe(true)

    wrapper.unmount()
  })
})
