import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import { mountWithApp } from '@/test-utils/mountWithApp'
import { createTokenStore } from '../../../stores/createTokenStore'
import { useCurrentUserStore } from '@/core/stores/currentUserStore'
import { useHostStore } from '@/core/host/stores/hostStore'
import { i18n } from '@/core/i18n'
import { setDisplayTimezone } from '@/core/utils/dates'

import type { UsageLogParams, TokenApi } from '../../../api/createTokenApi'
import type { PageResponse } from '@/core/api/types'
import type {
  CreatedToken,
  CreateTokenCommand,
  RevokeAllTokensResult,
  TokenFilterParams,
  TokenSummary,
  TokenUsageLogEntry,
} from '../../../types/tokenTypes'
import type { UserResponse } from '@/core/types/userResponse'

import TokenFormDialog from '../TokenFormDialog.vue'

function makeApi(): TokenApi {
  return {
    list: vi.fn<(params?: TokenFilterParams) => Promise<PageResponse<TokenSummary>>>(),
    create: vi.fn<(cmd: CreateTokenCommand) => Promise<CreatedToken>>(),
    revoke: vi.fn<(id: number) => Promise<TokenSummary>>(),
    revokeAll: vi.fn<() => Promise<RevokeAllTokensResult>>(),
    getUsageLog:
      vi.fn<
        (id: number, params?: UsageLogParams) => Promise<PageResponse<TokenUsageLogEntry>>
      >(),
  }
}

// TokenFormDialog is the one create surface shared by both PAT
// (account.pat) and API-key (settings.apiKeys) management, see
// TokenManagementControls.vue, which passes i18nPrefix straight through
// without ever swapping the dialog component itself.
//
// OpenVue's Dialog teleports its content to document.body, outside the
// wrapper's own DOM subtree, so `wrapper.text()`/`wrapper.find()` see only
// the teleport markers, so assertions below read `document.body.textContent`
// (mirrors WebhookFormDialog.spec.ts's own "query document.body" workaround)
// or use `findComponent`, which follows the logical component tree and
// isn't affected by where Teleport renders its DOM output.
async function mountDialog(api: TokenApi, tokenMaxLifetimeDays: number) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = {
    is_systemuser: false,
    permissions: ['read:orders', 'write:orders'],
  } as unknown as UserResponse
  useHostStore().tokenMaxLifetimeDays = tokenMaxLifetimeDays

  const store = createTokenStore(`testTokenFormDialog-${Math.random()}`, api)()

  const wrapper = mountWithApp(TokenFormDialog, {
    pinia,
    attachTo: document.body,
    props: { store, i18nPrefix: 'account.pat', visible: true },
  })
  await flushPromises()
  return wrapper
}

// Mounted hidden and then revealed (unlike mountDialog above), so the
// `watch(visible, ...)` pre-fill actually runs, mirroring how
// TokenManagementControls really opens this dialog (showCreateForm starts
// false, flips true on the button click).
async function mountAddinDialog(
  api: TokenApi,
  tokenMaxLifetimeDays: number,
  options: { permissions?: string[]; addinScopes?: string[] } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = {
    is_systemuser: false,
    permissions: options.permissions ?? [],
  } as unknown as UserResponse
  const hostStore = useHostStore()
  hostStore.tokenMaxLifetimeDays = tokenMaxLifetimeDays
  hostStore.addinScopes = options.addinScopes ?? []

  const store = createTokenStore(`testTokenFormDialogAddin-${Math.random()}`, api)()

  const wrapper = mountWithApp(TokenFormDialog, {
    pinia,
    attachTo: document.body,
    props: { store, i18nPrefix: 'account.pat', visible: false, addin: true },
  })
  await flushPromises()
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

function permissionCheckbox(wrapper: Awaited<ReturnType<typeof mountDialog>>, perm: string) {
  return wrapper.findAllComponents({ name: 'Checkbox' }).find((c) => c.props('value') === perm)
}

function expiresInDaysInput(wrapper: Awaited<ReturnType<typeof mountDialog>>) {
  return wrapper.findComponent({ name: 'InputNumber' })
}

function nameInput(wrapper: Awaited<ReturnType<typeof mountDialog>>) {
  return wrapper.findComponent({ name: 'InputText' })
}

function saveButton(wrapper: Awaited<ReturnType<typeof mountDialog>>) {
  return wrapper
    .findAllComponents({ name: 'Button' })
    .find((b) => b.props('label') === (i18n.global.t('common.save') as string))!
}

describe('TokenFormDialog, configured token lifetime cap', () => {
  let api: TokenApi

  beforeEach(() => {
    api = makeApi()
  })

  it("caps the expiry InputNumber's max at hostStore.tokenMaxLifetimeDays", async () => {
    const wrapper = await mountDialog(api, 90)

    expect(expiresInDaysInput(wrapper).props('max')).toBe(90)

    wrapper.unmount()
  })

  it('shows the configured cap in the field hint', async () => {
    const wrapper = await mountDialog(api, 90)

    expect(document.body.textContent).toContain(
      i18n.global.t('account.pat.fields.expiresInDaysHint', { days: 90 }),
    )

    wrapper.unmount()
  })

  it('follows a different cap for a different tenant configuration', async () => {
    const wrapper = await mountDialog(api, 3650)

    expect(expiresInDaysInput(wrapper).props('max')).toBe(3650)
    expect(document.body.textContent).toContain(
      i18n.global.t('account.pat.fields.expiresInDaysHint', { days: 3650 }),
    )

    wrapper.unmount()
  })

  it('creates with the form-entered name and expiresInDays, within the cap', async () => {
    vi.mocked(api.create).mockResolvedValue({
      id: 1,
      public_id: '11111111-1111-1111-1111-111111111111',
      name: 'CI token',
      token_prefix: 'glados_abcd',
      permissions: [],
      created: '2026-01-01',
      expires_at: '2026-01-31',
      revoked_at: null,
      is_expired: false,
      secret: 'glados_abcd_secret',
    })
    const wrapper = await mountDialog(api, 90)

    await nameInput(wrapper).vm.$emit('update:modelValue', 'CI token')
    await expiresInDaysInput(wrapper).vm.$emit('update:modelValue', 60)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(api.create).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'CI token', expires_in_days: 60 }),
    )

    wrapper.unmount()
  })
})

