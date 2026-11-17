import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const getValuesMock = vi.fn<() => Promise<unknown>>()
const getCapabilitiesMock = vi.fn<() => Promise<unknown>>()
const getNumberingPolicyMock = vi.fn<() => Promise<unknown>>()

vi.mock('../../api/getValues', () => ({ getValues: () => getValuesMock() }))
vi.mock('../../api/getCapabilities', () => ({ getCapabilities: () => getCapabilitiesMock() }))
vi.mock('../../api/getNumberingPolicy', () => ({
  getNumberingPolicy: () => getNumberingPolicyMock(),
}))

import { useHostStore } from '../hostStore'
import { getDisplayCurrency } from '@/core/utils/currency'
import { getDisplayTimezone, setDisplayTimezone } from '@/core/utils/dates'

const VALUES = {
  languages: ['enGB'],
  timezones: ['Europe/Vienna'],
  date_formats: ['iso'],
  theme_presets: ['Aura'],
  theme_surfaces: ['glados'],
  theme_primaries: ['glados'],
  supplier_levels: ['A'],
  start_pages: ['dashboard', 'todo', 'workspace'],
}
const CAPS = {
  storage_enabled: true,
  mail_enabled: false,
  mail_attachment_limit_mb: 10,
  features: { production_planning: true, time_tracking: true },
  empty_value_placeholder: '-',
  office_launcher_enabled: false,
  office_sharepoint_url: '',
  maintenance_enabled: false,
  maintenance_message: null,
  default_language: 'enGB',
  default_timezone: 'Europe/Vienna',
  default_date_format: 'iso',
  currency: 'EUR',
  token_max_lifetime_days: 3650,
  addin_scopes: ['write:source_items'],
}
const NUMBERING = {
  bought_items: { auto: true, editable: false, source: 'internal', example: 'PUR-1' },
  made_items: { auto: true, editable: false, source: 'internal', example: 'MAD-1' },
  product_number_pattern: '',
  project_number_pattern: '',
  allow_headless_projects: true,
}

describe('hostStore.fetch, concurrency', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getValuesMock.mockResolvedValue(VALUES)
    getCapabilitiesMock.mockResolvedValue(CAPS)
    getNumberingPolicyMock.mockResolvedValue(NUMBERING)
  })

  it('fires each /host/* request exactly once for two concurrent callers', async () => {
    const store = useHostStore()

    // Two callers racing before the first response lands, e.g. the router
    // guard and a component's onMounted both calling fetch() on the same tick.
    await Promise.all([store.fetch(), store.fetch()])

    expect(getValuesMock).toHaveBeenCalledTimes(1)
    expect(getCapabilitiesMock).toHaveBeenCalledTimes(1)
    expect(getNumberingPolicyMock).toHaveBeenCalledTimes(1)
    expect(store.loaded).toBe(true)
    expect(store.languages).toEqual(['enGB'])
    expect(store.defaultLanguage).toBe('enGB')
    expect(store.defaultTimezone).toBe('Europe/Vienna')
    expect(store.defaultDateFormat).toBe('iso')
    expect(store.startPages).toEqual(['dashboard', 'todo', 'workspace'])
    expect(store.tokenMaxLifetimeDays).toBe(3650)
    expect(store.addinScopes).toEqual(['write:source_items'])
  })

  it('defaults addinScopes to an empty array before fetch() has answered', () => {
    const store = useHostStore()

    expect(store.addinScopes).toEqual([])
  })

  it('pushes the fetched currency into currency.ts so formatPrice picks it up by default', async () => {
    getCapabilitiesMock.mockResolvedValue({ ...CAPS, currency: 'USD' })
    const store = useHostStore()

    await store.fetch()

    expect(store.currency).toBe('USD')
    expect(getDisplayCurrency()).toBe('USD')
  })

  it('makes the tenant default timezone the display timezone of the whole app', async () => {
    setDisplayTimezone(null)
    getCapabilitiesMock.mockResolvedValue({ ...CAPS, default_timezone: 'America/New_York' })
    const store = useHostStore()

    await store.fetch()

    expect(store.defaultTimezone).toBe('America/New_York')
    expect(getDisplayTimezone()).toBe('America/New_York')
    setDisplayTimezone(null)
  })

  it('does not refetch once already loaded', async () => {
    const store = useHostStore()
    await store.fetch()
    await store.fetch()

    expect(getValuesMock).toHaveBeenCalledTimes(1)
  })

  it('retries on the next call after a failed attempt', async () => {
    const store = useHostStore()
    getValuesMock.mockRejectedValueOnce(new Error('network error'))

    await expect(store.fetch()).rejects.toThrow('network error')
    expect(store.loaded).toBe(false)

    await store.fetch()
    expect(store.loaded).toBe(true)
    expect(getValuesMock).toHaveBeenCalledTimes(2)
  })

  it('a caller joining an in-flight request also sees the failure', async () => {
    const store = useHostStore()
    let reject!: (err: unknown) => void
    getValuesMock.mockReturnValueOnce(
      new Promise((_, r) => {
        reject = r
      }),
    )

    const first = store.fetch()
    const second = store.fetch()
    reject(new Error('boom'))

    await expect(first).rejects.toThrow('boom')
    await expect(second).rejects.toThrow('boom')
    // Both callers awaited the exact same in-flight request, not two
    // independent ones: the capabilities/numbering mocks prove it.
    expect(getValuesMock).toHaveBeenCalledTimes(1)
  })
})