function neverExpiresToggle(wrapper: Awaited<ReturnType<typeof mountDialog>>) {
  return wrapper.findComponent({ name: 'ToggleSwitch' })
}

const createdToken: CreatedToken = {
  id: 1,
  public_id: '33333333-3333-3333-3333-333333333333',
  name: 'Forever',
  token_prefix: 'glados_abcd',
  permissions: [],
  created: '2026-01-01',
  expires_at: null,
  revoked_at: null,
  is_expired: false,
  secret: 'glados_abcd_secret',
}

// While the security settings cap token lifetimes, every token needs an
// expiry, so "never expires" stays visible but disabled, its tooltip saying
// why. A cap of 0 lifts that.
describe('TokenFormDialog, never expires', () => {
  let api: TokenApi

  beforeEach(() => {
    api = makeApi()
  })

  it('is disabled while a cap is set', async () => {
    const wrapper = await mountDialog(api, 90)

    expect(neverExpiresToggle(wrapper).props('disabled')).toBe(true)

    wrapper.unmount()
  })

  it('always sends an expiry while a cap is set', async () => {
    vi.mocked(api.create).mockResolvedValue(createdToken)
    const wrapper = await mountDialog(api, 90)

    await nameInput(wrapper).vm.$emit('update:modelValue', 'Capped')
    await neverExpiresToggle(wrapper).vm.$emit('update:modelValue', true)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(api.create).toHaveBeenCalledWith(expect.objectContaining({ expires_in_days: 30 }))

    wrapper.unmount()
  })

  it('can be chosen when the cap is lifted', async () => {
    vi.mocked(api.create).mockResolvedValue(createdToken)
    const wrapper = await mountDialog(api, 0)

    expect(neverExpiresToggle(wrapper).props('disabled')).toBe(false)
    expect(expiresInDaysInput(wrapper).props('max')).toBe(36500)
    expect(document.body.textContent).toContain(
      i18n.global.t('account.pat.fields.expiresInDaysNoCapHint'),
    )

    await nameInput(wrapper).vm.$emit('update:modelValue', 'Forever')
    await neverExpiresToggle(wrapper).vm.$emit('update:modelValue', true)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(api.create).toHaveBeenCalledWith(expect.objectContaining({ expires_in_days: null }))

    wrapper.unmount()
  })
})