// Drives MaintenanceBanner.vue, the in-app warning for signed-in (exempt)
// users, so an admin working through maintenance doesn't forget the switch.
describe('hostStore.fetch, maintenance capability fields', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getValuesMock.mockResolvedValue(VALUES)
    getNumberingPolicyMock.mockResolvedValue(NUMBERING)
  })

  it('exposes enabled + the admin message from /host/capabilities', async () => {
    getCapabilitiesMock.mockResolvedValue({
      ...CAPS,
      maintenance_enabled: true,
      maintenance_message: 'Upgrading the database, back shortly.',
    })

    const store = useHostStore()
    await store.fetch()

    expect(store.maintenanceEnabled).toBe(true)
    expect(store.maintenanceMessage).toBe('Upgrading the database, back shortly.')
  })

  it('defaults to false/null before fetch() has answered', () => {
    const store = useHostStore()

    expect(store.maintenanceEnabled).toBe(false)
    expect(store.maintenanceMessage).toBeNull()
  })
})

// Drives the time tracking surfaces (sidebar shortcut, account tab, My
// Account section) and the provider name their labels interpolate.
describe('hostStore.fetch, time tracking capability fields', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    getValuesMock.mockResolvedValue(VALUES)
    getNumberingPolicyMock.mockResolvedValue(NUMBERING)
  })

  it('stays off with no provider before fetch() has answered', () => {
    const store = useHostStore()

    expect(store.timeTrackingEnabled).toBe(false)
    expect(store.timeTrackingProviderLabel).toBeNull()
  })

  it('exposes the flag and the provider from /host/capabilities', async () => {
    getCapabilitiesMock.mockResolvedValue({
      ...CAPS,
      features: { production_planning: true, time_tracking: true, time_tracking_provider_label: 'Example Time' },
    })

    const store = useHostStore()
    await store.fetch()

    expect(store.timeTrackingEnabled).toBe(true)
    expect(store.timeTrackingProviderLabel).toBe('Example Time')
  })
})

describe('hostStore, module flags', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getValuesMock.mockResolvedValue(VALUES)
    getNumberingPolicyMock.mockResolvedValue(NUMBERING)
  })

  it('keeps every module on before fetch() has answered', () => {
    const store = useHostStore()

    expect(store.calculationsEnabled).toBe(true)
    expect(store.todosEnabled).toBe(true)
  })

  it('takes the module flags from /host/capabilities', async () => {
    getCapabilitiesMock.mockResolvedValue({
      ...CAPS,
      features: {
        production_planning: true,
        time_tracking: false,
        calculations: false,
        checklists: true,
        devices: false,
        sequences: false,
        todos: false,
      },
    })

    const store = useHostStore()
    await store.fetch()

    expect(store.calculationsEnabled).toBe(false)
    expect(store.checklistsEnabled).toBe(true)
    expect(store.devicesEnabled).toBe(false)
    expect(store.sequencesEnabled).toBe(false)
    expect(store.todosEnabled).toBe(false)
  })
})