// The "Create add-in token" shortcut opens this same dialog with the
// `addin` prop set: a dated name, an expiry through the end of the current
// year (clamped to the tenant's cap), and hostStore.addinScopes intersected
// with what the current user may grant.
describe('TokenFormDialog, add-in pre-fill', () => {
  let api: TokenApi

  beforeEach(() => {
    api = makeApi()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    setDisplayTimezone(null)
  })

  it('pre-fills a dated name and an expiry through the end of the year, capped at the tenant lifetime', async () => {
    vi.setSystemTime(new Date('2026-06-15T09:00:00.000Z'))
    const now = new Date()
    const wrapper = await mountAddinDialog(api, 3650, {
      permissions: ['write:source_items'],
      addinScopes: ['write:source_items'],
    })

    expect(nameInput(wrapper).props('modelValue')).toMatch(/^SW Addin \d{4}-\d{2}-\d{2}$/)

    const days = expiresInDaysInput(wrapper).props('modelValue') as number
    const expiry = new Date(now.getTime() + days * 86_400_000)
    const endOfYear = new Date(now.getFullYear(), 11, 31, 23, 59, 59, 999)
    // Rounds up to at least the end of the year, but by less than a full day.
    expect(expiry.getTime()).toBeGreaterThanOrEqual(endOfYear.getTime())
    expect(expiry.getTime()).toBeLessThan(endOfYear.getTime() + 86_400_000)

    wrapper.unmount()
  })

  it('runs the pre-filled expiry to the end of the year in the tenant timezone', async () => {
    // 16:00 UTC on 31 December is already 1 January 2027 in Tokyo, so the
    // year to cover is 2027 there, whatever the browser's own zone says.
    vi.setSystemTime(new Date('2026-12-31T16:00:00.000Z'))
    setDisplayTimezone('Asia/Tokyo')
    const now = Date.now()
    const wrapper = await mountAddinDialog(api, 3650, {
      permissions: ['write:source_items'],
      addinScopes: ['write:source_items'],
    })

    const days = expiresInDaysInput(wrapper).props('modelValue') as number
    const expiry = now + days * 86_400_000
    const endOfYearInTokyo = Date.parse('2027-12-31T14:59:59.999Z')
    expect(expiry).toBeGreaterThanOrEqual(endOfYearInTokyo)
    expect(expiry).toBeLessThan(endOfYearInTokyo + 86_400_000)

    wrapper.unmount()
  })

  it('clamps the pre-filled expiry to a lower configured lifetime cap', async () => {
    vi.setSystemTime(new Date('2026-01-15T09:00:00.000Z'))
    const wrapper = await mountAddinDialog(api, 5, {
      permissions: ['write:source_items'],
      addinScopes: ['write:source_items'],
    })

    // Natural days-to-year-end is far above 5 in mid-January, so the cap wins.
    expect(expiresInDaysInput(wrapper).props('modelValue')).toBe(5)

    wrapper.unmount()
  })

  it('pre-checks every add-in scope the current user is allowed to grant', async () => {
    const wrapper = await mountAddinDialog(api, 3650, {
      permissions: ['write:source_items', 'write:orders'],
      addinScopes: ['write:source_items'],
    })

    expect(permissionCheckbox(wrapper, 'write:source_items')!.props('modelValue')).toContain(
      'write:source_items',
    )

    wrapper.unmount()
  })

  it('leaves a scope unchecked and shows an inline notice when the user cannot grant it', async () => {
    const wrapper = await mountAddinDialog(api, 3650, {
      permissions: ['write:orders'],
      addinScopes: ['write:source_items'],
    })

    // Not grantable, so it never even renders as a checkbox option.
    expect(permissionCheckbox(wrapper, 'write:source_items')).toBeUndefined()
    expect(document.body.textContent).toContain(
      i18n.global.t('account.pat.addinMissingPermission', {
        permissions: i18n.global.t('settings.users.permissions.writeSourceItems'),
      }),
    )

    wrapper.unmount()
  })

  it('shows no missing-permission notice once the user holds every add-in scope', async () => {
    const wrapper = await mountAddinDialog(api, 3650, {
      permissions: ['write:source_items'],
      addinScopes: ['write:source_items'],
    })

    expect(document.body.textContent).not.toContain(
      i18n.global.t('account.pat.addinMissingPermission', {
        permissions: i18n.global.t('settings.users.permissions.writeSourceItems'),
      }),
    )

    wrapper.unmount()
  })

  it('stays fully editable after the add-in pre-fill', async () => {
    vi.mocked(api.create).mockResolvedValue({
      id: 1,
      public_id: '22222222-2222-2222-2222-222222222222',
      name: 'Renamed token',
      token_prefix: 'glados_abcd',
      permissions: [],
      created: '2026-01-01',
      expires_at: '2026-01-31',
      revoked_at: null,
      is_expired: false,
      secret: 'glados_abcd_secret',
    })
    const wrapper = await mountAddinDialog(api, 3650, {
      permissions: ['write:source_items'],
      addinScopes: ['write:source_items'],
    })

    await nameInput(wrapper).vm.$emit('update:modelValue', 'Renamed token')
    await expiresInDaysInput(wrapper).vm.$emit('update:modelValue', 10)
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(api.create).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Renamed token', expires_in_days: 10 }),
    )

    wrapper.unmount()
  })
})

// The PDM vault add-in's PAT shortcut. Same pre-fill mechanics as the
// SolidWorks PAT block above, differing only in which backend-served scope
// set it draws from (hostStore.pdmAddinScopes) and the name it builds.
async function mountPdmAddinDialog(
  api: TokenApi,
  tokenMaxLifetimeDays: number,
  options: { permissions?: string[]; pdmAddinScopes?: string[] } = {},
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  useCurrentUserStore().user = {
    is_systemuser: false,
    permissions: options.permissions ?? [],
  } as unknown as UserResponse
  const hostStore = useHostStore()
  hostStore.tokenMaxLifetimeDays = tokenMaxLifetimeDays
  hostStore.pdmAddinScopes = options.pdmAddinScopes ?? []

  const store = createTokenStore(`testTokenFormDialogPdm-${Math.random()}`, api)()

  const wrapper = mountWithApp(TokenFormDialog, {
    pinia,
    attachTo: document.body,
    props: { store, i18nPrefix: 'account.pat', visible: false, pdmAddin: true },
  })
  await flushPromises()
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

describe('TokenFormDialog, PDM add-in pre-fill', () => {
  let api: TokenApi

  beforeEach(() => {
    api = makeApi()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('pre-fills a dated PDM name and an expiry through the end of the year', async () => {
    vi.setSystemTime(new Date('2026-06-15T09:00:00.000Z'))
    const now = new Date()
    const wrapper = await mountPdmAddinDialog(api, 3650, {
      permissions: ['use:pdm_addin'],
      pdmAddinScopes: ['use:pdm_addin'],
    })

    expect(nameInput(wrapper).props('modelValue')).toMatch(/^PDM Addin \d{4}-\d{2}-\d{2}$/)

    const days = expiresInDaysInput(wrapper).props('modelValue') as number
    const expiry = new Date(now.getTime() + days * 86_400_000)
    const endOfYear = new Date(now.getFullYear(), 11, 31, 23, 59, 59, 999)
    expect(expiry.getTime()).toBeGreaterThanOrEqual(endOfYear.getTime())
    expect(expiry.getTime()).toBeLessThan(endOfYear.getTime() + 86_400_000)

    wrapper.unmount()
  })

  it('pre-checks the backend-served PDM scope rather than the SolidWorks one', async () => {
    const wrapper = await mountPdmAddinDialog(api, 3650, {
      permissions: ['use:pdm_addin', 'write:source_items'],
      pdmAddinScopes: ['use:pdm_addin'],
    })

    expect(permissionCheckbox(wrapper, 'use:pdm_addin')!.props('modelValue')).toContain(
      'use:pdm_addin',
    )
    expect(permissionCheckbox(wrapper, 'use:pdm_addin')!.props('modelValue')).not.toContain(
      'write:source_items',
    )

    wrapper.unmount()
  })

  it('warns instead of silently dropping a PDM scope the creator cannot grant', async () => {
    const wrapper = await mountPdmAddinDialog(api, 3650, {
      permissions: [],
      pdmAddinScopes: ['use:pdm_addin'],
    })

    expect(permissionCheckbox(wrapper, 'use:pdm_addin')).toBeUndefined()
    // The dialog teleports, so assert against the document, not the wrapper.
    expect(document.body.textContent).toContain(
      i18n.global.t('account.pat.addinMissingPermission', {
        permissions: i18n.global.t('settings.users.permissions.usePdmAddin'),
      }),
    )

    wrapper.unmount()
  })
})

// A PAT outlives the session that creates it, so its surface asks for the
// current password; the API key surface does not.
describe('TokenFormDialog, password confirmation', () => {
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('needs the password before it saves, and sends it', async () => {
    const api = { ...makeApi(), requiresPassword: true }
    vi.mocked(api.create).mockResolvedValue(createdToken)
    const wrapper = await mountDialog(api, 90)

    await nameInput(wrapper).vm.$emit('update:modelValue', 'CI token')
    expect(saveButton(wrapper).attributes('disabled')).toBeDefined()

    await wrapper.findComponent({ name: 'Password' }).vm.$emit('update:modelValue', 'my-password')
    await saveButton(wrapper).trigger('click')
    await flushPromises()

    expect(api.create).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'CI token', password: 'my-password' }),
    )
    wrapper.unmount()
  })

  it('shows no password field where none is needed', async () => {
    const wrapper = await mountDialog(makeApi(), 90)

    expect(wrapper.findComponent({ name: 'Password' }).exists()).toBe(false)
    wrapper.unmount()
  })
})
